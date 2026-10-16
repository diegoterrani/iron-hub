"""Tests for CampaignRunner (Phase 4)."""

from __future__ import annotations

import pytest

from src.factory.campaign_runner import (
    CampaignConfig,
    CampaignRunner,
    CampaignReport,
    CampaignAccountStatus,
    STAGE_PENDING,
    STAGE_REGISTERED,
    STAGE_WAGERED,
    STAGE_WITHDRAWN,
    STAGE_FAILED,
)


class _FakeIdentity:
    def __init__(self, email, name):
        self.email = email
        self.full_name = name


class _FakeIdentities:
    def __init__(self):
        self._idx = 0

    def generate_batch(self, n):
        return [_FakeIdentity(f"user{i}@test.com", f"User {i}") for i in range(n)]

    def generate(self):
        self._idx += 1
        return _FakeIdentity(f"retry{self._idx}@test.com", f"Retry {self._idx}")


class _FakeFactory:
    def __init__(self, success=True):
        self.identities = _FakeIdentities()
        self._success = success

    def create_account(self, identity, platform):
        class _R:
            success = self._success
            token = "tok-123"
            error = "" if self._success else "reg failed"
        return _R()


class _FakeEngine:
    def wager(self, platform, token, email, method="api"):
        return {"balance": 100.0, "wagered": 500.0}

    def claim_bonus(self, platform, token, email):
        return {"bonus_amount": 50.0, "balance": 150.0}


class _FakeOrchestrator:
    def withdraw(self, platform, token, email, amount, split=True):
        return {"withdrawn": amount * 0.9}


# --- CampaignConfig ---

def test_campaign_config_defaults():
    cfg = CampaignConfig()
    assert cfg.accounts == 10
    assert cfg.max_parallel == 4
    assert cfg.retry_failed is True
    assert cfg.dry_run is False
    d = cfg.to_dict()
    assert d["accounts"] == 10


# --- run (dry_run) ---

def test_run_dry_run():
    factory = _FakeFactory()
    runner = CampaignRunner(factory)
    cfg = CampaignConfig(accounts=3, dry_run=True)
    report = runner.run(cfg)
    assert len(report.accounts) == 3
    assert report.success_rate == 1.0
    for acct in report.accounts:
        assert acct.stage == STAGE_WAGERED
        assert acct.withdrawn > 0


# --- run (full pipeline with mocks) ---

def test_run_full_pipeline():
    factory = _FakeFactory(success=True)
    runner = CampaignRunner(factory, engine=_FakeEngine(), orchestrator=_FakeOrchestrator())
    cfg = CampaignConfig(accounts=2, dry_run=False, retry_failed=False)
    report = runner.run(cfg)
    assert len(report.accounts) == 2
    for acct in report.accounts:
        assert acct.stage == STAGE_WITHDRAWN
        assert acct.withdrawn > 0
    assert report.total_extracted > 0


# --- run (registration failure) ---

def test_run_registration_failure():
    factory = _FakeFactory(success=False)
    runner = CampaignRunner(factory, engine=_FakeEngine())
    cfg = CampaignConfig(accounts=2, dry_run=False, retry_failed=False)
    report = runner.run(cfg)
    for acct in report.accounts:
        assert acct.stage == STAGE_FAILED
        assert "Registration failed" in acct.error
    assert report.success_rate == 0.0


# --- retry logic ---

def test_retry_failed_accounts():
    factory = _FakeFactory(success=True)
    runner = CampaignRunner(factory, engine=_FakeEngine())
    # First run: simulate failure by using a factory that fails first time
    class _FlakyFactory(_FakeFactory):
        def __init__(self):
            super().__init__(success=False)
            self._calls = 0
            self.identities = _FakeIdentities()

        def create_account(self, identity, platform):
            self._calls += 1
            class _R:
                success = self._calls > 2  # fail first 2, succeed after
                token = "tok"
                error = "" if self._calls > 2 else "fail"
            return _R()

    flaky = _FlakyFactory()
    runner = CampaignRunner(flaky, engine=_FakeEngine())
    cfg = CampaignConfig(accounts=2, dry_run=False, retry_failed=True, max_retries=2)
    report = runner.run(cfg)
    # After retries, at least some should succeed
    assert report.success_rate > 0.0


# --- P&L computation ---

def test_compute_pnl():
    factory = _FakeFactory(success=True)
    runner = CampaignRunner(factory, engine=_FakeEngine(), orchestrator=_FakeOrchestrator())
    cfg = CampaignConfig(accounts=2, dry_run=False, retry_failed=False)
    report = runner.run(cfg)
    assert report.total_extracted > 0
    assert report.total_cost > 0
    assert report.net_profit == round(report.total_extracted - report.total_cost, 2)


# --- progress ---

def test_progress_empty():
    factory = _FakeFactory()
    runner = CampaignRunner(factory)
    report = CampaignReport(campaign_id="test", config=CampaignConfig())
    p = runner.progress(report)
    assert p["total"] == 0
    assert p["pct"] == 0.0


def test_progress_populated():
    factory = _FakeFactory()
    runner = CampaignRunner(factory)
    cfg = CampaignConfig()
    report = CampaignReport(
        campaign_id="test", config=cfg,
        accounts=[
            CampaignAccountStatus(account_id="a1", platform="p", identity_name="U1", stage=STAGE_WITHDRAWN),
            CampaignAccountStatus(account_id="a2", platform="p", identity_name="U2", stage=STAGE_FAILED),
            CampaignAccountStatus(account_id="a3", platform="p", identity_name="U3", stage=STAGE_PENDING),
        ],
    )
    p = runner.progress(report)
    assert p["total"] == 3
    assert p["completed"] == 1
    assert p["failed"] == 1
    assert p["in_progress"] == 1


# --- CampaignReport serialization ---

def test_report_to_dict():
    cfg = CampaignConfig()
    report = CampaignReport(campaign_id="c1", config=cfg,
                            accounts=[CampaignAccountStatus(
                                account_id="a1", platform="p", identity_name="U")])
    d = report.to_dict()
    assert d["campaign_id"] == "c1"
    assert len(d["accounts"]) == 1
    assert "config" in d
