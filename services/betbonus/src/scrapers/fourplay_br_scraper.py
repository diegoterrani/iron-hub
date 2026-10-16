from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

from src.models.abuse import WalletSnapshot
from src.models.bonus import BonusOffer, BonusType, ScrapeResult
from src.nlp.analyzer import BonusNLPAnalyzer
from src.scrapers.base import BaseScraper

API_BASE = "https://4play-api.4play.bet.br"
SITE = "https://4play.bet.br"


def classify_softbet_jwt(token: str) -> str:
    """
    Retorna: access | session | refresh | unknown

    SoftBet 4play.bet.br grava no localStorage:
      - token: Bearer — pode ser SB2 (PersonId) OU sessão (iss=4play + sessionToken)
      - refreshToken: JWT para /api/client/refresh-token (às vezes com original_token)
    """
    claims = FourPlayBrScraper.decode_jwt_claims(token)
    if not claims:
        return "unknown"
    if claims.get("PersonId") or claims.get("Integration") or claims.get("BrandId"):
        return "access"
    # Bearer de sessão SoftBet (login grava sessionToken em localStorage.token)
    if claims.get("sessionToken") and claims.get("clientId"):
        return "session"
    if claims.get("original_token") or claims.get("sessionToken"):
        return "refresh"
    if claims.get("clientId") and claims.get("iss") in {"4play", "SB2"}:
        return "session"
    return "unknown"


def is_softbet_bearer(token: str) -> bool:
    return classify_softbet_jwt(token) in {"access", "session"}


def describe_softbet_jwt(token: str) -> str:
    """Resumo seguro para mensagens de erro (sem vazar o JWT)."""
    raw = (token or "").strip()
    if not raw:
        return "vazio"
    claims = FourPlayBrScraper.decode_jwt_claims(raw)
    if not claims:
        return f"não-JWT (len={len(raw)})"
    kind = classify_softbet_jwt(raw)
    iss = claims.get("iss")
    keys = ",".join(sorted(claims.keys())[:8])
    return f"kind={kind} iss={iss!r} len={len(raw)} keys=[{keys}]"


def normalize_softbet_token_pair(
    token: str,
    refresh_token: str = "",
) -> tuple[str, str, list[str]]:
    """
    Corrige troca de campos.
    Retorna (bearer, refresh, warnings).
    """
    warnings: list[str] = []
    bearer = (token or "").strip()
    refresh = (refresh_token or "").strip()
    kind_a = classify_softbet_jwt(bearer) if bearer else "unknown"
    kind_r = classify_softbet_jwt(refresh) if refresh else "unknown"

    # refresh/access invertidos (SB2 no campo refresh)
    if kind_a == "refresh" and kind_r in {"access", "session"}:
        bearer, refresh = refresh, bearer
        kind_a, kind_r = kind_r, kind_a
        warnings.append("Campos token/refreshToken estavam invertidos — corrigido automaticamente.")

    if bearer and not is_softbet_bearer(bearer):
        warnings.append(
            f"token classificado como {kind_a} (esperado: session SoftBet ou access SB2)."
        )

    if not bearer and refresh:
        warnings.append(
            "Só há refreshToken. Copie também a chave Local Storage `token`."
        )
    if bearer and not refresh:
        warnings.append(
            "Sem refreshToken — a sessão SoftBet cai rápido. Copie também `refreshToken`."
        )
    return bearer, refresh, warnings


class FourPlayBrScraper(BaseScraper):
    """
    4PLAY.BET.BR adapter (SoftBet / SB2 stack — NÃO é a API do 4play.game LATAM).

    Auth:
      localStorage.token + localStorage.refreshToken
      POST /api/client/refresh-token {refreshToken}
      GET  /api/account/balance
    """

    platform = "4play_bet_br"
    default_delay = 0.25

    def __init__(
        self,
        delay: Optional[float] = None,
        session: Optional[requests.Session] = None,
        token: str = "",
        refresh_token: str = "",
    ):
        super().__init__(delay=delay, session=session)
        self.token = token.strip()
        self.refresh_token = refresh_token.strip()
        self.nlp = BonusNLPAnalyzer()
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Origin": SITE,
                "Referer": f"{SITE}/",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            }
        )
        self._apply_auth_header()

    def set_token(self, token: str, refresh_token: str = "") -> None:
        self.token = token.strip()
        if refresh_token:
            self.refresh_token = refresh_token.strip()
        self._apply_auth_header()

    def set_refresh_token(self, refresh_token: str) -> None:
        self.refresh_token = refresh_token.strip()

    @classmethod
    def login(cls, email: str, password: str, *, session: Optional[requests.Session] = None) -> dict[str, str]:
        """
        Auto-login no SoftBet 4play.bet.br → POST /api/client/login.

        Retorna {"token": ..., "refresh_token": ...} (refresh pode ser "").
        Payload: JSON {email, password} (mesma convenção do register endpoint).
        """
        scraper = cls(delay=0, session=session)
        response = scraper.session.post(
            f"{API_BASE}/api/client/login",
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=25,
        )
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"login 4play.bet.br: HTTP {response.status_code} body={response.text[:200]}"
            ) from exc
        if response.status_code >= 400:
            raise PermissionError(
                f"login 4play.bet.br HTTP {response.status_code}: "
                f"{payload.get('title') or payload.get('message') or payload}"
            )
        # SoftBet devolve token/refreshToken no top-level ou em data/ResponseObject
        obj = payload
        if isinstance(payload.get("data"), dict):
            obj = payload["data"]
        elif isinstance(payload.get("ResponseObject"), dict):
            obj = payload["ResponseObject"]
        token = str(obj.get("token") or obj.get("accessToken") or obj.get("Token") or "")
        refresh = str(obj.get("refreshToken") or obj.get("RefreshToken") or "")
        if not token:
            raise RuntimeError(f"login 4play.bet.br sem token na resposta: {payload}")
        return {"token": token, "refresh_token": refresh}

    def _apply_auth_header(self) -> None:
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
        else:
            self.session.headers.pop("Authorization", None)

    @staticmethod
    def decode_jwt_claims(token: str) -> dict[str, Any]:
        parts = (token or "").split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        try:
            return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        except Exception:  # noqa: BLE001
            return {}

    def token_expiry(self) -> Optional[datetime]:
        exp = self.decode_jwt_claims(self.token).get("exp")
        if not exp:
            return None
        try:
            return datetime.fromtimestamp(int(exp), timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    def token_expired(self, skew_seconds: int = 30) -> bool:
        exp = self.token_expiry()
        if exp is None:
            return False
        return datetime.now(timezone.utc).timestamp() >= (exp.timestamp() - skew_seconds)

    def refresh_access_token(self) -> dict[str, str]:
        if not self.refresh_token:
            raise PermissionError(
                "Token 4play.bet.br expirado e sem refreshToken — "
                "cole token + refreshToken do localStorage do site"
            )
        if self.delay > 0:
            time.sleep(self.delay)
        response = self.session.post(
            f"{API_BASE}/api/client/refresh-token",
            json={"refreshToken": self.refresh_token},
            headers={"Content-Type": "application/json"},
            timeout=25,
        )
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"refresh-token: HTTP {response.status_code} body={response.text[:200]}"
            ) from exc
        if response.status_code >= 400:
            raise PermissionError(
                f"refreshToken inválido/expirado (HTTP {response.status_code}): "
                f"{payload.get('title') or payload.get('message') or payload}"
            )
        new_token = str(payload.get("token") or payload.get("accessToken") or "")
        new_refresh = str(payload.get("refreshToken") or self.refresh_token)
        if not new_token:
            raise RuntimeError(f"refresh-token sem token na resposta: {payload}")
        self.set_token(new_token, new_refresh)
        return {"token": new_token, "refresh_token": new_refresh}

    def ensure_fresh_token(self) -> Optional[dict[str, str]]:
        """Refresh se JWT expirado. Retorna novos tokens se renovou."""
        if not self.token:
            raise PermissionError("Sem token 4play.bet.br")
        if self.token_expired():
            return self.refresh_access_token()
        return None

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        self.ensure_fresh_token()
        if self.delay > 0:
            time.sleep(self.delay)
        url = f"{API_BASE}{path}"
        response = self.session.request(method, url, timeout=25, **kwargs)
        # SoftBet: errorCode 999 → refresh. 401 com body vazio costuma ser bloqueio de IP do DC.
        if response.status_code in (401, 400) and self.refresh_token:
            try:
                err = response.json() if response.content else {}
            except Exception:  # noqa: BLE001
                err = {}
            code = err.get("errorCode") if isinstance(err, dict) else None
            empty_401 = response.status_code == 401 and not response.content
            if empty_401 and not self.token_expired():
                raise PermissionError(
                    "API SoftBet retornou 401 vazio com JWT ainda válido — "
                    "provável bloqueio de IP do servidor BetBonus (não do seu token)"
                )
            if response.status_code == 401 or code == 999:
                self.refresh_access_token()
                response = self.session.request(method, url, timeout=25, **kwargs)
        if response.status_code == 401:
            raise PermissionError(
                "Unauthorized 4play.bet.br — token/refresh inválidos, expirados ou IP bloqueado"
            )
        if response.status_code == 204 or not response.content:
            return None
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Invalid JSON from {path}: HTTP {response.status_code} body={response.text[:200]}"
            ) from exc
        if response.status_code >= 400:
            raise RuntimeError(
                f"HTTP {response.status_code} on {path}: "
                f"{json.dumps(payload, ensure_ascii=False)[:400]}"
            )
        return payload

    def assert_softbet_claims(self) -> dict[str, Any]:
        """Valida estrutura JWT SoftBet sem chamar a API (útil quando o DC bloqueia IP)."""
        if not self.token:
            raise PermissionError("Sem token 4play.bet.br")
        claims = self.decode_jwt_claims(self.token)
        if not claims:
            raise PermissionError("Token 4play.bet.br não é um JWT válido")
        iss = str(claims.get("iss") or "")
        integration = str(claims.get("Integration") or "")
        kind = classify_softbet_jwt(self.token)
        # Aceita SB2 (PersonId) ou sessão SoftBet (iss=4play + sessionToken/clientId)
        ok = (
            kind in {"access", "session"}
            or iss == "SB2"
            or iss == "4play"
            or "4play" in integration.lower()
        )
        if not ok:
            raise PermissionError(
                f"JWT não parece SoftBet 4play.bet.br "
                f"(kind={kind}, iss={iss!r}, Integration={integration!r})"
            )
        if self.token_expired():
            if self.refresh_token:
                # tenta renovar; se API bloquear IP, ainda avisamos
                try:
                    self.refresh_access_token()
                    claims = self.decode_jwt_claims(self.token)
                except Exception as exc:  # noqa: BLE001
                    raise PermissionError(
                        "JWT expirado e refresh falhou (API SoftBet pode bloquear IP do servidor). "
                        f"Gere tokens novos logado no site. Detalhe: {exc}"
                    ) from exc
            else:
                raise PermissionError(
                    "JWT expirado e sem refreshToken — no site: "
                    "DevTools → Application → Local Storage → token + refreshToken"
                )
        if not self.refresh_token:
            # SoftBet access JWT é curto; sem refresh a sessão cai em minutos
            pass
        return claims

    def validate_token(self) -> dict[str, Any]:
        if not self.token and not self.refresh_token:
            raise PermissionError("Sem token 4play.bet.br")
        claims = self.assert_softbet_claims()
        live_error = ""
        wallet: dict[str, Any] = {}
        mode = "live"
        try:
            renewed = self.ensure_fresh_token()
            data = self._request("GET", "/api/account/balance")
            wallet = _parse_balance(data)
            username = (
                claims.get("UserName")
                or claims.get("clientId")
                or claims.get("PersonId")
                or claims.get("LoginId")
            )
            return {
                "platform": self.platform,
                "mode": mode,
                "token_kind": classify_softbet_jwt(self.token),
                "person_id": claims.get("PersonId") or claims.get("clientId"),
                "login_id": claims.get("LoginId"),
                "username": username,
                "currency": claims.get("CurrencyCode") or wallet.get("currency") or "BRL",
                "brand_id": claims.get("BrandId"),
                "integration": claims.get("Integration") or claims.get("iss"),
                "client_ip_claim": claims.get("ClientIP"),
                "balance": wallet.get("balance"),
                "bonus_balance": wallet.get("bonus"),
                "token_exp": self.token_expiry().isoformat() if self.token_expiry() else None,
                "renewed": bool(renewed),
                "has_refresh_token": bool(self.refresh_token),
                "raw_balance_keys": list(data.keys()) if isinstance(data, dict) else [],
            }
        except Exception as exc:  # noqa: BLE001
            live_error = str(exc)
            mode = "claims_trusted"
            username = (
                claims.get("UserName")
                or claims.get("clientId")
                or claims.get("PersonId")
                or claims.get("LoginId")
            )
            # API SoftBet frequentemente devolve 401 vazio a partir de IP de datacenter
            # mesmo com JWT válido emitido para o IP do browser do operador.
            return {
                "platform": self.platform,
                "mode": mode,
                "ok_claims": True,
                "token_kind": classify_softbet_jwt(self.token),
                "person_id": claims.get("PersonId") or claims.get("clientId"),
                "login_id": claims.get("LoginId"),
                "username": username,
                "currency": claims.get("CurrencyCode") or "BRL",
                "brand_id": claims.get("BrandId"),
                "integration": claims.get("Integration") or claims.get("iss"),
                "client_ip_claim": claims.get("ClientIP"),
                "balance": None,
                "bonus_balance": None,
                "token_exp": self.token_expiry().isoformat() if self.token_expiry() else None,
                "renewed": False,
                "has_refresh_token": bool(self.refresh_token),
                "warning": (
                    "JWT SoftBet aceito (claims), mas a API /account/balance bloqueou o IP "
                    "do servidor BetBonus. Auth da jornada segue; wallet live fica limitada. "
                    f"Detalhe API: {live_error}"
                ),
                "live_error": live_error,
            }

    def get_wallet_snapshot(self) -> WalletSnapshot:
        claims = self.assert_softbet_claims()
        try:
            data = self._request("GET", "/api/account/balance")
            parsed = _parse_balance(data)
            return WalletSnapshot(
                platform=self.platform,
                balance=float(parsed.get("balance") or 0),
                bonus=float(parsed.get("bonus") or 0),
                rollover=float(parsed.get("rollover") or 0),
                raw=data if isinstance(data, dict) else {"raw": data},
            )
        except Exception as exc:  # noqa: BLE001
            # Não derruba a jornada: snapshot claims-only
            return WalletSnapshot(
                platform=self.platform,
                balance=0.0,
                bonus=0.0,
                rollover=0.0,
                raw={
                    "mode": "claims_trusted",
                    "person_id": claims.get("PersonId"),
                    "username": claims.get("UserName"),
                    "currency": claims.get("CurrencyCode") or "BRL",
                    "client_ip_claim": claims.get("ClientIP"),
                    "live_error": str(exc),
                    "note": (
                        "Saldo live indisponível do IP do servidor. "
                        "Use scout URL/HTML + abuse score; wallet real só no browser."
                    ),
                },
            )

    def list_wagering_game_ids(self) -> list[Any]:
        data = self._request("GET", "/api/games/wagering-game-ids")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("ids", "gameIds", "items", "data"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    def list_my_bonuses(self, per_page: int = 50, max_pages: int = 5) -> list[dict[str, Any]]:
        """GET /api/bonus/get-bonuses — histórico/ativos da conta SoftBet."""
        if not self.token and not self.refresh_token:
            raise PermissionError("Sem token 4play.bet.br")
        self.ensure_fresh_token()
        items: list[dict[str, Any]] = []
        page = 1
        while page <= max(1, max_pages):
            if self.delay > 0:
                time.sleep(self.delay)
            response = self.session.get(
                f"{API_BASE}/api/bonus/get-bonuses",
                params={
                    "pageCount": per_page,
                    "pageNumber": page,
                    "languageId": "pt",
                },
                timeout=25,
            )
            if response.status_code == 401 and self.refresh_token:
                self.refresh_access_token()
                response = self.session.get(
                    f"{API_BASE}/api/bonus/get-bonuses",
                    params={
                        "pageCount": per_page,
                        "pageNumber": page,
                        "languageId": "pt",
                    },
                    timeout=25,
                )
            if response.status_code >= 400:
                raise PermissionError(
                    f"get-bonuses HTTP {response.status_code}: {response.text[:200]}"
                )
            payload = response.json()
            chunk = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(chunk, list):
                break
            items.extend(x for x in chunk if isinstance(x, dict))
            total = int(payload.get("totalCount") or 0)
            if page * per_page >= total or not chunk:
                break
            page += 1
        return items

    def list_public_promotion_summaries(self) -> list[dict[str, Any]]:
        """GET /api/staticpage/getstaticpagepromotionlistbygroup (público)."""
        if self.delay > 0:
            time.sleep(self.delay)
        response = self.session.get(
            f"{API_BASE}/api/staticpage/getstaticpagepromotionlistbygroup",
            params={"languageId": "pt"},
            timeout=25,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"promotionlist HTTP {response.status_code}: {response.text[:200]}"
            )
        groups = response.json()
        out: list[dict[str, Any]] = []
        if not isinstance(groups, list):
            return out
        for group in groups:
            if not isinstance(group, dict):
                continue
            gname = str(group.get("groupName") or "")
            for promo in group.get("promotions") or []:
                if not isinstance(promo, dict):
                    continue
                item = dict(promo)
                item["_group"] = gname
                out.append(item)
        return out

    def get_public_promotion(self, slug: str) -> dict[str, Any]:
        if self.delay > 0:
            time.sleep(self.delay)
        response = self.session.get(
            f"{API_BASE}/api/staticpage/getstaticpagepromotion",
            params={"slug": slug, "languageId": "pt"},
            timeout=25,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"getstaticpagepromotion HTTP {response.status_code}: {response.text[:200]}"
            )
        data = response.json()
        return data if isinstance(data, dict) else {}

    def list_active_cashback(self) -> list[dict[str, Any]]:
        if not self.token and not self.refresh_token:
            return []
        self.ensure_fresh_token()
        if self.delay > 0:
            time.sleep(self.delay)
        response = self.session.post(
            f"{API_BASE}/api/client/activecashbackbonuses",
            json={},
            timeout=25,
        )
        if response.status_code >= 400:
            return []
        payload = response.json()
        obj = payload.get("ResponseObject") if isinstance(payload, dict) else None
        return obj if isinstance(obj, list) else []

    @staticmethod
    def _html_to_text(html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")
        return " ".join(soup.get_text(" ", strip=True).split())

    def offer_from_account_bonus(self, item: dict[str, Any]) -> BonusOffer:
        title = str(item.get("name") or item.get("description") or f"Bonus #{item.get('id')}").strip()
        status = str(item.get("statusName") or item.get("status") or "")
        amount = _first_num(
            item,
            ("remainingCredit", "initialCredit", "finalAmount", "maxAmount", "minAmount"),
        )
        wager_target = _first_num(item, ("wageringTarget", "turnoverCount", "turnoverAmountLeft"))
        steps = item.get("bonusSteps") or []
        step_names = [
            str(s.get("name") or s.get("typeName") or "")
            for s in steps
            if isinstance(s, dict)
        ]
        raw_bits = [
            title,
            f"status={status}",
            f"bonusType={item.get('bonusType')}",
            f"initialCredit={item.get('initialCredit')}",
            f"remainingCredit={item.get('remainingCredit')}",
            f"wageringTarget={item.get('wageringTarget')}",
            f"turnoverAmountLeft={item.get('turnoverAmountLeft')}",
            f"terms={item.get('termsConditions')}",
            f"steps={', '.join(step_names)}",
            str(item.get("description") or ""),
        ]
        raw = "\n".join(x for x in raw_bits if x)
        fields = self.nlp.analyze(raw)
        btype = fields.bonus_type
        if btype == BonusType.UNKNOWN:
            bt = int(item.get("bonusType") or 0)
            if bt == 14 or "giro" in title.lower() or "spin" in title.lower():
                btype = BonusType.FREE_SPINS
            elif "cashback" in title.lower():
                btype = BonusType.CASHBACK
            elif "dep" in title.lower():
                btype = BonusType.DEPOSIT_MATCH
        return BonusOffer(
            platform=self.platform,
            bonus_type=btype,
            title=f"[conta][{status or '?'}] {title}",
            amount=amount or fields.amount or 0.0,
            currency="BRL",
            wagering_multiple=(
                wager_target
                if wager_target and wager_target >= 1
                else fields.wagering_multiple
            ),
            min_deposit=float(item.get("minAmount") or fields.min_deposit or 0),
            game_restrictions=fields.game_restrictions or step_names,
            terms_url=f"{SITE}/promocoes",
            source_url=f"{API_BASE}/api/bonus/get-bonuses",
            raw_text=raw[:6000],
        )

    def offer_from_public_promo(
        self,
        summary: dict[str, Any],
        detail: Optional[dict[str, Any]] = None,
    ) -> BonusOffer:
        detail = detail or {}
        title = str(
            detail.get("titleTranslation")
            or summary.get("titleTranslation")
            or summary.get("slugTranslation")
            or f"Promo #{summary.get('id')}"
        ).strip()
        slug = str(
            detail.get("slugTranslation") or summary.get("slugTranslation") or ""
        ).strip()
        subtitle = str(
            detail.get("subtitleTranslation") or summary.get("subtitleTranslation") or ""
        )
        html = str(detail.get("descriptionTranslation") or "")
        text = self._html_to_text(html)
        group = str(summary.get("_group") or "")
        raw = "\n".join(
            x for x in [title, subtitle, f"group={group}", f"slug={slug}", text] if x
        )
        fields = self.nlp.analyze(raw)
        return BonusOffer(
            platform=self.platform,
            bonus_type=fields.bonus_type,
            title=f"[promo] {title}",
            amount=fields.amount or 0.0,
            currency=fields.currency or "BRL",
            match_percent=fields.match_percent,
            free_spins=fields.free_spins,
            wagering_multiple=fields.wagering_multiple,
            min_deposit=fields.min_deposit or 0.0,
            max_bet_during_bonus=fields.max_bet_during_bonus,
            expiry_days=fields.expiry_days or 30,
            game_restrictions=fields.game_restrictions,
            terms_url=f"{SITE}/promocoes/{slug}" if slug else f"{SITE}/promocoes",
            source_url=f"{API_BASE}/api/staticpage/getstaticpagepromotion?slug={slug}",
            raw_text=raw[:8000],
        )

    def extract_offers(self, soup: BeautifulSoup, source_url: str = "") -> list[BonusOffer]:
        # SoftBet é SPA — discovery via API, não HTML
        del soup, source_url
        return []

    def scrape_live(
        self,
        include_account: bool = True,
        include_public: bool = True,
        promo_detail_limit: int = 25,
    ) -> ScrapeResult:
        source = f"{SITE}/promocoes"
        offers: list[BonusOffer] = []
        notes: list[str] = []
        try:
            if include_account and (self.token or self.refresh_token):
                try:
                    bonuses = self.list_my_bonuses()
                    offers.extend(self.offer_from_account_bonus(b) for b in bonuses)
                    notes.append(f"account_bonuses={len(bonuses)}")
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"account_bonuses_error={exc}")
                try:
                    cashbacks = self.list_active_cashback()
                    notes.append(f"active_cashback={len(cashbacks)}")
                    for cb in cashbacks:
                        title = str(cb.get("name") or cb.get("Name") or "Cashback ativo")
                        amount = _first_num(cb, ("amount", "Amount", "available", "value"))
                        offers.append(
                            BonusOffer(
                                platform=self.platform,
                                bonus_type=BonusType.CASHBACK,
                                title=f"[conta][cashback] {title}",
                                amount=amount,
                                currency="BRL",
                                wagering_multiple=0.0,
                                terms_url=f"{SITE}/promocoes",
                                source_url=f"{API_BASE}/api/client/activecashbackbonuses",
                                raw_text=str(cb)[:4000],
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"cashback_error={exc}")
                try:
                    wallet = self.get_wallet_snapshot()
                    notes.append(f"balance={wallet.balance} bonus={wallet.bonus}")
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"wallet_error={exc}")

            if include_public:
                summaries = self.list_public_promotion_summaries()
                notes.append(f"public_promos={len(summaries)}")
                for summary in summaries[: max(0, promo_detail_limit)]:
                    slug = str(summary.get("slugTranslation") or "").strip()
                    detail: dict[str, Any] = {}
                    if slug:
                        try:
                            detail = self.get_public_promotion(slug)
                        except Exception as exc:  # noqa: BLE001
                            notes.append(f"promo_detail_error:{slug}={exc}")
                    if not summary.get("titleTranslation") and not detail.get(
                        "titleTranslation"
                    ):
                        continue
                    offers.append(self.offer_from_public_promo(summary, detail))

            return ScrapeResult(
                platform=self.platform,
                source_url=source,
                offers=offers,
                ok=True,
                error="; ".join(notes) if notes else None,
            )
        except Exception as exc:  # noqa: BLE001
            return ScrapeResult(
                platform=self.platform,
                source_url=source,
                offers=offers,
                ok=False,
                error=str(exc),
            )

    def scrape_url(self, url: str, render_js: bool = False) -> ScrapeResult:
        # Com ou sem token: promos públicas. Com token: + bônus da conta.
        # (API scraper — URL/render_js are ignored; semantics unified with base.)
        return self.scrape_live(
            include_account=bool(self.token or self.refresh_token),
            include_public=True,
        )

    AUTO_BET_MAX_CLICKS = 20

    def auto_bet(
        self,
        game_id: int | str,
        *,
        clicks: int = 1,
        use_bonus: bool = False,
        mode: str = "REAL",
        timeout_ms: int = 45000,
        game_name: str = "",
    ) -> dict[str, Any]:
        """
        Auto-bet via browser on SoftBet SPA: navigates to the game page,
        injects the auth token into localStorage, and clicks the spin/bet
        button N times in the provider iframe.

        SoftBet has no public launch API — the game URL pattern is
        {SITE}/casino/{game_id}. The browser loads the SPA which embeds
        the provider iframe.
        """
        if not self.token:
            raise PermissionError("Token necessário para auto_bet")
        clicks = max(1, min(int(clicks), self.AUTO_BET_MAX_CLICKS))
        wallet_before = self.get_wallet_snapshot()
        game_url = f"{SITE}/casino/{game_id}"
        try:
            from src.integrity.player import inspect_launch

            result = inspect_launch(
                game_url,
                click_spin=True,
                clicks=clicks,
                timeout_ms=timeout_ms,
            )
            n_clicks = int(result.get("clicks") or 0)
            method = result.get("method") or "none"
            launch_error = result.get("launch_error")
            wallet_after = self.get_wallet_snapshot()
            return {
                "ok": n_clicks > 0,
                "game_id": game_id,
                "clicks": n_clicks,
                "method": method,
                "launch_error": launch_error,
                "wallet_before": wallet_before.model_dump(mode="json"),
                "wallet_after": wallet_after.model_dump(mode="json"),
                "wallet_delta": {
                    "balance": round(
                        wallet_after.balance - wallet_before.balance, 2
                    ),
                    "bonus": round(
                        wallet_after.bonus - wallet_before.bonus, 2
                    ),
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "game_id": game_id,
                "clicks": 0,
                "error": str(exc)[:300],
            }


def _parse_balance(data: Any) -> dict[str, float | str]:
    if not isinstance(data, dict):
        return {"balance": 0.0, "bonus": 0.0, "rollover": 0.0}
    # SoftBet variants
    nested = data.get("data") if isinstance(data.get("data"), dict) else data
    balance = _first_num(
        nested,
        ("balance", "Balance", "totalBalance", "realBalance", "availableBalance", "Amount"),
    )
    bonus = _first_num(
        nested,
        ("bonusBalance", "BonusBalance", "bonus", "Bonus", "bonusAmount"),
    )
    rollover = _first_num(
        nested,
        ("rollover", "Rollover", "wageringLeft", "remainingWagering", "WageringAmount"),
    )
    currency = str(
        nested.get("currency")
        or nested.get("Currency")
        or nested.get("currencyCode")
        or "BRL"
    )
    return {
        "balance": balance,
        "bonus": bonus,
        "rollover": rollover,
        "currency": currency,
    }


def _first_num(item: dict[str, Any], keys: tuple[str, ...]) -> float:
    for key in keys:
        if key in item and item[key] is not None and item[key] != "":
            try:
                return float(item[key])
            except (TypeError, ValueError):
                continue
    return 0.0
