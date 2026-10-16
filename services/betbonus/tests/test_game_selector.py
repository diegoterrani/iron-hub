"""Tests for GameSelector (Phase 4)."""

from __future__ import annotations

import pytest

from src.abuse.game_selector import GameSelector, GameSelectionResult


def _candidates():
    return [
        {"game_id": 1, "name": "Slot A", "provider": "PG", "rtp": 0.96, "variance": "low", "eligible": True},
        {"game_id": 2, "name": "Slot B", "provider": "Pragmatic", "rtp": 0.94, "variance": "high", "eligible": True},
        {"game_id": 3, "name": "Table C", "provider": "Evo", "rtp": 0.995, "variance": "low", "eligible": False},
    ]


# --- select (deterministic fallback) ---

def test_select_empty_candidates():
    gs = GameSelector()
    result = gs.select([], {}, 5.0, 1000.0)
    assert result.game_name == "(none)"
    assert result.confidence == 0.0


def test_select_prefers_eligible_high_rtp():
    gs = GameSelector()
    result = gs.select(_candidates(), {}, 5.0, 1000.0)
    # Slot A (eligible, RTP 0.96, low variance) should beat Table C (RTP 0.995 but ineligible)
    assert result.game_id == 1


def test_select_returns_valid_result():
    gs = GameSelector()
    result = gs.select(_candidates(), {}, 5.0, 1000.0)
    assert result.game_name != ""
    assert result.rtp > 0.9
    assert result.confidence > 0


# --- rank_games ---

def test_rank_games_ordering():
    gs = GameSelector()
    ranked = gs.rank_games(_candidates(), max_bet=5.0)
    assert len(ranked) == 3
    # Eligible games should rank above ineligible
    assert ranked[0]["eligible"] is True
    # Higher RTP + lower variance should score higher
    assert ranked[0]["ev_score"] >= ranked[1]["ev_score"]


def test_rank_games_fields():
    gs = GameSelector()
    ranked = gs.rank_games(_candidates(), max_bet=5.0)
    for entry in ranked:
        assert "game_id" in entry
        assert "ev_score" in entry
        assert "eligible" in entry


# --- ev_score ---

def test_ev_score_higher_rtp_better():
    gs = GameSelector()
    s1 = gs.ev_score(0.99, "low", 100)
    s2 = gs.ev_score(0.90, "low", 100)
    assert s1 > s2


def test_ev_score_lower_variance_better():
    gs = GameSelector()
    s1 = gs.ev_score(0.96, "low", 100)
    s2 = gs.ev_score(0.96, "extreme", 100)
    assert s1 > s2


def test_ev_score_sweet_spot_rounds():
    gs = GameSelector()
    s_mid = gs.ev_score(0.96, "low", 200)   # sweet spot
    s_many = gs.ev_score(0.96, "low", 5000)  # too many rounds
    s_zero = gs.ev_score(0.96, "low", 0)     # no rounds
    assert s_mid > s_many
    assert s_mid > s_zero


# --- LLM path ---

class _FakeLLM:
    def __init__(self, response_text):
        self._text = response_text

    def complete(self, messages, **kwargs):
        class _R:
            text = self._text
        return _R()


def test_select_llm_path():
    import json
    resp = json.dumps({
        "game_id": 2, "game_name": "Slot B", "provider": "Pragmatic",
        "rtp": 0.94, "variance": "high", "reasoning": "best fit",
        "confidence": 0.85, "alternatives": [],
    })
    gs = GameSelector(llm=_FakeLLM(resp))
    result = gs.select(_candidates(), {}, 5.0, 1000.0)
    assert result.game_id == 2
    assert result.confidence == 0.85


def test_select_llm_hallucinated_id_falls_back():
    import json
    resp = json.dumps({
        "game_id": 999, "game_name": "Ghost", "provider": "X",
        "rtp": 0.99, "variance": "low", "reasoning": "??",
        "confidence": 0.9, "alternatives": [],
    })
    gs = GameSelector(llm=_FakeLLM(resp))
    result = gs.select(_candidates(), {}, 5.0, 1000.0)
    # Should fall back to deterministic (game 1)
    assert result.game_id == 1


def test_select_llm_error_falls_back():
    class _BadLLM:
        def complete(self, messages, **kwargs):
            raise RuntimeError("LLM down")
    gs = GameSelector(llm=_BadLLM())
    result = gs.select(_candidates(), {}, 5.0, 1000.0)
    assert result.game_id == 1  # deterministic fallback


# --- to_dict ---

def test_game_selection_result_to_dict():
    r = GameSelectionResult(
        game_id=1, game_name="Slot A", provider="PG",
        rtp=0.96, variance="low", reasoning="test", confidence=0.7,
    )
    d = r.to_dict()
    assert d["game_id"] == 1
    assert d["confidence"] == 0.7
    assert d["alternatives"] == []
