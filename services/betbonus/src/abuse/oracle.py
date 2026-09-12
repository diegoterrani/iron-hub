from __future__ import annotations

import json
import math
from typing import Any, Optional

from src.abuse.house_profile import HouseProfile
from src.models.abuse import (
    AbuseFinding,
    AbuseSeverity,
    ConversionSnapshot,
    ConversionStatus,
    WalletSnapshot,
    WithdrawOracleResult,
)
from src.scrapers.fourplay_scraper import FourPlayScraper
from src.scrapers.pagol_scraper import PagolScraper

# Fallbacks when no HouseProfile is supplied.
DEFAULT_MIN_WITHDRAW = FourPlayScraper.MIN_WITHDRAW_AMOUNT
PAGOL_MIN_WITHDRAW = PagolScraper.MIN_WITHDRAW_AMOUNT


def classify_conversion(
    wallet: WalletSnapshot,
    account_bonuses: int = 0,
    *,
    profile: Optional[HouseProfile] = None,
) -> ConversionSnapshot:
    """Classifica o estado de conversão da carteira.

    Quando `profile` é fornecido, os gates de min-withdraw e métodos de
    saque vêm do HouseProfile (house-agnostic). Sem profile, usa fallbacks
    por plataforma (4play CRC / pagol_bet_br BRL).
    """
    gates: list[str] = []
    status = ConversionStatus.UNKNOWN
    notes = ""

    if wallet.rollover > 0:
        status = ConversionStatus.WAGERING
        gates.append(f"rollover_remaining={wallet.rollover}")
        notes = "Rollover ativo — saldo ainda não livre para saque."
    elif wallet.bonus > 0 and wallet.balance <= 0:
        status = ConversionStatus.CLAIMED
        gates.append("bonus_balance_only")
        notes = "Há bônus na carteira, sem balance principal."
    elif wallet.bonus > 0 and wallet.balance > 0:
        status = ConversionStatus.CLAIMED
        gates.append("mixed_bonus_and_balance")
        notes = "Balance + bônus presentes; validar se balance é sacável."
    elif wallet.balance > 0 and wallet.rollover <= 0 and wallet.bonus <= 0:
        status = ConversionStatus.WITHDRAWABLE
        notes = "Balance > 0, bonus=0, rollover=0 — candidato a saque."
    elif account_bonuses > 0:
        status = ConversionStatus.CLAIMED
        gates.append("account_bonus_records")
        notes = "Existem registros em GET /bonus."
    else:
        status = ConversionStatus.NO_BONUS
        notes = "Sem bônus ativo e sem sinal de wagering."

    # --- Min-withdraw gate (house-agnostic via profile, fallback per platform) ---
    min_wd: Optional[float] = None
    currency: str = ""
    methods: list[str] = []

    if profile is not None:
        min_wd = profile.min_withdraw
        currency = profile.currency or ""
        methods = profile.withdraw_methods
    else:
        # Legacy fallbacks
        if wallet.platform == "4play":
            min_wd = DEFAULT_MIN_WITHDRAW
            currency = "CRC"
        elif wallet.platform == "pagol_bet_br":
            min_wd = PAGOL_MIN_WITHDRAW
            currency = "BRL"
            methods = ["PIX", "PAY_BROKERS"]

    if min_wd is not None and wallet.balance < min_wd:
        gates.append(f"below_min_withdraw={min_wd}")
        if status == ConversionStatus.WITHDRAWABLE:
            status = ConversionStatus.BLOCKED
            notes = (
                f"Balance {wallet.balance} < min saque {min_wd}"
                + (f" {currency}" if currency else "")
                + "."
            )

    # Extra gates for bonus balance / withdraw methods
    if wallet.bonus > 0 and wallet.balance <= 0:
        gates.append("bonus_balance_present")
    if methods:
        gates.append(f"withdraw_methods={'|'.join(methods)}")

    return ConversionSnapshot(
        platform=wallet.platform,
        status=status,
        wallet=wallet,
        account_bonuses=account_bonuses,
        gates=gates,
        notes=notes,
    )


class WithdrawalOracle:
    """
    Oracle de saque real — house-agnostic.

    Segurança operacional:
    - exige confirm_real_withdraw=True
    - teto max_amount (profile-driven, fallback 10000)
    - use_max_available=True (default): saca min(saldo, max_amount)
    - método/phone/iban resolution per house (profile or scraper attrs)
    """

    def __init__(
        self,
        scraper: Any,
        findings: Any = None,
        profile: Optional[HouseProfile] = None,
    ):
        self.scraper = scraper
        self.findings = findings
        self.profile = profile

    @staticmethod
    def resolve_max_amount(balance: float, max_amount: float, *, cents: bool = False) -> float:
        """Máximo sacável agora: min(saldo, teto lab), arredondado para baixo."""
        raw = min(max(float(balance), 0.0), max(float(max_amount), 0.0))
        if cents:
            return math.floor(raw * 100) / 100.0
        return math.floor(raw)

    def snapshot(self) -> ConversionSnapshot:
        wallet = self.scraper.get_wallet_snapshot()
        try:
            bonuses = self.scraper.list_my_bonuses(per_page=5, max_pages=1)
            n = len(bonuses)
        except Exception:  # noqa: BLE001
            n = 0
        snap = classify_conversion(wallet, account_bonuses=n, profile=self.profile)
        return snap

    def _try_convert_bonus(
        self,
        before: WalletSnapshot,
        *,
        game_id: Optional[int | str] = None,
    ) -> tuple[WalletSnapshot, list[str]]:
        """Attempt to convert bonus balance → real balance by starting a game.

        Returns (post_conversion_snapshot, conversion_gates).
        """
        if before.bonus <= 0 or before.balance > 0:
            return before, []

        if not hasattr(self.scraper, "start_game"):
            return before, ["no_start_game_method"]

        gid: Optional[int | str] = game_id
        if gid is None:
            gid = getattr(self.scraper, "default_game_id", None)
        if gid is None:
            gid = 1

        try:
            self.scraper.start_game(
                gid,
                mode="REAL",
                use_bonus_balance=True,
            )
        except Exception as exc:  # noqa: BLE001
            return before, [f"bonus_convert_start_game_error={exc}"]

        try:
            after = self.scraper.get_wallet_snapshot()
        except Exception:  # noqa: BLE001
            return before, ["bonus_convert_snapshot_error"]

        converted = after.balance > before.balance
        gates = [
            f"bonus_convert_attempted=game:{gid}",
            f"bonus_before={before.bonus}",
            f"balance_before={before.balance}",
            f"balance_after={after.balance}",
            f"converted={converted}",
        ]
        return (after if converted else before), gates

    def attempt_withdraw(
        self,
        *,
        amount: float,
        confirm_real_withdraw: bool,
        method: str = "tft",
        iban: str = "",
        phone: str = "",
        max_amount: Optional[float] = None,
        preflight_only: bool = False,
        use_max_available: bool = True,
        convert_bonus: bool = True,
        game_id: Optional[int | str] = None,
    ) -> WithdrawOracleResult:
        before = self.scraper.get_wallet_snapshot()
        snap = classify_conversion(before, profile=self.profile)
        gates = list(snap.gates)

        # Resolve max_amount and cents from profile (house-agnostic)
        if max_amount is None:
            max_amount = self.profile.max_withdraw if self.profile else 10_000.0
        uses_cents = self.profile.uses_cents if self.profile else (
            str(getattr(self.scraper, "platform", "")).endswith("bet_br")
            or isinstance(self.scraper, PagolScraper)
        )

        # Bonus → real balance conversion: if only bonus exists, start a game
        # with useBonusBalance to convert it to withdrawable real balance.
        if convert_bonus and before.bonus > 0 and before.balance <= 0:
            before, conv_gates = self._try_convert_bonus(before, game_id=game_id)
            gates.extend(conv_gates)
            if before.balance > 0:
                snap = classify_conversion(before, profile=self.profile)
                gates.append(f"post_conversion_status={snap.status}")

        if use_max_available:
            amount = self.resolve_max_amount(before.balance, max_amount, cents=uses_cents)
            gates.append(f"use_max_available={amount}")

        if not confirm_real_withdraw:
            return WithdrawOracleResult(
                ok=False,
                attempted=False,
                preflight_only=True,
                status=snap.status,
                message="confirm_real_withdraw=false — nenhuma chamada à casa",
                amount=amount,
                wallet_before=before,
                gates=gates + ["confirm_required"],
            )

        if amount <= 0:
            return WithdrawOracleResult(
                ok=False,
                attempted=False,
                status=ConversionStatus.BLOCKED,
                message="amount deve ser > 0 (saldo zerado ou abaixo da precisão)",
                amount=amount,
                wallet_before=before,
                gates=gates + ["invalid_amount"],
            )

        if amount > max_amount:
            return WithdrawOracleResult(
                ok=False,
                attempted=False,
                status=ConversionStatus.BLOCKED,
                message=f"amount {amount} excede max_amount {max_amount} (safety cap)",
                amount=amount,
                wallet_before=before,
                gates=gates + [f"capped_max={max_amount}"],
            )

        if preflight_only:
            extra: dict[str, Any] = {}
            if hasattr(self.scraper, "withdraw_preflight"):
                try:
                    extra = self.scraper.withdraw_preflight() or {}
                    if isinstance(extra, dict) and extra.get("methods"):
                        gates = gates + [f"methods={extra.get('methods')}"]
                except Exception as exc:  # noqa: BLE001
                    extra = {"preflight_error": str(exc)}
            return WithdrawOracleResult(
                ok=False,
                attempted=False,
                preflight_only=True,
                status=snap.status,
                message="preflight_only — snapshot/gates sem POST de saque",
                amount=amount,
                wallet_before=before,
                gates=gates,
                response_data=extra if isinstance(extra, dict) else {},
            )

        user: dict[str, Any] = {}
        try:
            validated = self.scraper.validate_token()
            if isinstance(validated, dict):
                user = validated.get("user") or validated
        except Exception as exc:  # noqa: BLE001
            gates.append(f"auth_user_error={exc}")

        meta_phone = phone or str(user.get("phone") or "")
        digits = "".join(ch for ch in meta_phone if ch.isdigit())

        # Resolve withdraw method from profile (house-agnostic)
        withdraw_method = method
        if self.profile and self.profile.withdraw_methods:
            # Use the first profile method if the requested method is generic
            if method.lower() in {"tft", "dtr", "pix", "preflight", "", "auto"}:
                withdraw_method = self.profile.withdraw_methods[0]
            else:
                withdraw_method = method.upper()
            # Preflight check for open withdrawals / allowed methods
            if hasattr(self.scraper, "withdraw_preflight"):
                try:
                    pre = self.scraper.withdraw_preflight()
                    if isinstance(pre, dict):
                        if pre.get("have_opened") is True:
                            gates.append("have_opened_withdraw=true")
                        if pre.get("methods"):
                            gates.append(f"methods={pre.get('methods')}")
                        if pre.get("withdrawal_allowed") is False:
                            gates.append("withdrawal_allowed=false")
                except Exception as exc:  # noqa: BLE001
                    gates.append(f"preflight_error={exc}")

        try:
            payload = self.scraper.withdraw(
                amount=amount,
                method=withdraw_method,
                phone=digits,
                iban=iban,
            )
            http_status = 200
            code = str(payload.get("code") or "SUCCESS")
            message = str(payload.get("message") or "OK")
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            if not data and isinstance(payload, dict) and payload.get("withdrawalId"):
                data = {
                    "withdrawalId": payload.get("withdrawalId"),
                    "url": payload.get("url"),
                }
            status = ConversionStatus.WITHDRAW_OK
            ok = True
        except Exception as exc:  # noqa: BLE001
            http_status, code, message, data = _parse_withdraw_error(exc)
            status = ConversionStatus.WITHDRAW_DENIED
            ok = False
            payload = {"error": str(exc)}

        after: Optional[WalletSnapshot] = None
        try:
            after = self.scraper.get_wallet_snapshot()
        except Exception:  # noqa: BLE001
            after = None

        result = WithdrawOracleResult(
            ok=ok,
            attempted=True,
            status=status,
            http_status=http_status,
            code=code,
            message=message,
            amount=amount,
            method=withdraw_method,
            wallet_before=before,
            wallet_after=after,
            gates=gates,
            response_data={
                "code": code,
                "data": data,
                "raw_keys": list(payload.keys()) if isinstance(payload, dict) else [],
            },
        )

        if self.findings is not None:
            severity = AbuseSeverity.HIGH if ok else AbuseSeverity.MEDIUM
            if code in (
                "ERR_AMOUNT_IS_TOO_LOW",
                "ERR_INSUFFICIENT_BALANCE",
                "withdrawal_method_disabled",
                "invalid_params",
            ):
                severity = AbuseSeverity.INFO
            finding = AbuseFinding(
                platform=self.scraper.platform,
                vector="withdraw_oracle_real",
                severity=severity,
                title=f"Saque {'OK' if ok else 'negado'}: {code or message}",
                status=status,
                evidence={
                    "amount": amount,
                    "method": withdraw_method,
                    "http_status": http_status,
                    "code": code,
                    "message": message,
                    "wallet_before": before.model_dump(mode="json"),
                    "wallet_after": after.model_dump(mode="json") if after else None,
                    "gates": gates,
                    "response_data": result.response_data,
                },
            )
            saved = self.findings.add(finding)
            result.finding_id = saved.id

        return result


def _parse_withdraw_error(exc: Exception) -> tuple[int, str, str, dict[str, Any]]:
    text = str(exc)
    http_status = 0
    code = "ERR_UNKNOWN"
    message = text
    data: dict[str, Any] = {}
    # FourPlayScraper raises RuntimeError with JSON snippet when possible
    if "HTTP " in text:
        try:
            http_status = int(text.split("HTTP ", 1)[1].split(" ", 1)[0].strip(":,"))
        except (IndexError, ValueError):
            pass
    for marker in ("{",):
        if marker in text:
            try:
                blob = text[text.index("{") :]
                # trim trailing noise
                end = blob.rfind("}")
                if end > 0:
                    blob = blob[: end + 1]
                parsed = json.loads(blob)
                if isinstance(parsed, dict):
                    code = str(parsed.get("code") or code)
                    message = str(parsed.get("message") or message)
                    if isinstance(parsed.get("data"), dict):
                        data = parsed["data"]
                    if parsed.get("status"):
                        try:
                            http_status = int(parsed["status"])
                        except (TypeError, ValueError):
                            pass
            except json.JSONDecodeError:
                pass
            break
    if "ERR_" in text and code == "ERR_UNKNOWN":
        for part in text.replace(",", " ").split():
            if part.startswith("ERR_"):
                code = part.strip("'\"")
                break
    return http_status, code, message, data
