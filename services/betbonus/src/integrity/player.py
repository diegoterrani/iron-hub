"""Emula o jogador no cliente do jogo e mapeia a cadeia iframe/provedor.

Não decodifica protocolo de spin (Pragmatic gs2c, Patagonia, Spribe SmartFox).
URLs na evidência saem sem query (tokens, session, lobby).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
BROWSERS = ROOT / ".playwright"
SHOTS = ROOT / "data" / "integrity_play"

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS))

_GAME_ROLES = frozenset(
    {
        "pragmatic",
        "patagonia",
        "spribe",
        "evolution",
        "pgsoft",
        "relax",
        "playngo",
        "hacksaw",
        "quickspin",
        "netent",
        "redtiger",
        "playson",
        "bgaming",
        "softswiss",
    }
)

_HOST_HINTS: tuple[tuple[str, str], ...] = (
    ("salsagator", "aggregator"),
    ("salsa-cdn", "aggregator"),
    ("pragmaticplay", "pragmatic"),
    ("pragmatic", "pragmatic"),
    ("ppgames", "pragmatic"),
    ("patagonia", "patagonia"),
    ("spribe.co", "spribe"),
    ("spribe", "spribe"),
    ("smartfoxserver", "spribe"),
    ("softswiss", "softswiss"),
    ("a8r.", "softswiss"),
    ("evolution", "evolution"),
    ("evo-games", "evolution"),
    ("pgsoft", "pgsoft"),
    ("relax-gaming", "relax"),
    ("playngo", "playngo"),
    ("hacksawgaming", "hacksaw"),
    ("quickspin", "quickspin"),
    ("netent", "netent"),
    ("redtiger", "redtiger"),
    ("playson", "playson"),
    ("bgaming", "bgaming"),
    ("cloudflare", "cdn"),
    ("akamai", "cdn"),
    ("fastly", "cdn"),
    ("gstatic", "cdn"),
    ("googleapis", "cdn"),
    ("jquery.com", "cdn"),
    ("bootstrapcdn", "cdn"),
    ("stackpath", "cdn"),
    ("google-analytics", "telemetry"),
    ("doubleclick", "telemetry"),
    ("facebook", "telemetry"),
    ("hotjar", "telemetry"),
    ("sentry", "telemetry"),
)

_PATH_HINTS: tuple[tuple[str, str], ...] = (
    ("/gs2c/", "pragmatic"),
    ("/html5game.do", "pragmatic"),
    ("/playgame.do", "pragmatic"),
    ("/gameservice", "pragmatic"),
    ("/casinogameapi/", "pragmatic"),
    ("/integrationservice/", "pragmatic"),
    ("/bluebox", "spribe"),
    ("/smartfox", "spribe"),
)

_HTTP_URL = re.compile(r"https?://[^\s\"'<>\\]+", re.I)


def extract_http_urls(text: str) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for match in _HTTP_URL.findall(text):
        clean = match.rstrip(").,;]}\"\\")
        parsed = urlparse(clean)
        if "w3.org" in (parsed.netloc or "").lower():
            continue
        red = redact_url(clean)
        if red and red not in seen:
            seen.add(red)
            out.append(clean)
    return out[:40]


def uniq_redacted(urls: list[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in urls or []:
        key = redact_url(str(item))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def parse_launch_error(text: str) -> str:
    blob = re.sub(r"\s+", " ", (text or "")).strip()
    if not blob:
        return ""
    lower = blob.lower()
    if "oops" in lower or "i/o error" in lower or "socketexception" in lower:
        return scrub_secrets(blob)[:280]
    if "error:" in lower and len(blob) < 400:
        return scrub_secrets(blob)[:280]
    return ""


def merge_launch_maps(*parts: dict[str, Any] | None) -> dict[str, Any]:
    urls: list[str] = []
    iframes: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        for iframe in part.get("iframes") or []:
            if iframe:
                iframes.append(str(iframe))
                urls.append(str(iframe))
        for host in part.get("hosts") or []:
            if not isinstance(host, dict):
                continue
            name = str(host.get("host") or "")
            scheme = "wss" if host.get("ws") else "https"
            for path in host.get("paths") or ["/"]:
                urls.append(f"{scheme}://{name}{path}")
        for ep in part.get("endpoints") or []:
            if not isinstance(ep, dict):
                continue
            urls.append(f"{ep.get('scheme') or 'https'}://{ep.get('host')}{ep.get('path') or '/'}")
        for extra in part.get("urls") or []:
            urls.append(str(extra))
    merged = summarize_endpoints(urls)
    merged["iframes"] = uniq_redacted(iframes)
    return merged


_SECRET_Q = re.compile(r"(token|session|auth|key|lobby|password|secret)=[^&\s\"']+", re.I)


def scrub_secrets(text: str) -> str:
    if not text:
        return ""
    return _SECRET_Q.sub(r"\1=redacted", text)[:300]


_SLUG_HINTS: tuple[tuple[str, str], ...] = (
    ("prag", "pragmatic"),
    ("pate", "patagonia"),
    ("spri", "spribe"),
    ("aviator", "spribe"),
    ("evo-", "evolution"),
    ("pgsoft", "pgsoft"),
    ("relax", "relax"),
    ("hacksaw", "hacksaw"),
    ("netent", "netent"),
    ("redtiger", "redtiger"),
    ("playson", "playson"),
    ("bgaming", "bgaming"),
)


def redact_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url)
        if p.scheme in {"http", "https", "ws", "wss"}:
            path = p.path or "/"
            return f"{p.scheme}://{p.netloc}{path}"
        if p.scheme in {"about", "blob", "data"}:
            return f"{p.scheme}:"
        return "redacted"
    except Exception:  # noqa: BLE001
        return "redacted"


def classify_host(host: str) -> str:
    h = (host or "").lower()
    if not h:
        return "unknown"
    for needle, role in _HOST_HINTS:
        if needle in h:
            return role
    return "unknown"


def classify_path(path: str) -> str:
    p = (path or "").lower()
    for needle, role in _PATH_HINTS:
        if needle in p:
            return role
    return ""


def classify_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return "unknown"
    by_path = classify_path(parsed.path)
    if by_path:
        return by_path
    return classify_host(parsed.netloc)


def classify_salsa_slug(game: str) -> str:
    g = (game or "").strip().lower()
    if not g:
        return "unknown"
    for prefix, role in _SLUG_HINTS:
        if g.startswith(prefix) or prefix in g:
            return role
    return "unknown"


def catalog_vs_client(catalog_provider: str, salsa_game: str, game_client: str) -> dict[str, Any]:
    cat = (catalog_provider or "").strip().lower()
    client = (game_client or classify_salsa_slug(salsa_game) or "").strip().lower()
    slug = classify_salsa_slug(salsa_game)
    mismatch = False
    if cat and client and client not in {"unknown", "aggregator", "cdn", "telemetry"}:
        cat_hint = ""
        for needle, role in (
            ("patagonia", "patagonia"),
            ("pragmatic", "pragmatic"),
            ("spribe", "spribe"),
            ("evolution", "evolution"),
            ("pg", "pgsoft"),
        ):
            if needle in cat:
                cat_hint = role
                break
        if cat_hint and cat_hint != client:
            mismatch = True
        elif slug not in {"unknown", client} and slug != client:
            mismatch = True
    return {
        "catalog_provider": catalog_provider or "",
        "salsa_game": salsa_game or "",
        "salsa_vendor": slug,
        "game_client": client,
        "mismatch": mismatch,
    }


def summarize_endpoints(urls: list[str], *, limit: int = 40) -> dict[str, Any]:
    hosts: dict[str, dict[str, Any]] = {}
    endpoints: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in urls:
        if not raw or raw.startswith(("data:", "blob:", "about:")):
            continue
        parsed = urlparse(raw)
        host = parsed.netloc
        path = parsed.path or "/"
        if not host or "w3.org" in host.lower():
            continue
        role = classify_url(raw)
        bucket = hosts.setdefault(
            host,
            {"host": host, "role": role, "paths": [], "ws": parsed.scheme in {"ws", "wss"}},
        )
        if path not in bucket["paths"] and len(bucket["paths"]) < 8:
            bucket["paths"].append(path)
        if role not in {"unknown", "cdn", "telemetry"} and bucket["role"] in {"unknown", "cdn"}:
            bucket["role"] = role
        if parsed.scheme in {"ws", "wss"}:
            bucket["ws"] = True
        key = (host, path)
        if key in seen:
            continue
        seen.add(key)
        if len(endpoints) < limit:
            endpoints.append(
                {
                    "host": host,
                    "path": path,
                    "role": role,
                    "scheme": parsed.scheme,
                }
            )
    roles = sorted({h["role"] for h in hosts.values() if h["role"] not in {"cdn", "telemetry", "unknown"}})
    game_client = next((r for r in roles if r in _GAME_ROLES), "")
    if not game_client and "aggregator" in roles:
        game_client = "aggregator"
    return {
        "hosts": sorted(hosts.values(), key=lambda row: (row["role"], row["host"])),
        "endpoints": endpoints,
        "roles": roles,
        "game_client": game_client or "unknown",
    }


def map_launch_html(html: str, *, base_url: str = "") -> dict[str, Any]:
    """Parse estático do HTML Salsa: iframes, scripts, options= (SoftSwiss/a8r)."""
    iframes = [redact_url(u) for u in re.findall(r"""<iframe[^>]+src=["']([^"']+)""", html, re.I)]
    scripts = [redact_url(u) for u in re.findall(r"""<script[^>]+src=["']([^"']+)""", html, re.I)]
    urls = [u for u in [*iframes, *scripts] if u]
    if base_url:
        urls.append(redact_url(base_url))
    out = summarize_endpoints(urls)
    out["iframes"] = uniq_redacted(iframes)[:12]
    m = re.search(r"options=([^\"&]+)", html)
    out["has_softswiss_options"] = bool(m)
    return out


def _fetch_html(url: str, timeout: int = 18) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) BetBonusAI-integrity",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — URL de launch da própria casa
        raw = resp.read(800_000)
    return raw.decode("utf-8", errors="replace")


def _pick_game_frame(frames: list[Any]) -> Any | None:
    scored: list[tuple[int, Any]] = []
    for frame in frames:
        url = getattr(frame, "url", "") or ""
        if not url or url.startswith("about:"):
            continue
        role = classify_url(url)
        score = 0
        if role in _GAME_ROLES:
            score += 30
        if role == "aggregator":
            score += 5
        if "html5" in url.lower() or "game" in url.lower():
            score += 4
        scored.append((score, frame))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1] if scored else None


def _chromium_args() -> list[str]:
    return [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--use-gl=angle",
        "--use-angle=swiftshader",
        "--enable-webgl",
        "--ignore-gpu-blocklist",
    ]


def _click_game_ui(page: Any, frames: list[Any]) -> tuple[bool, str]:
    """Clica no iframe do jogo (botão, canvas ou hitbox). Sem protocolo de spin."""
    game = _pick_game_frame(frames)
    ordered: list[Any] = []
    if game is not None:
        ordered.append(game)
    named = next((f for f in frames if (getattr(f, "name", "") or "") == "game-iframe"), None)
    if named is not None and named not in ordered:
        ordered.insert(0, named)
    for frame in frames:
        if frame not in ordered:
            ordered.append(frame)
    labels = ("spin", "girar", "play", "continuar", "continue", "start")
    for frame in ordered[:8]:
        for label in labels:
            try:
                loc = frame.get_by_role("button", name=re.compile(label, re.I))
                loc.first.click(timeout=700)
                return True, f"iframe_button:{label}"
            except Exception:
                continue
        try:
            canvas = frame.locator("canvas").first
            canvas.wait_for(state="attached", timeout=9000)
            box = canvas.bounding_box()
            if box and box.get("width", 0) > 20:
                canvas.click(
                    position={
                        "x": max(8, box["width"] * 0.84),
                        "y": max(8, box["height"] * 0.82),
                    },
                    timeout=1500,
                )
                try:
                    canvas.press("Space")
                except Exception:
                    pass
                return True, "iframe_canvas"
        except Exception:
            continue
    try:
        loc = page.locator("iframe[name='game-iframe'], iframe").first
        loc.wait_for(state="attached", timeout=2500)
        box = loc.bounding_box()
        if box and box.get("width", 0) > 20:
            page.mouse.click(
                box["x"] + box["width"] * 0.84,
                box["y"] + box["height"] * 0.82,
            )
            page.keyboard.press("Space")
            return True, "iframe_hitbox"
    except Exception:
        pass
    return False, "no_iframe_target"


def inspect_launch(
    launch_url: str,
    *,
    click_spin: bool = False,
    timeout_ms: int = 28000,
) -> dict[str, Any]:
    """Abre o launch Salsa uma vez, lista iframe/hosts do provedor e opcionalmente clica no canvas.

    Não faz GET HTTP antes do Chromium: o token Salsa é de uso único e um fetch prévio
    queima a sessão (Oops! / CasinoGameAPI).
    """
    if not launch_url:
        return {"ok": False, "reason": "no_launch_url", "clicked": False}

    if os.environ.get("INTEGRITY_SKIP_BROWSER") == "1":
        static: dict[str, Any] = {}
        try:
            html = _fetch_html(launch_url)
            static = map_launch_html(html, base_url=launch_url)
        except Exception as exc:  # noqa: BLE001
            static = {"error": scrub_secrets(str(exc))}
        return {
            "ok": True,
            "clicked": False,
            "reason": "browser_skipped",
            "url": redact_url(launch_url),
            "static": static,
            "provider": static,
            "note": "HTML Salsa sem Chromium.",
        }

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "reason": "playwright_not_installed",
            "clicked": False,
            "url": redact_url(launch_url),
            "note": "pip install playwright && playwright install chromium",
        }

    SHOTS.mkdir(parents=True, exist_ok=True)
    shot = SHOTS / ("last_spin.png" if click_spin else "last_provider_map.png")
    captured: list[str] = []
    clicked = False
    method = ""
    error = ""
    title = ""
    body_text = ""
    html = ""
    frame_rows: list[dict[str, str]] = []
    iframe_srcs: list[str] = []
    launch_error = ""

    def _on_request(req: Any) -> None:
        try:
            captured.append(req.url)
        except Exception:  # noqa: BLE001
            return

    def _on_ws(ws: Any) -> None:
        try:
            captured.append(ws.url)
        except Exception:  # noqa: BLE001
            return

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=_chromium_args())
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.set_default_timeout(min(timeout_ms, 15000))
            page.on("request", _on_request)
            page.on("websocket", _on_ws)
            page.goto(launch_url, wait_until="domcontentloaded", timeout=min(timeout_ms, 20000))
            try:
                page.wait_for_function(
                    """() => {
                      const f = document.querySelector("iframe[name='game-iframe'], iframe");
                      const src = (f && f.src) || "";
                      return src.includes("gs2c") || src.includes("http");
                    }""",
                    timeout=12000,
                )
            except Exception:
                try:
                    page.wait_for_selector("iframe", timeout=2500)
                except Exception:
                    pass
            page.wait_for_timeout(2500 if click_spin else 1500)
            game = page.frame(name="game-iframe")
            if click_spin and game is not None:
                try:
                    game.wait_for_selector("canvas", timeout=12000)
                except Exception:
                    pass
            elif click_spin:
                page.wait_for_timeout(4000)
            title = page.title()
            try:
                html = page.content()
            except Exception:  # noqa: BLE001
                html = ""
            try:
                body_text = page.inner_text("body")
            except Exception:  # noqa: BLE001
                body_text = ""
            launch_error = parse_launch_error(body_text)
            try:
                iframe_srcs = page.eval_on_selector_all(
                    "iframe",
                    "els => els.map(e => e.src || '')",
                )
            except Exception:  # noqa: BLE001
                iframe_srcs = []
            for frame in page.frames:
                frame_rows.append(
                    {
                        "name": (frame.name or "")[:80],
                        "url": redact_url(frame.url),
                        "role": classify_url(frame.url),
                    }
                )
            if click_spin and not launch_error:
                clicked, method = _click_game_ui(page, list(page.frames))
            elif click_spin and launch_error:
                method = "salsa_launch_error"
            page.wait_for_timeout(2500 if click_spin and clicked else 400)
            try:
                target = page.frame(name="game-iframe")
                if target is not None:
                    target.locator("body").screenshot(path=str(shot))
                else:
                    page.screenshot(path=str(shot), full_page=False)
            except Exception as exc:  # noqa: BLE001
                try:
                    page.screenshot(path=str(shot), full_page=False)
                except Exception:
                    error = f"screenshot:{exc}"[:160]
            browser.close()
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "reason": "browser_error",
            "clicked": False,
            "error": scrub_secrets(str(exc)),
            "url": redact_url(launch_url),
        }

    static = map_launch_html(html, base_url=launch_url) if html else {}
    error_urls = extract_http_urls(f"{html}\n{body_text}")
    captured.extend(iframe_srcs)
    captured.extend(error_urls)
    captured.extend(row["url"] for row in frame_rows)
    provider = merge_launch_maps(
        summarize_endpoints(captured),
        static,
        {"urls": error_urls, "iframes": iframe_srcs},
    )
    provider["iframes"] = uniq_redacted([*iframe_srcs, *(static.get("iframes") or [])])[:12]
    provider["frames"] = [row for row in frame_rows if row.get("url") and row["url"] != "about:"][:16]
    if static.get("has_softswiss_options"):
        provider["has_softswiss_options"] = True

    return {
        "ok": True,
        "clicked": clicked,
        "method": method,
        "title": title[:120],
        "screenshot": str(shot) if shot.exists() else "",
        "url": redact_url(launch_url),
        "error": error,
        "launch_error": launch_error,
        "static": {k: v for k, v in static.items() if k != "endpoints"} if static else {},
        "provider": provider,
        "note": "Cadeia iframe mapeada. Clique só no canvas/UI — sem protocolo de spin.",
    }


def try_player_spin(launch_url: str, *, timeout_ms: int = 45000) -> dict[str, Any]:
    """Abre a URL Salsa/provider e tenta 1 spin no iframe do jogo (não na página wrapper)."""
    return inspect_launch(launch_url, click_spin=True, timeout_ms=timeout_ms)
