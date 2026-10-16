"""Tests for BehavioralFingerprint (Phase 2)."""

from __future__ import annotations

import pytest

from src.factory.behavior import BehavioralFingerprint, BehavioralProfile

# --- generate_profile ---

def test_generate_profile_basic():
    fp = BehavioralFingerprint(seed=42)
    profile = fp.generate_profile("acct-1")
    assert profile.account_id == "acct-1"
    assert profile.seed > 0
    assert profile.session_duration_range[0] < profile.session_duration_range[1]
    assert profile.stake_pattern in ("steady", "variable", "aggressive")
    assert profile.user_agent != ""
    assert profile.device_info != {}


def test_generate_profile_deterministic():
    fp = BehavioralFingerprint(seed=42)
    p1 = fp.generate_profile("acct-1")
    p2 = fp.generate_profile("acct-1")
    assert p1.seed == p2.seed
    assert p1.session_duration_range == p2.session_duration_range
    assert p1.stake_pattern == p2.stake_pattern
    assert p1.user_agent == p2.user_agent


def test_generate_profile_unique_per_account():
    fp = BehavioralFingerprint(seed=42)
    p1 = fp.generate_profile("acct-1")
    p2 = fp.generate_profile("acct-2")
    assert p1.seed != p2.seed


def test_generate_profile_device_info():
    fp = BehavioralFingerprint(seed=42)
    profile = fp.generate_profile("acct-1")
    di = profile.device_info
    assert "os" in di
    assert "browser" in di
    assert "is_mobile" in di
    assert "screen" in di
    assert "device_type" in di
    assert di["screen"]["width"] > 0
    assert di["screen"]["height"] > 0


# --- session_duration ---

def test_session_duration_in_range():
    fp = BehavioralFingerprint(seed=42)
    profile = fp.generate_profile("acct-1")
    lo, hi = profile.session_duration_range
    for _ in range(20):
        d = fp.session_duration(profile)
        assert lo <= d <= hi


# --- inter_bet_delay ---

def test_inter_bet_delay_positive():
    fp = BehavioralFingerprint(seed=42)
    profile = fp.generate_profile("acct-1")
    for _ in range(20):
        d = fp.inter_bet_delay(profile)
        assert d >= 0.5


# --- bet_stake_sequence ---

def test_bet_stake_sequence_length():
    fp = BehavioralFingerprint(seed=42)
    profile = fp.generate_profile("acct-1")
    stakes = fp.bet_stake_sequence(profile, base_stake=1.0, n=10)
    assert len(stakes) == 10


def test_bet_stake_sequence_starts_with_base():
    fp = BehavioralFingerprint(seed=42)
    profile = fp.generate_profile("acct-1")
    stakes = fp.bet_stake_sequence(profile, base_stake=2.5, n=5)
    assert stakes[0] == 2.5


def test_bet_stake_sequence_positive():
    fp = BehavioralFingerprint(seed=42)
    profile = fp.generate_profile("acct-1")
    stakes = fp.bet_stake_sequence(profile, base_stake=1.0, n=20)
    assert all(s > 0 for s in stakes)


# --- idle_gaps ---

def test_idle_gaps_count():
    fp = BehavioralFingerprint(seed=42)
    profile = fp.generate_profile("acct-1")
    gaps = fp.idle_gaps(profile, total_duration=3600.0)
    assert 2 <= len(gaps) <= 4


def test_idle_gaps_sorted():
    fp = BehavioralFingerprint(seed=42)
    profile = fp.generate_profile("acct-1")
    gaps = fp.idle_gaps(profile, total_duration=3600.0)
    offsets = [g[0] for g in gaps]
    assert offsets == sorted(offsets)


# --- activity_window ---

def test_activity_window_returns_datetimes():
    from datetime import datetime
    fp = BehavioralFingerprint(seed=42)
    profile = fp.generate_profile("acct-1")
    start_dt, end_dt = fp.activity_window(profile)
    assert isinstance(start_dt, datetime)
    assert isinstance(end_dt, datetime)
    assert end_dt > start_dt


# --- to_dict ---

def test_to_dict():
    fp = BehavioralFingerprint(seed=42)
    profile = fp.generate_profile("acct-1")
    d = fp.to_dict(profile)
    assert d["account_id"] == "acct-1"
    assert d["stake_pattern"] in ("steady", "variable", "aggressive")
    assert "user_agent" in d
    assert "device_info" in d
    assert len(d["session_duration_range"]) == 2
