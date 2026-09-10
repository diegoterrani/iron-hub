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
from src.scrapers.base import BaseScraper
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
    Runner house-agnostic: inventário → probes → estratégia de max valor →
    saque (opt) → settle BO.

    Suporta PagolScraper, FourPlayScraper (4play.game), FourPlayBrScraper
    (4play.bet.br) — cada estágio é adaptado via capability detection.
    """

    def __init__(
        self,
        scraper: BaseScraper,
        *,
        oracle: Optional[WithdrawalOracle] = None,
        findings: Any = None,
    ):
        self.scraper = scraper
        self.oracle = oracle or WithdrawalOracle(scraper, findings=findings)
        self.findings = findings

    # --- Capability helpers ---

    def _has(self, method: str) -> bool:
        return callable(getattr(self.scraper, method, None))

    def _get_wallet(self, **kwargs: Any) -> Any:
        """Call get_wallet_snapshot, dropping unsupported kwargs."""
        if kwargs:
            try:
                return self.scraper.get_wallet_snapshot(**kwargs)
            except TypeError:
                pass
        return self.scraper.get_wallet_snapshot()

    def _get_bonus_state(self, wallet: Any) -> dict[str, Any]:
        """Extract bonus state dict from wallet or fallback to scraper method."""
        bs = (wallet.raw or {}).get("bonus_state")
        if bs:
            return bs
        if self._has("get_bonus_conversion_state"):
            return self.scraper.get_bonus_conversion_state()
        # Fallback: build minimal state from wallet + list_my_bonuses
        return self._build_bonus_state_fallback(wallet)

    def _build_bonus_state_fallback(self, wallet: Any) -> dict[str, Any]:
        """Build a minimal bonus_state dict for scrapers without PAGOL-specific state."""
        count = 0
        if self._has("list_my_bonuses"):
            try:
                count = len(self.scraper.list_my_bonuses())
            except Exception:  # noqa: BLE001
                count = 0
        return {
            "count": count,
            "primary": None,
            "theoretical_max_convert_brl": None,
            "strategy": {},
        }

    def _max_withdraw_amount(self) -> float:
        """Platform-specific max withdraw cap."""
        return float(getattr(self.scraper, "MAX_WITHDRAW_AMOUNT", 10_000.0))

    def _is_cents(self) -> bool:
        """Whether the platform uses cents for amounts."""
        return bool(getattr(self.scraper, "AMOUNT_SCALE", 1)) != 1

    def _list_withdrawals_fallback(self) -> list[dict[str, Any]]:
        """Get withdrawal history via platform-specific method."""
        if self._has("list_withdrawals"):
            hist = self.scraper.list_withdrawals(0, 8)
            return list(hist.get("items") or [])
        if self._has("list_wallet_transactions"):
            data = self.scraper.list_wallet_transactions(page=1, per_page=8)
            items = data.get("items") or data.get("data") or []
            if isinstance(items, list):
                return [
                    {
                        "id": x.get("id"),
                        "status": str(x.get("type") or x.get("status") or "").upper(),
                        "amount_brl": x.get("amount"),
                    }
                    for x in items
                    if isinstance(x, dict)
                ]
        return []

    def _find_first_game(self) -> Any:
        """Find the first available game ID via the scraper's game listing."""
        if self._has("list_casino_games"):
            games = self.scraper.list_casino_games(page=1, per_page=5)
            items = games.get("items") or games.get("data") or []
            if isinstance(items, list) and items:
                g = items[0]
                return g.get("id") or g.get("gameId") or g.get("game_id")
        if self._has("list_wagering_game_ids"):
            ids = self.scraper.list_wagering_game_ids()
            if isinstance(ids, list) and ids:
                return ids[0]
        return None

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
        auto_spin: bool = False,
        spin_clicks: int = 1,
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
        wallet = self._get_wallet(include_bonus_state=True)
        bonus_state = self._get_bonus_state(wallet)
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
        if code and self._has("validate_promocode"):
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
                    wallet = self._get_wallet(include_bonus_state=True)
                    bonus_state = self._get_bonus_state(wallet)
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
        elif code:
            add(
                MatrixStageResult(
                    id="acquire_promocode",
                    title=f"Promocode {code} (não suportado nesta plataforma)",
                    mode="BLOCKED",
                    ok=False,
                    note="Scraper não implementa validate_promocode",
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
        if probe_high_ev and self._has("probe_high_ev_contribution"):
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
        elif probe_high_ev:
            add(
                MatrixStageResult(
                    id="probe_high_ev",
                    title="Soft-probe high-EV",
                    mode="SKIPPED",
                    ok=True,
                    note="Método probe_high_ev_contribution indisponível nesta plataforma",
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
        if probe_slots and self._has("probe_slots_for_bonus"):
            try:
                slots = self.scraper.probe_slots_for_bonus(
                    limit=slots_limit,
                    use_bonus_balance=bool(primary and float(primary.get("balance_brl") or 0) > 0),
                    auto_spin=auto_spin,
                    spin_clicks=spin_clicks,
                )
                slots_auto = bool(slots.get("auto_spin"))
                add(
                    MatrixStageResult(
                        id="probe_slots",
                        title=(
                            "Auto-spin slots elegíveis (browser Chromium)"
                            if slots_auto
                            else "Soft-probe slots elegíveis (path de rollover real)"
                        ),
                        mode="AUTOMATED",
                        ok=int(slots.get("launches_ok") or 0) > 0,
                        severity="medium",
                        vulnerability=(
                            "slots_bonus_auto_spin_executed"
                            if slots_auto
                            else "slots_bonus_launch_ok_spin_manual"
                        ),
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
        elif probe_slots and self._has("start_game"):
            # Generic: launch a game to verify the launch path works
            try:
                use_bonus = bool(primary and float(primary.get("balance_brl") or 0) > 0)
                game_id = self._find_first_game()
                if game_id is None:
                    raise RuntimeError("Nenhum jogo encontrado para probe")
                launch = self.scraper.start_game(
                    game_id, use_bonus_balance=use_bonus,
                )
                ok = bool(launch.get("url") or launch.get("ok"))
                add(
                    MatrixStageResult(
                        id="probe_slots",
                        title="Launch probe (start_game — path de sessão real)",
                        mode="AUTOMATED",
                        ok=ok,
                        severity="medium",
                        vulnerability="game_launch_ok_spin_manual",
                        note=str(launch.get("note") or launch.get("error") or "launch via start_game"),
                        evidence={"game_id": game_id, "url": launch.get("url", "")[:200]},
                    )
                )
            except Exception as exc:  # noqa: BLE001
                add(
                    MatrixStageResult(
                        id="probe_slots",
                        title="Launch probe (start_game)",
                        mode="BLOCKED",
                        ok=False,
                        note=str(exc)[:300],
                    )
                )
        elif probe_slots:
            add(
                MatrixStageResult(
                    id="probe_slots",
                    title="Soft-probe slots",
                    mode="SKIPPED",
                    ok=True,
                    note="Nenhum método de probe disponível (probe_slots_for_bonus/start_game)",
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
        auto_bet_available = bool(strategy.get("auto_bet_available"))
        add(
            MatrixStageResult(
                id="maximize_convertible",
                title="Maximizar valor conversível (plano + teto maxConvert)",
                mode="AUTOMATED" if auto_bet_available else "SEMI_AUTO",
                ok=remaining <= 0 and bool(primary),
                severity="high" if remaining > 0 else "info",
                vulnerability="rollover_gate_caps_extractable_value",
                note=(
                    f"Teto teórico materializável via bônus ≈ R$ {bonus_state.get('theoretical_max_convert_brl')}. "
                    f"Auto-bet: {strategy.get('auto_bet_available')} "
                    f"({strategy.get('auto_bet_method') or strategy.get('auto_bet_blocker')})."
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
                    "auto_spin_implemented": auto_bet_available,
                    "auto_bet_spribe_implemented": auto_bet_available,
                },
            )
        )

        if arm_wager_poll and self._has("run_bonus_multiplier_lab"):
            # Arma Mines só se high-EV elegível; senão arma 1º slot ok
            try:
                max_stake = float(getattr(self.scraper, "MAX_LAB_STAKE_BRL", 100.0))
                default_stake = float(getattr(self.scraper, "DEFAULT_LAB_STAKE_BRL", 10.0))
                lab = self.scraper.run_bonus_multiplier_lab(
                    stake_brl=min(
                        float((primary or {}).get("max_bet_brl") or default_stake),
                        max_stake,
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
        elif arm_wager_poll:
            add(
                MatrixStageResult(
                    id="arm_wager_poll",
                    title="Armar sessão + poll",
                    mode="SKIPPED",
                    ok=True,
                    note="run_bonus_multiplier_lab não disponível nesta plataforma",
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
        if self._has("withdraw_preflight"):
            try:
                pre = self.scraper.withdraw_preflight()
                have_opened = bool(pre.get("have_opened"))
                allowed = pre.get("withdrawal_allowed")
                add(
                    MatrixStageResult(
                        id="withdraw_preflight",
                        title="Preflight saque (methods/have_opened)",
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
        else:
            add(
                MatrixStageResult(
                    id="withdraw_preflight",
                    title="Preflight saque",
                    mode="SKIPPED",
                    ok=True,
                    note="withdraw_preflight não disponível nesta plataforma",
                )
            )

        # 8) Withdraw request (max available) — only with confirm
        withdraw_result: dict[str, Any] | None = None
        withdrawal_id: Any = None
        platform_name = str(getattr(self.scraper, "platform", "") or "")
        withdraw_method = "tft" if "4play" in platform_name else "PIX"
        if confirm_real_withdraw and self._has("withdraw"):
            result = self.oracle.attempt_withdraw(
                amount=0,
                confirm_real_withdraw=True,
                method=withdraw_method,
                max_amount=self._max_withdraw_amount(),
                preflight_only=False,
                use_max_available=True,
            )
            withdraw_result = result.model_dump(mode="json")
            data = (result.response_data or {}).get("data") or {}
            withdrawal_id = data.get("withdrawalId") or data.get("id")
            add(
                MatrixStageResult(
                    id="withdraw_request",
                    title="Pedir saque máximo (API)",
                    mode="AUTOMATED",
                    ok=bool(result.ok),
                    severity="high",
                    vulnerability=(
                        "api_accepts_withdraw_request"
                        if result.ok
                        else "api_rejects_withdraw_request"
                    ),
                    note=(
                        "API SUCCESS/withdraw_ok ≠ materializado — "
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
        elif confirm_real_withdraw:
            add(
                MatrixStageResult(
                    id="withdraw_request",
                    title="Pedir saque máximo",
                    mode="SKIPPED",
                    ok=True,
                    note="withdraw() não disponível nesta plataforma",
                )
            )
        else:
            add(
                MatrixStageResult(
                    id="withdraw_request",
                    title="Pedir saque máximo (API)",
                    mode="SKIPPED",
                    ok=True,
                    note="confirm_real_withdraw=false — nenhum saque solicitado",
                    evidence={
                        "would_amount": WithdrawalOracle.resolve_max_amount(
                            wallet.balance,
                            self._max_withdraw_amount(),
                            cents=self._is_cents(),
                        )
                    },
                )
            )

        # 9) Settle / materialization
        _result_ok = bool(withdraw_result and withdraw_result.get("ok"))
        if confirm_real_withdraw and settle_withdraw and _result_ok and self._has("poll_withdrawal_settlement"):
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
            items = self._list_withdrawals_fallback()[:8]
            if items:
                denied_n = sum(
                    1
                    for x in items
                    if str(x.get("status") or "").upper() in {"DENIED", "REJECTED"}
                )
                verified_n = sum(
                    1
                    for x in items
                    if str(x.get("status") or "").upper()
                    in {"VERIFIED", "APPROVED", "PAID", "COMPLETED", "SUCCESS"}
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
            else:
                add(
                    MatrixStageResult(
                        id="withdraw_settle",
                        title="Histórico de materialização",
                        mode="SKIPPED",
                        ok=True,
                        note="Nenhum histórico de saque disponível",
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

        # Determine if auto-bet is implemented (env-gated + capability)
        auto_bet_implemented = bool(getattr(self.scraper, "AUTO_BET_ENABLED", False))
        not_automatable: list[str] = []
        if not auto_bet_implemented:
            not_automatable.append("provider_slot_auto_spin")
        if not self._has("run_bonus_multiplier_lab"):
            not_automatable.append("bonus_multiplier_lab")
        not_automatable.extend(["bo_bonus_credit_claim", "bo_approve_withdraw"])
        coverage = {
            "automated_stages": automated,
            "semi_auto_stages": semi,
            "manual_stages": manual,
            "blocked_or_failed": blocked,
            "not_automatable_yet": not_automatable,
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


def run_pagol_matrix(scraper: BaseScraper, **kwargs: Any) -> dict[str, Any]:
    """Backward-compatible entry point — works with any scraper."""
    return KillChainMatrix(scraper).run(**kwargs)
