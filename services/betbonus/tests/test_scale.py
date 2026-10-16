"""Tests for Scale Orchestrator modules (Phase 2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.factory.behavior import BehavioralFingerprint, BehavioralProfile
from src.factory.scheduler import TimingScheduler, ScheduledEvent
from src.factory.pnl import CampaignPnL, AccountPnL


# ---------------------------------------------------------------------------
# BehavioralFingerprint
# ---------------------------------------------------------------------------

def test_generate_profile_unique():
    fp = BehavioralFingerprint(seed=42)
    p1 = fp.generate_profile("acct-1")
    p2 = fp.generate_profile("acct-2")
    assert p1.account_id == "acct-1"
    assert p2.account_id == "acct-2"
    # Profiles should differ (different RNG draws)
    assert p1.session_duration_range != p2.session_duration_range or \
           p1.inter_bet_delay != p2.inter_bet_delay


def test_session_duration_in_range():
    fp = BehavioralFingerprint(seed=42)
    p = fp.generate_profile("acct-1")
    for _ in range(50):
        d = fp.session_duration(p)
        assert p.session_duration_range[0] <= d <= p.session_duration_range[1]


def test_inter_bet_delay_in_range():
    fp = BehavioralFingerprint(seed=42)
    p = fp.generate_profile("acct-1")
    for _ in range(50):
        d = fp.inter_bet_delay(p)
        assert d > 0


def test_bet_stake_sequence_length():
    fp = BehavioralFingerprint(seed=42)
    p = fp.generate_profile("acct-1")
    stakes = fp.bet_stake_sequence(p, base_stake=5.0, n=20)
    assert len(stakes) == 20
    assert all(s > 0 for s in stakes)


def test_activity_window_valid():
    fp = BehavioralFingerprint(seed=42)
    p = fp.generate_profile("acct-1")
    start_h, end_h = p.activity_window
    assert 0 <= start_h <= 23
    assert 0 <= end_h <= 23


def test_profile_to_dict():
    fp = BehavioralFingerprint(seed=42)
    p = fp.generate_profile("acct-1")
    d = fp.to_dict(p)
    assert d["account_id"] == "acct-1"
    assert "session_duration_range" in d


# ---------------------------------------------------------------------------
# TimingScheduler
# ---------------------------------------------------------------------------

def test_schedule_registration_staggered():
    sched = TimingScheduler(min_gap_minutes=10)
    ids = ["a", "b", "c", "d", "e"]
    events = sched.schedule_registration(ids)
    assert len(events) == 5
    # Events should be in chronological order
    times = [e.scheduled_at for e in events]
    assert times == sorted(times)
    # Minimum gap between consecutive events
    for i in range(1, len(times)):
        gap = (times[i] - times[i - 1]).total_seconds() / 60
        assert gap >= 5  # at least 5 min apart


def test_schedule_withdrawal_no_overlap():
    sched = TimingScheduler(min_gap_minutes=30)
    ids = ["a", "b", "c"]
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    cleared = {aid: now for aid in ids}
    events = sched.schedule_withdrawal(ids, cleared)
    assert len(events) == 3
    times = [e.scheduled_at for e in events]
    for i in range(1, len(times)):
        gap = (times[i] - times[i - 1]).total_seconds() / 60
        assert gap >= 29  # ~30 min gap


def test_next_event_and_complete():
    sched = TimingScheduler()
    ids = ["a", "b"]
    events = sched.schedule_registration(ids)
    nxt = sched.next_event()
    assert nxt is not None
    assert nxt.account_id in ("a", "b")
    sched.complete_event(nxt.event_id)
    nxt2 = sched.next_event()
    assert nxt2 is not None
    assert nxt2.event_id != nxt.event_id


def test_cancel_event():
    sched = TimingScheduler()
    ids = ["a", "b"]
    events = sched.schedule_registration(ids)
    sched.cancel_event(events[0].event_id)
    remaining = sched.pending_events()
    assert len(remaining) == 1


def test_campaign_timeline():
    sched = TimingScheduler()
    ids = ["a", "b", "c"]
    sched.schedule_registration(ids)
    tl = sched.campaign_timeline()
    assert tl["total_events"] == 3
    assert "first_event" in tl
    assert "last_event" in tl


# ---------------------------------------------------------------------------
# CampaignPnL
# ---------------------------------------------------------------------------

def test_add_account():
    pnl = CampaignPnL(campaign_id="test")
    acct = AccountPnL(
        account_id="a1",
        platform="pagol_bet_br",
        identity_name="João Silva",
        bonus_acquired=50.0,
    )
    pnl.add_account(acct)
    assert pnl.total_accounts == 1


def test_pnl_computation():
    pnl = CampaignPnL(campaign_id="test")
    acct = AccountPnL(
        account_id="a1",
        platform="pagol_bet_br",
        identity_name="João Silva",
        bonus_acquired=50.0,
        wagered=250.0,
        house_edge_loss=2.5,
        net_extractable=47.5,
        withdrawn=45.0,
        withdrawal_status="materialized",
        deposit_cost=5.0,
        proxy_cost=2.0,
    )
    acct.total_cost = acct.deposit_cost + acct.proxy_cost
    acct.net_profit = acct.withdrawn - acct.total_cost
    pnl.add_account(acct)
    assert pnl.total_extracted == pytest.approx(45.0)
    assert pnl.total_cost == pytest.approx(7.0)
    assert pnl.net_profit == pytest.approx(38.0)
    assert pnl.success_rate == 1.0


def test_pnl_denied_not_counted():
    pnl = CampaignPnL(campaign_id="test")
    acct = AccountPnL(
        account_id="a1",
        platform="pagol_bet_br",
        identity_name="Test",
        bonus_acquired=50.0,
        withdrawn=0.0,
        withdrawal_status="denied",
    )
    pnl.add_account(acct)
    assert pnl.total_extracted == 0.0
    assert pnl.success_rate == 0.0


def test_pnl_summary():
    pnl = CampaignPnL(campaign_id="test")
    for i in range(3):
        acct = AccountPnL(
            account_id=f"a{i}",
            platform="pagol_bet_br",
            identity_name=f"User {i}",
            bonus_acquired=50.0,
            withdrawn=45.0 if i < 2 else 0.0,
            withdrawal_status="materialized" if i < 2 else "pending",
            deposit_cost=5.0,
        )
        acct.total_cost = acct.deposit_cost
        acct.net_profit = acct.withdrawn - acct.total_cost
        pnl.add_account(acct)
    s = pnl.summary()
    assert s["total_accounts"] == 3
    assert s["total_extracted"] == pytest.approx(90.0)
    assert s["success_rate"] == pytest.approx(2 / 3)
