"""
Estágios discretos da jornada de exploração de bônus.

Cada estágio é uma classe independente que:
  * declara `id` + `title`
  * declara `capabilities` (métodos que o scraper precisa expor)
  * implementa `run(ctx) -> StageResult`

O `JourneyPlan` decide quais estágios rodam para uma casa:
  * `recon` e `report` sempre rodam
  * os demais são habilitados se `HouseProfile.recommended_stages` tem o id
    (e o scraper expõe as capacidades mínimas)

`JourneyContext` é o "ponto de passagem" entre estágios — cada estágio pode
ler o que os anteriores produziram e enriquecer para os seguintes.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from src.abuse.house_profile import HouseProfile
from src.scrapers.base import BaseScraper


# ---------------------------------------------------------------------------
# StageResult / JourneyContext / JourneyPlan
# ---------------------------------------------------------------------------


@dataclass
class StageResult:
    """Resultado de um estágio — entra na timeline do relatório."""

    id: str
    title: str
    ok: bool
    mode: str = "AUTOMATED"
    note: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "ok": self.ok,
            "mode": self.mode,
            "note": self.note,
            "evidence": self.evidence,
        }


@dataclass
class JourneyContext:
    """Estado compartilhado entre estágios da jornada."""

    scraper: BaseScraper
    profile: HouseProfile
    # opções (vindas do request/CLI)
    confirm_redeem: bool = True
    confirm_real_withdraw: bool = False
    confirm_real_bet: bool = True
    auto_bet_clicks: int = 1
    settle_withdraw: bool = True
    settle_timeout_s: int = 90
    promocode_limit: int = 25
    llm_limit: int = 2
    run_deep_attack: bool = True
    poll_seconds: int = 25
    persist_findings: bool = True
    # serviços
    findings: Any = None
    oracle: Any = None
    ledger: Any = None
    offer_store: Any = None
    process_offers: Optional[Any] = None
    # produção entre estágios
    auth: dict[str, Any] = field(default_factory=dict)
    wallet_start: Any = None
    wallet_end: Any = None
    offers: list[Any] = field(default_factory=list)
    claim: dict[str, Any] = field(default_factory=dict)
    arm: dict[str, Any] = field(default_factory=dict)
    llm: dict[str, Any] = field(default_factory=dict)
    high_ev: dict[str, Any] = field(default_factory=dict)
    matrix: dict[str, Any] = field(default_factory=dict)
    withdraw_result: Optional[dict[str, Any]] = None
    withdrawal_id: Optional[str] = None
    settle: dict[str, Any] = field(default_factory=dict)
    diagnosis: dict[str, Any] = field(default_factory=dict)
    # timeline
    steps: list[dict[str, Any]] = field(default_factory=list)

    def add_step(self, result: StageResult, level: Optional[str] = None) -> None:
        self.steps.append(result.to_dict())
        if level is None:
            level = "success" if result.ok else ("warn" if result.mode == "SKIPPED" else "error")
        return level


@dataclass
class JourneyPlan:
    """Lista ordenada de estágios habilitados para uma casa."""

    stages: list[Any] = field(default_factory=list)

    def ids(self) -> list[str]:
        return [s.id for s in self.stages]


# ---------------------------------------------------------------------------
# Estágios
# ---------------------------------------------------------------------------


class ReconStage:
    id = "recon"
    title = "Recon da casa (capacidades + wallet + T&Cs)"
    capabilities: tuple[str, ...] = ()

    def run(self, ctx: JourneyContext) -> StageResult:
        profile = ctx.profile
        return StageResult(
            id=self.id,
            title=self.title,
            ok=True,
            mode="AUTOMATED",
            note=(
                f"capacidades={sum(1 for v in profile.capabilities.values() if v)} · "
                f"bônus={profile.bonus_count} promo={profile.promocode_count} "
                f"llm={profile.llm_used}"
            ),
            evidence={
                "platform": profile.platform,
                "capabilities": profile.capabilities,
                "recommended_stages": profile.recommended_stages,
                "withdraw_methods": profile.withdraw_methods,
                "min_withdraw": profile.min_withdraw,
                "currency": profile.currency,
                "uses_cents": profile.uses_cents,
                "summary": profile.summary,
            },
        )


class AuthStage:
    id = "auth"
    title = "Login / Auth token"
    capabilities: tuple[str, ...] = ("validate_token",)

    def run(self, ctx: JourneyContext) -> StageResult:
        try:
            auth = ctx.scraper.validate_token()
            ctx.auth = auth or {}
            return StageResult(
                id=self.id,
                title=self.title,
                ok=True,
                note=f"user_id={ctx.auth.get('user_id')}",
                evidence=ctx.auth,
            )
        except Exception as exc:  # noqa: BLE001
            return StageResult(
                id=self.id,
                title=self.title,
                ok=False,
                note=str(exc)[:300],
            )


class DiscoveryStage:
    id = "discovery"
    title = "Discovery de bônus (conta + promocodes)"
    capabilities: tuple[str, ...] = ("scrape_live",)

    def run(self, ctx: JourneyContext) -> StageResult:
        try:
            scrape = ctx.scraper.scrape_live(
                include_account=True,
                include_promocodes=True,
                promocode_limit=max(ctx.promocode_limit, 40),
            )
            offers = list(scrape.offers or [])
            if ctx.process_offers:
                offers = ctx.process_offers(offers)
            elif ctx.offer_store and hasattr(ctx.offer_store, "upsert"):
                ctx.offer_store.upsert(offers)
            if ctx.ledger and offers:
                from src.storage.wallet import WalletCredit

                credits = [
                    WalletCredit(
                        platform=ctx.scraper.platform,
                        bonus_id=str(o.id),
                        title=o.title,
                        amount=float(o.amount or 0),
                        currency=o.currency or "BRL",
                        source="account" if o.title.startswith("[conta]") else "promo",
                        reality="internal_sim",
                        note="Jornada discovery — ledger interno, não credita a casa",
                    )
                    for o in offers
                ]
                ctx.ledger.credit_many(credits)
            ctx.offers = offers
            return StageResult(
                id=self.id,
                title=self.title,
                ok=bool(scrape.ok),
                note=str(scrape.error or f"offers={len(offers)}"),
                evidence={
                    "offers": len(offers),
                    "titles": [o.title[:60] for o in offers[:12]],
                },
            )
        except Exception as exc:  # noqa: BLE001
            return StageResult(
                id=self.id,
                title=self.title,
                ok=False,
                note=str(exc)[:300],
            )


class AcquireStage:
    id = "acquire"
    title = "Claim / redeem de todos os bônus possíveis"
    capabilities: tuple[str, ...] = (
        "redeem_promocode",
        "claim_or_activate_bonus",
        "list_enabled_promocodes",
    )

    def run(self, ctx: JourneyContext) -> StageResult:
        from src.abuse.auto_journey import claim_all_bonuses

        evidence = claim_all_bonuses(
            ctx.scraper,
            offers=ctx.offers,
            confirm_redeem=ctx.confirm_redeem,
            promocode_limit=ctx.promocode_limit,
        )
        ctx.claim = evidence
        ok = bool(evidence.get("any_success") or evidence.get("active_bonus"))
        return StageResult(
            id=self.id,
            title=self.title,
            ok=ok,
            mode="AUTOMATED" if ctx.confirm_redeem else "SKIPPED",
            note=str(evidence.get("note", "")),
            evidence=evidence,
        )


class ArmStage:
    id = "arm"
    title = "Armar redeem + Mines + poll + slots launch"
    capabilities: tuple[str, ...] = (
        "run_bonus_multiplier_lab",
        "probe_slots_for_bonus",
    )

    def run(self, ctx: JourneyContext) -> StageResult:
        from src.scrapers.pagol_scraper import PagolScraper

        arm_ev: dict[str, Any] = {}
        try:
            primary = (
                ctx.scraper.get_bonus_conversion_state().get("primary") or {}
                if callable(getattr(ctx.scraper, "get_bonus_conversion_state", None))
                else {}
            )
            max_stake = float(getattr(PagolScraper, "MAX_LAB_STAKE_BRL", 100.0) or 100.0)
            default_stake = float(getattr(PagolScraper, "DEFAULT_LAB_STAKE_BRL", 10.0) or 10.0)
            stake = min(float(primary.get("max_bet_brl") or default_stake), max_stake)
            if ctx.confirm_real_bet and callable(
                getattr(ctx.scraper, "run_bonus_multiplier_lab", None)
            ):
                import inspect
                _lab_params = inspect.signature(ctx.scraper.run_bonus_multiplier_lab).parameters

                # --- I2: Rollover-aware multi-round wagering ---
                # Determine how many rounds are needed to clear the rollover.
                # rollover_remaining = bonus * multiplier - wagered_so_far
                bonus_amt = float(primary.get("bonus_brl") or 0)
                multiplier = float(primary.get("rollover_multiplier") or 20)
                wagered = float(primary.get("wagered_brl") or 0)
                rollover_remaining = max(0.0, bonus_amt * multiplier - wagered)
                rounds_needed = max(1, int(rollover_remaining / max(stake, 1.0))) if rollover_remaining > 0 else 1
                # Cap at reasonable max to avoid infinite loops
                rounds_needed = min(rounds_needed, 500)

                # Find a real game ID for 4play (crash category, first available)
                _game_id = 15
                if "game_id" in _lab_params:
                    try:
                        _games = ctx.scraper.list_casino_games(category="Crash", page=1, per_page=1)
                        _items = _games.get("items") or []
                        if _items:
                            _game_id = _items[0].get("id", 15)
                    except Exception:
                        pass

                # Execute wagering rounds until rollover is cleared or max rounds
                last_lab: dict[str, Any] = {}
                total_wagered_this_stage = 0.0
                for _round in range(rounds_needed):
                    if "game_id" in _lab_params:
                        lab = ctx.scraper.run_bonus_multiplier_lab(
                            game_id=_game_id,
                            stake_brl=stake,
                            use_bonus_balance=True,
                            confirm_real_bet=True,
                            poll_seconds=ctx.poll_seconds,
                            clicks=ctx.auto_bet_clicks,
                        )
                    else:
                        lab = ctx.scraper.run_bonus_multiplier_lab(
                            stake_brl=stake,
                            confirm_redeem=False,
                            confirm_real_bet=True,
                            use_bonus_balance=True,
                            poll_seconds=ctx.poll_seconds,
                            clicks=ctx.auto_bet_clicks,
                        )
                    last_lab = lab
                    total_wagered_this_stage += stake
                    # I3: Anti-detection jitter between rounds
                    if _round < rounds_needed - 1:
                        time.sleep(random.uniform(0.5, 2.0))
                    # Check if rollover is now cleared
                    try:
                        _bs = ctx.scraper.get_bonus_conversion_state().get("primary") or {}
                        _remaining = max(
                            0.0,
                            float(_bs.get("bonus_brl") or 0) * float(_bs.get("rollover_multiplier") or 20)
                            - float(_bs.get("wagered_brl") or 0),
                        )
                        if _remaining <= 0:
                            break
                    except Exception:
                        pass

                arm_ev["mines_lab"] = {
                    "bet_armed": last_lab.get("bet_armed"),
                    "provider_url": last_lab.get("provider_url"),
                    "gates": last_lab.get("gates"),
                    "poll": last_lab.get("poll"),
                    "auto_bet_implemented": last_lab.get("auto_bet_implemented"),
                    "auto_bet_ok": last_lab.get("auto_bet_ok"),
                    "auto_bet_result": last_lab.get("auto_bet_result"),
                }
                arm_ev["wagering"] = {
                    "rounds_planned": rounds_needed,
                    "stake_brl": stake,
                    "total_wagered_brl": total_wagered_this_stage,
                    "rollover_remaining_before": rollover_remaining,
                    "game_id": _game_id,
                }
            if callable(getattr(ctx.scraper, "probe_slots_for_bonus", None)):
                slots = ctx.scraper.probe_slots_for_bonus(
                    limit=3,
                    use_bonus_balance=bool(primary),
                )
                arm_ev["slots_probe"] = slots
            ctx.arm = arm_ev
            mines = arm_ev.get("mines_lab") or {}
            auto_bet_ok = bool(mines.get("auto_bet_ok"))
            changed = bool((mines.get("poll") or {}).get("changed"))
            ok = bool(
                auto_bet_ok
                or mines.get("bet_armed")
                or (arm_ev.get("slots_probe") or {}).get("launches_ok")
            )
            note_parts = []
            if auto_bet_ok:
                note_parts.append(
                    f"auto_bet OK ({mines.get('auto_bet_result', {}).get('clicks', '?')} clicks)"
                )
            elif ctx.confirm_real_bet:
                note_parts.append("auto_bet failed/incomplete")
            note_parts.append(f"poll_changed={changed}")
            note_parts.append(f"slots_ok={arm_ev.get('slots_probe', {}).get('launches_ok')}")
            return StageResult(
                id=self.id,
                title=self.title,
                ok=ok,
                mode="AUTO_BET" if auto_bet_ok else "SEMI_AUTO",
                note=" ".join(note_parts),
                evidence=arm_ev,
            )
        except Exception as exc:  # noqa: BLE001
            return StageResult(
                id=self.id,
                title=self.title,
                ok=False,
                mode="SEMI_AUTO",
                note=str(exc)[:300],
            )


class AnalyzeStage:
    id = "analyze"
    title = "LLM Maverick · analisar T&Cs + deep attack"
    capabilities: tuple[str, ...] = ()

    def run(self, ctx: JourneyContext) -> StageResult:
        from src.abuse.auto_journey import (
            _enrich_offer_with_live_bonus,
            _pick_llm_targets,
        )
        from src.llm.abuse_assist import AbuseLLMAssist

        if ctx.llm_limit <= 0 and not ctx.run_deep_attack:
            return StageResult(
                id=self.id,
                title=self.title,
                ok=True,
                mode="SKIPPED",
                note="llm_limit=0 e deep desligado",
            )
        ev: dict[str, Any] = {"items": [], "deep": None, "errors": []}
        try:
            assist = AbuseLLMAssist()
            bonus_state = (
                ctx.scraper.get_bonus_conversion_state()
                if callable(getattr(ctx.scraper, "get_bonus_conversion_state", None))
                else {"primary": {}}
            )
            primary = bonus_state.get("primary") or {}
            targets = (
                _pick_llm_targets(ctx.offers, primary, limit=max(ctx.llm_limit, 1))
                if ctx.llm_limit > 0 or ctx.run_deep_attack
                else []
            )
            analyze_n = max(ctx.llm_limit, 0)
            for offer in targets[:analyze_n]:
                try:
                    enriched = _enrich_offer_with_live_bonus(offer, primary, bonus_state)
                    item = assist.analyze_offer(enriched, timeout=90.0)
                    ev["items"].append(item)
                except Exception as exc:  # noqa: BLE001
                    ev["errors"].append(
                        {"title": offer.title, "error": str(exc)[:240]}
                    )
            if ctx.run_deep_attack and targets:
                try:
                    deep_offer = _enrich_offer_with_live_bonus(
                        targets[0], primary, bonus_state
                    )
                    prior = ev["items"][0] if ev["items"] else {}
                    ev["deep"] = assist.analyze_offer_deep(
                        deep_offer,
                        prior_summary=str(
                            (prior.get("llm") or {}).get("summary") or ""
                        ),
                        prior_vectors=list(
                            (prior.get("llm") or {}).get("abuse_vectors") or []
                        ),
                        timeout=110.0,
                    )
                except Exception as exc:  # noqa: BLE001
                    ev["errors"].append({"deep": str(exc)[:240]})
            ctx.llm = ev
            usable_n = sum(
                1
                for i in ev["items"]
                if isinstance(((i.get("llm") or {}).get("abuse_vectors")), list)
                and not (i.get("llm") or {}).get("parse_error")
            )
            deep_ok = bool(
                ev["deep"]
                and isinstance(
                    ((ev["deep"].get("llm") or {}).get("abuse_vectors")), list
                )
                and not (ev["deep"].get("llm") or {}).get("parse_error")
            )
            return StageResult(
                id=self.id,
                title=self.title,
                ok=bool(usable_n or deep_ok),
                note=(
                    f"analyzed={len(ev['items'])} deep={bool(ev['deep'])} "
                    f"errors={len(ev['errors'])}"
                ),
                evidence={
                    "count": len(ev["items"]),
                    "deep_title": (ev["deep"] or {}).get("title"),
                    "errors": ev["errors"][:5],
                    "summaries": [
                        str((i.get("llm") or {}).get("summary") or "")[:280]
                        for i in ev["items"][:3]
                    ],
                },
            )
        except Exception as exc:  # noqa: BLE001
            return StageResult(
                id=self.id,
                title=self.title,
                ok=False,
                note=str(exc)[:300],
            )


class ProbeStage:
    id = "probe"
    title = "High-EV discovery + soft-probe"
    capabilities: tuple[str, ...] = ("probe_high_ev_contribution",)

    def run(self, ctx: JourneyContext) -> StageResult:
        try:
            import inspect
            _hev_params = inspect.signature(ctx.scraper.probe_high_ev_contribution).parameters
            if "max_probes" in _hev_params:
                # FourPlay-style: (terms, max_probes, use_bonus_balance)
                hev = ctx.scraper.probe_high_ev_contribution(
                    max_probes=4, use_bonus_balance=True
                )
            else:
                # Pagol-style: (limit, include_bonus_flag)
                hev = ctx.scraper.probe_high_ev_contribution(
                    limit=4, include_bonus_flag=True
                )
            ctx.high_ev = hev
            return StageResult(
                id=self.id,
                title=self.title,
                ok=int(hev.get("probed") or 0) > 0,
                note=str(hev.get("note") or ""),
                evidence={
                    "probed": hev.get("probed"),
                    "findings": hev.get("findings"),
                    "probes": (hev.get("probes") or [])[:6],
                },
            )
        except Exception as exc:  # noqa: BLE001
            return StageResult(
                id=self.id,
                title=self.title,
                ok=False,
                note=str(exc)[:300],
            )


class CashoutStage:
    id = "cashout"
    title = "Oracle saque + settle/validação"
    capabilities: tuple[str, ...] = ("withdraw",)

    def run(self, ctx: JourneyContext) -> StageResult:
        from src.abuse.auto_journey import diagnose_withdraw_stuck
        from src.abuse.oracle import WithdrawalOracle

        try:
            ctx.wallet_start = ctx.scraper.get_wallet_snapshot(
                include_bonus_state=True
            )
        except TypeError:
            ctx.wallet_start = ctx.scraper.get_wallet_snapshot()
        except Exception:  # noqa: BLE001
            ctx.wallet_start = None

        withdraw_result: Optional[dict[str, Any]] = None
        withdrawal_id: Optional[str] = None
        if ctx.confirm_real_withdraw and ctx.oracle is not None:
            try:
                result = ctx.oracle.attempt_withdraw(
                    amount=0,
                    confirm_real_withdraw=True,
                    use_max_available=True,
                )
                withdraw_result = result.model_dump(mode="json")
                data = (result.response_data or {}).get("data") or {}
                withdrawal_id = data.get("withdrawalId") or data.get("id")
            except Exception as exc:  # noqa: BLE001
                withdraw_result = {"ok": False, "error": str(exc)[:300]}
        else:
            pre: dict[str, Any] = {}
            if callable(getattr(ctx.scraper, "withdraw_preflight", None)):
                try:
                    pre = ctx.scraper.withdraw_preflight()
                except Exception:  # noqa: BLE001
                    pre = {}
            bal = 0.0
            if ctx.wallet_start is not None:
                bal = float(getattr(ctx.wallet_start, "balance", 0) or 0)
            max_amt = float(ctx.profile.max_withdraw or 10_000.0)
            would = WithdrawalOracle.resolve_max_amount(
                bal, max_amt, cents=ctx.profile.uses_cents
            )
            withdraw_result = {
                "ok": True,
                "preflight_only": True,
                "would_amount": would,
                "preflight": {
                    k: pre.get(k)
                    for k in (
                        "have_opened",
                        "withdrawal_allowed",
                        "methods",
                        "day_totals_brl",
                        "min_withdraw",
                    )
                },
            }
        # --- I5: Withdrawal denial handling ---
        # If the oracle returned a denial, extract the reason and provide guidance.
        if withdraw_result and not withdraw_result.get("ok"):
            deny_code = withdraw_result.get("denyReasonCode") or ""
            if deny_code:
                withdraw_result["denial_guidance"] = {
                    "WAGERING_NOT_MET": "Rollover incomplete. Increase wagering rounds in arm stage or reduce bonus amount.",
                    "MIN_WITHDRAW_NOT_MET": "Balance below minimum withdrawal. Wager less (accept smaller loss) to retain withdrawable balance.",
                    "BONUS_ACTIVE": "Bonus still active. Ensure rollover is fully cleared before withdrawing.",
                    "WITHDRAWAL_LIMIT": "Daily/weekly withdrawal limit reached. Wait or split into smaller withdrawals.",
                    "KYC_REQUIRED": "Account requires identity verification before withdrawal. Complete KYC first.",
                    "METHOD_UNAVAILABLE": "Selected withdrawal method unavailable. Try a different method (tft/pix/iban).",
                }.get(deny_code, f"Unknown denial: {deny_code}. Check house T&Cs for specific requirements.")
            if not withdraw_result.get("gates"):
                withdraw_result["gates"] = []

        ctx.withdraw_result = withdraw_result
        ctx.withdrawal_id = withdrawal_id

        settle: dict[str, Any] = {}
        if (
            ctx.confirm_real_withdraw
            and ctx.settle_withdraw
            and withdraw_result
            and withdraw_result.get("ok")
            and callable(
                getattr(ctx.scraper, "poll_withdrawal_settlement", None)
            )
        ):
            try:
                settle = ctx.scraper.poll_withdrawal_settlement(
                    withdrawal_id=withdrawal_id,
                    timeout_s=ctx.settle_timeout_s,
                    interval_s=5.0,
                    expect_amount_brl=float(withdraw_result.get("amount") or 0)
                    or None,
                )
            except Exception as exc:  # noqa: BLE001
                settle = {"error": str(exc)[:300]}
        else:
            try:
                hist = ctx.scraper.list_withdrawals(0, 10)
                items = list(hist.get("items") or [])[:10]
                settle = {
                    "mode": "history_only",
                    "items": [
                        {
                            "id": x.get("id"),
                            "status": x.get("status"),
                            "amount_brl": x.get("amount_brl"),
                        }
                        for x in items
                    ],
                }
            except Exception as exc:  # noqa: BLE001
                settle = {"error": str(exc)[:200]}
        ctx.settle = settle

        try:
            ctx.wallet_end = ctx.scraper.get_wallet_snapshot(
                include_bonus_state=True
            )
        except TypeError:
            ctx.wallet_end = ctx.scraper.get_wallet_snapshot()
        except Exception:  # noqa: BLE001
            ctx.wallet_end = None
        bonus_state = (
            (ctx.wallet_end.raw or {}).get("bonus_state")
            if ctx.wallet_end is not None
            else {}
        )
        ctx.diagnosis = diagnose_withdraw_stuck(
            wallet_start=(
                ctx.wallet_start.model_dump(mode="json")
                if ctx.wallet_start is not None
                else {}
            ),
            wallet_end=(
                ctx.wallet_end.model_dump(mode="json")
                if ctx.wallet_end is not None
                else {}
            ),
            withdraw_result=withdraw_result,
            settle=settle,
            bonus_state=bonus_state or {},
            arm_evidence=ctx.arm,
            confirm_real_withdraw=ctx.confirm_real_withdraw,
        )
        return StageResult(
            id=self.id,
            title=self.title,
            ok=bool(
                ctx.diagnosis.get("pix_materialized")
                or ctx.diagnosis.get("balance_increased")
            ),
            note=str(ctx.diagnosis.get("summary", "")),
            evidence={
                "withdraw": withdraw_result,
                "withdrawal_id": withdrawal_id,
                "settle": settle,
                "diagnosis": ctx.diagnosis,
            },
        )


class WageringCheckStage:
    id = "wagering_check"
    title = "Verificar rollover/wagering completion"
    capabilities: tuple[str, ...] = ()

    def run(self, ctx: JourneyContext) -> StageResult:
        """Verify that the wagering requirement is met before cashout.

        Reads bonus_state from the wallet snapshot. If rollover is incomplete,
        reports the remaining amount and marks the stage as not-ok (which
        prevents the cashout from being considered successful).

        If rollover is complete (or no bonus is active), the stage passes.
        """
        # Get current wallet + bonus state
        try:
            wallet = ctx.scraper.get_wallet_snapshot(
                include_bonus_state=True
            )
        except TypeError:
            wallet = ctx.scraper.get_wallet_snapshot()
        except Exception as exc:  # noqa: BLE001
            return StageResult(
                id=self.id,
                title=self.title,
                ok=False,
                note=f"wallet_snapshot_error: {exc}",
            )

        bonus_state = (wallet.raw or {}).get("bonus_state") or {}
        primary = bonus_state.get("primary") or {}

        # Determine rollover status
        rollover_remaining = float(
            primary.get("remaining_rollover_brl")
            or getattr(wallet, "rollover", 0)
            or 0
        )
        wagered = float(primary.get("wagered_brl") or 0)
        required = float(primary.get("required_rollover_brl") or 0)
        bonus_active = bool(primary) or float(getattr(wallet, "bonus", 0) or 0) > 0

        evidence: dict[str, Any] = {
            "rollover_remaining": rollover_remaining,
            "wagered": wagered,
            "required": required,
            "bonus_active": bonus_active,
            "bonus_balance": float(getattr(wallet, "bonus", 0) or 0),
            "cash_balance": float(getattr(wallet, "balance", 0) or 0),
        }

        if not bonus_active:
            return StageResult(
                id=self.id,
                title=self.title,
                ok=True,
                note="No bonus active — no rollover to verify",
                evidence=evidence,
            )

        if rollover_remaining <= 0:
            return StageResult(
                id=self.id,
                title=self.title,
                ok=True,
                note=f"Rollover complete (wagered={wagered:.2f}/{required:.2f})",
                evidence=evidence,
            )

        # Rollover incomplete — I4: poll briefly in case server is still processing
        for _poll in range(3):
            time.sleep(5.0)
            try:
                wallet2 = ctx.scraper.get_wallet_snapshot(include_bonus_state=True)
            except TypeError:
                wallet2 = ctx.scraper.get_wallet_snapshot()
            except Exception:
                break
            bs2 = (wallet2.raw or {}).get("bonus_state") or {}
            p2 = bs2.get("primary") or {}
            remaining2 = float(p2.get("remaining_rollover_brl") or 0)
            wagered2 = float(p2.get("wagered_brl") or 0)
            if remaining2 <= 0 or wagered2 >= required:
                evidence["rollover_remaining"] = remaining2
                evidence["wagered"] = wagered2
                evidence["settled_after_poll"] = True
                return StageResult(
                    id=self.id,
                    title=self.title,
                    ok=True,
                    note=f"Rollover settled after polling ({wagered2:.2f}/{required:.2f})",
                    evidence=evidence,
                )

        pct = 0.0
        if required > 0:
            pct = min(100.0, (wagered / required) * 100.0)
        return StageResult(
            id=self.id,
            title=self.title,
            ok=False,
            mode="BLOCKED",
            note=(
                f"Rollover incomplete: {wagered:.2f}/{required:.2f} "
                f"({pct:.1f}%) — remaining {rollover_remaining:.2f}. "
                "Cashout may be denied or bonus forfeited."
            ),
            evidence=evidence,
        )


class ReportStage:
    id = "report"
    title = "Relatório final (markdown + JSON)"
    capabilities: tuple[str, ...] = ()

    def run(self, ctx: JourneyContext) -> StageResult:
        # O relatório em si é escrito pelo orquestrador — aqui só sinaliza.
        return StageResult(
            id=self.id,
            title=self.title,
            ok=True,
            note="relatório emitido pelo orquestrador",
            evidence={"steps": len(ctx.steps)},
        )


# ---------------------------------------------------------------------------
# Plano da jornada
# ---------------------------------------------------------------------------

STAGE_ORDER: tuple[str, ...] = (
    "recon",
    "auth",
    "discovery",
    "acquire",
    "arm",
    "analyze",
    "probe",
    "wagering_check",
    "cashout",
    "report",
)

STAGE_CLASSES: dict[str, type] = {
    "recon": ReconStage,
    "auth": AuthStage,
    "discovery": DiscoveryStage,
    "acquire": AcquireStage,
    "arm": ArmStage,
    "analyze": AnalyzeStage,
    "probe": ProbeStage,
    "wagering_check": WageringCheckStage,
    "cashout": CashoutStage,
    "report": ReportStage,
}


def build_plan(profile: HouseProfile) -> JourneyPlan:
    """Escolhe estágios habilitados a partir do HouseProfile."""
    recommended = set(profile.recommended_stages)
    # Cashout is always available when the house exposes withdraw —
    # the oracle handles min_withdraw gates and denial codes internally.
    if profile.has("withdraw"):
        recommended.add("cashout")
    stages: list[Any] = []
    for sid in STAGE_ORDER:
        cls = STAGE_CLASSES[sid]
        # recon + report sempre rodam
        if sid in {"recon", "report"}:
            stages.append(cls())
            continue
        # auth é pré-requisito — sempre tenta
        if sid == "auth":
            stages.append(cls())
            continue
        # os demais: habilitados pelo profile + capacidades mínimas
        if sid not in recommended:
            continue
        caps = cls.capabilities
        if caps and not any(profile.has(c) for c in caps):
            continue
        stages.append(cls())
    return JourneyPlan(stages=stages)
