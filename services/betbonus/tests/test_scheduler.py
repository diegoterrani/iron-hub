"""Tests for TimingScheduler (Phase 2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.factory.scheduler import ScheduledEvent, TimingScheduler

# --- ScheduledEvent ---

def test_scheduled_event_defaults():
    dt = datetime.now(timezone.utc)
    evt = ScheduledEvent(
        event_id="evt-001",
        account_id="acct-1",
        action="register",
        scheduled_at=dt,
    )
    assert evt.priority == 0
    assert evt.metadata == {}
    assert evt.completed is False


# --- schedule_registration ---

def test_schedule_registration_count():
    sched = TimingScheduler(seed=42)
    start = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)
    events = sched.schedule_registration(["a1", "a2", "a3"], start=start)
    assert len(events) == 3
    assert all(e.action == "register" for e in events)
    for i in range(len(events) - 1):
        assert events[i].scheduled_at <= events[i + 1].scheduled_at


def test_schedule_registration_weekday_window():
    sched = TimingScheduler(seed=42)
    start = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)  # Saturday
    events = sched.schedule_registration(["a1"], start=start)
    assert len(events) == 1
    local = events[0].scheduled_at.astimezone(sched.tz)
    assert local.weekday() < 5


def test_schedule_registration_min_gap():
    sched = TimingScheduler(seed=42, min_gap_minutes=30)
    start = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)
    events = sched.schedule_registration(["a1", "a2", "a3", "a4"], start=start)
    for i in range(len(events) - 1):
        gap = (events[i + 1].scheduled_at - events[i].scheduled_at).total_seconds()
        assert gap >= 29 * 60


# --- schedule_first_deposit ---

def test_schedule_first_deposit():
    sched = TimingScheduler(seed=42)
    reg_times = {
        "a1": datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc),
        "a2": datetime(2026, 9, 14, 16, 0, tzinfo=timezone.utc),
    }
    events = sched.schedule_first_deposit(["a1", "a2"], reg_times)
    assert len(events) == 2
    assert all(e.action == "deposit" for e in events)
    for evt in events:
        assert evt.scheduled_at > reg_times[evt.account_id]


def test_schedule_first_deposit_skips_missing():
    sched = TimingScheduler(seed=42)
    reg_times = {"a1": datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)}
    events = sched.schedule_first_deposit(["a1", "a2"], reg_times)
    assert len(events) == 1
    assert events[0].account_id == "a1"


# --- schedule_wagering ---

def test_schedule_wagering():
    sched = TimingScheduler(seed=42)
    act_times = {"a1": datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)}
    events = sched.schedule_wagering(["a1"], act_times)
    assert len(events) == 1
    assert events[0].action == "wager"
    delta = (events[0].scheduled_at - act_times["a1"]).total_seconds() / 3600
    assert 19 <= delta <= 73


# --- schedule_withdrawal ---

def test_schedule_withdrawal_window():
    sched = TimingScheduler(seed=42)
    cleared = {"a1": datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)}
    events = sched.schedule_withdrawal(["a1"], cleared)
    assert len(events) == 1
    assert events[0].action == "withdraw"
    local = events[0].scheduled_at.astimezone(sched.tz)
    assert 10 <= local.hour < 16


def test_schedule_withdrawal_min_gap():
    sched = TimingScheduler(seed=42, min_gap_minutes=30)
    cleared = {
        "a1": datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc),
        "a2": datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc),
    }
    events = sched.schedule_withdrawal(["a1", "a2"], cleared)
    if len(events) == 2:
        gap = (events[1].scheduled_at - events[0].scheduled_at).total_seconds()
        assert gap >= 29 * 60


# --- Query / lifecycle ---

def test_pending_events():
    sched = TimingScheduler(seed=42)
    start = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)
    sched.schedule_registration(["a1", "a2"], start=start)
    pending = sched.pending_events()
    assert len(pending) == 2
    assert pending[0].scheduled_at <= pending[1].scheduled_at


def test_next_event():
    sched = TimingScheduler(seed=42)
    assert sched.next_event() is None
    start = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)
    sched.schedule_registration(["a1"], start=start)
    nxt = sched.next_event()
    assert nxt is not None
    assert nxt.account_id == "a1"


def test_complete_event():
    sched = TimingScheduler(seed=42)
    start = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)
    events = sched.schedule_registration(["a1"], start=start)
    assert len(sched.pending_events()) == 1
    sched.complete_event(events[0].event_id)
    assert len(sched.pending_events()) == 0


def test_cancel_event():
    sched = TimingScheduler(seed=42)
    start = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)
    events = sched.schedule_registration(["a1", "a2"], start=start)
    assert len(sched.pending_events()) == 2
    sched.cancel_event(events[0].event_id)
    pending = sched.pending_events()
    assert len(pending) == 1
    assert pending[0].event_id == events[1].event_id


# --- campaign_timeline ---

def test_campaign_timeline_empty():
    sched = TimingScheduler(seed=42)
    tl = sched.campaign_timeline()
    assert tl["total_events"] == 0
    assert tl["first_event"] is None
    assert tl["last_event"] is None
    assert tl["events_per_day"] == {}


def test_campaign_timeline_populated():
    sched = TimingScheduler(seed=42)
    start = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)
    sched.schedule_registration(["a1", "a2"], start=start)
    tl = sched.campaign_timeline()
    assert tl["total_events"] == 2
    assert tl["first_event"] is not None
    assert tl["last_event"] is not None
    assert tl["events_per_day"]


# --- wait_for_next ---

def test_wait_for_next_empty():
    sched = TimingScheduler(seed=42)
    assert sched.wait_for_next(timeout_s=0.1) is None


def test_wait_for_next_past_event():
    sched = TimingScheduler(seed=42)
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    evt = ScheduledEvent(
        event_id="evt-past", account_id="a1",
        action="register", scheduled_at=past,
    )
    sched._add(evt)
    result = sched.wait_for_next(timeout_s=1.0)
    assert result is not None
    assert result.event_id == "evt-past"
