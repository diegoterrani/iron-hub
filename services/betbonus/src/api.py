from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.abuse.auto_journey import AutoJourneyRunner
from src.abuse.matrix import KillChainMatrix
from src.abuse.oracle import WithdrawalOracle
from src.abuse.store import AbuseFindingStore
from src.integrity.adapters import FourPlayBrHouse, FourPlayHouse, PagolHouse
from src.integrity.catalog import load_catalog
from src.integrity.house import HouseAdapter, UnsupportedCapability
from src.integrity.planner import IntegrityPlanner
from src.integrity.report import build_integrity_markdown
from src.integrity.runner import IntegrityRunner, empty_matrix
from src.integrity.sims import table_suite
from src.integrity.store import IntegrityRunStore
from src.llm.abuse_assist import AbuseLLMAssist
from src.llm.client import IronLLMClient, load_iron_llm_config, set_iron_llm_model
from src.llm.json_extract import llm_json_ok
from src.models.abuse import (
    AbuseFinding,
    AbuseSeverity,
    ConversionSnapshot,
    ConversionStatus,
    RulesCanon,
    WithdrawOracleResult,
)
from src.models.bonus import BonusOffer, BonusType
from src.nlp.analyzer import BonusNLPAnalyzer
from src.notify.activity import ActivityLog
from src.notify.journey_report import build_journey_markdown
from src.notify.journey_session import JourneySessionStore
from src.pipeline.runner import BonusPipeline
from src.scoring.abuse import AbuseScoringEngine, classify_abuse_severity
from src.scoring.game_bonus_vectors import summarize_platform_game_risk
from src.scrapers.fourplay_br_scraper import (
    FourPlayBrScraper,
    describe_softbet_jwt,
    is_softbet_bearer,
    normalize_softbet_token_pair,
)
from src.scrapers.fourplay_scraper import FourPlayScraper
from src.scrapers.pagol_scraper import PagolScraper
from src.storage import (
    make_findings,
    make_integrity,
    make_journey_sessions,
    make_redis,
    make_store,
    make_wallet,
)
from src.storage.wallet import WalletCredit

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
FIXTURES_DIR = ROOT / "tests" / "fixtures"
UPLOADS_DIR = DATA_DIR / "uploads"
DASHBOARD_DIST = ROOT / "dashboard" / "dist"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="BetBonus AI", version="0.5.1", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = BonusPipeline(
    store_path=DATA_DIR / "bonuses.json",
    credentials_path=DATA_DIR / "credentials.json",
)
wallet = make_wallet(DATA_DIR / "wallet.json")
abuse_findings = make_findings(DATA_DIR / "abuse_findings.json")
integrity_runs = make_integrity(DATA_DIR / "integrity_runs.json")
journey_sessions = make_journey_sessions(DATA_DIR / "journey_sessions.json")
redis_cache = make_redis()
abuse_scoring = AbuseScoringEngine()
activity = ActivityLog()
nlp = BonusNLPAnalyzer()


def _normalize_platform(platform: str) -> str:
    """Normalize a platform name/alias via the central scraper registry."""
    return pipeline.registry.normalize(platform)


def _fourplay_scraper() -> FourPlayScraper:
    token = pipeline.credentials.get_token("4play")
    if not token:
        raise HTTPException(status_code=401, detail="Sem token 4play — autentique na jornada/Auth")
    return FourPlayScraper(delay=0, token=token)


def _fourplay_br_scraper() -> FourPlayBrScraper:
    token = pipeline.credentials.get_token("4play_bet_br")
    refresh = pipeline.credentials.get_refresh_token("4play_bet_br")
    if not token and not refresh:
        raise HTTPException(
            status_code=401,
            detail="Sem token 4play.bet.br — cole localStorage.token (+ refreshToken)",
        )
    return FourPlayBrScraper(delay=0, token=token, refresh_token=refresh)


def _pagol_scraper() -> PagolScraper:
    token = pipeline.credentials.get_token("pagol_bet_br") or pipeline.credentials.get_token("pagol")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Sem token PAGOL — autentique na jornada/Auth (platform pagol_bet_br)",
        )
    return PagolScraper(delay=0, token=token)


# Ping de sessão das casas — token salvo ≠ sessão viva.
_SESSION_PING: dict[str, tuple[float, bool, str]] = {}
_SESSION_PING_TTL_S = 45.0


def _invalidate_session_ping(platform: str | None = None) -> None:
    if platform is None:
        _SESSION_PING.clear()
        return
    _SESSION_PING.pop(platform, None)
    if platform == "pagol_bet_br":
        _SESSION_PING.pop("pagol", None)


def _house_session_health(platform: str, *, has_token: bool) -> tuple[bool, str]:
    if not has_token:
        return False, "sem token"
    now = time.monotonic()
    cached = _SESSION_PING.get(platform)
    if cached and now - cached[0] < _SESSION_PING_TTL_S:
        return cached[1], cached[2]
    try:
        auth = _integrity_house(platform).validate_session()
        note = str(auth.get("currency") or auth.get("platform") or "ok")[:80]
        _SESSION_PING[platform] = (now, True, note)
        return True, note
    except Exception as exc:  # noqa: BLE001
        note = str(exc)[:180]
        _SESSION_PING[platform] = (now, False, note)
        return False, note


def _integrity_house(platform: str) -> HouseAdapter:
    """Factory para o runner de cassino — PermissionError vira BLOCKED, não 401 global."""
    plat = _normalize_platform(platform)
    if plat == "pagol_bet_br":
        token = pipeline.credentials.get_token("pagol_bet_br") or pipeline.credentials.get_token("pagol")
        if not token:
            raise PermissionError("Sem token PAGOL — autentique na jornada/Auth")
        return PagolHouse(PagolScraper(delay=0, token=token))
    if plat == "4play_bet_br":
        token = pipeline.credentials.get_token("4play_bet_br")
        refresh = pipeline.credentials.get_refresh_token("4play_bet_br")
        if not token and not refresh:
            raise PermissionError("Sem token 4play.bet.br")
        return FourPlayBrHouse(FourPlayBrScraper(delay=0, token=token, refresh_token=refresh))
    if plat == "4play":
        token = pipeline.credentials.get_token("4play")
        if not token:
            raise PermissionError("Sem token 4play.game")
        return FourPlayHouse(FourPlayScraper(delay=0, token=token))
    raise ValueError(f"Casa fora do produto cassino: {plat}")


def _persist_fourplay_br_tokens(scraper: FourPlayBrScraper) -> None:
    """Persiste token/refresh renovados pelo SoftBet refresh-token."""
    if not scraper.token:
        return
    prev = pipeline.credentials.get("4play_bet_br")
    pipeline.credentials.save(
        platform="4play_bet_br",
        token=scraper.token,
        refresh_token=scraper.refresh_token,
        email=prev.email if prev else "",
        label=prev.label if prev else "",
    )
    pipeline._hydrate_tokens()
    _invalidate_session_ping("4play_bet_br")


def _oracle(platform: str = "4play") -> WithdrawalOracle:
    plat = _normalize_platform(platform)
    if plat == "pagol_bet_br":
        return WithdrawalOracle(_pagol_scraper(), findings=abuse_findings)  # type: ignore[arg-type]
    if plat == "4play_bet_br":
        return WithdrawalOracle(_fourplay_br_scraper(), findings=abuse_findings)  # type: ignore[arg-type]
    return WithdrawalOracle(_fourplay_scraper(), findings=abuse_findings)


def _house_call(fn):  # type: ignore[no-untyped-def]
    """Executa chamada à casa convertendo auth errors em HTTP 401 claros."""
    try:
        return fn()
    except PermissionError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Sessão inválida/expirada — refaça Auth. ({exc})",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Falha na API da casa: {exc}") from exc


class AnalyzeTextRequest(BaseModel):
    platform: str = "generic"
    text: str
    title: str = ""
    persist: bool = True


class ScrapeFileRequest(BaseModel):
    platform: str = "bet365"
    path: str


class ScrapeHtmlRequest(BaseModel):
    platform: str = "generic"
    html: str
    source_url: str = "upload://html"


class ScrapeUrlRequest(BaseModel):
    platform: str = "generic"
    url: str
    delay: float = Field(default=1.5, ge=0, le=30)
    render_js: bool = False


class RunFixtureRequest(BaseModel):
    platforms: list[str] = Field(default_factory=lambda: ["bet365", "betway", "888"])
    fixture: str = "sample_promos.html"


def _stats(offers: list[BonusOffer]) -> dict[str, Any]:
    if not offers:
        return {
            "total": 0,
            "avg_score": 0,
            "by_category": {},
            "by_platform": {},
            "by_type": {},
            "top_score": 0,
            "notify_ready": 0,
        }
    scores = [o.score for o in offers]
    return {
        "total": len(offers),
        "avg_score": round(sum(scores) / len(scores), 2),
        "by_category": dict(Counter(o.category.value for o in offers)),
        "by_platform": dict(Counter(o.platform for o in offers)),
        "by_type": dict(Counter(o.bonus_type.value for o in offers)),
        "top_score": max(scores),
        "notify_ready": sum(1 for o in offers if o.score >= 65),
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "BetBonus AI",
        "version": "0.6.0",
        "mode": "casino-integrity",
        "product": "casino_online",
        "pilot": "pagol.bet.br / 4play.bet.br / 4play.game",
        "llm": load_iron_llm_config().status(),
        "journey_sessions": len(journey_sessions.list(limit=1000)),
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    offers = pipeline.store.load()
    return {
        **_stats(offers),
        "platforms_configured": list(pipeline.scrapers.keys()),
        "pipeline": [
            "Scrape",
            "Parse",
            "NLP Analysis",
            "Score",
            "Classify",
            "Store",
            "Notify",
        ],
    }


@app.get("/api/platforms")
def platforms() -> list[dict[str, str]]:
    return [
        {"id": key, "name": key, "scraper": type(scraper).__name__}
        for key, scraper in pipeline.scrapers.items()
    ]


@app.get("/api/bonuses", response_model=list[BonusOffer])
def list_bonuses(
    min_score: Optional[float] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    bonus_type: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[BonusOffer]:
    offers = pipeline.store.load()
    if min_score is not None:
        offers = [o for o in offers if o.score >= min_score]
    if platform:
        offers = [o for o in offers if o.platform.lower() == platform.lower()]
    if category:
        offers = [o for o in offers if o.category.value == category]
    if bonus_type:
        offers = [o for o in offers if o.bonus_type.value == bonus_type]
    if q:
        needle = q.lower()
        offers = [
            o
            for o in offers
            if needle in o.title.lower()
            or needle in o.raw_text.lower()
            or needle in o.platform.lower()
        ]
    return sorted(offers, key=lambda o: o.score, reverse=True)[:limit]


@app.get("/api/bonuses/{bonus_id}", response_model=BonusOffer)
def get_bonus(bonus_id: str) -> BonusOffer:
    offer = pipeline.store.get(bonus_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Bonus not found")
    return offer


@app.delete("/api/bonuses/{bonus_id}")
def delete_bonus(bonus_id: str) -> dict[str, Any]:
    ok = pipeline.store.delete(bonus_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Bonus not found")
    activity.add("bonus.delete", f"Removed bonus {bonus_id[:8]}", level="warn")
    return {"deleted": True, "id": bonus_id}


@app.delete("/api/bonuses")
def clear_bonuses() -> dict[str, Any]:
    count = pipeline.store.clear()
    activity.add("bonus.clear", f"Cleared {count} bonuses", level="warn", meta={"count": count})
    return {"deleted": count}


@app.post("/api/analyze", response_model=BonusOffer)
def analyze_text(body: AnalyzeTextRequest) -> BonusOffer:
    fields = nlp.analyze(body.text)
    offer = BonusOffer(
        platform=body.platform,
        bonus_type=fields.bonus_type,
        title=body.title or body.text[:80],
        amount=fields.amount,
        currency=fields.currency,
        match_percent=fields.match_percent,
        free_spins=fields.free_spins,
        wagering_multiple=fields.wagering_multiple,
        min_deposit=fields.min_deposit,
        max_bet_during_bonus=fields.max_bet_during_bonus,
        expiry_days=fields.expiry_days,
        expiry_hours=fields.expiry_hours,
        game_restrictions=fields.game_restrictions,
        raw_text=body.text,
    )
    if body.persist:
        scored = pipeline.process_offers([offer], notify=True)[0]
    else:
        scored = pipeline.scoring.score(offer)
    activity.add(
        "nlp.analyze",
        f"Analyzed '{scored.title[:48]}' → {scored.score:.1f}",
        level="success",
        meta={"score": scored.score, "platform": scored.platform},
    )
    return scored


@app.post("/api/pipeline/fixture", response_model=list[BonusOffer])
def run_fixture(body: RunFixtureRequest) -> list[BonusOffer]:
    path = FIXTURES_DIR / body.fixture
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Fixture not found: {body.fixture}")
    collected: list[BonusOffer] = []
    for platform in body.platforms:
        offers = pipeline.run_file(platform, path)
        collected.extend(offers)
    activity.add(
        "pipeline.fixture",
        f"Fixture {body.fixture} on {', '.join(body.platforms)} → {len(collected)} offers",
        level="success",
        meta={"count": len(collected), "platforms": body.platforms},
    )
    return sorted(collected, key=lambda o: o.score, reverse=True)


@app.post("/api/pipeline/html", response_model=list[BonusOffer])
def run_html(body: ScrapeHtmlRequest) -> list[BonusOffer]:
    offers = pipeline.run_html(body.platform, body.html, source_url=body.source_url)
    activity.add(
        "pipeline.html",
        f"HTML scrape ({body.platform}) → {len(offers)} offers",
        level="success" if offers else "warn",
        meta={"count": len(offers), "platform": body.platform},
    )
    return offers


@app.post("/api/pipeline/url")
def run_url(body: ScrapeUrlRequest) -> dict[str, Any]:
    result = pipeline.run_url(body.platform, body.url, delay=body.delay, render_js=body.render_js)
    level = "success" if result.ok and result.offers else ("error" if not result.ok else "warn")
    activity.add(
        "pipeline.url",
        f"URL scrape {body.url[:60]} → {len(result.offers)} offers"
        + (f" ({result.error})" if result.error else ""),
        level=level,
        meta={"platform": body.platform, "ok": result.ok, "count": len(result.offers)},
    )
    return {
        "ok": result.ok,
        "error": result.error,
        "platform": result.platform,
        "source_url": result.source_url,
        "offers": result.offers,
    }


class ScrapeBatchTarget(BaseModel):
    platform: str
    mode: str = "auto"  # auto | url | html | file | live
    url: str = ""
    html: str = ""
    path: str = ""
    source_url: str = ""
    delay: float = Field(default=1.5, ge=0, le=30)
    render_js: bool = False


class ScrapeBatchRequest(BaseModel):
    targets: list[ScrapeBatchTarget]
    max_workers: int = Field(default=4, ge=1, le=16)


@app.post("/api/pipeline/batch")
def run_batch(body: ScrapeBatchRequest) -> dict[str, Any]:
    results = pipeline.run_many([t.model_dump() for t in body.targets], max_workers=body.max_workers)
    ok_count = sum(1 for r in results if r.ok)
    offer_count = sum(len(r.offers) for r in results)
    activity.add(
        "pipeline.batch",
        f"Batch scrape → {ok_count}/{len(results)} ok, {offer_count} offers",
        level="success" if ok_count == len(results) else "warn",
        meta={"total": len(results), "ok": ok_count, "offers": offer_count},
    )
    return {
        "total": len(results),
        "ok": ok_count,
        "offers": offer_count,
        "results": [
            {
                "ok": r.ok,
                "error": r.error,
                "platform": r.platform,
                "source_url": r.source_url,
                "offers": r.offers,
            }
            for r in results
        ],
    }


class LivePlatformRequest(BaseModel):
    platform: str = "4play"


class SaveTokenRequest(BaseModel):
    platform: str = "4play"
    token: str
    refresh_token: str = ""
    email: str = ""
    label: str = ""


class LoginRequest(BaseModel):
    platform: str = "4play"
    email: str
    password: str
    label: str = ""


@app.post("/api/pipeline/live")
def run_live_platform(body: LivePlatformRequest) -> dict[str, Any]:
    result = pipeline.run_live_platform(body.platform)
    level = "success" if result.ok and result.offers else ("error" if not result.ok else "warn")
    activity.add(
        "pipeline.live",
        f"Live scrape {body.platform} → {len(result.offers)} offers"
        + (f" ({result.error})" if result.error else ""),
        level=level,
        meta={"platform": body.platform, "ok": result.ok, "count": len(result.offers)},
    )
    return {
        "ok": result.ok,
        "error": result.error,
        "platform": result.platform,
        "source_url": result.source_url,
        "offers": result.offers,
        "has_token": bool(pipeline.credentials.get_token(body.platform)),
    }


@app.get("/api/credentials")
def list_credentials() -> list[dict[str, Any]]:
    return pipeline.credentials.list()


@app.put("/api/credentials/{platform}")
def save_token(platform: str, body: SaveTokenRequest) -> dict[str, Any]:
    plat = _normalize_platform(platform)
    token_in = body.token.strip()
    refresh_in = body.refresh_token.strip()
    warnings: list[str] = []

    # SoftBet: aceita JSON colado no campo token
    # {"token":"...","refreshToken":"..."}
    if plat == "4play_bet_br" and token_in.startswith("{"):
        try:
            blob = json.loads(token_in)
            if isinstance(blob, dict):
                token_in = str(
                    blob.get("token")
                    or blob.get("accessToken")
                    or blob.get("access_token")
                    or ""
                ).strip()
                refresh_in = str(
                    blob.get("refreshToken")
                    or blob.get("refresh_token")
                    or refresh_in
                    or ""
                ).strip()
                warnings.append("JSON SoftBet detectado e separado em token + refreshToken.")
        except json.JSONDecodeError:
            pass

    if plat == "4play_bet_br":
        token_in, refresh_in, norm_warn = normalize_softbet_token_pair(token_in, refresh_in)
        warnings.extend(norm_warn)
        if not token_in:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Falta o token SoftBet (chave localStorage `token`). "
                    + (" ".join(warnings) if warnings else "")
                ),
            )
        if not is_softbet_bearer(token_in):
            diag = (
                f"Diagnóstico: token→{describe_softbet_jwt(token_in)}; "
                f"refreshToken→{describe_softbet_jwt(refresh_in)}."
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "O valor em `token` não parece Bearer SoftBet "
                    "(esperado: sessão iss=4play+sessionToken OU access iss=SB2). "
                    f"{diag} "
                    + (" ".join(warnings) if warnings else "")
                ),
            )
        if not refresh_in:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Falta refreshToken (chave localStorage `refreshToken`). "
                    f"token→{describe_softbet_jwt(token_in)}"
                ),
            )

    if not token_in:
        raise HTTPException(status_code=400, detail="Token vazio")

    saved = pipeline.credentials.save(
        platform=plat,
        token=token_in,
        refresh_token=refresh_in,
        email=body.email,
        label=body.label,
    )
    pipeline._hydrate_tokens()
    _invalidate_session_ping(plat)
    # SoftBet: JWT curto — avisa se já veio expirado sem refresh
    if plat == "4play_bet_br":
        br = FourPlayBrScraper(
            delay=0,
            token=token_in,
            refresh_token=refresh_in
            or pipeline.credentials.get_refresh_token("4play_bet_br"),
        )
        if br.token_expired() and not br.refresh_token:
            warnings.append(
                "JWT access expirado e sem refreshToken válido — copie os dois do Local Storage."
            )
        if warnings:
            activity.add(
                "auth.token",
                f"Token 4play.bet.br salvo com avisos: {warnings[0][:120]}",
                level="warn",
            )
            return {**saved, "warning": " ".join(warnings)}
    activity.add("auth.token", f"Token salvo para {plat}", level="success")
    if warnings:
        return {**saved, "warning": " ".join(warnings)}
    return saved


@app.delete("/api/credentials/{platform}")
def delete_credentials(platform: str) -> dict[str, Any]:
    plat = _normalize_platform(platform)
    ok = pipeline.credentials.delete(plat) or pipeline.credentials.delete(platform)
    if not ok:
        raise HTTPException(status_code=404, detail="Credencial não encontrada")
    pipeline._hydrate_tokens()
    _invalidate_session_ping(plat)
    activity.add("auth.delete", f"Token removido de {plat}", level="warn")
    return {"deleted": True, "platform": plat}


@app.post("/api/credentials/{platform}/login")
def login_platform(platform: str, body: LoginRequest) -> dict[str, Any]:
    plat = _normalize_platform(platform)
    try:
        if plat == "4play":
            token = FourPlayScraper.login(body.email, body.password)
            save_platform = "4play"
        elif plat == "pagol_bet_br":
            token = PagolScraper.login(body.email, body.password)
            save_platform = "pagol_bet_br"
        elif plat == "4play_bet_br":
            raise HTTPException(
                status_code=400,
                detail=(
                    "4play.bet.br (SoftBet): login automático ainda não ligado. "
                    "Cole localStorage.token + refreshToken na Auth."
                ),
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Login automático só suportado para 4play e pagol_bet_br",
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        activity.add("auth.login", f"Login {plat} falhou: {exc}", level="error")
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    saved = pipeline.credentials.save(
        platform=save_platform,
        token=token,
        email=body.email,
        label=body.label or body.email,
    )
    pipeline._hydrate_tokens()
    _invalidate_session_ping(save_platform)

    user_info: dict[str, Any] = {}
    try:
        if save_platform == "4play":
            user_info = FourPlayScraper(delay=0, token=token).validate_token()
        else:
            user_info = PagolScraper(delay=0, token=token).validate_token()
    except Exception as exc:  # noqa: BLE001
        user_info = {"warning": str(exc)}

    activity.add("auth.login", f"Login {save_platform} OK ({body.email})", level="success")
    return {"ok": True, "credentials": saved, "session": user_info}


@app.post("/api/credentials/{platform}/validate")
def validate_credentials(platform: str) -> dict[str, Any]:
    plat = _normalize_platform(platform)
    token = pipeline.credentials.get_token(plat) or pipeline.credentials.get_token(platform)
    refresh = pipeline.credentials.get_refresh_token(plat) or pipeline.credentials.get_refresh_token(
        platform
    )
    if not token and not refresh:
        raise HTTPException(status_code=404, detail="Sem token salvo")
    try:
        if plat == "4play":
            info = FourPlayScraper(delay=0, token=token).validate_token()
        elif plat == "pagol_bet_br":
            info = PagolScraper(delay=0, token=token).validate_token()
        elif plat == "4play_bet_br":
            scraper = FourPlayBrScraper(delay=0, token=token, refresh_token=refresh)
            info = scraper.validate_token()
            _persist_fourplay_br_tokens(scraper)
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Validate real não suportado para platform={platform}. "
                    "Use 4play, 4play_bet_br ou pagol_bet_br."
                ),
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    # SoftBet claims_trusted ainda é auth OK para a jornada
    ok = True
    if isinstance(info, dict) and info.get("mode") == "claims_trusted":
        ok = True
    return {
        "ok": ok,
        "platform": plat,
        "session": info,
        "has_token": bool(pipeline.credentials.get_token(plat)),
        "has_refresh_token": bool(pipeline.credentials.get_refresh_token(plat)),
        "warning": (info.get("warning") if isinstance(info, dict) else None),
    }


@app.post("/api/pipeline/upload", response_model=list[BonusOffer])
async def upload_html(
    platform: str = Form("generic"),
    file: UploadFile = File(...),
) -> list[BonusOffer]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    suffix = Path(file.filename).suffix.lower() or ".html"
    dest = UPLOADS_DIR / f"{platform}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}{suffix}"
    content = await file.read()
    dest.write_bytes(content)
    offers = pipeline.run_file(platform, dest)
    activity.add(
        "pipeline.upload",
        f"Uploaded {file.filename} ({platform}) → {len(offers)} offers",
        level="success" if offers else "warn",
        meta={"file": file.filename, "count": len(offers)},
    )
    return offers


@app.get("/api/activity")
def list_activity(limit: int = Query(default=40, ge=1, le=200)) -> list[dict[str, Any]]:
    return [e.model_dump(mode="json") for e in activity.list(limit=limit)]


@app.delete("/api/activity")
def clear_activity() -> dict[str, str]:
    activity.clear()
    return {"status": "cleared"}


@app.get("/api/bonus-types")
def bonus_types() -> list[str]:
    return [t.value for t in BonusType]


class CreditBonusItem(BaseModel):
    bonus_id: str = ""
    title: str
    amount: float = 0.0
    currency: str = "CRC"
    source: str = "promo"
    note: str = ""


class CreditRequest(BaseModel):
    platform: str = "4play"
    items: list[CreditBonusItem]


@app.get("/api/wallet")
def wallet_summary(platform: str = Query(default="")) -> dict[str, Any]:
    summary = wallet.summary()
    summary["ledger"] = "betbonus_ops"
    summary["reality"] = "internal_sim"
    summary["note"] = (
        "Este ledger é operacional/simulação do BetBonus. Não altera balance/bonus da casa."
    )
    houses: list[dict[str, Any]] = []
    wanted = _normalize_platform(platform) if platform else ""
    targets = [wanted] if wanted else ["4play", "pagol_bet_br", "4play_bet_br"]
    for plat in targets:
        try:
            if plat == "4play" and pipeline.credentials.get_token("4play"):
                snap = FourPlayScraper(
                    delay=0, token=pipeline.credentials.get_token("4play")
                ).get_wallet_snapshot()
                houses.append(
                    {
                        "connected": True,
                        "platform": "4play",
                        "balance": snap.balance,
                        "bonus": snap.bonus,
                        "rollover": snap.rollover,
                    }
                )
            elif plat == "pagol_bet_br" and (
                pipeline.credentials.get_token("pagol_bet_br")
                or pipeline.credentials.get_token("pagol")
            ):
                snap = _pagol_scraper().get_wallet_snapshot()
                houses.append(
                    {
                        "connected": True,
                        "platform": "pagol_bet_br",
                        "balance": snap.balance,
                        "bonus": snap.bonus,
                        "rollover": snap.rollover,
                        "raw": snap.raw,
                    }
                )
            elif plat == "4play_bet_br" and (
                pipeline.credentials.get_token("4play_bet_br")
                or pipeline.credentials.get_refresh_token("4play_bet_br")
            ):
                scraper = _fourplay_br_scraper()
                snap = scraper.get_wallet_snapshot()
                _persist_fourplay_br_tokens(scraper)
                houses.append(
                    {
                        "connected": True,
                        "platform": "4play_bet_br",
                        "balance": snap.balance,
                        "bonus": snap.bonus,
                        "rollover": snap.rollover,
                        "raw": snap.raw,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            houses.append({"connected": True, "platform": plat, "error": str(exc)})
    summary["house_wallet"] = houses[0] if len(houses) == 1 else {"connected": bool(houses)}
    summary["house_wallets"] = houses
    return summary


@app.post("/api/wallet/credit")
def wallet_credit(body: CreditRequest) -> dict[str, Any]:
    credits = [
        WalletCredit(
            platform=body.platform,
            bonus_id=item.bonus_id,
            title=item.title,
            amount=item.amount,
            currency=item.currency,
            source=item.source,
            status="credited",
            reality="internal_sim",
            note=(item.note or "Ledger interno BetBonus — não credita a casa"),
        )
        for item in body.items
    ]
    saved = wallet.credit_many(credits)
    activity.add(
        "wallet.credit",
        f"Ledger INTERNO (simulação): {len(saved)} itens em {body.platform} — saldo da casa intacto",
        level="success",
        meta={"count": len(saved), "platform": body.platform},
    )
    return {"ok": True, "credited": len(saved), "wallet": wallet.summary()}


@app.delete("/api/wallet")
def wallet_clear() -> dict[str, Any]:
    n = wallet.clear()
    activity.add("wallet.clear", f"Carteira limpa ({n})", level="warn")
    return {"deleted": n}


@app.get("/api/journey/presets")
def journey_presets() -> list[dict[str, str]]:
    return [
        {
            "id": "4play",
            "name": "4Play.game",
            "url": "https://4play.game/promotions",
            "platform": "4play",
            "auth": "token|login",
            "notes": "API pública + /bonus + oracle de saque real",
        },
        {
            "id": "pagol",
            "name": "PAGOL.BET.BR",
            "url": "https://pagol.bet.br/br/my-account/bonuses-rollover/bonus-list",
            "platform": "pagol_bet_br",
            "auth": "token|login",
            "notes": "Live API Lucky Gaming · /user/bonuses.do + balance + promocodes",
        },
        {
            "id": "generic",
            "name": "Casa genérica (HTML)",
            "url": "",
            "platform": "generic",
            "auth": "optional",
            "notes": "Cole HTML ou faça upload",
        },
    ]


class JourneySessionStartRequest(BaseModel):
    platform: str = "4play"
    house_name: str = ""
    house_url: str = ""
    scout_mode: str = ""
    label: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)
    close_previous: bool = True


class JourneySessionEventRequest(BaseModel):
    step: str = ""
    kind: str
    message: str
    level: str = "info"
    detail: dict[str, Any] = Field(default_factory=dict)


class JourneySessionCloseRequest(BaseModel):
    note: str = ""


@app.get("/api/journey/sessions")
def list_journey_sessions(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return journey_sessions.list(limit=limit)


@app.get("/api/journey/sessions/active")
def active_journey_session() -> dict[str, Any]:
    session = journey_sessions.active()
    if not session:
        return {"active": False, "session": None}
    return {"active": True, "session": session.model_dump(mode="json")}


@app.post("/api/journey/sessions")
def start_journey_session(body: JourneySessionStartRequest) -> dict[str, Any]:
    session = journey_sessions.start(
        platform=body.platform,
        house_name=body.house_name,
        house_url=body.house_url,
        scout_mode=body.scout_mode,
        label=body.label,
        meta=body.meta,
        close_previous=body.close_previous,
    )
    activity.add(
        "journey.session.start",
        f"Sessão de logs {session.id[:8]} · {session.house_name or session.platform}",
        level="success",
        meta={"session_id": session.id, "platform": session.platform},
    )
    return {"ok": True, "session": session.model_dump(mode="json")}


@app.get("/api/journey/sessions/{session_id}")
def get_journey_session(session_id: str) -> dict[str, Any]:
    session = journey_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return session.model_dump(mode="json")


@app.post("/api/journey/sessions/{session_id}/events")
def append_journey_session_event(session_id: str, body: JourneySessionEventRequest) -> dict[str, Any]:
    try:
        event = journey_sessions.append(
            session_id,
            step=body.step,
            kind=body.kind,
            message=body.message,
            level=body.level,
            detail=body.detail,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from exc
    # espelha no feed activity (resumo)
    activity.add(
        body.kind,
        body.message,
        level=body.level if body.level in {"info", "success", "warn", "error"} else "info",
        meta={"session_id": session_id, "step": body.step, **(body.detail or {})},
    )
    return {"ok": True, "event": event.model_dump(mode="json")}


@app.post("/api/journey/sessions/{session_id}/close")
def close_journey_session(session_id: str, body: JourneySessionCloseRequest) -> dict[str, Any]:
    try:
        session = journey_sessions.close(session_id, note=body.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from exc
    activity.add(
        "journey.session.close",
        f"Sessão {session_id[:8]} encerrada",
        level="info",
        meta={"session_id": session_id},
    )
    return {"ok": True, "session": session.model_dump(mode="json")}


@app.delete("/api/journey/sessions/{session_id}")
def delete_journey_session(session_id: str) -> dict[str, Any]:
    ok = journey_sessions.delete(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return {"deleted": True, "id": session_id}


@app.delete("/api/journey/sessions")
def clear_journey_sessions() -> dict[str, int]:
    n = journey_sessions.clear()
    activity.add("journey.sessions.clear", f"Limpas {n} sessões de log", level="warn")
    return {"deleted": n}


class AbuseScoreRequest(BaseModel):
    offer_ids: list[str] = Field(default_factory=list)
    # optional inline offers from journey session
    offers: list[BonusOffer] = Field(default_factory=list)
    platform: str = "4play"


class WithdrawOracleRequest(BaseModel):
    platform: str = "4play"
    # amount ignorado quando use_max_available=True (default): saca min(saldo, max_amount)
    amount: float = Field(default=0, ge=0)
    confirm_real_withdraw: bool = False
    method: str = Field(default="tft", pattern="^(tft|dtr|PIX|pix|preflight)$")
    phone: str = ""
    iban: str = ""
    max_amount: float = Field(default=FourPlayScraper.MAX_WITHDRAW_AMOUNT, ge=1)
    preflight_only: bool = False
    use_max_available: bool = True
    convert_bonus: bool = True
    game_id: Optional[int] = None


@app.get("/api/abuse/snapshot", response_model=ConversionSnapshot)
def abuse_snapshot(platform: str = Query(default="4play")) -> ConversionSnapshot:
    """Estado de conversão na casa: balance/bonus/rollover → status."""
    plat = _normalize_platform(platform)
    snap = _house_call(lambda: _oracle(plat).snapshot())
    activity.add(
        "abuse.snapshot",
        f"Conversão={snap.status.value} balance={snap.wallet.balance} gates={len(snap.gates)}",
        level="info",
        meta={"status": snap.status.value, "gates": snap.gates, "platform": plat},
    )
    return snap


@app.post("/api/abuse/score")
def abuse_score(body: AbuseScoreRequest) -> dict[str, Any]:
    """Score de abusabilidade (alto = mais fácil abusar)."""
    offers: list[BonusOffer] = list(body.offers)
    if body.offer_ids:
        stored = {o.id: o for o in pipeline.store.load()}
        for oid in body.offer_ids:
            if oid in stored:
                offers.append(stored[oid])
    scored = []
    for offer in offers:
        score, breakdown, game_vectors = abuse_scoring.score_offer_with_vectors(offer)
        severity = classify_abuse_severity(score)
        scored.append(
            {
                "offer_id": offer.id,
                "title": offer.title,
                "platform": offer.platform,
                "abuse_score": score,
                "severity": severity.value,
                "breakdown": breakdown,
                "game_bonus_vectors": game_vectors,
                "rules": RulesCanon(
                    platform=offer.platform,
                    offer_id=offer.id,
                    title=offer.title,
                    wagering_multiple=offer.wagering_multiple,
                    min_deposit=offer.min_deposit,
                    max_bet_during_bonus=offer.max_bet_during_bonus,
                    game_restrictions=offer.game_restrictions,
                    expiry_days=offer.effective_expiry_days,
                    currency=offer.currency,
                    amount=offer.amount,
                ).model_dump(mode="json"),
            }
        )
    scored.sort(key=lambda x: x["abuse_score"], reverse=True)
    activity.add(
        "abuse.score",
        f"Abuse score em {len(scored)} offers",
        level="success" if scored else "warn",
        meta={"count": len(scored)},
    )
    return {"count": len(scored), "items": scored}


@app.post("/api/abuse/oracle/withdraw", response_model=WithdrawOracleResult)
def abuse_oracle_withdraw(body: WithdrawOracleRequest) -> WithdrawOracleResult:
    """
    Oracle de saque — 4Play (SINPE real) ou PAGOL (PIX real via request.do).

    Requer confirm_real_withdraw=true para tentativa (exceto preflight_only).
    """
    plat = _normalize_platform(body.platform)
    method = body.method
    max_amount = body.max_amount
    if plat == "pagol_bet_br":
        method = "PIX" if method.lower() in {"tft", "dtr", "pix", "preflight"} else method
        if max_amount < body.amount:
            max_amount = body.amount
        # Teto lab PAGOL (BRL); default da request vem do 4Play CRC
        if max_amount <= 1 or max_amount > PagolScraper.MAX_WITHDRAW_AMOUNT:
            max_amount = PagolScraper.MAX_WITHDRAW_AMOUNT
    elif plat == "4play" and max_amount <= 1:
        max_amount = FourPlayScraper.MAX_WITHDRAW_AMOUNT
    result = _house_call(
        lambda: _oracle(plat).attempt_withdraw(
            amount=body.amount,
            confirm_real_withdraw=body.confirm_real_withdraw,
            method=method,
            phone=body.phone,
            iban=body.iban,
            max_amount=max_amount,
            preflight_only=body.preflight_only,
            use_max_available=body.use_max_available,
            convert_bonus=body.convert_bonus,
            game_id=body.game_id,
        )
    )
    level = "success" if result.ok else ("warn" if result.attempted else "info")
    activity.add(
        "abuse.oracle.withdraw",
        f"Saque attempted={result.attempted} ok={result.ok} code={result.code or '-'}",
        level=level,
        meta={
            "attempted": result.attempted,
            "ok": result.ok,
            "code": result.code,
            "amount": result.amount,
            "status": result.status.value,
            "finding_id": result.finding_id,
        },
    )
    return result


class HighEvProbeRequest(BaseModel):
    platform: str = "pagol_bet_br"
    limit: int = Field(default=6, ge=1, le=20)
    include_bonus_flag: bool = True


class BonusMultiplierLabRequest(BaseModel):
    platform: str = "pagol_bet_br"
    promocode: str = ""
    game_id: int = Field(default=PagolScraper.DEFAULT_STAKE_GAME_ID, ge=1)
    stake_brl: float = Field(default=PagolScraper.DEFAULT_LAB_STAKE_BRL, gt=0, le=PagolScraper.MAX_LAB_STAKE_BRL)
    confirm_redeem: bool = False
    confirm_real_bet: bool = False
    use_bonus_balance: bool = True
    poll_seconds: int = Field(default=30, ge=0, le=120)


class KillChainMatrixRequest(BaseModel):
    """Cerca a kill-chain automatizável: bônus → max valor → saque materializado."""

    platform: str = "pagol_bet_br"
    promocode: str = ""
    confirm_redeem: bool = False
    confirm_real_withdraw: bool = False
    settle_withdraw: bool = True
    settle_timeout_s: int = Field(default=60, ge=10, le=300)
    probe_high_ev: bool = True
    probe_slots: bool = True
    arm_wager_poll: bool = False
    poll_seconds: int = Field(default=20, ge=0, le=120)
    high_ev_limit: int = Field(default=4, ge=1, le=12)
    slots_limit: int = Field(default=3, ge=1, le=8)
    persist_findings: bool = True


class AutoJourneyRequest(BaseModel):
    """Jornada completa automática house-agnostic (recon→stages→report)."""

    platform: str = "pagol_bet_br"
    session_id: str = ""
    exhaust_mode: bool = True
    confirm_redeem: bool = True
    confirm_real_withdraw: bool = False
    confirm_real_bet: bool = True
    settle_withdraw: bool = True
    settle_timeout_s: int = Field(default=90, ge=10, le=300)
    promocode_limit: int = Field(default=20, ge=0, le=80)
    llm_limit: int = Field(default=2, ge=0, le=4)
    run_deep_attack: bool = True
    poll_seconds: int = Field(default=20, ge=0, le=120)
    persist_findings: bool = True
    recon_use_llm: bool = True
    recon_refresh: bool = False
    recon_timeout_s: float = Field(default=45.0, ge=5.0, le=120.0)


@app.get("/api/abuse/games/high-ev")
def abuse_games_high_ev(
    platform: str = Query(default="pagol_bet_br"),
    max_games: int = Query(default=60, ge=5, le=120),
) -> dict[str, Any]:
    """Discovery de jogos high-EV (crash/mines/plinko/aviator) na casa autenticada."""
    plat = _normalize_platform(platform)
    if plat != "pagol_bet_br":
        raise HTTPException(
            status_code=400,
            detail="Discovery high-EV live só implementado para pagol_bet_br neste lab.",
        )

    def _run() -> dict[str, Any]:
        return _pagol_scraper().discover_high_ev_games(max_games=max_games)

    data = _house_call(_run)
    activity.add(
        "abuse.games.high_ev",
        f"High-EV discovery: {data.get('count', 0)} jogos",
        level="success",
        meta={"count": data.get("count"), "term_hits": data.get("term_hits")},
    )
    return data


@app.post("/api/abuse/games/probe-contribution")
def abuse_games_probe_contribution(body: HighEvProbeRequest) -> dict[str, Any]:
    """
    Soft-probe: abre sessão Salsa em jogos high-EV (cash vs bonusBalance).
    Não envia aposta ao provider — contribuição % real ainda exige stake manual/controlado.
    """
    plat = _normalize_platform(body.platform)
    if plat != "pagol_bet_br":
        raise HTTPException(
            status_code=400,
            detail="Probe high-EV só implementado para pagol_bet_br neste lab.",
        )

    def _run() -> dict[str, Any]:
        return _pagol_scraper().probe_high_ev_contribution(
            limit=body.limit,
            include_bonus_flag=body.include_bonus_flag,
        )

    data = _house_call(_run)
    snap = _house_call(lambda: _oracle(plat).snapshot())
    for row in data.get("findings") or []:
        sev_raw = str(row.get("severity") or "medium").lower()
        try:
            sev = AbuseSeverity(sev_raw)
        except ValueError:
            sev = AbuseSeverity.MEDIUM
        if sev not in {AbuseSeverity.HIGH, AbuseSeverity.CRITICAL, AbuseSeverity.MEDIUM}:
            continue
        abuse_findings.add(
            AbuseFinding(
                platform=plat,
                vector=str(row.get("id") or "high_ev_probe"),
                severity=sev,
                title=str(row.get("title") or "High-EV probe")[:160],
                status=snap.status,
                abuse_score=0.0,
                evidence={
                    "rationale": row.get("rationale"),
                    "test_idea": row.get("test_idea"),
                    "probe_kind": data.get("probe_kind"),
                },
            )
        )
    activity.add(
        "abuse.games.probe",
        f"High-EV probe: {data.get('probed', 0)} jogos, "
        f"{len(data.get('findings') or [])} findings",
        level="success",
        meta={
            "probed": data.get("probed"),
            "findings": len(data.get("findings") or []),
            "wallet_unchanged": data.get("wallet_unchanged"),
        },
    )
    return data


@app.post("/api/abuse/auto-journey/run")
def abuse_auto_journey_run(body: AutoJourneyRequest) -> dict[str, Any]:
    """
    Executa a jornada house-agnostic inteira de uma vez:
    Recon → Auth → Discovery → Acquire → Arm → Analyze → Probe →
    Cashout → Report. Estágios selecionados pelo HouseProfile.
    """
    plat = _normalize_platform(body.platform)

    # Factory: select scraper by platform
    if plat == "pagol_bet_br":
        scraper = _pagol_scraper()
        house_name = "PAGOL.BET.BR"
        house_url = "https://pagol.bet.br/br/"
    elif plat == "4play":
        scraper = _fourplay_scraper()
        house_name = "4PLAY.GAME"
        house_url = "https://4play.game"
    elif plat == "4play_bet_br":
        scraper = _fourplay_br_scraper()
        house_name = "4PLAY.BET.BR"
        house_url = "https://4play.bet.br"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Plataforma '{plat}' não suportada. Use: pagol_bet_br, 4play, 4play_bet_br.",
        )

    session = None
    if body.session_id:
        session = journey_sessions.get(body.session_id)
    if session is None:
        session = journey_sessions.start(
            platform=plat,
            house_name=house_name,
            house_url=house_url,
            scout_mode="live",
            label=f"{house_name} · auto-journey",
            meta={"mode": "auto_journey"},
            close_previous=False,
        )

    def _journey_log(
        step: str, kind: str, message: str, level: str, detail: dict[str, Any]
    ) -> None:
        try:
            journey_sessions.append(
                session.id,
                step=step,
                kind=kind,
                message=message,
                level=level,
                detail=detail,
            )
        except Exception:  # noqa: BLE001
            pass

    def _run() -> dict[str, Any]:
        runner = AutoJourneyRunner(
            scraper,
            oracle=WithdrawalOracle(scraper, findings=abuse_findings),
            findings=abuse_findings if body.persist_findings else None,
            ledger=wallet,
            process_offers=lambda offs: pipeline.process_offers(offs, notify=False),
            reports_dir=DATA_DIR / "reports",
            cache_dir=DATA_DIR / "house_profiles",
            log=_journey_log,
        )
        # exhaust_mode: esgota o máximo de recursos mapeados na kill-chain
        promo_limit = body.promocode_limit
        llm_limit = body.llm_limit
        poll_s = body.poll_seconds
        settle_s = body.settle_timeout_s
        deep = body.run_deep_attack
        if body.exhaust_mode:
            promo_limit = max(promo_limit, 40)
            llm_limit = max(llm_limit, 2)
            poll_s = max(poll_s, 30)
            settle_s = max(settle_s, 120)
            deep = True
        return runner.run(
            confirm_redeem=body.confirm_redeem,
            confirm_real_withdraw=body.confirm_real_withdraw,
            confirm_real_bet=body.confirm_real_bet,
            settle_withdraw=body.settle_withdraw,
            settle_timeout_s=settle_s,
            promocode_limit=promo_limit,
            llm_limit=llm_limit,
            run_deep_attack=deep,
            poll_seconds=poll_s,
            persist_findings=body.persist_findings,
            recon_use_llm=body.recon_use_llm,
            recon_refresh=body.recon_refresh,
            recon_timeout_s=body.recon_timeout_s,
        )

    # LLM + probes can exceed default proxy timeouts — still run sync in lab
    data = _house_call(_run)
    data = {**data, "session_id": session.id, "exhaust_mode": body.exhaust_mode}
    try:
        journey_sessions.append(
            session.id,
            step="auto",
            kind="auto.report_ready",
            message=f"Relatório auto-journey · stuck={data.get('stuck_point')}",
            level="success",
            detail={
                "report_md_path": data.get("report_md_path"),
                "stuck_point": data.get("stuck_point"),
                "automation_goal_met": data.get("automation_goal_met"),
            },
        )
    except Exception:  # noqa: BLE001
        pass
    activity.add(
        "abuse.auto_journey",
        f"Auto-journey · stuck={data.get('stuck_point')} · "
        f"goal_met={data.get('automation_goal_met')}",
        level="success" if data.get("ok") else "warn",
        meta={
            "run_id": data.get("run_id"),
            "stuck_point": data.get("stuck_point"),
            "session_id": session.id,
            "report": data.get("report_md_path"),
        },
    )
    return data


@app.get("/api/abuse/auto-journey/latest.md")
def abuse_auto_journey_latest_md(platform: str = "") -> Response:
    """Download do último relatório .md da jornada automática.

    Sem `platform` param: devolve o mais recente de qualquer casa.
    Com `platform`: devolve o latest daquela casa específica.

    Handles both naming conventions:
      new: auto-journey-{plat}-latest.md
      old: {plat}-auto-journey-latest.md
    """
    reports_dir = DATA_DIR / "reports"
    if platform:
        plat = _normalize_platform(platform)
        # Try new naming first, then old naming
        path = reports_dir / f"auto-journey-{plat}-latest.md"
        if not path.exists():
            path = reports_dir / f"{plat}-auto-journey-latest.md"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Nenhum relatório auto-journey para {plat}")
        content = path.read_text(encoding="utf-8")
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{path.name}"'
            },
        )
    # No platform: find the most recent auto-journey latest (both naming conventions)
    candidates = sorted(
        list(reports_dir.glob("auto-journey-*-latest.md"))
        + list(reports_dir.glob("*-auto-journey-latest.md")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise HTTPException(status_code=404, detail="Nenhum relatório auto-journey ainda")
    path = candidates[0]
    content = path.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{path.name}"'
        },
    )


@app.post("/api/abuse/matrix/run")
def abuse_kill_chain_matrix(body: KillChainMatrixRequest) -> dict[str, Any]:
    """
    Kill-chain matrix PAGOL: inventário de bônus/regras → probes → plano maxConvert →
    saque (opt) → settle BO. Devolve cobertura AUTOMATED/SEMI/MANUAL e vulnerabilidades.
    """
    plat = _normalize_platform(body.platform)
    if plat != "pagol_bet_br":
        raise HTTPException(
            status_code=400,
            detail="Kill-chain matrix só implementada para pagol_bet_br neste lab.",
        )

    def _run() -> dict[str, Any]:
        scraper = _pagol_scraper()
        matrix = KillChainMatrix(
            scraper,
            oracle=WithdrawalOracle(scraper, findings=abuse_findings),
            findings=abuse_findings if body.persist_findings else None,
        )
        return matrix.run(
            promocode=body.promocode,
            confirm_redeem=body.confirm_redeem,
            confirm_real_withdraw=body.confirm_real_withdraw,
            settle_withdraw=body.settle_withdraw,
            settle_timeout_s=body.settle_timeout_s,
            probe_high_ev=body.probe_high_ev,
            probe_slots=body.probe_slots,
            arm_wager_poll=body.arm_wager_poll,
            poll_seconds=body.poll_seconds,
            high_ev_limit=body.high_ev_limit,
            slots_limit=body.slots_limit,
            persist_findings=body.persist_findings,
        )

    data = _house_call(_run)
    # Persist markdown snapshot for the operator
    try:
        reports_dir = DATA_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        run_id = str(data.get("run_id") or "matrix")[:8]
        path = reports_dir / f"pagol-killchain-{run_id}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        data = {**data, "report_path": str(path)}
        # compact md
        md_path = reports_dir / f"pagol-killchain-{run_id}.md"
        md_path.write_text(_matrix_to_markdown(data), encoding="utf-8")
        data = {**data, "report_md_path": str(md_path)}
    except Exception:  # noqa: BLE001
        pass
    activity.add(
        "abuse.matrix.run",
        f"Kill-chain matrix · vulns={len(data.get('vulnerabilities') or [])} · "
        f"blocker={((data.get('verdict') or {}).get('dominant_blocker'))}",
        level="success" if data.get("ok") else "warn",
        meta={
            "run_id": data.get("run_id"),
            "vuln_count": len(data.get("vulnerabilities") or []),
            "blocker": (data.get("verdict") or {}).get("dominant_blocker"),
        },
    )
    return data


def _matrix_to_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# PAGOL · Kill-chain matrix",
        "",
        f"- Run: `{data.get('run_id')}`",
        f"- Finished: `{data.get('finished_at')}`",
        f"- Blocker: **{(data.get('verdict') or {}).get('dominant_blocker')}**",
        f"- Summary: {(data.get('verdict') or {}).get('summary')}",
        "",
        "## Coverage",
        "",
        "```json",
        json.dumps(data.get("coverage") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Stages",
        "",
    ]
    for s in data.get("stages") or []:
        if not isinstance(s, dict):
            continue
        lines.append(
            f"### [{s.get('mode')}] `{s.get('id')}` — {s.get('title')} "
            f"{'✅' if s.get('ok') else '⛔'}"
        )
        lines.append("")
        if s.get("vulnerability"):
            lines.append(f"- Vulnerability: `{s.get('vulnerability')}` ({s.get('severity')})")
        if s.get("note"):
            lines.append(f"- Note: {s.get('note')}")
        if s.get("gates"):
            lines.append(f"- Gates: {', '.join(map(str, s.get('gates') or []))}")
        lines.append("")
    lines.extend(
        [
            "## Vulnerabilities",
            "",
            "```json",
            json.dumps(data.get("vulnerabilities") or [], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


@app.post("/api/abuse/games/bonus-multiplier")
def abuse_games_bonus_multiplier(body: BonusMultiplierLabRequest) -> dict[str, Any]:
    """
    Lab multiplicador: redeem promo (confirm) + arma sessão Mines/Aviator + poll carteira.

    Não envia aposta automática ao Spribe (SmartFox WS). Com confirm_real_bet, devolve
    provider_url para stake mínimo manual/operador dentro do teto lab.
    """
    plat = _normalize_platform(body.platform)
    if plat != "pagol_bet_br":
        raise HTTPException(
            status_code=400,
            detail="Bonus multiplier lab só implementado para pagol_bet_br.",
        )

    def _run() -> dict[str, Any]:
        return _pagol_scraper().run_bonus_multiplier_lab(
            promocode=body.promocode,
            game_id=body.game_id,
            stake_brl=body.stake_brl,
            confirm_redeem=body.confirm_redeem,
            confirm_real_bet=body.confirm_real_bet,
            use_bonus_balance=body.use_bonus_balance,
            poll_seconds=body.poll_seconds,
        )

    data = _house_call(_run)
    snap = _house_call(lambda: _oracle(plat).snapshot())
    for row in data.get("findings") or []:
        sev_raw = str(row.get("severity") or "medium").lower()
        try:
            sev = AbuseSeverity(sev_raw)
        except ValueError:
            sev = AbuseSeverity.MEDIUM
        if sev in {AbuseSeverity.INFO, AbuseSeverity.LOW}:
            continue
        abuse_findings.add(
            AbuseFinding(
                platform=plat,
                vector=str(row.get("id") or "bonus_multiplier_lab"),
                severity=sev,
                title=str(row.get("title") or "Bonus multiplier lab")[:160],
                status=snap.status,
                abuse_score=0.0,
                evidence={
                    "rationale": row.get("rationale"),
                    "test_idea": row.get("test_idea"),
                    "gates": data.get("gates"),
                    "stake_brl": data.get("stake_brl"),
                    "bet_armed": data.get("bet_armed"),
                },
            )
        )
    activity.add(
        "abuse.games.bonus_multiplier",
        f"Bonus-lab armed={data.get('bet_armed')} gates={len(data.get('gates') or [])}",
        level="warn" if data.get("gates") else "success",
        meta={
            "bet_armed": data.get("bet_armed"),
            "confirm_redeem": body.confirm_redeem,
            "confirm_real_bet": body.confirm_real_bet,
            "stake_brl": body.stake_brl,
            "findings": len(data.get("findings") or []),
        },
    )
    return data


@app.get("/api/abuse/findings", response_model=list[AbuseFinding])
def list_abuse_findings(limit: int = Query(default=100, ge=1, le=500)) -> list[AbuseFinding]:
    return abuse_findings.list(limit=limit)


@app.delete("/api/abuse/findings")
def clear_abuse_findings() -> dict[str, int]:
    n = abuse_findings.clear()
    activity.add("abuse.findings.clear", f"Limpos {n} findings", level="warn")
    return {"deleted": n}


@app.post("/api/abuse/evaluate")
def abuse_evaluate(body: AbuseScoreRequest) -> dict[str, Any]:
    """Snapshot de conversão + abuse scores + vetores de jogos/bônus (sem saque)."""
    plat = _normalize_platform(body.platform or (body.offers[0].platform if body.offers else "4play"))
    snap = _house_call(lambda: _oracle(plat).snapshot())
    scored = abuse_score(body)
    offers_for_vectors: list[BonusOffer] = list(body.offers)
    if body.offer_ids:
        stored = {o.id: o for o in pipeline.store.load()}
        for oid in body.offer_ids:
            if oid in stored:
                offers_for_vectors.append(stored[oid])
    game_risk = summarize_platform_game_risk(
        offers_for_vectors,
        wallet_bonus=snap.wallet.bonus,
        wallet_rollover=snap.wallet.rollover,
    )
    # Persiste vetores high/critical como findings defensivos
    for vector in game_risk.get("items") or []:
        sev_raw = str(vector.get("severity") or "medium").lower()
        if sev_raw not in {"high", "critical"}:
            continue
        sev = AbuseSeverity.CRITICAL if sev_raw == "critical" else AbuseSeverity.HIGH
        abuse_findings.add(
            AbuseFinding(
                platform=plat,
                vector=str(vector.get("id") or "game_bonus_vector"),
                severity=sev,
                title=str(vector.get("title") or "Vetor jogos/bônus")[:160],
                status=snap.status,
                abuse_score=0.0,
                offer_id=str(vector.get("offer_id") or ""),
                evidence={
                    "rationale": vector.get("rationale"),
                    "test_idea": vector.get("test_idea"),
                    "evidence": vector.get("evidence"),
                    "source": vector.get("source"),
                    "offer_title": vector.get("offer_title"),
                },
            )
        )
    finding_note = {
        "blocked": "Controle da casa ativo: saldo abaixo do mínimo de saque (finding válido).",
        "withdrawable": "Saldo aparentemente sacável — pronto para oracle de saque.",
        "wagering": "Rollover ativo — conversão ainda em andamento.",
        "no_bonus": "Sem bônus ativo na conta.",
        "claimed": "Bônus presente; validar path até saque.",
    }.get(snap.status.value, "")
    if game_risk.get("count"):
        finding_note = (
            (finding_note + " " if finding_note else "")
            + f"Vetores jogos/bônus: {game_risk['count']} "
            f"(critical={game_risk.get('critical', 0)}, high={game_risk.get('high', 0)})."
        )
    if plat == "pagol_bet_br":
        house = {
            "min_withdraw": PagolScraper.MIN_WITHDRAW_AMOUNT,
            "max_withdraw": PagolScraper.MAX_WITHDRAW_AMOUNT,
            "withdraw_methods": ["PIX", "PAY_BROKERS"],
            "currency": "BRL",
            "note": (
                "Oracle PAGOL: POST /user/withdrawals/request.do (PIX real, confirm obrigatório). "
                "Valores BetBonus em BRL; API Lucky envia em centavos (R$20 = 2000)."
            ),
        }
    elif plat == "4play_bet_br":
        house = {
            "min_withdraw": None,
            "max_withdraw": None,
            "withdraw_methods": [],
            "currency": "BRL",
            "note": (
                "4play.bet.br SoftBet: auth via token+refreshToken. "
                "Saque real ainda não ligado; snapshot via /api/account/balance."
            ),
        }
    else:
        house = {
            "min_withdraw": FourPlayScraper.MIN_WITHDRAW_AMOUNT,
            "max_withdraw": FourPlayScraper.MAX_WITHDRAW_AMOUNT,
            "withdraw_methods": ["tft", "dtr"],
            "currency": "CRC",
        }
    return {
        "conversion": snap.model_dump(mode="json"),
        "abuse": scored,
        "game_bonus_risk": game_risk,
        "house": house,
        "llm": load_iron_llm_config().status(),
        "verdict": {
            "ok": True,
            "status": snap.status.value,
            "note": finding_note,
            "platform": plat,
            "redteam_success": snap.status.value
            in {"blocked", "withdrawable", "wagering", "withdraw_denied", "withdraw_ok"}
            or bool(game_risk.get("count")),
        },
    }


class AbuseLLMRequest(BaseModel):
    offer_ids: list[str] = Field(default_factory=list)
    offers: list[BonusOffer] = Field(default_factory=list)
    text: str = ""
    title: str = ""
    platform: str = "4play"
    limit: int = Field(default=3, ge=1, le=8)


class AbuseLLMDeepRequest(BaseModel):
    offer_id: str = ""
    offer: Optional[BonusOffer] = None
    platform: str = "4play"
    prior_summary: str = ""
    prior_vectors: list[dict[str, Any]] = Field(default_factory=list)


class JourneyReportRequest(BaseModel):
    summary: str = ""
    conversion: Optional[dict[str, Any]] = None
    abuse_items: list[dict[str, Any]] = Field(default_factory=list)
    game_bonus_risk: Optional[dict[str, Any]] = None
    llm_report: str = ""
    llm_vectors: list[dict[str, Any]] = Field(default_factory=list)
    deep_attack: Optional[dict[str, Any]] = None
    offers: list[dict[str, Any]] = Field(default_factory=list)
    withdraw_result: Optional[dict[str, Any]] = None


@app.get("/api/llm/status")
def llm_status() -> dict[str, Any]:
    """Status da LLM compartilhada Iron Red Team (Maverick OpenRouter)."""
    return load_iron_llm_config().status()


@app.get("/api/llm/ping")
def llm_ping() -> dict[str, Any]:
    """Smoke connectivity contra o modelo selecionado (OpenRouter)."""
    result = IronLLMClient().ping()
    activity.add(
        "llm.ping",
        f"LLM ping ok={result.get('ok')} model={result.get('chat_model')}",
        level="success" if result.get("ok") else "error",
        meta={"ok": result.get("ok"), "source": result.get("source")},
    )
    return result


class LlmModelSelect(BaseModel):
    model: str


@app.post("/api/llm/model")
def llm_set_model(body: LlmModelSelect) -> dict[str, Any]:
    """Seleciona o modelo OpenRouter usado pelo BetBonus (DeepSeek ou Dolphin Venice)."""
    try:
        cfg = set_iron_llm_model(body.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    activity.add(
        "llm.model",
        f"LLM model={cfg.chat_model}",
        level="info",
        meta={"model": cfg.chat_model, "name": cfg.status().get("name")},
    )
    return cfg.status()


@app.post("/api/abuse/llm/analyze")
def abuse_llm_analyze(body: AbuseLLMRequest) -> dict[str, Any]:
    """
    Usa a LLM do Maverick (OpenRouter/DeepSeek) para extrair RulesCanon
    e sugerir vetores de abuso a partir das T&Cs da campanha.
    """
    cfg = load_iron_llm_config()
    if not cfg.configured:
        raise HTTPException(
            status_code=503,
            detail="LLM não configurada — verifique OPENROUTER_API_KEY no .env do Maverick",
        )

    offers: list[BonusOffer] = list(body.offers)
    if body.offer_ids:
        stored = {o.id: o for o in pipeline.store.load()}
        for oid in body.offer_ids:
            if oid in stored:
                offers.append(stored[oid])
    if body.text.strip():
        fields = nlp.analyze(body.text)
        offers.insert(
            0,
            BonusOffer(
                platform=body.platform,
                bonus_type=fields.bonus_type,
                title=body.title or body.text[:80],
                amount=fields.amount,
                currency=fields.currency,
                match_percent=fields.match_percent,
                free_spins=fields.free_spins,
                wagering_multiple=fields.wagering_multiple,
                min_deposit=fields.min_deposit,
                max_bet_during_bonus=fields.max_bet_during_bonus,
                expiry_days=fields.expiry_days,
                expiry_hours=fields.expiry_hours,
                game_restrictions=fields.game_restrictions,
                raw_text=body.text,
            ),
        )
    if not offers:
        # fallback: top stored offers
        offers = sorted(pipeline.store.load(), key=lambda o: o.score, reverse=True)[: body.limit]

    offers = offers[: body.limit]
    assist = AbuseLLMAssist()
    results = []
    errors = []
    for offer in offers:
        try:
            results.append(assist.analyze_offer(offer))
        except Exception as exc:  # noqa: BLE001
            errors.append({"offer_id": offer.id, "title": offer.title, "error": str(exc)[:300]})

    usable: list[dict[str, Any]] = []
    for item in results:
        llm = item.get("llm") or {}
        if llm_json_ok(llm, require_vectors=True):
            usable.append(item)
            continue
        reason = llm.get("reason") or "JSON truncado/inválido (parse_error)"
        errors.append(
            {
                "offer_id": item.get("offer_id"),
                "title": item.get("title"),
                "error": str(reason)[:300],
                "truncated": bool(item.get("truncated")),
            }
        )

    # Persist high-signal LLM vectors as findings (defensive catalog)
    for item in usable:
        llm = item.get("llm") or {}
        for vector in llm.get("abuse_vectors") or []:
            if not isinstance(vector, dict):
                continue
            sev_raw = str(vector.get("severity") or "medium").lower()
            from src.models.abuse import AbuseSeverity, ConversionStatus

            try:
                severity = AbuseSeverity(sev_raw)
            except ValueError:
                severity = AbuseSeverity.MEDIUM
            abuse_findings.add(
                AbuseFinding(
                    platform=item.get("platform") or body.platform,
                    vector=str(vector.get("id") or "llm_vector"),
                    severity=severity,
                    title=str(vector.get("title") or "Vetor LLM")[:160],
                    status=ConversionStatus.UNKNOWN,
                    abuse_score=float(item.get("abuse_score_heuristic") or 0),
                    offer_id=str(item.get("offer_id") or ""),
                    evidence={
                        "source": "llm",
                        "model": item.get("model"),
                        "rationale": vector.get("rationale"),
                        "test_idea": vector.get("test_idea"),
                        "rules": llm.get("rules"),
                        "summary": llm.get("summary"),
                    },
                )
            )

    activity.add(
        "abuse.llm.analyze",
        f"LLM analisou {len(usable)}/{len(results)} offers ({len(errors)} erros)",
        level="success" if usable and not errors else ("warn" if usable else "error"),
        meta={"count": len(usable), "errors": len(errors), "model": cfg.chat_model},
    )
    return {
        "ok": bool(usable),
        "model": cfg.chat_model,
        "source": cfg.source,
        "count": len(usable),
        "items": results,
        "errors": errors,
    }


@app.post("/api/abuse/llm/deep-attack")
def abuse_llm_deep_attack(body: AbuseLLMDeepRequest) -> dict[str, Any]:
    """
    Tentativa ofensiva reforçada sobre UMA promo selecionada.
    Usa mais tokens/contexto (deep attack) para expandir vetores e runbook.
    """
    cfg = load_iron_llm_config()
    if not cfg.configured:
        raise HTTPException(
            status_code=503,
            detail="LLM não configurada — verifique OPENROUTER_API_KEY no .env do Maverick",
        )

    offer: Optional[BonusOffer] = body.offer
    if offer is None and body.offer_id:
        stored = {o.id: o for o in pipeline.store.load()}
        offer = stored.get(body.offer_id)
    if offer is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Informe offer (objeto) ou offer_id de um alvo já discoverado "
                "([promo] / [promocode] / [conta])"
            ),
        )

    # PAGOL: injeta regras live do bônus ACTIVE (rollover/maxBet/maxConvert/gameTypes)
    # para o deep attack não depender só de texto scrapeado de promocode afiliado.
    plat = _normalize_platform(body.platform or offer.platform)
    if plat == "pagol_bet_br":
        try:
            bonus_state = _house_call(lambda: _pagol_scraper().get_bonus_conversion_state())
            primary = bonus_state.get("primary") if isinstance(bonus_state, dict) else None
            if isinstance(primary, dict) and primary:
                live_block = (
                    "\n\n--- LIVE BONUS STATE (API) ---\n"
                    + json.dumps(primary, ensure_ascii=False, indent=2, default=str)
                    + "\n--- STRATEGY ---\n"
                    + json.dumps(
                        bonus_state.get("strategy") or {},
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    )
                )
                offer = offer.model_copy(
                    update={
                        "raw_text": ((offer.raw_text or "") + live_block)[:12000],
                        "amount": float(
                            primary.get("balance_brl")
                            or offer.amount
                            or 0
                        ),
                        "max_bet_during_bonus": primary.get("max_bet_brl")
                        or offer.max_bet_during_bonus,
                        "game_restrictions": list(primary.get("bonus_game_types") or [])
                        or list(offer.game_restrictions or []),
                        "wagering_multiple": float(
                            primary.get("wagering_multiple_est")
                            or offer.wagering_multiple
                            or 0
                        )
                        or offer.wagering_multiple,
                    }
                )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            activity.add(
                "abuse.llm.deep_attack.live_bonus_skip",
                f"Live bonus state indisponível: {exc}",
                level="warn",
            )

    assist = AbuseLLMAssist()
    try:
        result = assist.analyze_offer_deep(
            offer,
            prior_summary=body.prior_summary,
            prior_vectors=body.prior_vectors,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Deep attack LLM falhou: {exc}") from exc

    llm = result.get("llm") or {}
    ok = llm_json_ok(llm, require_vectors=True)
    if ok:
        for vector in llm.get("abuse_vectors") or []:
            if not isinstance(vector, dict):
                continue
            sev_raw = str(vector.get("severity") or "medium").lower()
            try:
                severity = AbuseSeverity(sev_raw)
            except ValueError:
                severity = AbuseSeverity.MEDIUM
            abuse_findings.add(
                AbuseFinding(
                    platform=result.get("platform") or body.platform,
                    vector=str(vector.get("id") or "llm_deep_vector"),
                    severity=severity,
                    title=f"[deep] {str(vector.get('title') or 'Vetor')[:150]}",
                    status=ConversionStatus.UNKNOWN,
                    abuse_score=float(result.get("abuse_score_heuristic") or 0),
                    offer_id=str(result.get("offer_id") or ""),
                    evidence={
                        "source": "llm_deep_attack",
                        "model": result.get("model"),
                        "exploitability": vector.get("exploitability"),
                        "rationale": vector.get("rationale"),
                        "steps": vector.get("steps"),
                        "kill_control": vector.get("kill_control"),
                        "remediation": vector.get("remediation"),
                        "summary": llm.get("summary"),
                        "primary_kill_chain": llm.get("primary_kill_chain"),
                        "protection_plan": llm.get("protection_plan")
                        or llm.get("protection_backlog"),
                    },
                )
            )

    activity.add(
        "abuse.llm.deep_attack",
        f"Deep attack · {offer.title[:80]}",
        level="success" if ok else "warn",
        meta={
            "offer_id": offer.id,
            "model": cfg.chat_model,
            "vectors": len(llm.get("abuse_vectors") or []),
            "parse_error": not ok,
            "truncated": bool(result.get("truncated")),
        },
    )
    return {
        "ok": ok,
        "model": cfg.chat_model,
        "source": cfg.source,
        "item": result,
        "error": None
        if ok
        else str(llm.get("reason") or llm.get("summary") or "JSON truncado/inválido")[:300],
    }


@app.post("/api/journey/sessions/{session_id}/report.md")
def journey_session_report_md(session_id: str, body: JourneyReportRequest) -> Response:
    """Gera e devolve .md completo do teste (timeline + resultados da UI)."""
    session = journey_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    markdown = build_journey_markdown(
        session,
        extras={
            "summary": body.summary,
            "conversion": body.conversion,
            "abuse_items": body.abuse_items,
            "game_bonus_risk": body.game_bonus_risk,
            "llm_report": body.llm_report,
            "llm_vectors": body.llm_vectors,
            "deep_attack": body.deep_attack,
            "offers": body.offers,
            "withdraw_result": body.withdraw_result,
        },
    )
    fname = f"betbonus-journey-{session_id[:8]}.md"
    activity.add(
        "journey.report.md",
        f"Relatório MD gerado · sessão {session_id[:8]}",
        level="success",
        meta={"session_id": session_id, "bytes": len(markdown.encode('utf-8'))},
    )
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.get("/api/journey/sessions/{session_id}/report.md")
def journey_session_report_md_get(session_id: str) -> PlainTextResponse:
    """Download rápido só com timeline da sessão (sem extras da UI)."""
    session = journey_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    markdown = build_journey_markdown(session)
    fname = f"betbonus-journey-{session_id[:8]}.md"
    return PlainTextResponse(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


class TargetGameBody(BaseModel):
    game_id: str | int
    name: str = ""
    provider: str = ""
    house: str = ""
    slug: str = ""
    aggregator: str = ""
    category: str = ""
    category_hint: str = ""


class IntegrityRunRequest(BaseModel):
    houses: list[str] = Field(default_factory=lambda: ["pagol_bet_br", "4play_bet_br", "4play"])
    axes: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    run_mode: str = "PROBE"
    confirm_real_bet: bool = False
    persist: bool = True
    plan: bool = True
    require_auth: bool = True
    target_game: Optional[TargetGameBody] = None


class IntegrityPlanRequest(BaseModel):
    run_id: str = ""
    use_llm: bool = True


@app.get("/api/integrity/games")
def integrity_games(
    house: str = Query(..., description="pagol_bet_br | 4play_bet_br | 4play"),
    q: str = Query(default="", max_length=80),
    limit: int = Query(default=120, ge=1, le=250),
) -> dict[str, Any]:
    """Catálogo autenticado para o modal de sessão de jogo."""
    plat = _normalize_platform(house)
    if plat not in {"pagol_bet_br", "4play_bet_br", "4play"}:
        raise HTTPException(status_code=400, detail="Casa inválida")
    try:
        adapter = _integrity_house(plat)
        games = adapter.list_catalog(query=q, limit=limit)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except UnsupportedCapability as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)[:300]) from exc
    if plat == "4play_bet_br" and isinstance(adapter, FourPlayBrHouse):
        _persist_fourplay_br_tokens(adapter.scraper)
    notes = {
        "pagol_bet_br": "Launch no PROBE não aposta. Digite ≥3 letras para filtrar (PAGOL).",
        "4play": "Catálogo GET /casino/games. Busca por nome (≥2 letras: olympus, aviator, jetx). Launch de iframe ainda não mapeado nesta stack.",
        "4play_bet_br": "SoftBet: IDs de wagering. Sem nome de título nesta API.",
    }
    return {
        "ok": True,
        "house": plat,
        "query": q,
        "count": len(games),
        "games": games,
        "note": notes.get(plat, "Catálogo da casa."),
    }


def _integrity_report_filename(payload: dict[str, Any]) -> str:
    target = payload.get("target_game") if isinstance(payload.get("target_game"), dict) else {}
    slug = str(target.get("name") or target.get("game_id") or payload.get("id") or "run")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in slug)[:40]
    return f"casino-integrity-{safe}-{str(payload.get('id') or '')[:8]}.md"


def _latest_reports_payload() -> dict[str, Any]:
    latest_run = integrity_runs.latest()
    integrity_md = build_integrity_markdown(latest_run) if latest_run else ""
    promo_path = DATA_DIR / "reports" / "pagol-auto-journey-latest.md"
    promo_md = promo_path.read_text(encoding="utf-8") if promo_path.is_file() else ""
    return {
        "ok": True,
        "integrity": {
            "available": bool(integrity_md),
            "markdown": integrity_md,
            "filename": _integrity_report_filename(latest_run) if latest_run else "casino-integrity-latest.md",
            "run_id": (latest_run or {}).get("id"),
            "label": "Jornada de teste / Matriz",
            "missing": "Nenhum run DRY/PROBE persistido. Execute a Jornada de teste.",
        },
        "promo": {
            "available": bool(promo_md.strip()),
            "markdown": promo_md,
            "filename": "betbonus-auto-journey-latest.md",
            "run_id": None,
            "label": "Jornada promo",
            "missing": "Nenhuma jornada promo persistida. Execute EXECUTAR em Jornada promo.",
        },
    }


@app.get("/api/reports/latest")
def latest_reports() -> dict[str, Any]:
    """Último .md da Jornada de teste/Matriz e da Jornada promo, juntos."""
    return _latest_reports_payload()


@app.get("/api/integrity/runs/{run_id}/report.md")
def integrity_run_report(run_id: str) -> Response:
    payload = integrity_runs.latest() if run_id == "latest" else integrity_runs.get(run_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Run não encontrado")
    markdown = build_integrity_markdown(payload)
    fname = _integrity_report_filename(payload)
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.get("/api/integrity/catalog")
def integrity_catalog() -> dict[str, Any]:
    data = empty_matrix()
    latest = integrity_runs.latest()
    if latest:
        data["latest_run_id"] = latest.get("id")
        data["coverage"] = latest.get("coverage") or data["coverage"]
        data["finished_at"] = latest.get("finished_at")
        data["run_mode"] = latest.get("run_mode")
        data["results"] = latest.get("results") or []
        data["planner"] = latest.get("planner") or {}
        data["notes"] = latest.get("notes") or []
    return data


@app.get("/api/integrity/latest")
def integrity_latest() -> dict[str, Any]:
    latest = integrity_runs.latest()
    if not latest:
        return {"ok": False, "run": None, "catalog": empty_matrix()}
    return {"ok": True, "run": latest}


@app.get("/api/integrity/runs")
def integrity_runs_list(limit: int = Query(default=20, ge=1, le=50)) -> dict[str, Any]:
    return {"ok": True, "runs": integrity_runs.summaries(limit=limit)}


@app.get("/api/ops/status")
def ops_status() -> dict[str, Any]:
    """Painel de operação: sessões das 3 casas + LLM + última cobertura."""
    creds = {c["platform"]: c for c in pipeline.credentials.list()}
    houses = []
    for hid, label in (
        ("pagol_bet_br", "pagol.bet.br"),
        ("4play_bet_br", "4play.bet.br"),
        ("4play", "4play.game"),
    ):
        row = creds.get(hid) or creds.get("pagol" if hid == "pagol_bet_br" else hid) or {}
        has_token = bool(row.get("has_token"))
        session_ok, session_note = _house_session_health(hid, has_token=has_token)
        houses.append(
            {
                "id": hid,
                "label": label,
                "has_token": has_token,
                "has_refresh_token": bool(row.get("has_refresh_token")),
                "session_ok": session_ok,
                "session_note": session_note,
                "email": row.get("email") or "",
                "updated_at": row.get("updated_at") or "",
            }
        )
    cat = load_catalog()
    latest = integrity_runs.latest()
    cov = (latest or {}).get("coverage") if latest else empty_matrix()["coverage"]
    return {
        "ok": True,
        "product": "casino_online",
        "health": {
            "status": "ok",
            "service": "BetBonus AI",
            "mode": "casino-integrity",
        },
        "houses": houses,
        "llm": load_iron_llm_config().status(),
        "safety": {
            "default_mode": cat.safety.default_mode,
            "max_lab_stake_brl": cat.safety.max_lab_stake_brl,
            "kill_switch": cat.safety.kill_switch,
        },
        "latest_run": integrity_runs.summaries(limit=1)[0] if latest else None,
        "coverage": cov,
        "axes": cat.axes,
        "scenario_count": len(cat.scenarios),
    }


@app.get("/api/integrity/sims")
def integrity_sims() -> dict[str, Any]:
    return {"ok": True, "product": "casino_online", "offline": True, "suite": table_suite()}


@app.post("/api/integrity/run")
def integrity_run(body: IntegrityRunRequest) -> dict[str, Any]:
    houses = [_normalize_platform(h) for h in (body.houses or [])]
    houses = [h for h in houses if h in {"pagol_bet_br", "4play_bet_br", "4play"}]
    if not houses:
        houses = ["pagol_bet_br", "4play_bet_br", "4play"]
    target = body.target_game.model_dump() if body.target_game else None
    if target:
        target["house"] = _normalize_platform(str(target.get("house") or houses[0]))
        houses = [target["house"]]
    runner = IntegrityRunner(_integrity_house)
    run = runner.run(
        houses=houses,
        axes=body.axes or None,
        scenario_ids=body.scenario_ids or None,
        run_mode=body.run_mode,
        confirm_real_bet=body.confirm_real_bet,
        confirm_real_withdraw=False,
        require_auth=body.require_auth if body.run_mode != "DRY" else False,
        target_game=target,
    )
    if body.plan:
        try:
            run.planner = IntegrityPlanner(catalog=runner.catalog).plan(run, use_llm=True)
        except Exception as exc:  # noqa: BLE001
            run.planner = {"error": str(exc)[:240], "source": "planner_error"}
    payload = run.to_dict()
    if body.persist:
        integrity_runs.add(payload)
        for row in run.results:
            if row.severity not in {"high", "critical"}:
                continue
            if row.mode in {"DRY", "SKIPPED"}:
                continue
            try:
                sev = AbuseSeverity(row.severity)
            except ValueError:
                sev = AbuseSeverity.HIGH
            abuse_findings.add(
                AbuseFinding(
                    tool="casino-integrity",
                    platform=row.platform,
                    vector=f"integrity.{row.axis}.{row.scenario_id}",
                    severity=sev,
                    title=row.title[:160],
                    evidence={
                        "mode": row.mode,
                        "vulnerability": row.vulnerability,
                        "note": row.note,
                        "run_id": run.id,
                        "evidence": row.evidence,
                    },
                )
            )
    activity.add(
        "integrity.run",
        f"Casino integrity {run.run_mode}: {len(run.results)} cenários · "
        f"auto={run.coverage.get('mode_counts', {}).get('AUTOMATED', 0)}",
        level="success",
        meta={"run_id": run.id, "houses": houses, "mode": run.run_mode, "kind": run.kind},
    )
    payload["report_markdown"] = build_integrity_markdown(payload)
    slug = str((payload.get("target_game") or {}).get("name") or payload["id"])[:32]
    payload["report_filename"] = f"casino-integrity-{slug}-{payload['id'][:8]}.md"
    return payload


@app.post("/api/integrity/plan")
def integrity_plan(body: IntegrityPlanRequest) -> dict[str, Any]:
    cat = load_catalog()
    run_payload = integrity_runs.get(body.run_id) if body.run_id else integrity_runs.latest()
    run_obj = None
    if run_payload:
        from src.integrity.models import IntegrityRun, ScenarioResult

        run_obj = IntegrityRun(
            id=str(run_payload.get("id") or ""),
            started_at=str(run_payload.get("started_at") or ""),
            finished_at=str(run_payload.get("finished_at") or ""),
            run_mode=str(run_payload.get("run_mode") or "PROBE"),
            houses=list(run_payload.get("houses") or []),
            axes=list(run_payload.get("axes") or []),
            coverage=dict(run_payload.get("coverage") or {}),
            results=[
                ScenarioResult(
                    id=str(r.get("id") or ""),
                    scenario_id=str(r.get("scenario_id") or ""),
                    axis=str(r.get("axis") or ""),
                    platform=str(r.get("platform") or ""),
                    title=str(r.get("title") or ""),
                    mode=str(r.get("mode") or ""),
                    ok=bool(r.get("ok")),
                    severity=str(r.get("severity") or "info"),
                    vulnerability=str(r.get("vulnerability") or ""),
                    note=str(r.get("note") or ""),
                    evidence=dict(r.get("evidence") or {}),
                )
                for r in (run_payload.get("results") or [])
                if isinstance(r, dict)
            ],
        )
    plan = IntegrityPlanner(catalog=cat).plan(run_obj, use_llm=body.use_llm)
    return {"ok": True, "plan": plan}


# Serve built dashboard (production) and SPA fallback
if DASHBOARD_DIST.exists():
    assets = DASHBOARD_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    def dashboard_index() -> FileResponse:
        return FileResponse(DASHBOARD_DIST / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="API route not found")
        candidate = DASHBOARD_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DASHBOARD_DIST / "index.html")
else:

    @app.get("/")
    def dashboard_missing() -> dict[str, str]:
        return {
            "status": "api_only",
            "message": "Dashboard not built. Run: cd dashboard && npm install && npm run build",
            "docs": "/api/docs",
        }
