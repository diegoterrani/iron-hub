"""
Withdrawal orchestrator — plan and execute withdrawals to minimize BO review risk.

Strategy:
- Amount: Withdraw ~95% of max_convert_brl (not the exact cap)
- Split: If balance > R$1000, do 2 withdrawals 24-48h apart
- Timing: 48+ hours after last wager, during 10:00-16:00 BR (business hours)
- Method: PIX to own CPF (not third-party)
- Frequency: Max 1 withdrawal per 72h per account
- Pattern: First withdrawal smaller (R$50-100), second gets the rest
- BO denial detection + retry logic
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from src.models.abuse import ConversionStatus, WalletSnapshot, WithdrawOracleResult

log = logging.getLogger("betbonus.abuse.withdraw")

# Business hours window (Brazil local time)
BUSINESS_HOUR_START = 10
BUSINESS_HOUR_END = 16

# Minimum hours after last wager before withdrawing
MIN_HOURS_AFTER_WAGER = 48

# Max hours between withdrawals for same account
MAX_HOURS_BETWEEN_WITHDRAWALS = 72

# Target fraction of max_convert to withdraw (avoid exact cap)
WITHDRAW_FRACTION = 0.95

# BO denial retry backoff (hours)
DENIAL_RETRY_HOURS = 24


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class WithdrawalPlan:
    """Plan for one or more withdrawals from an account."""
    account_id: str
    platform: str
    total_balance: float
    withdrawals: list[dict] = field(default_factory=list)
    expected_net: float = 0.0
    notes: str = ""


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class WithdrawalOrchestrator:
    """Plans and executes withdrawals to minimize BO (back-office) review risk.

    Parameters:
        scraper: platform scraper (PagolScraper, FourPlayScraper, etc.)
        profile: optional HouseProfile for house-agnostic parameters
        oracle: optional WithdrawalOracle for preflight classification
    """

    def __init__(self, scraper: Any, profile: Any = None, oracle: Any = None):
        self.scraper = scraper
        self.profile = profile
        self.oracle = oracle
        self.rng = random.Random()
        self._tz = ZoneInfo("America/Sao_Paulo")

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def build_plan(
        self,
        wallet: Any,
        max_convert: float = 0.0,
        *,
        split_threshold: float = 1000.0,
        first_withdraw_range: tuple[float, float] = (50.0, 100.0),
    ) -> WithdrawalPlan:
        """Compute a split-withdrawal strategy to minimize BO review risk.

        Args:
            wallet: WalletSnapshot (or object with .balance, .platform)
            max_convert: max convertible amount (0 = use wallet.balance)
            split_threshold: balance above this triggers 2-withdrawal split
            first_withdraw_range: (min, max) for the first (smaller) withdrawal

        Returns:
            WithdrawalPlan with 1 or 2 withdrawal steps
        """
        balance = float(getattr(wallet, "balance", 0.0) or 0.0)
        platform = str(getattr(wallet, "platform", "") or "unknown")
        account_id = str(
            getattr(self.scraper, "account_id", "")
            or getattr(self.scraper, "token", "")[:16]
            or "unknown"
        )

        # Target: 95% of max_convert (or balance if no max_convert given)
        target = max_convert if max_convert > 0 else balance
        target = target * WITHDRAW_FRACTION

        # Clamp to available balance
        target = min(target, balance)

        # Round to 2 decimals
        target = round(target, 2)

        plan = WithdrawalPlan(
            account_id=account_id,
            platform=platform,
            total_balance=balance,
        )

        if target <= 0:
            plan.notes = "No withdrawable balance."
            return plan

        if target > split_threshold:
            # Split: first small (50-100), second gets the rest
            first_amount = round(self.rng.uniform(*first_withdraw_range), 2)
            second_amount = round(target - first_amount, 2)

            # Ensure second is >= min_withdraw
            min_wd = self._min_withdraw()
            if second_amount < min_wd:
                first_amount = target
                second_amount = 0.0

            if second_amount > 0:
                plan.withdrawals = [
                    {
                        "amount": first_amount,
                        "method": "PIX",
                        "scheduled_at": self._optimal_window_start().isoformat(),
                        "is_first": True,
                    },
                    {
                        "amount": second_amount,
                        "method": "PIX",
                        "scheduled_at": self._optimal_window_start(
                            offset_hours=self.rng.uniform(24, 48)
                        ).isoformat(),
                        "is_first": False,
                    },
                ]
                plan.expected_net = target
                plan.notes = (
                    f"Split into 2 withdrawals ({first_amount} + {second_amount}) "
                    f"24-48h apart to avoid BO pattern detection."
                )
            else:
                plan.withdrawals = [
                    {
                        "amount": first_amount,
                        "method": "PIX",
                        "scheduled_at": self._optimal_window_start().isoformat(),
                        "is_first": True,
                    },
                ]
                plan.expected_net = first_amount
                plan.notes = f"Single withdrawal (split not viable above min_withdraw={min_wd})."
        else:
            # Single withdrawal
            plan.withdrawals = [
                {
                    "amount": target,
                    "method": "PIX",
                    "scheduled_at": self._optimal_window_start().isoformat(),
                    "is_first": True,
                },
            ]
            plan.expected_net = target
            plan.notes = f"Single withdrawal of {target} (below split threshold {split_threshold})."

        return plan

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, plan: WithdrawalPlan, *, confirm: bool = True) -> list[dict]:
        """Execute all withdrawals in the plan sequentially.

        Waits between withdrawals per the scheduled timing (simplified to
        a short delay in this implementation; full timing is handled by
        the scheduler in production).

        Returns:
            List of result dicts (one per withdrawal step)
        """
        results: list[dict] = []
        for i, wd in enumerate(plan.withdrawals):
            if i > 0:
                delay = 30.0
                log.info("Waiting %.0fs before next withdrawal...", delay)
                time.sleep(delay)

            log.info(
                "Executing withdrawal %d/%d: amount=%.2f method=%s",
                i + 1, len(plan.withdrawals), wd["amount"], wd["method"],
            )
            result = self.execute_single(
                amount=wd["amount"],
                method=wd["method"],
                confirm=confirm,
            )
            results.append(result)

            if not result.get("ok") and result.get("denied"):
                denial_info = self.handle_denial(result, attempt=i + 1)
                result["denial_handling"] = denial_info
                if denial_info.get("action") == "stop":
                    log.warning("Stopping plan: BO denial with no viable retry.")
                    break

        return results

    def execute_single(
        self,
        amount: float,
        method: str = "PIX",
        *,
        confirm: bool = True,
    ) -> dict:
        """Execute a single withdrawal with full error handling.

        Args:
            amount: withdrawal amount in platform currency (BRL for Pagol)
            method: withdrawal method (PIX, bank transfer, etc.)
            confirm: if False, only do preflight (no actual withdrawal)

        Returns:
            Dict with execution result details
        """
        result: dict[str, Any] = {
            "ok": False,
            "amount": amount,
            "method": method,
            "http_status": 0,
            "code": "",
            "message": "",
            "denied": False,
            "denial_reason": "",
            "retry_after_hours": 0.0,
            "wallet_before": None,
            "wallet_after": None,
            "raw_response": {},
        }

        # Preflight check: is there an open withdrawal?
        preflight = self.check_have_opened()
        if preflight.get("has_open"):
            result["message"] = "Open withdrawal exists — cannot submit new one."
            result["code"] = "OPEN_WITHDRAWAL_BLOCKED"
            return result

        # Get wallet before
        try:
            wallet_before = self.scraper.get_wallet_snapshot()
            result["wallet_before"] = (
                wallet_before.model_dump(mode="json")
                if hasattr(wallet_before, "model_dump")
                else dict(wallet_before)
            )
        except Exception as e:
            log.warning("Could not fetch wallet before withdrawal: %s", e)

        # Execute via oracle if available, else direct scraper call
        try:
            if self.oracle is not None:
                oracle_result: WithdrawOracleResult = self.oracle.attempt_withdraw(
                    amount=amount,
                    confirm_real_withdraw=confirm,
                    method=method,
                )
                result["ok"] = oracle_result.ok
                result["http_status"] = oracle_result.http_status or 0
                result["code"] = oracle_result.code
                result["message"] = oracle_result.message
                result["raw_response"] = oracle_result.response_data
                result["wallet_after"] = (
                    oracle_result.wallet_after.model_dump(mode="json")
                    if oracle_result.wallet_after else None
                )

                if oracle_result.status == ConversionStatus.WITHDRAW_DENIED:
                    result["denied"] = True
                    result["denial_reason"] = self._classify_denial(oracle_result)
            else:
                resp = self.scraper.withdraw(
                    amount=amount,
                    method=method,
                    confirm=confirm,
                )
                result["raw_response"] = resp if isinstance(resp, dict) else {"raw": str(resp)}
                result["http_status"] = (
                    resp.get("http_status", 200) if isinstance(resp, dict) else 200
                )

                if isinstance(resp, dict):
                    result["ok"] = resp.get("success", resp.get("ok", False))
                    result["code"] = str(resp.get("code", ""))
                    result["message"] = str(resp.get("message", ""))

                    status_str = str(resp.get("status", "")).upper()
                    if status_str in ("DENIED", "REJECTED", "FAILED") \
                            or "denied" in result["message"].lower():
                        result["denied"] = True
                        result["denial_reason"] = self._classify_denial_from_raw(resp)
        except PermissionError as e:
            result["message"] = f"Auth error: {e}"
            result["code"] = "AUTH_ERROR"
        except Exception as e:
            result["message"] = f"Error: {e}"
            result["code"] = "EXCEPTION"
            log.exception("Withdrawal execution error")

        # Get wallet after
        try:
            wallet_after = self.scraper.get_wallet_snapshot()
            result["wallet_after"] = (
                wallet_after.model_dump(mode="json")
                if hasattr(wallet_after, "model_dump")
                else dict(wallet_after)
            )
        except Exception:
            pass

        return result

    # ------------------------------------------------------------------
    # Denial handling
    # ------------------------------------------------------------------

    def handle_denial(self, result: dict, attempt: int = 1) -> dict:
        """Classify BO denial and decide retry strategy.

        Args:
            result: dict from execute_single() with denied=True
            attempt: current attempt number (1-based)

        Returns:
            Dict with: action ("retry"|"stop"|"reduce"), retry_after_hours,
                       reason, new_amount (if reduce), notes
        """
        reason = result.get("denial_reason", "unknown")
        amount = result.get("amount", 0.0)

        if "insufficient" in reason.lower() or "balance" in reason.lower():
            action = "reduce"
            new_amount = round(amount * 0.5, 2)
            retry_hours = 1.0
            notes = "Insufficient balance detected — reduce amount by 50%."
        elif "frequency" in reason.lower() or "cooldown" in reason.lower() \
                or "limit" in reason.lower():
            action = "retry"
            retry_hours = 72.0
            new_amount = amount
            notes = "Withdrawal frequency limit hit — wait 72h before retry."
        elif "review" in reason.lower() or "manual" in reason.lower() \
                or "bo" in reason.lower():
            action = "retry"
            retry_hours = DENIAL_RETRY_HOURS
            new_amount = round(amount * 0.8, 2)
            notes = "BO manual review triggered — wait 24h and reduce amount by 20%."
        elif "method" in reason.lower() or "pix" in reason.lower() \
                or "account" in reason.lower():
            action = "retry"
            retry_hours = 2.0
            new_amount = amount
            notes = "Payment method/account issue — retry after 2h (verify PIX key)."
        else:
            if attempt >= 3:
                action = "stop"
                retry_hours = 0.0
                new_amount = 0.0
                notes = f"Unknown denial after {attempt} attempts — stopping."
            else:
                action = "retry"
                retry_hours = DENIAL_RETRY_HOURS
                new_amount = round(amount * 0.75, 2)
                notes = f"Unknown denial (attempt {attempt}) — wait 24h, reduce 25%."

        log.info(
            "Denial handling: reason=%s action=%s retry_hours=%.1f new_amount=%.2f",
            reason, action, retry_hours, new_amount,
        )

        return {
            "action": action,
            "reason": reason,
            "retry_after_hours": retry_hours,
            "new_amount": new_amount,
            "notes": notes,
            "attempt": attempt,
        }

    # ------------------------------------------------------------------
    # Status queries
    # ------------------------------------------------------------------

    def check_have_opened(self) -> dict:
        """Check if a withdrawal is pending (blocks new ones).

        Returns:
            Dict with: has_open (bool), raw (Any)
        """
        try:
            if hasattr(self.scraper, "withdraw_preflight"):
                preflight = self.scraper.withdraw_preflight()
                have_opened = preflight.get("have_opened", False)
                return {"has_open": bool(have_opened), "raw": have_opened}
            elif hasattr(self.scraper, "_get"):
                resp = self.scraper._get("/user/withdrawals/have-opened")
                return {"has_open": bool(resp), "raw": resp}
            else:
                return {"has_open": False, "raw": None,
                        "note": "No preflight method available"}
        except Exception as e:
            log.warning("check_have_opened error: %s", e)
            return {"has_open": False, "raw": None, "error": str(e)}

    def wait_for_resolution(
        self,
        timeout_s: float = 90.0,
        poll_interval: float = 5.0,
    ) -> dict:
        """Poll until the current withdrawal resolves (terminal state).

        Returns:
            Dict with: resolved (bool), status (str), elapsed_s (float),
                       samples (list)
        """
        if hasattr(self.scraper, "poll_withdrawal_settlement"):
            try:
                return self.scraper.poll_withdrawal_settlement(
                    timeout_s=int(timeout_s),
                    interval_s=poll_interval,
                )
            except Exception as e:
                log.warning("poll_withdrawal_settlement error: %s", e)
                return {"resolved": False, "error": str(e)}

        # Fallback: manual polling
        terminal = {"DENIED", "REJECTED", "CANCELED", "CANCELLED",
                    "VERIFIED", "APPROVED", "PAID", "COMPLETED", "SUCCESS", "DONE"}
        started = time.time()
        samples: list[dict] = []
        while time.time() - started <= timeout_s:
            try:
                hist = self.scraper.list_withdrawals(0, 5)
                items = list(hist.get("items") or [])
                if items:
                    latest = items[0]
                    status = str(latest.get("status", "")).upper()
                    samples.append({"status": status, "ts": time.time()})
                    if status in terminal:
                        return {
                            "resolved": True,
                            "status": status,
                            "elapsed_s": time.time() - started,
                            "samples": samples,
                        }
            except Exception:
                pass
            time.sleep(poll_interval)

        return {
            "resolved": False,
            "status": "TIMEOUT",
            "elapsed_s": time.time() - started,
            "samples": samples,
        }

    def withdrawal_history(self) -> list[dict]:
        """Get past withdrawals from the scraper.

        Returns:
            List of withdrawal dicts (empty if unavailable)
        """
        try:
            if hasattr(self.scraper, "list_withdrawals"):
                hist = self.scraper.list_withdrawals(0, 50)
                return list(hist.get("items") or [])
            elif hasattr(self.scraper, "get_withdrawal_history"):
                return self.scraper.get_withdrawal_history()
            else:
                return []
        except Exception as e:
            log.warning("withdrawal_history error: %s", e)
            return []

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    def optimal_timing(
        self,
        last_wager_at: Optional[float] = None,
    ) -> tuple[datetime, datetime]:
        """Compute the optimal withdrawal window.

        Args:
            last_wager_at: Unix timestamp of last wager (None = no wager)

        Returns:
            (window_start, window_end) as aware UTC datetimes
        """
        now = datetime.now(timezone.utc)

        # Earliest allowed: 48h after last wager
        if last_wager_at is not None:
            earliest = datetime.fromtimestamp(last_wager_at, tz=timezone.utc) + timedelta(
                hours=MIN_HOURS_AFTER_WAGER
            )
        else:
            earliest = now

        # Window must be within business hours (10:00-16:00 BR)
        window_start = self._next_business_hour(earliest, BUSINESS_HOUR_START)
        window_end = self._next_business_hour(earliest, BUSINESS_HOUR_END)

        # If window_start is already past, push to next day
        if window_start <= now:
            window_start = self._next_business_hour(
                now + timedelta(hours=1), BUSINESS_HOUR_START
            )
            window_end = self._next_business_hour(
                now + timedelta(hours=1), BUSINESS_HOUR_END
            )

        return window_start, window_end

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _min_withdraw(self) -> float:
        """Get minimum withdrawal amount from profile or scraper."""
        if self.profile is not None:
            return float(getattr(self.profile, "min_withdraw", 20.0) or 20.0)
        min_wd = getattr(self.scraper, "MIN_WITHDRAW_AMOUNT", None)
        if min_wd is not None:
            return float(min_wd)
        return 20.0  # Pagol default

    def _optimal_window_start(self, offset_hours: float = 0.0) -> datetime:
        """Return the next optimal withdrawal time (business hours BR)."""
        base = datetime.now(timezone.utc) + timedelta(hours=offset_hours)
        return self._next_business_hour(base, BUSINESS_HOUR_START)

    def _next_business_hour(self, dt: datetime, hour: int) -> datetime:
        """Advance dt to the next occurrence of `hour` in BR local time."""
        local = dt.astimezone(self._tz)
        target = local.replace(hour=hour, minute=0, second=0, microsecond=0)
        if target <= local:
            target += timedelta(days=1)
        return target.astimezone(timezone.utc)

    def _classify_denial(self, oracle_result: WithdrawOracleResult) -> str:
        """Extract denial reason from an oracle result."""
        msg = (oracle_result.message or "").lower()
        code = (oracle_result.code or "").lower()
        combined = f"{code} {msg}"

        if "insufficient" in combined or "balance" in combined:
            return "insufficient_balance"
        if "frequency" in combined or "limit" in combined or "cooldown" in combined:
            return "frequency_limit"
        if "review" in combined or "manual" in combined:
            return "manual_review"
        if "method" in combined or "pix" in combined or "account" in combined:
            return "method_account_issue"
        return f"unknown: {oracle_result.message[:100]}"

    def _classify_denial_from_raw(self, resp: dict) -> str:
        """Extract denial reason from a raw scraper response."""
        msg = str(resp.get("message", "")).lower()
        code = str(resp.get("code", "")).lower()
        combined = f"{code} {msg}"

        if "insufficient" in combined or "balance" in combined:
            return "insufficient_balance"
        if "frequency" in combined or "limit" in combined or "cooldown" in combined:
            return "frequency_limit"
        if "review" in combined or "manual" in combined:
            return "manual_review"
        if "method" in combined or "pix" in combined or "account" in combined:
            return "method_account_issue"
        return f"unknown: {resp.get('message', '')[:100]}"
