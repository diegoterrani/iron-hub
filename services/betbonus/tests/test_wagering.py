"""Tests for the Wagering Strategy Engine (Phase 1)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest

from src.abuse.wagering import (
    GameCandidate,
    WagerPlan,
    WagerResult,
    WageringStrategyEngine,
)
from src.models.abuse import WalletSnapshot


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeScraper:
    """Minimal scraper stub for wagering tests."""

    def __init__(self, wallet: WalletSnapshot):
        self._wallet = wallet
        self.bets_placed = 0

    def get_wallet_snapshot(self) -> WalletSnapshot:
        self.bets_placed += 1
        # Simulate small loss per bet (1% house edge)
        self._wallet = WalletSnapshot(
            platform=self._wallet.platform,
            balance=round(self._wallet.balance * 0.99, 2),
            bonus=self._wallet.bonus,
            rollover=max(0.0, self._wallet.rollover - 5.0),
        )
        return self._wallet

    def start_game(self, game_id: Any, mode: str = "REAL", **kw: Any) -> dict:
        return {"ok": True, "game_id": game_id}


# ---------------------------------------------------------------------------
# GameCandidate
# ---------------------------------------------------------------------------

def test_game_candidate_defaults():
    g = GameCandidate(game_id=1, name="Mines")
    assert g.rtp == pytest.approx(0.96)
    assert g.variance == "medium"
    assert g.eligible is True


def test_game_candidate_custom():
    g = GameCandidate(game_id=1624, name="Mines", provider="spribe", rtp=0.99, variance="low")
    assert g.provider == "spribe"
    assert g.rtp == 0.99
    assert g.variance == "low"


# ---------------------------------------------------------------------------
# WageringStrategyEngine — select_game
# ---------------------------------------------------------------------------

def test_select_game_prefers_low_variance_high_rtp():
    engine = WageringStrategyEngine(scraper=FakeScraper(WalletSnapshot(rollover=250)))
    candidates = [
        GameCandidate(game_id=1, name="Slots", rtp=0.96, variance="high"),
        GameCandidate(game_id=2, name="Mines", rtp=0.99, variance="low"),
        GameCandidate(game_id=3, name="Aviator", rtp=0.97, variance="medium"),
    ]
    best = engine.select_game(candidates, max_bet=5.0, rollover_remaining=250.0)
    assert best.game_id == 2  # Mines: lowest variance, highest RTP


def test_select_game_skips_ineligible():
    engine = WageringStrategyEngine(scraper=FakeScraper(WalletSnapshot(rollover=250)))
    candidates = [
        GameCandidate(game_id=1, name="Mines", rtp=0.99, variance="low", eligible=False),
        GameCandidate(game_id=2, name="Slots", rtp=0.96, variance="medium", eligible=True),
    ]
    best = engine.select_game(candidates, max_bet=5.0, rollover_remaining=250.0)
    assert best.game_id == 2


def test_select_game_empty_list():
    engine = WageringStrategyEngine(scraper=FakeScraper(WalletSnapshot(rollover=250)))
    with pytest.raises(ValueError):
        engine.select_game([], max_bet=5.0, rollover_remaining=250.0)


# ---------------------------------------------------------------------------
# WageringStrategyEngine — build_plan
# ---------------------------------------------------------------------------

def test_build_plan_rounds():
    wallet = WalletSnapshot(balance=50, bonus=50, rollover=250)
    engine = WageringStrategyEngine(scraper=FakeScraper(wallet))
    plan = engine.build_plan(wallet, max_bet=5.0)
    assert plan.rounds_needed >= 50  # 250 / 5 = 50
    assert plan.stake <= 5.0
    assert plan.expected_loss > 0


def test_build_plan_stake_capped_at_max_bet():
    wallet = WalletSnapshot(balance=50, bonus=50, rollover=250)
    engine = WageringStrategyEngine(scraper=FakeScraper(wallet))
    plan = engine.build_plan(wallet, max_bet=2.0)
    assert plan.stake <= 2.0


# ---------------------------------------------------------------------------
# WageringStrategyEngine — execute
# ---------------------------------------------------------------------------

def test_execute_clears_rollover():
    wallet = WalletSnapshot(balance=50, bonus=50, rollover=25)
    scraper = FakeScraper(wallet)
    engine = WageringStrategyEngine(scraper=scraper)
    plan = engine.build_plan(wallet, max_bet=5.0)
    result = engine.execute(plan, max_rounds=10)
    assert result.rounds_played > 0
    assert result.rollover_cleared is True
    assert result.total_wagered > 0


def test_execute_max_rounds():
    wallet = WalletSnapshot(balance=50, bonus=50, rollover=10000)
    scraper = FakeScraper(wallet)
    engine = WageringStrategyEngine(scraper=scraper)
    plan = engine.build_plan(wallet, max_bet=5.0)
    result = engine.execute(plan, max_rounds=3)
    assert result.rounds_played <= 3
    assert result.rollover_cleared is False


# ---------------------------------------------------------------------------
# estimate_time
# ---------------------------------------------------------------------------

def test_estimate_time_api():
    wallet = WalletSnapshot(balance=50, bonus=50, rollover=250)
    engine = WageringStrategyEngine(scraper=FakeScraper(wallet))
    plan = engine.build_plan(wallet, max_bet=5.0)
    t = engine.estimate_time(plan, method="api")
    assert t > 0
    assert t < plan.rounds_needed * 2.0  # api is fast


def test_estimate_time_browser_slower():
    wallet = WalletSnapshot(balance=50, bonus=50, rollover=250)
    engine = WageringStrategyEngine(scraper=FakeScraper(wallet))
    plan = engine.build_plan(wallet, max_bet=5.0)
    t_api = engine.estimate_time(plan, method="api")
    t_browser = engine.estimate_time(plan, method="browser")
    assert t_browser > t_api


# ---------------------------------------------------------------------------
# Losing streak detection
# ---------------------------------------------------------------------------

def test_losing_streak_no_streak():
    engine = WageringStrategyEngine(scraper=FakeScraper(WalletSnapshot(rollover=100)))
    history = [5.0, 4.9, 5.1, 4.8, 5.0]
    assert engine._losing_streak_check(history) is False


def test_losing_streak_detected():
    engine = WageringStrategyEngine(scraper=FakeScraper(WalletSnapshot(rollover=100)))
    # 5 consecutive big losses
    history = [5.0, 4.9, 1.0, 0.5, 0.3, 0.1]
    assert engine._losing_streak_check(history) is True
