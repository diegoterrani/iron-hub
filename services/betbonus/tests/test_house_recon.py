"""Tests for HouseProfile, HouseRecon, and capability detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.abuse.house_profile import (
    CAPABILITY_KEYS,
    HouseProfile,
    HouseRecon,
    detect_capabilities,
)


# ---------------------------------------------------------------------------
# HouseProfile
# ---------------------------------------------------------------------------


def test_profile_has_method():
    p = HouseProfile(platform="test", capabilities={"withdraw": True, "scrape_live": False})
    assert p.has("withdraw") is True
    assert p.has("scrape_live") is False
    assert p.has("nonexistent") is False


def test_profile_recommended_stage():
    p = HouseProfile(platform="test", recommended_stages=["recon", "cashout", "report"])
    assert p.recommended_stage("recon") is True
    assert p.recommended_stage("arm") is False


def test_profile_to_dict():
    p = HouseProfile(platform="test", min_withdraw=25, currency="BRL", uses_cents=True)
    d = p.to_dict()
    assert d["platform"] == "test"
    assert d["min_withdraw"] == 25
    assert d["currency"] == "BRL"
    assert d["uses_cents"] is True


def test_profile_defaults():
    p = HouseProfile(platform="x")
    assert p.max_withdraw == 10_000.0
    assert p.uses_cents is False
    assert p.withdraw_methods == []
    assert p.capabilities == {}
    assert p.recommended_stages == []


# ---------------------------------------------------------------------------
# detect_capabilities
# ---------------------------------------------------------------------------


def test_detect_capabilities_full():
    scraper = MagicMock()
    scraper.validate_token = MagicMock()
    scraper.get_wallet_snapshot = MagicMock()
    scraper.withdraw = MagicMock()
    scraper.withdraw_preflight = MagicMock()
    # All other methods are MagicMock auto-attrs (callable)
    caps = detect_capabilities(scraper)
    assert isinstance(caps, dict)
    assert set(caps.keys()) == set(CAPABILITY_KEYS)
    assert caps["validate_token"] is True
    assert caps["get_wallet_snapshot"] is True
    assert caps["withdraw"] is True


def test_detect_capabilities_none():
    """A bare object with no methods should have all capabilities False."""

    class BareScraper:
        pass

    caps = detect_capabilities(BareScraper())
    assert all(v is False for v in caps.values())


# ---------------------------------------------------------------------------
# HouseRecon
# ---------------------------------------------------------------------------


def _make_scraper(
    *,
    platform: str = "test_house",
    balance: float = 100.0,
    bonus: float = 0.0,
    rollover: float = 0.0,
    withdraw_methods: list[str] | None = None,
    min_withdraw: float | None = None,
    has_withdraw: bool = True,
    has_promocodes: bool = True,
    has_bonuses: bool = True,
) -> MagicMock:
    """Build a mock scraper with configurable capabilities."""
    s = MagicMock()
    s.platform = platform

    # Wallet
    from src.models.abuse import WalletSnapshot

    wallet = WalletSnapshot(platform=platform, balance=balance, bonus=bonus, rollover=rollover)
    s.get_wallet_snapshot.return_value = wallet

    # Withdraw
    if has_withdraw:
        s.withdraw = MagicMock(return_value={"code": "SUCCESS"})
        s.withdraw_preflight = MagicMock(
            return_value={"methods": withdraw_methods or ["PIX"], "have_opened": False}
        )
        s.poll_withdrawal_settlement = MagicMock(return_value={"settled": True})
        s.list_withdrawals = MagicMock(return_value=[])
    else:
        s.withdraw = None
        s.withdraw_preflight = None
        s.poll_withdrawal_settlement = None
        s.list_withdrawals = None

    # Promocodes
    if has_promocodes:
        s.list_enabled_promocodes = MagicMock(return_value=["CODE1", "CODE2"])
        s.redeem_promocode = MagicMock(return_value={"ok": True})
    else:
        s.list_enabled_promocodes = None
        s.redeem_promocode = None

    # Bonuses
    if has_bonuses:
        s.list_bonuses = MagicMock(return_value=[{"id": 1}, {"id": 2}])
        s.list_my_bonuses = MagicMock(return_value=[{"id": 1}])
    else:
        s.list_bonuses = None
        s.list_my_bonuses = None

    # Auth
    s.validate_token = MagicMock(return_value={"user": {"phone": "5511999999999"}})

    # No LLM-dependent methods by default
    s.run_bonus_multiplier_lab = None
    s.probe_slots_for_bonus = None
    s.probe_high_ev_contribution = None
    s.get_bonus_conversion_state = None
    s.scrape_live = None
    s.claim_or_activate_bonus = None

    # Scraper class-level attrs (avoid Pydantic MagicMock warnings)
    s.CURRENCY = "BRL"
    s.MAX_WITHDRAW_AMOUNT = 10_000.0
    s.AMOUNT_SCALE = 1
    s.MIN_WITHDRAW_AMOUNT = None

    return s


def test_recon_detects_capabilities(tmp_path: Path):
    scraper = _make_scraper(platform="test_house")
    recon = HouseRecon(scraper, cache_dir=tmp_path)
    profile = recon.run(use_llm=False, refresh=False)

    assert profile.platform == "test_house"
    assert profile.has("withdraw") is True
    assert profile.has("withdraw_preflight") is True
    assert profile.has("list_enabled_promocodes") is True
    assert profile.has("run_bonus_multiplier_lab") is False
    assert profile.has("scrape_live") is False


def test_recon_recommended_stages_basic(tmp_path: Path):
    """A house with withdraw+promocodes+bonuses should get recon/acquire/cashout/report."""
    scraper = _make_scraper(platform="test_house")
    recon = HouseRecon(scraper, cache_dir=tmp_path)
    profile = recon.run(use_llm=False, refresh=False)

    stages = profile.recommended_stages
    assert "recon" in stages
    assert "report" in stages
    assert "acquire" in stages  # has redeem_promocode + list_enabled_promocodes
    assert "cashout" in stages  # has withdraw
    assert "arm" not in stages  # no run_bonus_multiplier_lab
    assert "probe" not in stages  # no probe_high_ev_contribution


def test_recon_with_arm_capabilities(tmp_path: Path):
    scraper = _make_scraper(platform="test_house")
    scraper.run_bonus_multiplier_lab = MagicMock(return_value={"ok": True})
    recon = HouseRecon(scraper, cache_dir=tmp_path)
    profile = recon.run(use_llm=False, refresh=False)

    assert "arm" in profile.recommended_stages


def test_recon_with_probe_capabilities(tmp_path: Path):
    scraper = _make_scraper(platform="test_house")
    scraper.probe_high_ev_contribution = MagicMock(return_value={"probed": 1})
    recon = HouseRecon(scraper, cache_dir=tmp_path)
    profile = recon.run(use_llm=False, refresh=False)

    assert "probe" in profile.recommended_stages


def test_recon_no_withdraw_no_cashout(tmp_path: Path):
    scraper = _make_scraper(platform="test_house", has_withdraw=False)
    recon = HouseRecon(scraper, cache_dir=tmp_path)
    profile = recon.run(use_llm=False, refresh=False)

    assert "cashout" not in profile.recommended_stages


def test_recon_caches_to_disk(tmp_path: Path):
    scraper = _make_scraper(platform="cache_test")
    recon = HouseRecon(scraper, cache_dir=tmp_path)
    profile = recon.run(use_llm=False, refresh=False)

    cache_file = tmp_path / "cache_test.json"
    assert cache_file.exists()
    cached = json.loads(cache_file.read_text())
    assert cached["platform"] == "cache_test"
    assert "capabilities" in cached


def test_recon_reads_cache(tmp_path: Path):
    """Second run should read from cache, not re-detect."""
    scraper = _make_scraper(platform="cache_test2")
    recon = HouseRecon(scraper, cache_dir=tmp_path)
    profile1 = recon.run(use_llm=False, refresh=False)

    # Modify scraper to have different capabilities
    scraper2 = _make_scraper(platform="cache_test2", has_withdraw=False)
    recon2 = HouseRecon(scraper2, cache_dir=tmp_path)
    profile2 = recon2.run(use_llm=False, refresh=False)

    # Should be same as first (from cache)
    assert profile2.has("withdraw") == profile1.has("withdraw")


def test_recon_refresh_bypasses_cache(tmp_path: Path):
    scraper = _make_scraper(platform="cache_test3")
    recon = HouseRecon(scraper, cache_dir=tmp_path)
    profile1 = recon.run(use_llm=False, refresh=False)

    # Remove withdraw capability
    scraper.withdraw = None
    scraper.withdraw_preflight = None
    profile2 = recon.run(use_llm=False, refresh=True)

    assert profile2.has("withdraw") is False


def test_recon_llm_disabled(tmp_path: Path):
    scraper = _make_scraper(platform="no_llm")
    recon = HouseRecon(scraper, cache_dir=tmp_path)
    profile = recon.run(use_llm=False, refresh=False)

    assert profile.llm_used is False
    assert profile.llm == {}


def test_recon_wallet_facts(tmp_path: Path):
    scraper = _make_scraper(platform="wallet_test", balance=500.0, bonus=100.0, rollover=5000.0)
    recon = HouseRecon(scraper, cache_dir=tmp_path)
    profile = recon.run(use_llm=False, refresh=False)

    assert profile.wallet.get("balance") == 500.0
    assert profile.wallet.get("bonus") == 100.0
    assert profile.wallet.get("rollover") == 5000.0


def test_recon_bonus_count(tmp_path: Path):
    scraper = _make_scraper(platform="bonus_count_test")
    recon = HouseRecon(scraper, cache_dir=tmp_path)
    profile = recon.run(use_llm=False, refresh=False)

    assert profile.bonus_count >= 1


def test_recon_promocode_count(tmp_path: Path):
    scraper = _make_scraper(platform="promo_count_test")
    recon = HouseRecon(scraper, cache_dir=tmp_path)
    profile = recon.run(use_llm=False, refresh=False)

    assert profile.promocode_count == 2
