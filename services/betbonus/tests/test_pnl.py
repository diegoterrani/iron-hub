"""Tests for CampaignPnL (Phase 2)."""

from __future__ import annotations

import pytest

from src.factory.pnl import AccountPnL, CampaignPnL

# --- AccountPnL ---

def test_account_pnl_defaults():
    acct = AccountPnL(account_id="a1", platform="pagol", identity_name="John")
    assert acct.bonus_acquired == 0.0
    assert acct.withdrawal_status == "pending"
    assert acct.total_cost == 0.0
    assert acct.timestamps == {}


def test_account_pnl_to_dict():
    acct = AccountPnL(
        account_id="a1", platform="pagol", identity_name="John",
        bonus_acquired=100.0, withdrawn=50.0, withdrawal_status="materialized",
    )
    d = acct.to_dict()
    assert d["account_id"] == "a1"
    assert d["bonus_acquired"] == 100.0
    assert d["withdrawn"] == 50.0
    assert d["withdrawal_status"] == "materialized"


# --- CampaignPnL mutators ---

def _make_acct(acct_id: str, **kwargs) -> AccountPnL:
    defaults = {"account_id": acct_id, "platform": "pagol", "identity_name": f"User {acct_id}"}
    defaults.update(kwargs)
    return AccountPnL(**defaults)


def test_add_account():
    pnl = CampaignPnL(campaign_id="op-1")
    pnl.add_account(_make_acct("a1"))
    pnl.add_account(_make_acct("a2"))
    assert pnl.total_accounts == 2


def test_remove_account():
    pnl = CampaignPnL(campaign_id="op-1")
    pnl.add_account(_make_acct("a1"))
    pnl.add_account(_make_acct("a2"))
    assert pnl.remove_account("a1") is True
    assert pnl.total_accounts == 1
    assert pnl.remove_account("nonexistent") is False


def test_update_account():
    pnl = CampaignPnL(campaign_id="op-1")
    pnl.add_account(_make_acct("a1", bonus_acquired=50.0))
    acct = pnl.update_account("a1", withdrawn=25.0, withdrawal_status="materialized")
    assert acct is not None
    assert acct.withdrawn == 25.0
    assert acct.withdrawal_status == "materialized"


def test_update_account_not_found():
    pnl = CampaignPnL(campaign_id="op-1")
    assert pnl.update_account("ghost", withdrawn=1.0) is None


# --- Aggregates ---

def test_total_bonus_acquired():
    pnl = CampaignPnL()
    pnl.add_account(_make_acct("a1", bonus_acquired=100.0))
    pnl.add_account(_make_acct("a2", bonus_acquired=200.0))
    assert pnl.total_bonus_acquired == 300.0


def test_total_wagered():
    pnl = CampaignPnL()
    pnl.add_account(_make_acct("a1", wagered=500.0))
    pnl.add_account(_make_acct("a2", wagered=300.0))
    assert pnl.total_wagered == 800.0


def test_total_extracted_only_materialized():
    pnl = CampaignPnL()
    pnl.add_account(_make_acct("a1", withdrawn=100.0, withdrawal_status="materialized"))
    pnl.add_account(_make_acct("a2", withdrawn=200.0, withdrawal_status="pending"))
    pnl.add_account(_make_acct("a3", withdrawn=50.0, withdrawal_status="denied"))
    assert pnl.total_extracted == 100.0


def test_net_profit():
    pnl = CampaignPnL()
    pnl.add_account(_make_acct("a1", withdrawn=100.0, withdrawal_status="materialized", total_cost=20.0))
    pnl.add_account(_make_acct("a2", withdrawn=0.0, withdrawal_status="denied", total_cost=10.0))
    assert pnl.net_profit == 70.0


def test_success_rate():
    pnl = CampaignPnL()
    pnl.add_account(_make_acct("a1", withdrawal_status="materialized"))
    pnl.add_account(_make_acct("a2", withdrawal_status="materialized"))
    pnl.add_account(_make_acct("a3", withdrawal_status="denied"))
    pnl.add_account(_make_acct("a4", withdrawal_status="pending"))
    assert pnl.success_rate == pytest.approx(0.5)


def test_success_rate_empty():
    pnl = CampaignPnL()
    assert pnl.success_rate == 0.0


def test_pending_count():
    pnl = CampaignPnL()
    pnl.add_account(_make_acct("a1", withdrawal_status="pending"))
    pnl.add_account(_make_acct("a2", withdrawal_status="materialized"))
    assert pnl.pending_count == 1


def test_denied_count():
    pnl = CampaignPnL()
    pnl.add_account(_make_acct("a1", withdrawal_status="denied"))
    pnl.add_account(_make_acct("a2", withdrawal_status="denied"))
    pnl.add_account(_make_acct("a3", withdrawal_status="pending"))
    assert pnl.denied_count == 2


# --- Summary / serialization ---

def test_summary():
    pnl = CampaignPnL(campaign_id="op-test")
    pnl.add_account(_make_acct("a1", bonus_acquired=100.0, wagered=500.0,
                               withdrawn=80.0, withdrawal_status="materialized",
                               total_cost=10.0))
    s = pnl.summary()
    assert s["campaign_id"] == "op-test"
    assert s["total_accounts"] == 1
    assert s["total_bonus_acquired"] == 100.0
    assert s["total_extracted"] == 80.0
    assert s["net_profit"] == 70.0
    assert s["success_rate"] == 1.0


def test_to_dict():
    pnl = CampaignPnL(campaign_id="op-test")
    pnl.add_account(_make_acct("a1", bonus_acquired=50.0))
    d = pnl.to_dict()
    assert d["campaign_id"] == "op-test"
    assert "summary" in d
    assert "accounts" in d
    assert len(d["accounts"]) == 1
    assert d["accounts"][0]["account_id"] == "a1"
