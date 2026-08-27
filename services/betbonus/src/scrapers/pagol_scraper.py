from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
import uuid
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

from src.models.abuse import WalletSnapshot
from src.models.bonus import BonusOffer, BonusType, ScrapeResult
from src.nlp.analyzer import BonusNLPAnalyzer
from src.scrapers.base import BaseScraper

API_BASE = "https://api.pagol.luckygaming.com.br"
AUTH_BASE = "https://auth.pagol.luckygaming.com.br"
SITE = "https://pagol.bet.br"
# Public client credentials embedded in frontend env (lucky-site)
CLIENT_BASIC = "bHVja3ktc2l0ZTo4OWVidDNJYiFxRmJpelo="
CLIENT_ID = "lucky-site"
# Frontend env.secretSalsaKey — HMAC for X-Client-Token
SECRET_SALSA_KEY = "f04f7bf2-cd5b-4b69-a4f6-088a0e619512"


class PagolScraper(BaseScraper):
    """
    PAGOL.BET.BR adapter (Lucky Gaming / Salsa stack).

    Authenticated:
      GET /user/balance.do
      GET /user/bonuses.do?status=ACTIVE|PENDING&page=&pageSize=
      GET /user/bonuses/balance.do
      GET /user/promocode/all-enabled.do
      GET /user/withdrawals/* 
    Auth login:
      POST {AUTH}/oauth/token (password / refresh_token) with Basic client
    """

    platform = "pagol_bet_br"
    default_delay = 0.25
    BONUS_STATUSES = ("ACTIVE", "PENDING")
    # API Lucky/Salsa usa CENTAVOS (amount=2000 ⇒ R$20,00). BetBonus trabalha em REAIS.
    AMOUNT_SCALE = 100
    # Frontend PAGOL: min R$20 (= 2000 cents). Cap lab R$1900. Default = mínimo da casa.
    MIN_WITHDRAW_AMOUNT = 20.0
    MAX_WITHDRAW_AMOUNT = 1900.0  # safety cap lab em REAIS
    DEFAULT_WITHDRAW_AMOUNT = 20.0
    DEFAULT_COUNTRY = "BR"
    DEFAULT_DEVICE_PLATFORM = "DESKTOP"
    # getCurrentLanguage() no frontend devolve "BR" (path /br/ → upper); games/start exige BR.
    GAME_LANGUAGE = "BR"
    HIGH_EV_SEARCH_TERMS = (
        "mines",
        "aviator",
        "crash",
        "plinko",
        "dice",
        "spaceman",
        "jetx",
        "rocket",
        "limbo",
        "flyx",
    )
    HIGH_EV_NAME_RE = re.compile(
        r"\b(?:mines?|aviator|aviatrix|crash|plinko|dice|spaceman|jetx|"
        r"rocket|limbo|flyx|kick\s*crash)\b",
        re.IGNORECASE,
    )
    # Stake lab: teto de segurança (reais). Aposta real no Spribe é SmartFox/WS (não auto ainda).
    MAX_LAB_STAKE_BRL = 5.0
    DEFAULT_LAB_STAKE_BRL = 1.0
    DEFAULT_STAKE_GAME_ID = 1624  # Mines (Spribe) — melhor que Aviator para stake controlado

    @classmethod
    def cents_to_reais(cls, value: Any) -> float:
        try:
            return float(value) / cls.AMOUNT_SCALE
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def reais_to_cents(cls, value: Any) -> int:
        try:
            return int(round(float(value) * cls.AMOUNT_SCALE))
        except (TypeError, ValueError):
            return 0

    def __init__(
        self,
        delay: Optional[float] = None,
        session: Optional[requests.Session] = None,
        token: str = "",
    ):
        super().__init__(delay=delay, session=session)
        self.token = token.strip()
        self.nlp = BonusNLPAnalyzer()
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Origin": SITE,
                "Referer": f"{SITE}/br/",
            }
        )
        self._apply_auth_header()

    def set_token(self, token: str) -> None:
        self.token = token.strip()
        self._apply_auth_header()

    def _apply_auth_header(self) -> None:
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
        else:
            self.session.headers.pop("Authorization", None)

    def _client_token(self, path: str) -> str:
        """X-Client-Token = base64(json{clientId:path,timestamp}).hmac_sha256(secret)."""
        payload = json.dumps(
            {"clientId": path, "timestamp": int(time.time() * 1000)},
            separators=(",", ":"),
        )
        encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        sig = hmac.new(
            SECRET_SALSA_KEY.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        return f"{encoded}.{sig}"

    def _default_params(self, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        params = {
            "language": "pt",
            "platform": self.DEFAULT_DEVICE_PLATFORM,
        }
        if extra:
            params.update(extra)
        return params

    def _request(
        self,
        method: str,
        path: str,
        *,
        base: str = API_BASE,
        client_token: bool = False,
        **kwargs: Any,
    ) -> Any:
        if self.delay > 0:
            time.sleep(self.delay)
        url = f"{base}{path}"
        headers = dict(kwargs.pop("headers", None) or {})
        if client_token:
            headers["X-Client-Token"] = self._client_token(path)
        response = self.session.request(
            method, url, timeout=25, headers=headers or None, **kwargs
        )
        if response.status_code == 401:
            raise PermissionError("Unauthorized — token PAGOL inválido/expirado")
        if response.status_code == 204:
            return None
        if not response.content:
            return None
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Invalid JSON from {path}: HTTP {response.status_code} body={response.text[:200]}"
            ) from exc
        if response.status_code >= 400:
            if isinstance(payload, dict):
                code = payload.get("code") or payload.get("error") or ""
                msg = payload.get("message") or payload.get("error_description") or payload
                raise RuntimeError(
                    f"HTTP {response.status_code} on {path}: {code} {msg} "
                    f"{json.dumps(payload, ensure_ascii=False)[:400]}"
                )
            raise RuntimeError(f"HTTP {response.status_code} on {path}: {payload}")
        return payload

    def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        return self._request("GET", path, params=params or None)

    @classmethod
    def login(cls, username: str, password: str) -> str:
        """OAuth password grant → access_token."""
        scraper = cls(delay=0)
        payload = scraper._request(
            "POST",
            "/oauth/token",
            base=AUTH_BASE,
            data={
                "grant_type": "password",
                "username": username,
                "password": password,
                "client_id": CLIENT_ID,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {CLIENT_BASIC}",
            },
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Login PAGOL: resposta inesperada")
        token = payload.get("access_token") or ""
        if not token:
            raise RuntimeError(f"Login PAGOL sem access_token: {payload}")
        return str(token)

    def validate_token(self) -> dict[str, Any]:
        if not self.token:
            raise PermissionError("Sem token PAGOL")
        balance = self._get("/user/balance.do")
        if not isinstance(balance, dict):
            raise RuntimeError("validate: balance.do inválido")
        return {
            "user_id": balance.get("userId"),
            "currency": balance.get("currency"),
            "balance": self.cents_to_reais(balance.get("balance")),
            "bonus_balance": self.cents_to_reais(balance.get("bonusBalance")),
            "balance_cents": balance.get("balance"),
            "loyalty_level": balance.get("loyaltyLevel"),
            "country": balance.get("countryISO2"),
            "amount_unit": "BRL",
        }

    def get_wallet_snapshot(self, *, include_bonus_state: bool = True) -> WalletSnapshot:
        if not self.token:
            raise PermissionError("Token necessário para GET /user/balance.do")
        data = self._get("/user/balance.do")
        if not isinstance(data, dict):
            raise RuntimeError("balance.do inválido")
        # API devolve centavos — snapshot BetBonus em REAIS.
        # Rollover/maxConvert vêm de /user/bonuses.do (não do balance.do).
        bonus_state: dict[str, Any] = {}
        remaining_rollover = 0.0
        bonus_from_wallet = self.cents_to_reais(data.get("bonusBalance"))
        bonus_brl = bonus_from_wallet
        if include_bonus_state:
            try:
                bonus_state = self.get_bonus_conversion_state()
            except Exception:  # noqa: BLE001
                bonus_state = {}
            primary = bonus_state.get("primary") if isinstance(bonus_state, dict) else None
            primary = primary if isinstance(primary, dict) else {}
            remaining_rollover = float(primary.get("remaining_rollover_brl") or 0.0)
            bonus_from_active = float(primary.get("balance_brl") or 0.0)
            # balance.do às vezes zera bonusBalance enquanto bonuses.do ainda tem saldo
            bonus_brl = max(bonus_from_wallet, bonus_from_active)
        return WalletSnapshot(
            platform=self.platform,
            balance=self.cents_to_reais(data.get("balance")),
            bonus=bonus_brl,
            rollover=remaining_rollover,
            raw={
                **{
                    k: data.get(k)
                    for k in (
                        "balance",
                        "bonusBalance",
                        "currency",
                        "loyaltyLevel",
                        "userId",
                        "showBalance",
                    )
                    if k in data
                },
                "balance_brl": self.cents_to_reais(data.get("balance")),
                "bonus_brl": bonus_brl,
                "bonus_field_brl": bonus_from_wallet,
                "amount_unit_api": "cents",
                "amount_unit_betbonus": "BRL",
                "bonus_state": bonus_state,
            },
        )

    def get_bonus_balances(self) -> list[dict[str, Any]]:
        """GET /user/bonuses/balance.do — saldos por bonusId (centavos + BRL)."""
        if not self.token:
            raise PermissionError("Token necessário para GET /user/bonuses/balance.do")
        data = self._get("/user/bonuses/balance.do")
        rows = list(data) if isinstance(data, list) else []
        out: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            enriched = dict(row)
            enriched["balance_brl"] = self.cents_to_reais(row.get("balance"))
            out.append(enriched)
        return out

    def normalize_bonus_rules(self, item: dict[str, Any]) -> dict[str, Any]:
        """Normaliza um item de /user/bonuses.do para regras canônicas em BRL."""
        balance_cents = item.get("balance")
        rollover_cents = item.get("rollover")
        target_cents = item.get("targetRollover")
        max_convert_cents = item.get("maxConvertValue")
        max_bet_cents = item.get("maxSelectableBalanceBet")
        balance_brl = self.cents_to_reais(balance_cents)
        rollover_brl = self.cents_to_reais(rollover_cents)
        target_brl = self.cents_to_reais(target_cents)
        remaining = max(target_brl - rollover_brl, 0.0)
        max_bet_brl = self.cents_to_reais(max_bet_cents) if max_bet_cents is not None else None
        max_convert_brl = (
            self.cents_to_reais(max_convert_cents) if max_convert_cents is not None else None
        )
        game_types = [
            str(x) for x in (item.get("bonusGameTypes") or []) if x is not None
        ]
        wagering_multiple = None
        if target_brl > 0 and balance_brl > 0:
            # aproximação: alvo / saldo inicial desconhecido → usa target/balance atual só se rollover=0
            if rollover_brl <= 0:
                wagering_multiple = round(target_brl / balance_brl, 2)
        return {
            "id": item.get("id") or item.get("bonusId"),
            "name": item.get("name") or item.get("title"),
            "status": item.get("status") or item.get("_status_query") or item.get("bonusStatus"),
            "bonus_type": item.get("bonusType"),
            "balance_cents": balance_cents,
            "balance_brl": balance_brl,
            "rollover_cents": rollover_cents,
            "rollover_brl": rollover_brl,
            "target_rollover_cents": target_cents,
            "target_rollover_brl": target_brl,
            "remaining_rollover_brl": round(remaining, 2),
            "max_convert_cents": max_convert_cents,
            "max_convert_brl": max_convert_brl,
            "max_bet_cents": max_bet_cents,
            "max_bet_brl": max_bet_brl,
            "bonus_game_types": game_types,
            "wagering_multiple_est": wagering_multiple,
            "allows_high_ev": any(
                t.upper() in {"CRASH_GAMES", "CRASH", "INSTANT", "OTHER"}
                or "CRASH" in t.upper()
                or "MINES" in t.upper()
                for t in game_types
            ),
            "slots_only": game_types == ["SLOTS"]
            or (len(game_types) == 1 and game_types[0].upper() == "SLOTS"),
            "raw_keys": sorted(str(k) for k in item.keys()),
        }

    def get_bonus_conversion_state(self) -> dict[str, Any]:
        """Inventário ACTIVE/READY/PENDING + balances + primary candidate para conversão."""
        statuses = ("ACTIVE", "READY", "PENDING")
        bonuses = self.list_bonuses(statuses=statuses, page_size=50, max_pages=3)
        normalized = [self.normalize_bonus_rules(b) for b in bonuses if isinstance(b, dict)]
        try:
            wallet_balances = self.get_bonus_balances()
        except Exception as exc:  # noqa: BLE001
            wallet_balances = [{"error": str(exc)[:200]}]
        # Prefer ACTIVE/READY with balance > 0
        ranked = sorted(
            normalized,
            key=lambda b: (
                0 if str(b.get("status") or "").upper() in {"ACTIVE", "READY"} else 1,
                -(float(b.get("balance_brl") or 0.0)),
                float(b.get("remaining_rollover_brl") or 0.0),
            ),
        )
        primary = next(
            (
                b
                for b in ranked
                if float(b.get("balance_brl") or 0) > 0
                or float(b.get("remaining_rollover_brl") or 0) > 0
            ),
            ranked[0] if ranked else None,
        )
        theoretical_ceiling = 0.0
        if primary:
            max_c = primary.get("max_convert_brl")
            bal = float(primary.get("balance_brl") or 0.0)
            if max_c is not None:
                theoretical_ceiling = min(float(max_c), bal) if bal > 0 else float(max_c)
            else:
                theoretical_ceiling = bal
        return {
            "count": len(normalized),
            "bonuses": normalized,
            "wallet_balances": wallet_balances,
            "primary": primary,
            "theoretical_max_convert_brl": round(float(theoretical_ceiling or 0.0), 2),
            "strategy": self._bonus_play_strategy(primary) if primary else {
                "mode": "no_bonus",
                "note": "Sem bônus ACTIVE/READY com saldo/rollover",
            },
        }

    def _bonus_play_strategy(self, primary: dict[str, Any]) -> dict[str, Any]:
        """Plano automatizável para maximizar valor conversível (sem auto-spin)."""
        remaining = float(primary.get("remaining_rollover_brl") or 0.0)
        max_bet = float(primary.get("max_bet_brl") or 0.0) or None
        max_convert = primary.get("max_convert_brl")
        game_types = list(primary.get("bonus_game_types") or [])
        if primary.get("slots_only"):
            path = "slots_under_max_bet"
            autobet = False
            autobet_blocker = "provider_slot_spin_api_not_implemented"
        elif primary.get("allows_high_ev"):
            path = "high_ev_under_max_bet"
            autobet = False
            autobet_blocker = "spribe_smartfox_ws_not_implemented"
        else:
            path = "restricted_game_types"
            autobet = False
            autobet_blocker = f"bonusGameTypes={game_types}"
        bets_at_max = None
        if max_bet and max_bet > 0 and remaining > 0:
            bets_at_max = int(-(-int(round(remaining * 100)) // int(round(max_bet * 100))))
        return {
            "mode": path,
            "bonus_id": primary.get("id"),
            "game_types": game_types,
            "remaining_rollover_brl": remaining,
            "max_bet_brl": max_bet,
            "max_convert_brl": max_convert,
            "bets_needed_at_max_bet": bets_at_max,
            "auto_bet_available": autobet,
            "auto_bet_blocker": autobet_blocker,
            "note": (
                "Rollover deve ser cumprido em jogos elegíveis; teto de materialização "
                f"= maxConvert ({max_convert}). Auto-spin/auto-bet ainda não implementado."
            ),
        }

    def list_my_bonuses(self, per_page: int = 50, max_pages: int = 10) -> list[dict[str, Any]]:
        """Alias compatível com o oracle/4Play."""
        return self.list_bonuses(page_size=per_page, max_pages=max_pages)

    def list_bonuses(
        self,
        statuses: tuple[str, ...] = BONUS_STATUSES,
        page_size: int = 50,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        if not self.token:
            raise PermissionError("Token necessário para GET /user/bonuses.do")
        items: list[dict[str, Any]] = []
        for status in statuses:
            page = 0
            while page < max_pages:
                data = self._get(
                    "/user/bonuses.do",
                    params={"status": status, "page": page, "pageSize": page_size},
                )
                if not isinstance(data, dict):
                    break
                batch = list(data.get("items") or [])
                for row in batch:
                    if isinstance(row, dict):
                        row = {**row, "_status_query": status}
                        items.append(row)
                total = int(data.get("count") or 0)
                if not batch or len(batch) < page_size or (page + 1) * page_size >= total:
                    break
                page += 1
        return items

    def list_enabled_promocodes(self) -> list[dict[str, Any]]:
        if not self.token:
            raise PermissionError("Token necessário para promocodes")
        data = self._get("/user/promocode/all-enabled.do")
        return list(data) if isinstance(data, list) else []

    def claim_or_activate_bonus(self, bonus_id: int | str) -> dict[str, Any]:
        """
        Tenta endpoints comuns de claim/activate (Lucky). Muitos respondem 204.
        Não garante crédito — use get_bonus_conversion_state depois.
        """
        bid = int(bonus_id)
        attempts: list[dict[str, Any]] = []
        paths = [
            (f"/user/bonuses/{bid}/activate.do", {}),
            (f"/user/bonuses/{bid}/claim.do", {}),
            (f"/user/bonuses/{bid}/accept.do", {}),
            ("/user/bonuses/activate.do", {"bonusId": bid}),
            ("/user/bonuses/claim.do", {"id": bid}),
        ]
        for path, body in paths:
            try:
                payload = self._request(
                    "POST",
                    path,
                    params=self._game_params(),
                    json=body,
                    client_token=True,
                    headers={"Content-Type": "application/json"},
                )
                attempts.append({"path": path, "ok": True, "response": payload})
                # primeiro 2xx já basta
                break
            except Exception as exc:  # noqa: BLE001
                attempts.append({"path": path, "ok": False, "error": str(exc)[:160]})
        return {"bonus_id": bid, "attempts": attempts, "ok": any(a.get("ok") for a in attempts)}

    def list_withdrawals(self, page: int = 0, page_size: int = 20) -> dict[str, Any]:
        data = self._get("/user/withdrawals.do", params={"page": page, "pageSize": page_size})
        if not isinstance(data, dict):
            return {"items": [], "raw": data}
        items = []
        for row in data.get("items") or []:
            if not isinstance(row, dict):
                continue
            enriched = dict(row)
            enriched["amount_brl"] = self.cents_to_reais(row.get("amount"))
            items.append(enriched)
        return {**data, "items": items}

    def withdraw_methods(self, country: str = "BR") -> list[str]:
        data = self._get(
            "/user/withdrawals/methods.do",
            params=self._default_params({"country": country}),
        )
        return [str(x) for x in data] if isinstance(data, list) else []

    def get_user_profile(self) -> dict[str, Any]:
        """GET /user.do?fullInfo=true — pixKey/pixType/fullName/withdrawalAllowed."""
        if not self.token:
            raise PermissionError("Token necessário para GET /user.do")
        data = self._request(
            "GET",
            "/user.do",
            params=self._default_params({"fullInfo": "true"}),
            client_token=True,
        )
        return data if isinstance(data, dict) else {}

    def withdraw_preflight(self) -> dict[str, Any]:
        wallet = self.get_wallet_snapshot()
        profile: dict[str, Any] = {}
        try:
            profile = self.get_user_profile()
        except Exception as exc:  # noqa: BLE001
            profile = {"profile_error": str(exc)}
        day_totals_raw = self._get("/user/withdrawals/dayTotals.do")
        day_totals_brl: Any = day_totals_raw
        if not isinstance(day_totals_raw, dict):
            day_totals_brl = self.cents_to_reais(day_totals_raw)
        return {
            "wallet": wallet.model_dump(mode="json"),
            "methods": self.withdraw_methods(self.DEFAULT_COUNTRY),
            "have_opened": self._get("/user/withdrawals/have-opened"),
            "day_totals": day_totals_raw,
            "day_totals_brl": day_totals_brl,
            "saved_accounts": self._get("/user/withdrawals/list-saved-account.do"),
            "min_withdraw": self.MIN_WITHDRAW_AMOUNT,
            "max_withdraw_lab_cap": self.MAX_WITHDRAW_AMOUNT,
            "default_withdraw": self.DEFAULT_WITHDRAW_AMOUNT,
            "amount_unit": "BRL",
            "api_amount_unit": "cents",
            "pix_key": profile.get("pixKey"),
            "pix_type": profile.get("pixType"),
            "withdrawal_allowed": profile.get("withdrawalAllowed"),
            "full_name": profile.get("fullName"),
        }

    def withdraw(
        self,
        *,
        amount: float,
        method: str = "PIX",
        phone: str = "",
        iban: str = "",
        country: str = DEFAULT_COUNTRY,
        account_owner: str = "",
        pix_key: str = "",
        pix_type: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        """
        POST /user/withdrawals/request.do?language=pt&platform=DESKTOP

        `amount` em REAIS (BetBonus). Convertido para CENTAVOS no body da API
        (frontend: formatControlValueToCents).

        Body (PIX):
          {
            country, amount (cents), method: "PIX",
            data: { pixKey, pixType, accountOwner }
          }

        phone/iban ignorados (compat signature com oracle 4Play).
        """
        del phone, iban  # unused — PIX key vem do perfil
        if not self.token:
            raise PermissionError("Token necessário para POST withdraw PAGOL")
        method_u = (method or "PIX").upper()
        if method_u in {"TFT", "DTR", "PREFLIGHT"}:
            method_u = "PIX"
        if method_u not in {"PIX", "PAY_BROKERS"}:
            raise ValueError("method PAGOL deve ser PIX ou PAY_BROKERS")

        amount_brl = float(amount)
        amount_cents = self.reais_to_cents(amount_brl)
        if amount_cents < self.reais_to_cents(self.MIN_WITHDRAW_AMOUNT):
            raise ValueError(
                f"Valor PAGOL abaixo do mínimo da casa "
                f"(R$ {self.MIN_WITHDRAW_AMOUNT:.2f} = {self.reais_to_cents(self.MIN_WITHDRAW_AMOUNT)} cents)"
            )

        profile = self.get_user_profile()
        owner = (account_owner or str(profile.get("fullName") or "")).strip()
        key = (pix_key or str(profile.get("pixKey") or "")).strip()
        key_type = (pix_type or str(profile.get("pixType") or "CPF")).strip().upper()
        if method_u == "PIX":
            if not key or not owner:
                raise ValueError(
                    "PIX requer pixKey + accountOwner (perfil /user.do incompleto)"
                )
            if profile.get("withdrawalAllowed") is False:
                raise RuntimeError(
                    "HTTP 403 on /user/withdrawals/request.do: withdrawal_not_allowed "
                    '{"code":"withdrawal_not_allowed","message":"withdrawalAllowed=false"}'
                )

        path = "/user/withdrawals/request.do"
        body: dict[str, Any] = {
            "country": country or self.DEFAULT_COUNTRY,
            "amount": amount_cents,
            "method": method_u,
        }
        if method_u == "PIX":
            body["data"] = {
                "pixKey": key,
                "pixType": key_type,
                "accountOwner": owner,
            }

        payload = self._request(
            "POST",
            path,
            params=self._default_params(),
            json=body,
            client_token=True,
            headers={"Content-Type": "application/json"},
        )
        if not isinstance(payload, dict):
            return {
                "raw": payload,
                "code": "SUCCESS",
                "amount_brl": amount_brl,
                "amount_cents": amount_cents,
            }
        # Normaliza para o oracle (4Play usa code/message/data)
        out = dict(payload)
        if "withdrawalId" in out and "code" not in out:
            out["code"] = "SUCCESS"
            out["message"] = (
                f"withdrawalId={out.get('withdrawalId')} "
                f"amount=R${amount_brl:.2f} ({amount_cents} cents)"
            )
            out["data"] = {
                "withdrawalId": out.get("withdrawalId"),
                "url": out.get("url"),
                "method": method_u,
                "amount_brl": amount_brl,
                "amount_cents": amount_cents,
            }
        out["amount_brl"] = amount_brl
        out["amount_cents"] = amount_cents
        return out

    def _game_params(self, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        params = {
            "language": self.GAME_LANGUAGE,
            "platform": self.DEFAULT_DEVICE_PLATFORM,
        }
        if extra:
            params.update(extra)
        return params

    def search_games(
        self,
        game_name: str,
        *,
        page: int = 0,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """GET /games.do?gameName=&page=&pageSize= (+ language/platform)."""
        name = (game_name or "").strip()
        if len(name) < 3:
            raise ValueError("gameName PAGOL exige ≥ 3 caracteres")
        data = self._request(
            "GET",
            "/games.do",
            params=self._game_params(
                {"page": page, "pageSize": page_size, "gameName": name}
            ),
            client_token=True,
        )
        if not isinstance(data, dict):
            return {"items": [], "count": 0, "raw": data}
        items = [x for x in (data.get("items") or []) if isinstance(x, dict)]
        return {"items": items, "count": int(data.get("count") or len(items))}

    def get_game_basic_info(self, game_id: int | str) -> dict[str, Any]:
        data = self._request(
            "GET",
            f"/games/{game_id}/basicInformation.do",
            params=self._game_params(),
            client_token=True,
        )
        return data if isinstance(data, dict) else {"raw": data}

    def discover_high_ev_games(
        self,
        *,
        terms: Optional[tuple[str, ...] | list[str]] = None,
        page_size: int = 50,
        max_games: int = 80,
    ) -> dict[str, Any]:
        """
        Discovery de jogos high-EV (crash/mines/plinko/aviator/…) via /games.do.
        Não coloca aposta — só catálogo + metadados básicos.
        """
        use_terms = tuple(terms or self.HIGH_EV_SEARCH_TERMS)
        by_id: dict[int, dict[str, Any]] = {}
        term_hits: dict[str, int] = {}
        for term in use_terms:
            try:
                result = self.search_games(term, page=0, page_size=page_size)
            except Exception as exc:  # noqa: BLE001
                term_hits[term] = -1
                continue
            items = result.get("items") or []
            term_hits[term] = len(items)
            for row in items:
                try:
                    gid = int(row.get("gameId"))
                except (TypeError, ValueError):
                    continue
                name = str(row.get("name") or "")
                if not self.HIGH_EV_NAME_RE.search(name) and term.lower() not in name.lower():
                    # mantém hits do search mesmo sem regex (ex.: "Big Bass Crash")
                    pass
                if gid not in by_id:
                    by_id[gid] = {
                        "game_id": gid,
                        "name": name,
                        "slug": row.get("slug"),
                        "provider": row.get("gameProviderName"),
                        "vertical_ids": row.get("verticalIds"),
                        "image": row.get("image"),
                        "matched_terms": [term],
                        "high_ev": bool(self.HIGH_EV_NAME_RE.search(name)),
                    }
                else:
                    matched = by_id[gid].setdefault("matched_terms", [])
                    if term not in matched:
                        matched.append(term)
            if len(by_id) >= max_games:
                break

        games = sorted(
            by_id.values(),
            key=lambda g: (0 if g.get("high_ev") else 1, str(g.get("name") or "").lower()),
        )[:max_games]
        # Enriquecer top N com basicInformation (paidToday / provider)
        enriched = 0
        for game in games[: min(12, len(games))]:
            try:
                info = self.get_game_basic_info(game["game_id"])
                game["basic"] = {
                    "name": info.get("name"),
                    "slug": info.get("slug"),
                    "provider": info.get("gameProviderName"),
                    "paid_today": info.get("paidToday"),
                    "volatility": info.get("volatility"),
                    "max_win_amount": info.get("maxWinAmount"),
                }
                enriched += 1
            except Exception as exc:  # noqa: BLE001
                game["basic_error"] = str(exc)[:200]
        return {
            "platform": self.platform,
            "terms": list(use_terms),
            "term_hits": term_hits,
            "count": len(games),
            "enriched": enriched,
            "games": games,
            "site_play_path": f"{SITE}/br/game/{{slug}}",
        }

    def start_game(
        self,
        game_id: int | str,
        *,
        mode: str = "REAL",
        use_bonus_balance: Optional[bool] = None,
        game_tab: str = "",
    ) -> dict[str, Any]:
        """
        POST /games/start.do — abre sessão Salsa (não aposta).

        Body real do frontend: {id, mode: REAL|FREE, language: BR, platform, gameTab?, useBonusBalance?}
        """
        if not self.token:
            raise PermissionError("Token necessário para POST /games/start.do")
        mode_u = (mode or "REAL").upper()
        if mode_u not in {"REAL", "FREE"}:
            raise ValueError("mode deve ser REAL ou FREE")
        tab = (game_tab or str(uuid.uuid4())).strip()
        try:
            gid: int | str = int(game_id)
        except (TypeError, ValueError):
            gid = game_id
        body: dict[str, Any] = {
            "id": gid,
            "mode": mode_u,
            "language": self.GAME_LANGUAGE,
            "platform": self.DEFAULT_DEVICE_PLATFORM,
            "gameTab": tab,
        }
        if use_bonus_balance is not None:
            body["useBonusBalance"] = bool(use_bonus_balance)
        payload = self._request(
            "POST",
            "/games/start.do",
            params=self._game_params(),
            json=body,
            client_token=False,
            headers={"Content-Type": "application/json"},
        )
        out = dict(payload) if isinstance(payload, dict) else {"raw": payload}
        out["game_id"] = gid
        out["mode"] = mode_u
        out["game_tab"] = tab
        out["use_bonus_balance"] = use_bonus_balance
        out["launch"] = self._parse_salsa_launch(out.get("url"))
        return out

    @staticmethod
    def _parse_salsa_launch(url: Any) -> dict[str, Any]:
        if not url or not isinstance(url, str):
            return {}
        try:
            parsed = urlparse(url)
            q = {k: (v[0] if v else "") for k, v in parse_qs(parsed.query).items()}
        except Exception:  # noqa: BLE001
            return {"url": url}
        balance_raw = q.get("balance")
        try:
            balance_cents = int(float(balance_raw)) if balance_raw not in (None, "") else None
        except (TypeError, ValueError):
            balance_cents = None
        return {
            "host": parsed.netloc,
            "game": q.get("game"),
            "type": q.get("type"),  # CHARGED / etc
            "lang": q.get("lang"),
            "pn": q.get("pn"),
            "username": q.get("username"),
            "balance_cents": balance_cents,
            "balance_brl": (balance_cents / 100.0) if balance_cents is not None else None,
        }

    def probe_high_ev_contribution(
        self,
        *,
        limit: int = 8,
        modes: tuple[str, ...] = ("REAL",),
        include_bonus_flag: bool = True,
    ) -> dict[str, Any]:
        """
        Soft-probe de contribuição / elegibilidade high-EV.

        - Descobre jogos crash/mines/…
        - Abre sessão REAL (e opcionalmente useBonusBalance true/false)
        - Compara wallet before/after + metadados da URL Salsa
        - NÃO envia aposta ao provider (sem bot de multiplicador ainda)

        Achado útil: jogo lança com bonusBalance, type=CHARGED, free_mode gaps, etc.
        """
        if not self.token:
            raise PermissionError("Token necessário para probe high-EV")
        wallet_before = self.get_wallet_snapshot()
        discovery = self.discover_high_ev_games(max_games=max(limit * 8, 60))
        # Prioriza nomes canônicos (aviator/mines/crash/plinko) no topo do probe
        games = list(discovery.get("games") or [])
        priority = ("aviator", "mines", "crash", "plinko", "jetx", "spaceman", "dice")
        def _rank(g: dict[str, Any]) -> tuple[int, str]:
            name = str(g.get("name") or "").lower()
            for i, key in enumerate(priority):
                if key in name:
                    return (i, name)
            return (len(priority), name)

        games.sort(key=_rank)
        targets = games[: max(1, min(limit, 20))]
        probes: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []

        flag_values: list[Optional[bool]]
        if include_bonus_flag:
            flag_values = [False, True]
        else:
            flag_values = [None]

        for game in targets:
            gid = game.get("game_id")
            entry: dict[str, Any] = {
                "game_id": gid,
                "name": game.get("name"),
                "slug": game.get("slug"),
                "provider": game.get("provider"),
                "launches": [],
            }
            for mode in modes:
                for flag in flag_values:
                    try:
                        launch = self.start_game(
                            gid, mode=mode, use_bonus_balance=flag
                        )
                        meta = {
                            "ok": True,
                            "mode": mode,
                            "use_bonus_balance": flag,
                            "token_present": bool(launch.get("token")),
                            "url_host": (launch.get("launch") or {}).get("host"),
                            "salsa_game": (launch.get("launch") or {}).get("game"),
                            "salsa_type": (launch.get("launch") or {}).get("type"),
                            "salsa_balance_brl": (launch.get("launch") or {}).get(
                                "balance_brl"
                            ),
                            "width": launch.get("width"),
                            "height": launch.get("height"),
                        }
                        entry["launches"].append(meta)
                    except Exception as exc:  # noqa: BLE001
                        msg = str(exc)
                        entry["launches"].append(
                            {
                                "ok": False,
                                "mode": mode,
                                "use_bonus_balance": flag,
                                "error": msg[:300],
                            }
                        )
            # sinal: ambos flags lançam (bonus e cash) — elegibilidade ampla
            oks = [x for x in entry["launches"] if x.get("ok") and x.get("mode") == "REAL"]
            if any(x.get("use_bonus_balance") is True for x in oks) and any(
                x.get("use_bonus_balance") is False for x in oks
            ):
                findings.append(
                    {
                        "id": f"bonus_and_cash_eligible_{gid}",
                        "severity": "high",
                        "title": f"Aceita cash e bonusBalance: {game.get('name')}",
                        "rationale": (
                            "start.do aceita useBonusBalance true e false — "
                            "candidato a probe de contribuição 0%/100% com stake mínimo."
                        ),
                        "test_idea": (
                            "Apostar 1x stake mínimo com useBonusBalance=true e comparar "
                            "bonusBalance/rollover/dayTotals antes e depois."
                        ),
                    }
                )
            probes.append(entry)

        wallet_after = self.get_wallet_snapshot()
        return {
            "platform": self.platform,
            "probe_kind": "soft_launch",
            "note": (
                "Soft-probe: abre sessão Salsa sem apostar. "
                "Contribuição % real exige stake controlado no provider."
            ),
            "wallet_before": wallet_before.model_dump(mode="json"),
            "wallet_after": wallet_after.model_dump(mode="json"),
            "wallet_unchanged": (
                wallet_before.balance == wallet_after.balance
                and wallet_before.bonus == wallet_after.bonus
            ),
            "discovery_count": discovery.get("count"),
            "term_hits": discovery.get("term_hits"),
            "probed": len(probes),
            "probes": probes,
            "findings": _dedup_findings(findings),
        }

    def validate_promocode(self, code: str, *, currency: str = "BRL") -> dict[str, Any]:
        """GET /user/promocode/validate.do — 204/None = válido no frontend."""
        promo = (code or "").strip()
        if not promo:
            raise ValueError("promocode vazio")
        try:
            data = self._request(
                "GET",
                "/user/promocode/validate.do",
                params=self._game_params({"promocode": promo, "currency": currency}),
                client_token=True,
            )
            return {"ok": True, "promocode": promo, "currency": currency, "raw": data}
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "promocode": promo,
                "currency": currency,
                "error": str(exc)[:300],
            }

    def redeem_promocode(
        self,
        code: str,
        *,
        confirm_redeem: bool = False,
        currency: str = "BRL",
    ) -> dict[str, Any]:
        """
        POST /user/promocode/redeem.do {promocode, currency}.
        Exige confirm_redeem=True (efeito real na conta).
        """
        promo = (code or "").strip()
        if not promo:
            raise ValueError("promocode vazio")
        if not confirm_redeem:
            return {
                "ok": False,
                "attempted": False,
                "promocode": promo,
                "message": "confirm_redeem=false — nenhum POST redeem",
            }
        if not self.token:
            raise PermissionError("Token necessário para redeem promocode")
        wallet_before = self.get_wallet_snapshot()
        body = {"promocode": promo, "currency": currency}
        try:
            payload = self._request(
                "POST",
                "/user/promocode/redeem.do",
                params=self._game_params(),
                json=body,
                client_token=True,
                headers={"Content-Type": "application/json"},
            )
            err = None
            ok = True
        except Exception as exc:  # noqa: BLE001
            payload = None
            err = str(exc)[:400]
            ok = False
        wallet_after = self.get_wallet_snapshot()
        bonuses = []
        try:
            bonuses = self.list_bonuses(page_size=10, max_pages=1)
        except Exception:  # noqa: BLE001
            pass
        return {
            "ok": ok,
            "attempted": True,
            "promocode": promo,
            "currency": currency,
            "error": err,
            "response": payload,
            "wallet_before": wallet_before.model_dump(mode="json"),
            "wallet_after": wallet_after.model_dump(mode="json"),
            "bonus_delta": round(wallet_after.bonus - wallet_before.bonus, 2),
            "balance_delta": round(wallet_after.balance - wallet_before.balance, 2),
            "active_bonuses": len(bonuses),
            "bonuses_sample": [
                {
                    "id": b.get("id") or b.get("userBonusId"),
                    "name": b.get("name") or b.get("title"),
                    "status": b.get("status") or b.get("_status_query"),
                }
                for b in bonuses[:5]
                if isinstance(b, dict)
            ],
        }

    def resolve_provider_launch(self, salsa_url: str) -> dict[str, Any]:
        """Segue Salsa → SoftSwiss/a8r options → URL Spribe (aviator/mines/…)."""
        out: dict[str, Any] = {"salsa_url": salsa_url, "provider_url": "", "game": ""}
        if not salsa_url:
            return out
        try:
            resp = self.session.get(salsa_url, timeout=25)
            html = resp.text or ""
            m = re.search(r"options=([^\"&]+)", html)
            if not m:
                out["error"] = "options_b64_not_found"
                return out
            from urllib.parse import unquote

            b64 = unquote(m.group(1))
            pad = "=" * ((4 - len(b64) % 4) % 4)
            try:
                data = json.loads(base64.b64decode(b64 + pad))
            except Exception:  # noqa: BLE001
                data = json.loads(base64.urlsafe_b64decode(b64 + pad))
            launch_opts = (data or {}).get("launch_options") or {}
            provider_url = str(launch_opts.get("game_url") or "")
            out["provider_url"] = provider_url
            out["lobby_token"] = (data or {}).get("lobby_token")
            if provider_url:
                path = urlparse(provider_url).path.strip("/").split("/")
                out["game"] = path[-1] if path else ""
            out["raw_options_keys"] = list((data or {}).keys())
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc)[:240]
        return out

    def run_bonus_multiplier_lab(
        self,
        *,
        promocode: str = "",
        game_id: int | str = DEFAULT_STAKE_GAME_ID,
        stake_brl: float = DEFAULT_LAB_STAKE_BRL,
        confirm_redeem: bool = False,
        confirm_real_bet: bool = False,
        use_bonus_balance: bool = True,
        poll_seconds: int = 30,
    ) -> dict[str, Any]:
        """
        Lab: resgatar promo (opt) → abrir Mines/Aviator → armar stake controlado → medir carteira.

        Limite operacional:
        - Spribe usa SmartFox BlueBox (WS binário). Este lab NÃO envia aposta automática ao provider.
        - Com confirm_real_bet=True: arma a sessão (URL + teto), faz poll da wallet para detectar
          delta após você (ou operador) apostar o stake mínimo na URL retornada.
        """
        if not self.token:
            raise PermissionError("Token necessário para bonus multiplier lab")

        stake = float(stake_brl)
        if stake <= 0:
            raise ValueError("stake_brl deve ser > 0")
        if stake > self.MAX_LAB_STAKE_BRL:
            raise ValueError(
                f"stake_brl {stake} excede teto lab R$ {self.MAX_LAB_STAKE_BRL:.2f}"
            )

        gates: list[str] = []
        steps: list[dict[str, Any]] = []
        wallet0 = self.get_wallet_snapshot()

        have_opened = False
        try:
            have_opened = bool(self._get("/user/withdrawals/have-opened"))
        except Exception as exc:  # noqa: BLE001
            gates.append(f"have_opened_error={exc}")
        if have_opened:
            gates.append("have_opened_withdraw=true")

        # 1) Redeem opcional
        redeem_result: dict[str, Any] | None = None
        code = (promocode or "").strip()
        if code:
            validation = self.validate_promocode(code)
            steps.append({"step": "validate_promocode", **validation})
            if confirm_redeem:
                redeem_result = self.redeem_promocode(code, confirm_redeem=True)
                steps.append({"step": "redeem_promocode", **redeem_result})
                if not redeem_result.get("ok"):
                    gates.append("redeem_failed")
            else:
                steps.append(
                    {
                        "step": "redeem_promocode",
                        "attempted": False,
                        "promocode": code,
                        "message": "confirm_redeem=false — redeem não executado",
                    }
                )
                gates.append("redeem_not_confirmed")

        wallet1 = self.get_wallet_snapshot()
        available = max(wallet1.balance, 0.0) + (
            max(wallet1.bonus, 0.0) if use_bonus_balance else 0.0
        )
        if available < stake:
            gates.append(f"insufficient_funds_for_stake={available}<{stake}")

        # 2) Launch sessão REAL
        launch: dict[str, Any] = {}
        provider: dict[str, Any] = {}
        try:
            launch = self.start_game(
                game_id,
                mode="REAL",
                use_bonus_balance=use_bonus_balance if wallet1.bonus > 0 else False,
            )
            provider = self.resolve_provider_launch(str(launch.get("url") or ""))
            steps.append(
                {
                    "step": "start_game",
                    "ok": True,
                    "game_id": game_id,
                    "use_bonus_balance": launch.get("use_bonus_balance"),
                    "salsa_game": (launch.get("launch") or {}).get("game"),
                    "provider_game": provider.get("game"),
                    "provider_url": provider.get("provider_url"),
                    "salsa_url": launch.get("url"),
                }
            )
        except Exception as exc:  # noqa: BLE001
            steps.append({"step": "start_game", "ok": False, "error": str(exc)[:300]})
            gates.append("start_game_failed")

        # 3) Armar stake / poll (sem auto-bet Spribe)
        bet_armed = bool(confirm_real_bet and provider.get("provider_url"))
        if confirm_real_bet and not provider.get("provider_url"):
            gates.append("provider_url_missing")
        if confirm_real_bet and available < stake:
            gates.append("bet_blocked_insufficient_funds")
            bet_armed = False
        if not confirm_real_bet:
            gates.append("bet_not_confirmed")

        poll: dict[str, Any] = {"ran": False}
        if bet_armed and poll_seconds > 0:
            poll = self._poll_wallet_delta(
                seconds=min(int(poll_seconds), 120),
                interval=2.0,
            )
            steps.append({"step": "wallet_poll", **poll})

        wallet_end = self.get_wallet_snapshot()
        auto_bet_note = (
            "Spribe Mines/Aviator usa SmartFox BlueBox (WebSocket binário). "
            "O lab arma a sessão e mede a carteira; a aposta mínima deve ser "
            f"feita na provider_url com stake ≤ R$ {stake:.2f}."
        )

        findings: list[dict[str, Any]] = []
        if redeem_result and redeem_result.get("ok") and redeem_result.get("bonus_delta", 0) > 0:
            findings.append(
                {
                    "id": "promocode_bonus_credited",
                    "severity": "high",
                    "title": f"Promo creditou bônus +R$ {redeem_result.get('bonus_delta')}",
                    "rationale": f"redeem {code} aumentou bonusBalance",
                    "test_idea": "Jogar stake mínimo com useBonusBalance e medir saque",
                }
            )
        if poll.get("changed"):
            findings.append(
                {
                    "id": "wallet_changed_during_poll",
                    "severity": "critical",
                    "title": "Carteira mudou durante janela de stake",
                    "rationale": (
                        f"Δbalance={poll.get('balance_delta')} "
                        f"Δbonus={poll.get('bonus_delta')} "
                        f"em {poll.get('elapsed_s')}s"
                    ),
                    "test_idea": "Correlacionar com aposta/cashout no provider e dayTotals",
                }
            )
        if "insufficient_funds_for_stake" in "".join(gates):
            findings.append(
                {
                    "id": "no_funds_for_multiplier",
                    "severity": "medium",
                    "title": "Sem saldo/bônus para multiplicar",
                    "rationale": (
                        f"available={available} stake={stake}. "
                        "Pending withdraw ou promo inválida bloqueiam o lab."
                    ),
                    "test_idea": "Liberar PENDING no BO ou resgatar promo no-deposit válida",
                }
            )

        return {
            "platform": self.platform,
            "lab": "bonus_multiplier",
            "auto_bet_implemented": False,
            "auto_bet_note": auto_bet_note,
            "stake_brl": stake,
            "max_lab_stake_brl": self.MAX_LAB_STAKE_BRL,
            "game_id": game_id,
            "confirm_redeem": confirm_redeem,
            "confirm_real_bet": confirm_real_bet,
            "bet_armed": bet_armed,
            "use_bonus_balance": use_bonus_balance,
            "gates": gates,
            "wallet_start": wallet0.model_dump(mode="json"),
            "wallet_after_redeem": wallet1.model_dump(mode="json"),
            "wallet_end": wallet_end.model_dump(mode="json"),
            "available_for_stake": available,
            "provider_url": provider.get("provider_url") or "",
            "salsa_url": launch.get("url") or "",
            "steps": steps,
            "poll": poll,
            "findings": _dedup_findings(findings),
            "ok": bool(bet_armed or (redeem_result and redeem_result.get("ok"))),
        }

    def probe_slots_for_bonus(
        self,
        *,
        limit: int = 4,
        use_bonus_balance: bool = True,
        search_terms: Optional[tuple[str, ...] | list[str]] = None,
    ) -> dict[str, Any]:
        """Soft-probe: lança slots elegíveis com useBonusBalance (sem spin)."""
        terms = tuple(search_terms or ("gates of olympus", "sweet bonanza", "fortune rabbit", "slots"))
        by_id: dict[int, dict[str, Any]] = {}
        for term in terms:
            try:
                result = self.search_games(term, page=0, page_size=30)
            except Exception:  # noqa: BLE001
                continue
            for row in result.get("items") or []:
                if not isinstance(row, dict):
                    continue
                try:
                    gid = int(row.get("gameId"))
                except (TypeError, ValueError):
                    continue
                if gid not in by_id:
                    by_id[gid] = {
                        "game_id": gid,
                        "name": row.get("name"),
                        "provider": row.get("gameProviderName"),
                        "slug": row.get("slug"),
                    }
            if len(by_id) >= limit:
                break
        games = list(by_id.values())[:limit]
        probes: list[dict[str, Any]] = []
        for game in games:
            launch_row: dict[str, Any] = {
                "game_id": game["game_id"],
                "name": game.get("name"),
                "provider": game.get("provider"),
                "ok": False,
            }
            try:
                launch = self.start_game(
                    game["game_id"],
                    mode="REAL",
                    use_bonus_balance=use_bonus_balance,
                )
                salsa_url = str(launch.get("url") or "")
                launch_row.update(
                    {
                        "ok": bool(salsa_url),
                        "use_bonus_balance": launch.get("use_bonus_balance"),
                        "salsa_url": salsa_url,
                        "salsa_game": (launch.get("launch") or {}).get("game"),
                        "salsa_balance": (launch.get("launch") or {}).get("balance"),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                launch_row["error"] = str(exc)[:240]
            probes.append(launch_row)
        ok_n = sum(1 for p in probes if p.get("ok"))
        return {
            "probe_kind": "slots_soft_launch",
            "note": "Launch only — spin no provider (Pragmatic/PG) não automatizado",
            "use_bonus_balance": use_bonus_balance,
            "probed": len(probes),
            "launches_ok": ok_n,
            "probes": probes,
        }

    def poll_withdrawal_settlement(
        self,
        *,
        withdrawal_id: int | str | None = None,
        timeout_s: int = 90,
        interval_s: float = 5.0,
        expect_amount_brl: float | None = None,
    ) -> dict[str, Any]:
        """
        Poll list_withdrawals até status terminal (DENIED/VERIFIED/APPROVED/PAID/…)
        ou timeout. Detecta materialização vs BO deny + restauração de saldo.
        """
        if not self.token:
            raise PermissionError("Token necessário para poll de saque")
        terminal = {
            "DENIED",
            "REJECTED",
            "CANCELED",
            "CANCELLED",
            "VERIFIED",
            "APPROVED",
            "PAID",
            "COMPLETED",
            "SUCCESS",
            "DONE",
        }
        wallet0 = self.get_wallet_snapshot(include_bonus_state=False)
        samples: list[dict[str, Any]] = []
        started = time.time()
        matched: dict[str, Any] | None = None
        while time.time() - started <= timeout_s:
            hist = self.list_withdrawals(0, 10)
            items = list(hist.get("items") or [])
            target = None
            if withdrawal_id is not None:
                wid = str(withdrawal_id)
                target = next((x for x in items if str(x.get("id")) == wid), None)
            elif expect_amount_brl is not None:
                target = next(
                    (
                        x
                        for x in items
                        if abs(float(x.get("amount_brl") or 0) - float(expect_amount_brl)) < 0.011
                    ),
                    items[0] if items else None,
                )
            else:
                target = items[0] if items else None
            wallet = self.get_wallet_snapshot(include_bonus_state=False)
            row = {
                "t": round(time.time() - started, 1),
                "status": (target or {}).get("status"),
                "id": (target or {}).get("id"),
                "amount_brl": (target or {}).get("amount_brl"),
                "balance": wallet.balance,
                "have_opened": None,
            }
            try:
                row["have_opened"] = bool(self._get("/user/withdrawals/have-opened"))
            except Exception:  # noqa: BLE001
                pass
            samples.append(row)
            if target and str(target.get("status") or "").upper() in terminal:
                matched = target
                break
            time.sleep(max(interval_s, 1.0))
        wallet1 = self.get_wallet_snapshot(include_bonus_state=False)
        last = matched or (samples[-1] if samples else {})
        status_u = str((last or {}).get("status") or "").upper()
        materialized = status_u in {"VERIFIED", "APPROVED", "PAID", "COMPLETED", "SUCCESS", "DONE"}
        denied = status_u in {"DENIED", "REJECTED", "CANCELED", "CANCELLED"}
        return {
            "ran": True,
            "timeout_s": timeout_s,
            "withdrawal_id": (matched or {}).get("id") if matched else withdrawal_id,
            "final_status": status_u or None,
            "materialized": materialized,
            "bo_denied": denied,
            "balance_before": wallet0.balance,
            "balance_after": wallet1.balance,
            "balance_delta": round(wallet1.balance - wallet0.balance, 2),
            "balance_likely_restored": bool(denied and wallet1.balance >= wallet0.balance - 0.01),
            "api_success_vs_pix": (
                "PIX_NOT_MATERIALIZED" if denied else ("PIX_LIKELY_PAID" if materialized else "PENDING")
            ),
            "samples": samples[-12:],
            "vulnerability": (
                "withdraw_ok_api_but_bo_denied"
                if denied
                else ("withdraw_materialized" if materialized else "withdraw_settle_timeout")
            ),
        }

    def _poll_wallet_delta(self, *, seconds: int = 30, interval: float = 2.0) -> dict[str, Any]:
        start = self.get_wallet_snapshot(include_bonus_state=False)
        samples = [
            {
                "t": 0,
                "balance": start.balance,
                "bonus": start.bonus,
            }
        ]
        elapsed = 0.0
        changed = False
        while elapsed < seconds:
            time.sleep(interval)
            elapsed += interval
            snap = self.get_wallet_snapshot(include_bonus_state=False)
            samples.append(
                {"t": round(elapsed, 1), "balance": snap.balance, "bonus": snap.bonus}
            )
            if snap.balance != start.balance or snap.bonus != start.bonus:
                changed = True
                break
        end = self.get_wallet_snapshot(include_bonus_state=False)
        return {
            "ran": True,
            "elapsed_s": round(elapsed, 1),
            "changed": changed,
            "balance_delta": round(end.balance - start.balance, 2),
            "bonus_delta": round(end.bonus - start.bonus, 2),
            "samples": samples[-8:],
            "wallet_before": start.model_dump(mode="json"),
            "wallet_after": end.model_dump(mode="json"),
        }

    def extract_offers(self, soup: BeautifulSoup, source_url: str = "") -> list[BonusOffer]:
        # SPA shell — live API only
        return []

    def offer_from_bonus(self, item: dict[str, Any]) -> BonusOffer:
        title = str(
            item.get("name")
            or item.get("title")
            or item.get("bonusName")
            or item.get("description")
            or f"Bonus #{item.get('id') or item.get('userBonusId') or '?'}"
        ).strip()
        status = str(item.get("status") or item.get("_status_query") or "")
        amount = _first_number(
            item,
            ("amount", "bonusAmount", "currentAmount", "initialAmount", "value", "prize"),
        )
        wagering = _first_number(
            item,
            (
                "wagering",
                "wageringMultiple",
                "rollover",
                "rolloverMultiplier",
                "multiplier",
                "wagerRequirement",
            ),
        )
        raw = f"{title}\nstatus={status}\n{item}"
        fields = self.nlp.analyze(f"{title}\n{status}")
        return BonusOffer(
            platform=self.platform,
            bonus_type=fields.bonus_type if fields.bonus_type != BonusType.UNKNOWN else BonusType.UNKNOWN,
            title=f"[conta] {title}",
            amount=amount if amount is not None else fields.amount,
            currency=str(item.get("currency") or fields.currency or "BRL"),
            wagering_multiple=wagering if wagering is not None else fields.wagering_multiple,
            free_spins=_first_int(item, ("freeSpins", "spins", "fsCount")),
            game_restrictions=fields.game_restrictions,
            terms_url=f"{SITE}/br/my-account/bonuses-rollover/bonus-list",
            source_url=f"{SITE}/br/my-account/bonuses-rollover/bonus-list",
            raw_text=raw[:4000],
        )

    def offer_from_promocode(self, item: dict[str, Any]) -> BonusOffer:
        code = str(item.get("code") or item.get("promocode") or "").strip()
        return BonusOffer(
            platform=self.platform,
            bonus_type=BonusType.UNKNOWN,
            title=f"[promocode] {code}",
            amount=0.0,
            currency="BRL",
            wagering_multiple=30.0,
            terms_url=f"{SITE}/br/promotions/",
            source_url=f"{API_BASE}/user/promocode/all-enabled.do",
            raw_text=f"promocode enabled id={item.get('id')} code={code}",
        )

    def scrape_live(
        self,
        include_account: bool = True,
        include_promocodes: bool = True,
        promocode_limit: int = 20,
    ) -> ScrapeResult:
        source = f"{SITE}/br/my-account/bonuses-rollover/bonus-list"
        if not self.token:
            return ScrapeResult(
                platform=self.platform,
                source_url=source,
                offers=[],
                ok=False,
                error="Token PAGOL necessário para live API",
            )
        try:
            offers: list[BonusOffer] = []
            notes: list[str] = []
            if include_account:
                bonuses = self.list_bonuses()
                offers.extend(self.offer_from_bonus(b) for b in bonuses)
                notes.append(f"bonuses={len(bonuses)}")
            if include_promocodes:
                codes = self.list_enabled_promocodes()
                notes.append(f"promocodes_enabled={len(codes)}")
                for item in codes[: max(0, promocode_limit)]:
                    offers.append(self.offer_from_promocode(item))
            wallet = self.get_wallet_snapshot()
            notes.append(
                f"balance={wallet.balance} bonusBalance={wallet.bonus} currency=BRL"
            )
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
                offers=[],
                ok=False,
                error=str(exc),
            )

    def scrape_url(self, url: str) -> ScrapeResult:
        # Prefer live API — HTML SPA shell is empty for generic scrape
        if self.token:
            return self.scrape_live()
        return ScrapeResult(
            platform=self.platform,
            source_url=url,
            offers=[],
            ok=False,
            error="PAGOL é SPA; use scout live + token (não HTML shell)",
        )


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


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


def _dedup_findings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in items:
        key = str(row.get("id") or row.get("title") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out
