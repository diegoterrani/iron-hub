"""Tests for Withdrawal Orchestrator + TLS Fingerprint (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import pytest

from src.abuse.withdraw_orchestrator import WithdrawalOrchestrator, WithdrawalPlan
from src.factory.tls import TLSFingerprintManager, BrowserFingerprint
from src.models.abuse import WalletSnapshot, ConversionStatus


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeScraper:
    def __init__(self, wallet: WalletSnapshot):
        self._wallet = wallet
        self.withdrawals_made: list[dict] = []

    def get_wallet_snapshot(self) -> WalletSnapshot:
        return self._wallet

    def withdraw(self, amount: float, method: str = "PIX", **kw: Any) -> dict:
        self.withdrawals_made.append({"amount": amount, "method": method})
        self._wallet = WalletSnapshot(
            platform=self._wallet.platform,
            balance=round(self._wallet.balance - amount, 2),
            bonus=self._wallet.bonus,
            rollover=self._wallet.rollover,
        )
        return {"ok": True, "amount": amount, "status": "PENDING"}

    def withdraw_preflight(self) -> dict:
        return {"have_opened": False, "withdrawal_allowed": True, "methods": ["PIX"]}

    def poll_withdrawal_settlement(self, **kw: Any) -> dict:
        return {"status": "materialized", "terminal": True}

    def list_withdrawals(self, **kw: Any) -> list:
        return self.withdrawals_made


# ---------------------------------------------------------------------------
# WithdrawalOrchestrator — build_plan
# ---------------------------------------------------------------------------

def test_build_plan_single_withdraw():
    wallet = WalletSnapshot(balance=100, bonus=0, rollover=0)
    orch = WithdrawalOrchestrator(scraper=FakeScraper(wallet))
    plan = orch.build_plan(wallet, max_convert=100.0)
    assert len(plan.withdrawals) == 1
    assert plan.withdrawals[0]["amount"] <= 100.0
    # Should be ~95% of max
    assert plan.withdrawals[0]["amount"] >= 80.0


def test_build_plan_split():
    wallet = WalletSnapshot(balance=1500, bonus=0, rollover=0)
    orch = WithdrawalOrchestrator(scraper=FakeScraper(wallet))
    plan = orch.build_plan(wallet, max_convert=1500.0, split_threshold=1000.0)
    assert len(plan.withdrawals) >= 2
    # First withdrawal should be smaller
    assert plan.withdrawals[0]["amount"] < plan.withdrawals[1]["amount"]


def test_build_plan_small_balance():
    wallet = WalletSnapshot(balance=25, bonus=0, rollover=0)
    orch = WithdrawalOrchestrator(scraper=FakeScraper(wallet))
    plan = orch.build_plan(wallet, max_convert=25.0)
    assert len(plan.withdrawals) == 1
    assert plan.withdrawals[0]["amount"] <= 25.0


# ---------------------------------------------------------------------------
# WithdrawalOrchestrator — execute
# ---------------------------------------------------------------------------

def test_execute_single():
    wallet = WalletSnapshot(balance=100, bonus=0, rollover=0)
    scraper = FakeScraper(wallet)
    orch = WithdrawalOrchestrator(scraper=scraper)
    result = orch.execute_single(amount=50.0, method="PIX", confirm=True)
    assert result["ok"] is True
    assert len(scraper.withdrawals_made) == 1
    assert scraper.withdrawals_made[0]["amount"] == 50.0


def test_execute_plan():
    wallet = WalletSnapshot(balance=200, bonus=0, rollover=0)
    scraper = FakeScraper(wallet)
    orch = WithdrawalOrchestrator(scraper=scraper)
    plan = orch.build_plan(wallet, max_convert=200.0)
    results = orch.execute(plan, confirm=True)
    assert len(results) >= 1
    assert all(r["ok"] for r in results)


# ---------------------------------------------------------------------------
# WithdrawalOrchestrator — denial handling
# ---------------------------------------------------------------------------

def test_handle_denial_retry():
    wallet = WalletSnapshot(balance=100, bonus=0, rollover=0)
    orch = WithdrawalOrchestrator(scraper=FakeScraper(wallet))
    denied_result = {
        "ok": False,
        "status": "denied",
        "message": "BO denied",
        "amount": 100.0,
    }
    action = orch.handle_denial(denied_result, attempt=1)
    assert "action" in action
    assert action["action"] in ("retry", "wait", "reduce", "manual")


# ---------------------------------------------------------------------------
# TLSFingerprintManager
# ---------------------------------------------------------------------------

def test_generate_fingerprint():
    mgr = TLSFingerprintManager(seed=42)
    fp = mgr.generate_fingerprint("acct-1")
    assert fp.user_agent.startswith("Mozilla/5.0")
    assert "Chrome" in fp.user_agent
    assert fp.accept_language
    assert fp.sec_ch_ua


def test_fingerprint_unique_per_account():
    mgr = TLSFingerprintManager(seed=42)
    fp1 = mgr.generate_fingerprint("acct-1")
    fp2 = mgr.generate_fingerprint("acct-2")
    # UAs may be same (from pool) but full fingerprint should differ
    d1 = mgr.headers_dict(fp1)
    d2 = mgr.headers_dict(fp2)
    # At least one header should differ
    assert any(d1.get(k) != d2.get(k) for k in d1) or fp1.user_agent != fp2.user_agent


def test_user_agent_pool():
    mgr = TLSFingerprintManager(seed=42)
    pool = mgr.user_agent_pool()
    assert len(pool) >= 10
    assert all("Chrome" in ua for ua in pool)


def test_validate_fingerprint():
    mgr = TLSFingerprintManager(seed=42)
    fp = mgr.generate_fingerprint("acct-1")
    assert mgr.validate_fingerprint(fp) is True


def test_headers_dict():
    mgr = TLSFingerprintManager(seed=42)
    fp = mgr.generate_fingerprint("acct-1")
    h = mgr.headers_dict(fp)
    assert "User-Agent" in h
    assert "Accept-Language" in h
    assert "Sec-Ch-Ua" in h


def test_create_session():
    mgr = TLSFingerprintManager(seed=42)
    session = mgr.create_session("acct-1")
    assert session is not None
    # Should be a requests.Session or curl_cffi Session
    assert hasattr(session, "headers")
