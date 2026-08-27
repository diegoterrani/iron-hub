from __future__ import annotations

import re
import time
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

from src.models.abuse import WalletSnapshot
from src.models.bonus import BonusOffer, BonusType, ScrapeResult
from src.nlp.analyzer import BonusNLPAnalyzer
from src.scrapers.base import BaseScraper

API_BASE = "https://api.4play.game/api/v1"
SITE = "https://4play.game"

# Valores de `category` na API (não traduzir para EN plural).
CASINO_CATEGORY = {
    "slots": "Slot",
    "slot": "Slot",
    "crash": "Crash",
    "table": "Table",
    "tables": "Table",
    "instant": "Instant Win",
    "lottery": "Loteria",
    "loteria": "Loteria",
    "live": "Live",
}


class FourPlayScraper(BaseScraper):
    """
    4play.game scraper / abuse adapter.

    Public:
      GET /site/promotions[+/{slug}]
    Authenticated (Bearer token from site localStorage key `token`):
      GET /bonus?page=&perPage=
      GET /wallet
      GET /wallet/transactions
      GET /auth/user
      GET /auth/authenticated
      POST /wallet/withdraw?platform=Web|Mobile
    Casino catalog (public):
      GET /casino/games?page=&perPage=&search=&category=&provider=&section=&live=&popular=&recommended=
      GET /casino/providers
      GET /casino/sections
    Casino launch (Bearer):
      POST /casino/game/launch {gameCode, walletType, forFun?, clientType?, aggregator?}
      — o query `id=` em /casino/games é ignorado; resolver gameCode via search.
    Login:
      POST /auth/login {email, password, cookie:false, provider:local}
    """

    platform = "4play"
    default_delay = 0.35
    MIN_WITHDRAW_AMOUNT = 10_000.0  # CRC (UI + API ERR_AMOUNT_IS_TOO_LOW)
    MAX_WITHDRAW_AMOUNT = 100_000.0  # CRC (UI cap)

    def __init__(
        self,
        delay: Optional[float] = None,
        session: Optional[requests.Session] = None,
        token: str = "",
    ):
        super().__init__(delay=delay, session=session)
        self.token = token.strip()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Origin": SITE,
                "Referer": f"{SITE}/casino",
            }
        )
        self.nlp = BonusNLPAnalyzer()
        self._apply_auth_header()

    def set_token(self, token: str) -> None:
        self.token = token.strip()
        self._apply_auth_header()

    def _apply_auth_header(self) -> None:
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
        else:
            self.session.headers.pop("Authorization", None)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if self.delay > 0:
            time.sleep(self.delay)
        url = f"{API_BASE}{path}"
        response = self.session.request(method, url, timeout=25, **kwargs)
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Invalid JSON from {path}: HTTP {response.status_code}") from exc
        if response.status_code == 401:
            raise PermissionError(payload.get("message") or "Unauthorized — token inválido/expirado")
        if payload.get("status") not in (200, None) and response.status_code >= 400:
            raise RuntimeError(
                f"API error HTTP {response.status_code} on {path}: "
                f"{json_dumps(payload)}"
            )
        if response.status_code >= 400:
            raise RuntimeError(
                f"HTTP {response.status_code} on {path}: {json_dumps(payload)}"
            )
        return payload

    def _get_json(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        payload = self._request("GET", path, params=params or None)
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    def get_wallet_snapshot(self) -> WalletSnapshot:
        if not self.token:
            raise PermissionError("Token necessário para GET /wallet")
        data = self._get_json("/wallet")
        return WalletSnapshot(
            platform=self.platform,
            balance=_as_float(data.get("balance")),
            bonus=_as_float(data.get("bonus")),
            rollover=_as_float(data.get("rollover")),
            raw={k: data.get(k) for k in ("balance", "bonus", "rollover") if k in data},
        )

    def list_wallet_transactions(self, page: int = 1, per_page: int = 20) -> dict[str, Any]:
        if not self.token:
            raise PermissionError("Token necessário para GET /wallet/transactions")
        return self._get_json(
            "/wallet/transactions",
            params={"page": page, "perPage": per_page},
        )

    def withdraw(
        self,
        *,
        amount: float,
        method: str = "tft",
        provider: str = "ridivi",
        wallet_type: int = 1,
        phone: str = "",
        iban: str = "",
        platform_hint: str = "Web",
    ) -> dict[str, Any]:
        """
        POST /wallet/withdraw?platform=Web

        amount is in CRC units (house multiplies by 100 → centavos).
        method: tft = SINPE Móvil, dtr = SINPE Bancario
        """
        if not self.token:
            raise PermissionError("Token necessário para POST /wallet/withdraw")
        metadata: dict[str, Any] = {}
        if method == "tft":
            if not phone:
                raise ValueError("phone obrigatório para method=tft (SINPE Móvil)")
            metadata["phone"] = phone
        elif method == "dtr":
            clean = iban.replace(" ", "").upper()
            if len(clean) != 22 or not clean.startswith("CR"):
                raise ValueError("iban CR… (22 chars) obrigatório para method=dtr")
            metadata["iban"] = clean
        else:
            raise ValueError("method deve ser tft ou dtr")

        body = {
            "amount": int(round(float(amount) * 100)),
            "method": method,
            "provider": provider,
            "walletType": wallet_type,
            "metadata": metadata,
        }
        return self._request(
            "POST",
            f"/wallet/withdraw?platform={platform_hint}",
            json=body,
        )

    @staticmethod
    def _html_to_text(html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)
        return re.sub(r"\n{2,}", "\n", text)

    @classmethod
    def login(cls, email: str, password: str) -> str:
        scraper = cls(delay=0)
        payload = scraper._request(
            "POST",
            "/auth/login",
            json={
                "email": email,
                "password": password,
                "cookie": False,
                "provider": "local",
            },
        )
        data = payload.get("data") or {}
        token = data.get("token") or data.get("access_token") or ""
        if not token:
            raise RuntimeError("Login OK mas token ausente na resposta")
        return str(token)

    def validate_token(self) -> dict[str, Any]:
        if not self.token:
            raise PermissionError("Sem token configurado")
        auth = self._get_json("/auth/authenticated")
        user = self._get_json("/auth/user")
        return {"authenticated": auth, "user": user}

    def list_promotions(self) -> list[dict[str, Any]]:
        data = self._get_json("/site/promotions")
        return list(data.get("items") or [])

    def list_casino_games(
        self,
        *,
        search: str = "",
        category: str = "",
        provider: str = "",
        aggregator: str = "",
        section: int | str | None = None,
        live: bool | None = None,
        popular: bool | None = None,
        recommended: bool | None = None,
        game_id: int | str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        """GET /casino/games — catálogo público (Salsa + outros aggregators)."""
        params: dict[str, Any] = {
            "page": max(1, int(page)),
            "perPage": min(100, max(1, int(per_page))),
        }
        if search.strip():
            params["search"] = search.strip()
        if category.strip():
            params["category"] = category.strip()
        if provider.strip():
            params["provider"] = provider.strip()
        if aggregator.strip():
            params["aggregator"] = aggregator.strip()
        if section is not None and str(section) != "":
            params["section"] = section
        if live:
            params["live"] = 1
        if popular:
            params["popular"] = 1
        if recommended:
            params["recommended"] = 1
        if game_id is not None and str(game_id) != "":
            params["id"] = game_id
        data = self._get_json("/casino/games", params=params)
        items = list(data.get("items") or [])
        return {
            "items": items,
            "total": int(data.get("total") or 0),
            "page": int(data.get("page") or params["page"]),
            "perPage": int(data.get("perPage") or params["perPage"]),
        }

    def list_casino_providers(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/casino/providers")
        data = payload.get("data")
        return list(data) if isinstance(data, list) else []

    def list_casino_sections(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/casino/sections")
        data = payload.get("data")
        return list(data) if isinstance(data, list) else []

    def resolve_casino_game(
        self,
        game_id: int | str | None = None,
        *,
        game_code: str = "",
        game_name: str = "",
    ) -> dict[str, Any]:
        """Resolve item do catálogo. `id=` na query é ignorado pela API — usa search."""
        code = (game_code or "").strip()
        if not code and game_id is not None and not _looks_numeric_id(game_id):
            code = str(game_id).strip()
        name = (game_name or "").strip()
        queries: list[str] = []
        for q in (code, name):
            if q and q not in queries:
                queries.append(q)
        last_items: list[dict[str, Any]] = []
        for query in queries:
            batch = self.list_casino_games(search=query, page=1, per_page=50)
            items = [x for x in (batch.get("items") or []) if isinstance(x, dict)]
            last_items = items
            hit = _match_casino_item(items, game_id=game_id, game_code=code)
            if hit:
                return hit
        label = code or name or game_id
        sample = ", ".join(str(x.get("gameCode") or x.get("id")) for x in last_items[:6])
        raise RuntimeError(
            f"Jogo {label!r} não encontrado em GET /casino/games?search= "
            f"(amostra: {sample or 'vazia'})"
        )

    def start_game(
        self,
        game_id: int | str,
        *,
        mode: str = "REAL",
        use_bonus_balance: Optional[bool] = None,
        game_code: str = "",
        aggregator: str = "",
        game_name: str = "",
        client_type: str = "desktop",
    ) -> dict[str, Any]:
        """
        POST /casino/game/launch — abre sessão no aggregator (Salsa). Não aposta.

        Frontend (Nuxt): {gameCode, walletType: 1, forFun?, clientType?, aggregator?}
        walletType 1 = cash; 2 = bônus quando use_bonus_balance=True.
        """
        if not self.token:
            raise PermissionError("Token necessário para POST /casino/game/launch")
        mode_u = (mode or "REAL").upper()
        if mode_u not in {"REAL", "FREE"}:
            raise ValueError("mode deve ser REAL ou FREE")
        catalog = self.resolve_casino_game(
            game_id,
            game_code=game_code,
            game_name=game_name,
        )
        code = str(catalog.get("gameCode") or game_code or "").strip()
        if not code:
            raise RuntimeError(f"Catálogo sem gameCode para {game_id}")
        agg = str(aggregator or catalog.get("aggregator") or "").strip()
        wallet_type = 2 if use_bonus_balance else 1
        body: dict[str, Any] = {
            "gameCode": code,
            "walletType": wallet_type,
            "clientType": client_type or "desktop",
        }
        if mode_u == "FREE":
            body["forFun"] = True
        if agg:
            body["aggregator"] = agg
        payload = self._request("POST", "/casino/game/launch", json=body)
        data = payload.get("data") if isinstance(payload, dict) else payload
        url = _extract_launch_url(payload)
        out: dict[str, Any] = {
            "game_id": catalog.get("id", game_id),
            "game_code": code,
            "name": catalog.get("gameName") or game_name,
            "provider": catalog.get("provider"),
            "aggregator": agg,
            "mode": mode_u,
            "for_fun": mode_u == "FREE",
            "use_bonus_balance": use_bonus_balance,
            "wallet_type": wallet_type,
            "url": url,
            "launch": _parse_salsa_launch(url),
        }
        if isinstance(data, dict):
            extra_keys = [
                k
                for k in data.keys()
                if k.lower() not in {"url", "token", "session", "sessiontoken", "authorization"}
                and "token" not in k.lower()
            ]
            out["response_keys"] = extra_keys[:24]
        if not url:
            out["error"] = "launch sem URL (token ok? body gameCode?)"
        return out

    def get_promotion(self, slug: str) -> dict[str, Any]:
        return self._get_json(f"/site/promotions/{slug}")

    def list_my_bonuses(self, per_page: int = 50, max_pages: int = 10) -> list[dict[str, Any]]:
        if not self.token:
            raise PermissionError("Token necessário para GET /bonus")
        items: list[dict[str, Any]] = []
        page = 1
        while page <= max_pages:
            data = self._get_json("/bonus", params={"page": page, "perPage": per_page})
            batch = list(data.get("items") or [])
            items.extend(batch)
            total = int(data.get("total") or 0)
            if not batch or len(items) >= total:
                break
            page += 1
        return items

    def extract_offers(self, soup: BeautifulSoup, source_url: str = "") -> list[BonusOffer]:
        return []

    def offer_from_detail(self, detail: dict[str, Any]) -> BonusOffer:
        title = str(detail.get("title") or "").strip()
        raw_html = str(detail.get("text") or "")
        text = self._html_to_text(raw_html)
        combined = f"{title}\n{text}"
        fields = self.nlp.analyze(combined)
        slug = str(detail.get("slug") or "")
        link = str(detail.get("link") or f"{SITE}/promotions/{slug}")
        tags = [str(t).lower() for t in (detail.get("tags") or [])]
        if "casino" in " ".join(tags) and "casino" not in fields.game_restrictions:
            fields.game_restrictions = list(dict.fromkeys([*fields.game_restrictions, "casino"]))

        return BonusOffer(
            platform=self.platform,
            bonus_type=fields.bonus_type,
            title=title or slug,
            amount=fields.amount,
            currency=fields.currency if fields.amount else ("CRC" if "₡" in combined else fields.currency),
            match_percent=fields.match_percent,
            free_spins=fields.free_spins,
            wagering_multiple=fields.wagering_multiple,
            min_deposit=fields.min_deposit,
            max_bet_during_bonus=fields.max_bet_during_bonus,
            expiry_days=fields.expiry_days,
            expiry_hours=fields.expiry_hours,
            game_restrictions=fields.game_restrictions,
            terms_url=f"{SITE}/promotions/{slug}" if slug else link,
            source_url=link,
            raw_text=combined[:4000],
        )

    def offer_from_player_bonus(self, item: dict[str, Any]) -> BonusOffer:
        """Map authenticated /bonus item → BonusOffer (fields vary by CMS)."""
        title = str(
            item.get("title")
            or item.get("name")
            or item.get("bonusName")
            or item.get("promotionTitle")
            or f"Bonus #{item.get('id', '?')}"
        ).strip()
        description = str(
            item.get("description")
            or item.get("text")
            or item.get("terms")
            or item.get("details")
            or ""
        )
        status = str(item.get("status") or item.get("state") or "")
        combined = f"{title}\n{description}\nstatus={status}\n{item}"
        # Prefer numeric fields from API when present
        amount = _first_number(item, ("amount", "bonusAmount", "value", "prize", "balance", "currentAmount"))
        wagering = _first_number(item, ("wagering", "wageringMultiple", "rollover", "wagerRequirement", "multiplier"))
        free_spins = _first_int(item, ("freeSpins", "spins", "fsCount", "remainingSpins"))
        fields = self.nlp.analyze(f"{title}\n{self._html_to_text(description)}")

        bonus_type = fields.bonus_type
        if free_spins and bonus_type == BonusType.UNKNOWN:
            bonus_type = BonusType.FREE_SPINS

        return BonusOffer(
            platform=self.platform,
            bonus_type=bonus_type,
            title=f"[conta] {title}",
            amount=amount if amount is not None else fields.amount,
            currency=str(item.get("currency") or fields.currency or "CRC"),
            match_percent=fields.match_percent,
            free_spins=free_spins if free_spins is not None else fields.free_spins,
            wagering_multiple=wagering if wagering is not None else fields.wagering_multiple,
            min_deposit=fields.min_deposit,
            max_bet_during_bonus=fields.max_bet_during_bonus,
            expiry_days=fields.expiry_days,
            expiry_hours=fields.expiry_hours,
            game_restrictions=fields.game_restrictions,
            terms_url=f"{SITE}/bonus",
            source_url=f"{SITE}/bonus",
            raw_text=combined[:4000],
        )

    def scrape_live(self, include_account: bool = True) -> ScrapeResult:
        source = f"{SITE}/promotions"
        try:
            offers: list[BonusOffer] = []
            for item in self.list_promotions():
                slug = item.get("slug")
                if not slug:
                    continue
                detail = self.get_promotion(str(slug))
                offers.append(self.offer_from_detail(detail))

            auth_error = None
            if include_account and self.token:
                try:
                    for item in self.list_my_bonuses():
                        offers.append(self.offer_from_player_bonus(item))
                    source = f"{SITE}/promotions+{SITE}/bonus"
                except Exception as exc:  # noqa: BLE001
                    auth_error = str(exc)

            result = ScrapeResult(platform=self.platform, source_url=source, offers=offers, ok=True)
            if auth_error:
                result.error = f"promos OK; account bonuses falhou: {auth_error}"
            return result
        except Exception as exc:  # noqa: BLE001
            return ScrapeResult(
                platform=self.platform,
                source_url=source,
                offers=[],
                ok=False,
                error=str(exc),
            )

    def scrape_url(self, url: str) -> ScrapeResult:
        return self.scrape_live()


def _first_number(item: dict[str, Any], keys: tuple[str, ...]) -> Optional[float]:
    for key in keys:
        if key in item and item[key] is not None and item[key] != "":
            try:
                return float(item[key])
            except (TypeError, ValueError):
                continue
    return None


def _first_int(item: dict[str, Any], keys: tuple[str, ...]) -> Optional[int]:
    value = _first_number(item, keys)
    return int(value) if value is not None else None


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _looks_numeric_id(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.isdigit()


def _match_casino_item(
    items: list[dict[str, Any]],
    *,
    game_id: int | str | None,
    game_code: str,
) -> dict[str, Any] | None:
    code = (game_code or "").strip().lower()
    gid = None if game_id is None or str(game_id).strip() == "" else str(game_id)
    if code:
        for item in items:
            if str(item.get("gameCode") or "").strip().lower() == code:
                return item
    if gid and _looks_numeric_id(gid):
        for item in items:
            if str(item.get("id")) == gid:
                return item
    return None


def _extract_launch_url(payload: Any, *, depth: int = 0) -> str:
    if depth > 4:
        return ""
    if isinstance(payload, str) and payload.startswith("http"):
        return payload
    if not isinstance(payload, dict):
        return ""
    for key in ("url", "gameUrl", "iframeUrl", "launchUrl", "game_url", "iframe_url", "link"):
        val = payload.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    nested = payload.get("data")
    if nested is not None:
        return _extract_launch_url(nested, depth=depth + 1)
    return ""


def _parse_salsa_launch(url: Any) -> dict[str, Any]:
    if not url or not isinstance(url, str):
        return {}
    try:
        parsed = urlparse(url)
        q = {k: (v[0] if v else "") for k, v in parse_qs(parsed.query).items()}
    except Exception:  # noqa: BLE001
        return {}
    balance_raw = q.get("balance")
    try:
        balance_cents = int(float(balance_raw)) if balance_raw not in (None, "") else None
    except (TypeError, ValueError):
        balance_cents = None
    return {
        "host": parsed.netloc,
        "game": q.get("game"),
        "type": q.get("type"),
        "lang": q.get("lang"),
        "pn": q.get("pn"),
        "username": q.get("username"),
        "balance_cents": balance_cents,
        "balance_brl": (balance_cents / 100.0) if balance_cents is not None else None,
    }


def json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)

