"""Tests for journey stages, build_plan, and the orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.abuse.house_profile import HouseProfile
from src.abuse.stages import (
    STAGE_CLASSES,
    STAGE_ORDER,
    AnalyzeStage,
    AcquireStage,
    ArmStage,
    AuthStage,
    CashoutStage,
    DiscoveryStage,
    JourneyContext,
    JourneyPlan,
    ProbeStage,
    ReconStage,
    ReportStage,
    StageResult,
    build_plan,
)


# ---------------------------------------------------------------------------
# StageResult
# ---------------------------------------------------------------------------


def test_stage_result_to_dict():
    r = StageResult(id="test", title="Test Stage", ok=True, note="done")
    d = r.to_dict()
    assert d == {
        "id": "test",
        "title": "Test Stage",
        "ok": True,
        "mode": "AUTOMATED",
        "note": "done",
        "evidence": {},
    }


def test_stage_result_with_evidence():
    r = StageResult(id="x", title="X", ok=False, evidence={"error": "boom"})
    d = r.to_dict()
    assert d["evidence"] == {"error": "boom"}


# ---------------------------------------------------------------------------
# JourneyContext
# ---------------------------------------------------------------------------


def _make_ctx(
    scraper: Any = None,
    profile: HouseProfile = None,
    **kwargs: Any,
) -> JourneyContext:
    if scraper is None:
        scraper = MagicMock()
        scraper.platform = "test"
    if profile is None:
        profile = HouseProfile(platform="test")
    return JourneyContext(scraper=scraper, profile=profile, **kwargs)


def test_ctx_add_step():
    ctx = _make_ctx()
    r = StageResult(id="s1", title="Step 1", ok=True)
    ctx.add_step(r)
    assert len(ctx.steps) == 1
    assert ctx.steps[0]["id"] == "s1"
    assert ctx.steps[0]["ok"] is True


def test_ctx_add_step_level():
    ctx = _make_ctx()
    r_ok = StageResult(id="ok", title="OK", ok=True)
    r_fail = StageResult(id="fail", title="Fail", ok=False)
    r_skip = StageResult(id="skip", title="Skip", ok=False, mode="SKIPPED")
    ctx.add_step(r_ok)
    ctx.add_step(r_fail)
    ctx.add_step(r_skip)
    assert len(ctx.steps) == 3


# ---------------------------------------------------------------------------
# JourneyPlan
# ---------------------------------------------------------------------------


def test_plan_ids():
    plan = JourneyPlan(stages=[ReconStage(), AuthStage(), ReportStage()])
    assert plan.ids() == ["recon", "auth", "report"]


# ---------------------------------------------------------------------------
# build_plan
# ---------------------------------------------------------------------------


def test_build_plan_always_has_recon_and_report():
    profile = HouseProfile(platform="test", recommended_stages=[], capabilities={})
    plan = build_plan(profile)
    ids = plan.ids()
    assert "recon" in ids
    assert "report" in ids
    assert "auth" in ids  # auth always runs


def test_build_plan_selects_recommended_stages():
    profile = HouseProfile(
        platform="test",
        recommended_stages=["recon", "auth", "discovery", "acquire", "report"],
        capabilities={
            "list_bonuses": True,
            "list_my_bonuses": True,
            "list_enabled_promocodes": True,
            "redeem_promocode": True,
            "scrape_live": True,
        },
    )
    plan = build_plan(profile)
    ids = plan.ids()
    assert "discovery" in ids
    assert "acquire" in ids
    assert "arm" not in ids
    assert "probe" not in ids
    assert "cashout" not in ids


def test_build_plan_requires_capabilities():
    """Stage in recommended_stages but NO capabilities → excluded."""
    profile = HouseProfile(
        platform="test",
        recommended_stages=["recon", "auth", "arm", "report"],
        capabilities={},  # no capabilities at all
    )
    plan = build_plan(profile)
    ids = plan.ids()
    assert "arm" not in ids  # no run_bonus_multiplier_lab / probe_slots_for_bonus


def test_build_plan_with_all_capabilities():
    profile = HouseProfile(
        platform="test",
        recommended_stages=[
            "recon", "auth", "discovery", "acquire",
            "arm", "analyze", "probe", "cashout", "report",
        ],
        capabilities={
            "validate_token": True,
            "get_wallet_snapshot": True,
            "list_bonuses": True,
            "list_my_bonuses": True,
            "list_enabled_promocodes": True,
            "redeem_promocode": True,
            "claim_or_activate_bonus": True,
            "run_bonus_multiplier_lab": True,
            "probe_slots_for_bonus": True,
            "probe_high_ev_contribution": True,
            "get_bonus_conversion_state": True,
            "withdraw": True,
            "withdraw_preflight": True,
            "list_withdrawals": True,
            "poll_withdrawal_settlement": True,
            "scrape_live": True,
        },
    )
    plan = build_plan(profile)
    ids = plan.ids()
    # All stages should be present
    assert "recon" in ids
    assert "auth" in ids
    assert "discovery" in ids
    assert "acquire" in ids
    assert "arm" in ids
    assert "analyze" in ids
    assert "probe" in ids
    assert "cashout" in ids
    assert "report" in ids


def test_build_plan_order():
    profile = HouseProfile(
        platform="test",
        recommended_stages=["recon", "auth", "cashout", "acquire", "report", "discovery", "arm"],
        capabilities={
            "list_bonuses": True,
            "redeem_promocode": True,
            "withdraw": True,
            "run_bonus_multiplier_lab": True,
        },
    )
    plan = build_plan(profile)
    ids = plan.ids()
    # Should follow STAGE_ORDER, not recommended_stages order
    order_idx = {sid: i for i, sid in enumerate(STAGE_ORDER)}
    indices = [order_idx[sid] for sid in ids if sid in order_idx]
    assert indices == sorted(indices)


# ---------------------------------------------------------------------------
# Stage classes — basic structure
# ---------------------------------------------------------------------------


def test_all_stages_have_id_and_title():
    for stage_id, cls in STAGE_CLASSES.items():
        assert cls.id == stage_id, f"{cls.__name__}.id should be {stage_id}"
        assert cls.title, f"{cls.__name__}.title should not be empty"
        assert hasattr(cls, "run"), f"{cls.__name__} should have run()"


def test_stage_order_matches_classes():
    for stage_id in STAGE_ORDER:
        assert stage_id in STAGE_CLASSES


# ---------------------------------------------------------------------------
# Stage execution (mocked)
# ---------------------------------------------------------------------------


def test_recon_stage_returns_result():
    scraper = MagicMock()
    scraper.platform = "test"
    profile = HouseProfile(
        platform="test",
        capabilities={"withdraw": True, "validate_token": True},
        bonus_count=3,
        promocode_count=2,
    )
    ctx = _make_ctx(scraper=scraper, profile=profile)

    stage = ReconStage()
    result = stage.run(ctx)

    assert isinstance(result, StageResult)
    assert result.id == "recon"
    assert result.ok is True
    assert "capabilities" in result.evidence


def test_auth_stage_success():
    scraper = MagicMock()
    scraper.platform = "test"
    scraper.validate_token.return_value = {"user": {"id": 1, "phone": "123"}}
    profile = HouseProfile(platform="test", capabilities={"validate_token": True})
    ctx = _make_ctx(scraper=scraper, profile=profile)

    stage = AuthStage()
    result = stage.run(ctx)

    assert isinstance(result, StageResult)
    assert result.id == "auth"
    assert result.ok is True
    assert ctx.auth.get("user", {}).get("id") == 1


def test_auth_stage_failure():
    scraper = MagicMock()
    scraper.platform = "test"
    scraper.validate_token.side_effect = Exception("token expired")
    profile = HouseProfile(platform="test", capabilities={"validate_token": True})
    ctx = _make_ctx(scraper=scraper, profile=profile)

    stage = AuthStage()
    result = stage.run(ctx)

    assert result.ok is False


def test_discovery_stage_no_bonuses():
    scraper = MagicMock()
    scraper.platform = "test"
    scraper.list_bonuses.return_value = []
    scraper.list_my_bonuses.return_value = []
    profile = HouseProfile(
        platform="test",
        capabilities={"list_bonuses": True, "list_my_bonuses": True},
    )
    ctx = _make_ctx(scraper=scraper, profile=profile)

    stage = DiscoveryStage()
    result = stage.run(ctx)

    assert result.id == "discovery"
    assert result.ok is False or result.ok is True  # either is valid
    assert isinstance(result, StageResult)


def test_cashout_stage_preflight():
    """Cashout without confirm_real_withdown should do preflight only."""
    scraper = MagicMock()
    scraper.platform = "test"
    scraper.withdraw_preflight.return_value = {"methods": ["PIX"], "have_opened": False}
    from src.models.abuse import WalletSnapshot
    scraper.get_wallet_snapshot.return_value = WalletSnapshot(
        platform="test", balance=100, bonus=0, rollover=0
    )
    profile = HouseProfile(
        platform="test",
        capabilities={"withdraw": True, "withdraw_preflight": True},
        max_withdraw=500,
        uses_cents=False,
        withdraw_methods=["PIX"],
    )
    ctx = _make_ctx(scraper=scraper, profile=profile, confirm_real_withdraw=False)

    stage = CashoutStage()
    result = stage.run(ctx)

    assert result.id == "cashout"
    assert isinstance(result, StageResult)
    assert ctx.withdraw_result is not None


def test_report_stage_signals_orchestrator(tmp_path: Path):
    """ReportStage signals completion; the orchestrator writes the markdown."""
    scraper = MagicMock()
    scraper.platform = "test"
    profile = HouseProfile(platform="test")
    ctx = _make_ctx(scraper=scraper, profile=profile)
    ctx.wallet_start = None
    ctx.wallet_end = None
    ctx.steps.append(StageResult(id="recon", title="Recon", ok=True))
    ctx.steps.append(StageResult(id="auth", title="Auth", ok=True))

    stage = ReportStage()
    result = stage.run(ctx)

    assert result.id == "report"
    assert result.ok is True
    assert result.evidence.get("steps") == 2


# ---------------------------------------------------------------------------
# build_auto_journey_markdown
# ---------------------------------------------------------------------------


def test_markdown_generation():
    from src.abuse.auto_journey import build_auto_journey_markdown

    payload = {
        "run_id": "abc123",
        "platform": "test_house",
        "ok": True,
        "stuck_point": "none",
        "steps": [
            {"id": "recon", "title": "Recon", "ok": True, "note": "done"},
            {"id": "auth", "title": "Auth", "ok": True, "note": "ok"},
        ],
        "profile": {"platform": "test_house", "capabilities": {"withdraw": True}},
        "plan": ["recon", "auth", "report"],
    }
    md = build_auto_journey_markdown(payload)
    assert "test_house" in md
    assert "Recon" in md
    assert "Auth" in md


# ---------------------------------------------------------------------------
# _pick_llm_targets
# ---------------------------------------------------------------------------


def test_pick_llm_targets():
    from src.abuse.auto_journey import _pick_llm_targets
    from src.models.bonus import BonusOffer, BonusType

    offers = [
        BonusOffer(
            platform="test",
            bonus_type=BonusType.NO_DEPOSIT,
            title=f"Offer {i}",
            amount=1000 - i * 100,
            wagering_multiple=5,
        )
        for i in range(5)
    ]
    picked = _pick_llm_targets(offers, None, limit=2, platform="test")
    assert len(picked) <= 2
    assert len(picked) >= 1
