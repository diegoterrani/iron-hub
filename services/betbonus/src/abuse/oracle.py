from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Optional

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

# Min saque default (4Play CRC). PAGOL PIX tem mínimo próprio (BRL).
DEFAULT_MIN_WITHDRAW = FourPlayScraper.MIN_WITHDRAW_AMOUNT
PAGOL_MIN_WITHDRAW = PagolScraper.MIN_WITHDRAW_AMOUNT

# #region agent log
_DEBUG_LOG = Path("/home/ubuntu/.cursor/debug-5390de.log")
_DEBUG_FALLBACK = Path(__file__).resolve().parents[2] / "data" / "debug-5390de.log"


def _agent_log(hypothesis_id: str, location: str, message: str, data: dict[str, Any]) -> None:
    payload = {
        "sessionId": "5390de",
        "runId": "phase-a",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    for path in (_DEBUG_LOG, _DEBUG_FALLBACK):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
            break
        except OSError:
            continue
    try:
        import urllib.request

        req = urllib.request.Request(
            "http://localhost:7467/ingest/9b993db5-7e47-443d-a53d-48e4547c7a13",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Debug-Session-Id": "5390de",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=1.5)
    except Exception:
        pass


# #endregion


def classify_conversion(wallet: WalletSnapshot, account_bonuses: int = 0) -> ConversionSnapshot:
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

    # House min withdraw gate (4Play CRC / PAGOL BRL).
    if wallet.platform == "4play" and wallet.balance < DEFAULT_MIN_WITHDRAW:
        gates.append(f"below_min_withdraw={DEFAULT_MIN_WITHDRAW}")
        if status == ConversionStatus.WITHDRAWABLE:
            status = ConversionStatus.BLOCKED
            notes = (
                f"Balance {wallet.balance} < min saque "
                f"{DEFAULT_MIN_WITHDRAW} CRC."
            )
    elif wallet.platform == "pagol_bet_br" and wallet.bonus > 0:
        gates.append("bonus_balance_present")
    elif wallet.platform == "pagol_bet_br" and wallet.balance > 0:
        gates.append("pagol_withdraw_methods=PIX|PAY_BROKERS")
        if wallet.balance < PAGOL_MIN_WITHDRAW:
            gates.append(f"below_min_withdraw={PAGOL_MIN_WITHDRAW}")
            if status == ConversionStatus.WITHDRAWABLE:
                status = ConversionStatus.BLOCKED
                notes = (
                    f"Balance {wallet.balance} < min saque "
                    f"{PAGOL_MIN_WITHDRAW} BRL (PIX)."
                )

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
    Oracle de saque real — 4Play (SINPE) e PAGOL (PIX).

    Segurança operacional:
    - exige confirm_real_withdraw=True
    - teto max_amount (4Play: 10000 CRC; PAGOL lab: 1900 BRL reais; API PAGOL em cents)
    - use_max_available=True (default): saca min(saldo, max_amount)
    - 4Play: SINPE Móvil (tft) com telefone do perfil
    - PAGOL: PIX com pixKey/pixType/accountOwner do /user.do
    """

    def __init__(self, scraper: Any, findings: Any = None):
        self.scraper = scraper
        self.findings = findings

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
        snap = classify_conversion(wallet, account_bonuses=n)
        # #region agent log
        _agent_log(
            "H1",
            "oracle.py:snapshot",
            "conversion snapshot",
            {
                "status": snap.status.value,
                "balance": wallet.balance,
                "bonus": wallet.bonus,
                "rollover": wallet.rollover,
                "gates": snap.gates,
                "account_bonuses": n,
            },
        )
        # #endregion
        return snap

    def attempt_withdraw(
        self,
        *,
        amount: float,
        confirm_real_withdraw: bool,
        method: str = "tft",
        iban: str = "",
        phone: str = "",
        max_amount: float = FourPlayScraper.MIN_WITHDRAW_AMOUNT,
        preflight_only: bool = False,
        use_max_available: bool = True,
    ) -> WithdrawOracleResult:
        before = self.scraper.get_wallet_snapshot()
        snap = classify_conversion(before)
        gates = list(snap.gates)

        platform_name = str(getattr(self.scraper, "platform", "") or "")
        is_pagol = platform_name == "pagol_bet_br" or isinstance(self.scraper, PagolScraper)
        if use_max_available:
            amount = self.resolve_max_amount(
                before.balance, max_amount, cents=is_pagol or "bet_br" in platform_name
            )
            gates.append(f"use_max_available={amount}")

        # #region agent log
        _agent_log(
            "H2",
            "oracle.py:attempt_withdraw:entry",
            "withdraw request",
            {
                "amount": amount,
                "confirm": confirm_real_withdraw,
                "preflight_only": preflight_only,
                "method": method,
                "max_amount": max_amount,
                "use_max_available": use_max_available,
                "balance_before": before.balance,
                "status_before": snap.status.value,
            },
        )
        # #endregion

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
            # #region agent log
            _agent_log(
                "H3",
                "oracle.py:attempt_withdraw:preflight",
                "preflight only — no POST",
                {"gates": gates, "would_amount": amount, "extra_keys": list(extra)[:12]},
            )
            # #endregion
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

        # PAGOL: bloquear se já há saque aberto (have-opened) — finding útil
        withdraw_method = method
        if is_pagol:
            withdraw_method = "PIX" if method.lower() in {"tft", "dtr", "pix", "preflight", ""} else method.upper()
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
                gates.append(f"pagol_preflight_error={exc}")

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
            # #region agent log
            _agent_log(
                "H4",
                "oracle.py:attempt_withdraw:denied",
                "withdraw denied by house",
                {
                    "http_status": http_status,
                    "code": code,
                    "message": message[:200],
                    "minAmount": data.get("minAmount"),
                },
            )
            # #endregion

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

        # #region agent log
        _agent_log(
            "H5",
            "oracle.py:attempt_withdraw:exit",
            "withdraw finished",
            {
                "ok": ok,
                "attempted": True,
                "status": status.value,
                "code": code,
                "balance_after": after.balance if after else None,
                "finding_id": result.finding_id[:8] if result.finding_id else "",
            },
        )
        # #endregion
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
