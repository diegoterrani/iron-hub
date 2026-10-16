"""Tests for BrowserFarm and BrowserContext (Phase 1)."""

from __future__ import annotations

import time

import pytest

from src.integrity.browser_farm import BrowserContext, BrowserFarm


# --- BrowserContext ---

def test_context_defaults():
    ctx = BrowserContext(context_id="ctx-1", page=None)
    assert ctx.context_id == "ctx-1"
    assert ctx.spin_count == 0
    assert ctx.stake == 1.0
    assert ctx.page is None
    assert ctx.game_loaded is False
    assert ctx.provider == ""


def test_context_touch():
    ctx = BrowserContext(context_id="ctx-1", page=None)
    before = time.time()
    ctx.touch()
    after = time.time()
    assert before <= ctx.last_activity <= after


def test_context_fields():
    ctx = BrowserContext(
        context_id="ctx-1", page=None, game_loaded=True,
        spin_count=5, stake=2.5, provider="PG",
    )
    assert ctx.spin_count == 5
    assert ctx.stake == 2.5
    assert ctx.provider == "PG"
    assert ctx.game_loaded is True


# --- BrowserFarm (without Playwright) ---

def test_farm_defaults():
    farm = BrowserFarm(max_contexts=5)
    assert farm.max_contexts == 5
    assert farm.headless is True
    assert farm.user_agent == ""
    assert farm._launched is False


def test_farm_stats_empty():
    farm = BrowserFarm(max_contexts=3)
    stats = farm.farm_stats()
    assert stats["active_contexts"] == 0
    assert stats["max_contexts"] == 3
    assert stats["total_clicks"] == 0
    assert stats["uptime_s"] == 0.0
    assert stats["contexts"] == []


def test_farm_stats_with_contexts():
    farm = BrowserFarm(max_contexts=3)
    ctx1 = BrowserContext(context_id="c1", page=None, spin_count=10, stake=1.0)
    ctx2 = BrowserContext(context_id="c2", page=None, spin_count=5, stake=2.0)
    farm._contexts["a1"] = ctx1
    farm._contexts["a2"] = ctx2
    farm._total_clicks = 15
    stats = farm.farm_stats()
    assert stats["active_contexts"] == 2
    assert stats["total_clicks"] == 15
    assert len(stats["contexts"]) == 2
    assert stats["contexts"][0]["spin_count"] == 10


def test_release_context_removes():
    farm = BrowserFarm(max_contexts=3)
    ctx = BrowserContext(context_id="c1", page=None)
    farm._contexts["a1"] = ctx
    farm.release_context(ctx)
    assert "a1" not in farm._contexts


def test_release_context_with_page():
    farm = BrowserFarm(max_contexts=3)
    closed = []

    class _FakePage:
        def close(self):
            closed.append(True)
    ctx = BrowserContext(context_id="c1", page=_FakePage())
    farm._contexts["a1"] = ctx
    farm.release_context(ctx)
    assert closed == [True]
    assert "a1" not in farm._contexts


def test_idle_gap_touches_context():
    farm = BrowserFarm(max_contexts=3)
    ctx = BrowserContext(context_id="c1", page=None)
    before = ctx.last_activity
    farm.idle_gap(ctx, min_s=0.01, max_s=0.02)
    assert ctx.last_activity >= before


def test_acquire_context_returns_existing():
    farm = BrowserFarm(max_contexts=3)
    ctx = BrowserContext(context_id="c1", page=None)
    farm._contexts["a1"] = ctx
    result = farm.acquire_context("a1")
    assert result.context_id == "c1"
    assert result is ctx
