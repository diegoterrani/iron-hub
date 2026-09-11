"""
Jornada automática house-agnostic end-to-end.

HouseRecon → JourneyPlan (estágios discretos) → execução por estágio →
relatório final (markdown + JSON) com nomes genéricos por plataforma.

Objetivo do lab: maximizar bônus e materializar saque com the máximo de
automação. Spin/bet no provider (Spribe/Pragmatic) continua SEMI when the
WS/game API não está implemented — a jornada registra the gap and segue.

O módulo mantém as funções auxiliares de alto nível (diagnose_withdraw_stuck,
build_remediation_plan, build_auto_journey_markdown, _pick_llm_targets,
_enrich_offer_with_live_bonus) e a função livre claim_all_bonuses que os
estágios de src.abuse.stages importam.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

from src.abuse.house_profile import HouseProfile, HouseRecon
from src.abuse.oracle import WithdrawalOracle
from src.abuse.stages import JourneyContext, StageResult, build_plan
from src.models.abuse import AbuseFinding, AbuseSeverity, ConversionStatus
from src.models.bonus import BonusOffer
from src.storage.wallet import WalletCredit, WalletLedger


StepLogger = Callable[[str, str, str, str, dict[str, Any]], None]


class AutoJourneyRunner:
    """Orquestrador house-agnostic da jornada de exploração de bônus."""

    def __init__(
        self,
        scraper: Any,
        *,
        oracle: Optional[WithdrawalOracle] = None,
        findings: Any = None,
        ledger: Optional[WalletLedger] = None,
        offer_store: Any = None,
        process_offers: Optional[Callable[[list[BonusOffer]], list[BonusOffer]]] = None,
        reports_dir: str | Path = "data/reports",
        cache_dir: str | Path = "data/house_profiles",
        log: Optional[StepLogger] = None,
    ):
        self.scraper = scraper
        self.findings = findings
        self.oracle = oracle or WithdrawalOracle(scraper, findings=findings)
        self.ledger = ledger
        self.offer_store = offer_store
        self.process_offers = process_offers
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._log = log

    def _emit(
        self,
        step: str,
        kind: str,
        message: str,
        level: str = "info",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        if self._log:
            self._log(step, kind, message, level, detail or {})

    def run(
        self,
        *,
        confirm_redeem: bool = True,
        confirm_real_withdraw: bool = False,
        confirm_real_bet: bool = True,
        settle_withdraw: bool = True,
        settle_timeout_s: int = 90,
        promocode_limit: int = 25,
        llm_limit: int = 2,
        run_deep_attack: bool = True,
        poll_seconds: int = 25,
        persist_findings: bool = True,
        recon_use_llm: bool = True,
        recon_refresh: bool = False,
        recon_timeout_s: float = 45.0,
    ) -> dict[str, Any]:
        run_id = str(uuid4())
        started = datetime.now(timezone.utc)
        platform = str(getattr(self.scraper, "platform", "") or "unknown")
        stuck_point = "not_started"

        # ---------- RECON ----------
        recon = HouseRecon(
            self.scraper,
            cache_dir=self.cache_dir,
            log=self._emit,
        )
        try:
            profile = recon.run(
                use_llm=recon_use_llm,
                refresh=recon_refresh,
                timeout=recon_timeout_s,
            )
        except Exception as exc:  # noqa: BLE001
            self._emit(
                "auto",
                "auto.recon",
                f"Recon falhou: {exc}",
                "error",
                {"error": str(exc)[:300]},
            )
            return self._finalize(
                run_id,
                started,
                [],
                stuck_point="recon_failed",
                confirm_real_withdraw=confirm_real_withdraw,
                extra={"error": str(exc)[:300]},
                persist_findings=persist_findings,
            )
        self._emit(
            "auto",
            "auto.recon",
            f"Recon ok · caps={list(profile.capabilities.keys())} "
            f"stages={profile.recommended_stages}",
            "info",
            profile.model_dump(mode="json"),
        )

        # Update oracle with profile (house-agnostic min-withdraw/methods/cents)
        self.oracle.profile = profile

        # ---------- PLANO ----------
        plan = build_plan(profile)
        self._emit(
            "auto",
            "auto.plan",
            f"Plano: {plan.ids()}",
            "info",
            {"stages": plan.ids()},
        )

        # ---------- CONTEXTO ----------
        ctx = JourneyContext(
            scraper=self.scraper,
            profile=profile,
            oracle=self.oracle,
            findings=self.findings if persist_findings else None,
            ledger=self.ledger,
            offer_store=self.offer_store,
            process_offers=self.process_offers,
            confirm_redeem=confirm_redeem,
            confirm_real_withdraw=confirm_real_withdraw,
            confirm_real_bet=confirm_real_bet,
            settle_withdraw=settle_withdraw,
            settle_timeout_s=settle_timeout_s,
            promocode_limit=promocode_limit,
            llm_limit=llm_limit,
            run_deep_attack=run_deep_attack,
            poll_seconds=poll_seconds,
            persist_findings=persist_findings,
        )

        # ---------- EXECUÇÃO POR ESTÁGIO ----------
        for stage in plan.stages:
            sid = stage.id
            title = stage.title
            self._emit(
                "auto",
                f"auto.{sid}.start",
                f"Iniciando {sid}",
                "info",
                {"title": title},
            )
            try:
                result = stage.run(ctx)
            except Exception as exc:  # noqa: BLE001
                result = StageResult(
                    id=sid,
                    title=title,
                    ok=False,
                    note=f"exception: {str(exc)[:300]}",
                    evidence={"error": str(exc)[:500]},
                )
            ctx.add_step(result)
            self._emit(
                "auto",
                f"auto.{sid}",
                f"{title} · ok={result.ok} · {result.note}"[:220],
                "success" if result.ok else ("warn" if result.mode == "SEMI_AUTO" else "error"),
                result.to_dict(),
            )
            # auth falhou → aborta
            if sid == "auth" and not result.ok:
                stuck_point = "auth_failed"
                break

        # ---------- STUCK POINT ----------
        diagnosis = ctx.diagnosis or {}
        stuck_point = diagnosis.get("stuck_point") or "journey_completed"
        if stuck_point == "journey_completed":
            if ctx.withdraw_result and ctx.withdraw_result.get("ok"):
                stuck_point = "none_pix_materialized"
            else:
                stuck_point = "withdraw_not_attempted_this_run"

        # ---------- RELATÓRIO ----------
        return self._finalize(
            run_id,
            started,
            ctx.steps,
            stuck_point=stuck_point,
            confirm_real_withdraw=confirm_real_withdraw,
            extra={
                "profile": profile.model_dump(mode="json"),
                "plan": plan.ids(),
                "wallet_start": (
                    ctx.wallet_start.model_dump(mode="json")
                    if ctx.wallet_start is not None
                    else None
                ),
                "wallet_end": (
                    ctx.wallet_end.model_dump(mode="json")
                    if ctx.wallet_end is not None
                    else None
                ),
                "claim": ctx.claim,
                "arm_play": ctx.arm,
                "llm": {
                    "count": len(ctx.llm.get("items") or []),
                    "deep": ctx.llm.get("deep"),
                    "items": ctx.llm.get("items"),
                    "errors": ctx.llm.get("errors"),
                },
                "high_ev": {
                    "probed": ctx.high_ev.get("probed"),
                    "findings": ctx.high_ev.get("findings"),
                },
                "matrix": {
                    "run_id": ctx.matrix.get("run_id"),
                    "verdict": ctx.matrix.get("verdict"),
                    "vulnerabilities": ctx.matrix.get("vulnerabilities"),
                    "coverage": ctx.matrix.get("coverage"),
                    "stages": ctx.matrix.get("stages"),
                },
                "withdraw_result": ctx.withdraw_result,
                "settle": ctx.settle,
                "diagnosis": diagnosis,
            },
            persist_findings=persist_findings,
            llm_deep=ctx.llm.get("deep"),
        )

    def _finalize(
        self,
        run_id: str,
        started: datetime,
        steps: list[dict[str, Any]],
        *,
        stuck_point: str,
        confirm_real_withdraw: bool,
        extra: Optional[dict[str, Any]] = None,
        persist_findings: bool = True,
        llm_deep: Any = None,
    ) -> dict[str, Any]:
        finished = datetime.now(timezone.utc)
        extra = extra or {}
        diagnosis = extra.get("diagnosis") or {"stuck_point": stuck_point}
        remediation = build_remediation_plan(
            diagnosis=diagnosis,
            matrix=extra.get("matrix") or {},
            llm_deep=llm_deep or (extra.get("llm") or {}).get("deep"),
            steps=steps,
        )
        platform = str(getattr(self.scraper, "platform", "") or "unknown")
        payload = {
            "ok": stuck_point not in {"auth_failed", "recon_failed", "discovery_failed"},
            "run_id": run_id,
            "platform": platform,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "goal": "multiply_bonus_and_withdraw_fully_automated",
            "automation_goal_met": bool(
                diagnosis.get("pix_materialized") and diagnosis.get("bonus_multiplied")
            ),
            "stuck_point": stuck_point,
            "steps": steps,
            "remediation": remediation,
            **extra,
        }
        md = build_auto_journey_markdown(payload)
        # Nomes genéricos por plataforma (não mais "pagol-auto-journey-*")
        json_path = self.reports_dir / f"auto-journey-{platform}-{run_id[:8]}.json"
        md_path = self.reports_dir / f"auto-journey-{platform}-{run_id[:8]}.md"
        latest_md = self.reports_dir / f"auto-journey-{platform}-latest.md"
        latest_json = self.reports_dir / f"auto-journey-{platform}-latest.json"
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        md_path.write_text(md, encoding="utf-8")
        latest_md.write_text(md, encoding="utf-8")
        latest_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        payload["report_md_path"] = str(md_path)
        payload["report_json_path"] = str(json_path)
        payload["report_latest_md"] = str(latest_md)
        payload["report_markdown"] = md
        payload["report_filename"] = f"auto-journey-{platform}-{run_id[:8]}.md"

        if persist_findings and self.findings is not None:
            self.findings.add(
                AbuseFinding(
                    platform=platform,
                    vector="auto_journey",
                    severity=AbuseSeverity.HIGH,
                    title=f"Auto-journey · stuck={stuck_point}",
                    status=ConversionStatus.UNKNOWN,
                    abuse_score=7.0,
                    evidence={
                        "run_id": run_id,
                        "stuck_point": stuck_point,
                        "diagnosis": diagnosis,
                        "automation_goal_met": payload["automation_goal_met"],
                    },
                )
            )
        self._emit(
            "auto",
            "auto.finished",
            f"Auto-journey finished · stuck={stuck_point} · report={md_path.name}",
            "success",
            {"run_id": run_id, "stuck_point": stuck_point},
        )
        return payload


def claim_all_bonuses(
    scraper: Any,
    offers: list[BonusOffer],
    *,
    confirm_redeem: bool,
    promocode_limit: int,
) -> dict[str, Any]:
    """Redeem promocodes + activate READY/ACTIVE bonuses (house-agnostic)."""
    results: list[dict[str, Any]] = []
    activated: list[dict[str, Any]] = []
    codes: list[str] = []
    for o in offers:
        if o.title.startswith("[promocode]"):
            code = o.title.replace("[promocode]", "", 1).strip()
            if code:
                codes.append(code)
    try:
        for item in scraper.list_enabled_promocodes()[:promocode_limit]:
            c = str(item.get("code") or item.get("promocode") or "").strip()
            if c and c not in codes:
                codes.append(c)
    except Exception:  # noqa: BLE001
        pass
    codes = codes[:promocode_limit]

    if confirm_redeem:
        for code in codes:
            try:
                results.append(scraper.redeem_promocode(code, confirm_redeem=True))
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {"ok": False, "promocode": code, "error": str(exc)[:200]}
                )

    try:
        bonuses = scraper.list_bonuses(
            statuses=("READY", "PENDING", "ACTIVE"), page_size=20, max_pages=2
        )
    except Exception:  # noqa: BLE001
        bonuses = []
    for b in bonuses:
        bid = b.get("id") or b.get("bonusId")
        if not bid:
            continue
        activated.append(scraper.claim_or_activate_bonus(int(bid)))

    state = {}
    try:
        state = scraper.get_bonus_conversion_state()
    except Exception:  # noqa: BLE001
        pass
    ok_redeem = sum(1 for r in results if r.get("ok"))
    active = bool(state.get("primary"))
    return {
        "promocodes_tried": len(results),
        "promocodes_ok": ok_redeem,
        "activate_tried": len(activated),
        "any_success": ok_redeem > 0,
        "active_bonus": active,
        "primary": state.get("primary"),
        "redeem_sample": [
            {
                "promocode": r.get("promocode"),
                "ok": r.get("ok"),
                "error": (r.get("error") or "")[:120],
                "bonus_delta": r.get("bonus_delta"),
            }
            for r in results[:12]
        ],
        "activate_sample": activated[:8],
        "note": (
            f"redeem_ok={ok_redeem}/{len(results)} · active_bonus={active} · "
            "códigos afiliado tipicamente promocode_not_found"
        ),
    }


def diagnose_withdraw_stuck(
    *,
    wallet_start: dict[str, Any],
    wallet_end: dict[str, Any],
    withdraw_result: Optional[dict[str, Any]],
    settle: dict[str, Any],
    bonus_state: dict[str, Any],
    arm_evidence: dict[str, Any],
    confirm_real_withdraw: bool,
) -> dict[str, Any]:
    bal0 = float((wallet_start or {}).get("balance") or 0)
    bal1 = float((wallet_end or {}).get("balance") or 0)
    bonus0 = float((wallet_start or {}).get("bonus") or 0)
    bonus1 = float((wallet_end or {}).get("bonus") or 0)
    primary = (bonus_state or {}).get("primary") or {}
    remaining = float(
        primary.get("remaining_rollover_brl")
        or (wallet_end or {}).get("rollover")
        or 0
    )
    poll = ((arm_evidence or {}).get("mines_lab") or {}).get("poll") or {}
    play_changed = bool(poll.get("changed"))

    pix_materialized = bool(settle.get("materialized"))
    bo_denied = bool(settle.get("bo_denied"))
    api_ok = bool(withdraw_result and withdraw_result.get("ok"))
    balance_increased = bal1 > bal0 + 0.009
    balance_restored_after_deny = bo_denied and bal1 >= bal0 - 0.01

    secondary: list[str] = []
    if not play_changed and not (
        (arm_evidence or {}).get("mines_lab") or {}
    ).get("auto_bet_implemented"):
        secondary.append("provider_autobet_missing_cannot_multiply")
    if remaining > 0:
        secondary.append("rollover_incomplete_blocks_bonus_cashout")
    items = settle.get("items") or []
    denied_n = sum(
        1 for x in items if str(x.get("status") or "").upper() in {"DENIED", "REJECTED"}
    )
    if denied_n >= 2:
        secondary.append("bo_denied_on_cash_withdraw_history")
    if float(primary.get("max_convert_brl") or 0) > 0:
        secondary.append("max_convert_caps_extractable_value")

    if not confirm_real_withdraw:
        if "provider_autobet_missing_cannot_multiply" in secondary:
            stuck = "provider_autobet_missing_cannot_multiply"
        elif "rollover_incomplete_blocks_bonus_cashout" in secondary:
            stuck = "rollover_incomplete_blocks_bonus_cashout"
        elif "bo_denied_on_cash_withdraw_history" in secondary:
            stuck = "bo_denied_on_cash_withdraw_history"
        else:
            stuck = "withdraw_not_attempted_this_run"
        summary = (
            f"Sem PIX nesta run. stuck={stuck}. "
            f"bloqueios={secondary}. "
            f"Δbalance={round(bal1 - bal0, 2)} Δbonus={round(bonus1 - bonus0, 2)} "
            f"rollover_restante={remaining}."
        )
    elif not api_ok:
        stuck = "oracle_api_rejected"
        summary = f"API rejeitou saque: {(withdraw_result or {}).get('code')}"
        secondary = [stuck] + secondary
    elif pix_materialized:
        stuck = "none_pix_materialized"
        summary = "PIX materializado (status terminal positivo no BO)."
    elif bo_denied:
        stuck = "api_success_but_bo_denied"
        summary = (
            "API aceitou pedido (SUCCESS/withdraw_ok) mas BO DENIED — "
            f"saldo restaurado={balance_restored_after_deny}."
        )
        secondary = [stuck] + [s for s in secondary if s != stuck]
    elif settle.get("final_status"):
        stuck = f"withdraw_pending_status_{settle.get('final_status')}"
        summary = f"Saque ainda em status {settle.get('final_status')}."
    else:
        stuck = "withdraw_settle_timeout"
        summary = "Timeout no poll de settle — status BO indefinido."

    seen: set[str] = set()
    secondary_u: list[str] = []
    for s in secondary:
        if s and s not in seen:
            seen.add(s)
            secondary_u.append(s)

    return {
        "stuck_point": stuck,
        "secondary_blockers": secondary_u,
        "summary": summary,
        "pix_materialized": pix_materialized,
        "bo_denied": bo_denied,
        "api_ok": api_ok,
        "balance_start": bal0,
        "balance_end": bal1,
        "balance_delta": round(bal1 - bal0, 2),
        "bonus_start": bonus0,
        "bonus_end": bonus1,
        "bonus_delta": round(bonus1 - bonus0, 2),
        "balance_increased": balance_increased,
        "balance_restored_after_deny": balance_restored_after_deny,
        "remaining_rollover_brl": remaining,
        "max_convert_brl": primary.get("max_convert_brl"),
        "bonus_multiplied": play_changed and (bonus1 > bonus0 or bal1 > bal0),
        "play_wallet_changed": play_changed,
        "auto_bet_implemented": bool(
            ((arm_evidence or {}).get("mines_lab") or {}).get("auto_bet_implemented")
        ),
    }


def build_remediation_plan(
    *,
    diagnosis: dict[str, Any],
    matrix: dict[str, Any],
    llm_deep: Any,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Plano de remediação sem datas de calendário — backlog por prioridade/owner."""
    stuck = diagnosis.get("stuck_point") or "unknown"
    backlog: list[dict[str, Any]] = []

    deep_llm = {}
    if isinstance(llm_deep, dict):
        deep_llm = llm_deep.get("llm") or {}
        for item in (
            deep_llm.get("protection_backlog")
            or deep_llm.get("protection_plan")
            or []
        ):
            if not isinstance(item, dict):
                continue
            backlog.append(
                {
                    "priority": item.get("priority") or "P1",
                    "owner": item.get("owner") or "product",
                    "title": item.get("title") or "Correção LLM",
                    "why": item.get("why") or "",
                    "implementation": (
                        item.get("implementation") or item.get("fixes") or []
                    ),
                    "blocks_vectors": item.get("blocks_vectors") or [],
                    "effort": item.get("effort") or item.get("effort_days"),
                }
            )

    proven = [
        {
            "priority": "P0",
            "owner": "payments",
            "title": "Separar accept de pedido PIX de materialização no BO",
            "why": (
                "API devolve SUCCESS/withdraw_ok enquanto BO DENIED em série; "
                "operadores e labs interpretam falso positivo de saque."
            ),
            "implementation": [
                "Status de cliente deve refletir BO (PENDING/DENIED/PAID), não só HTTP 200 do request.do",
                "Webhook/evento interno request_accepted ≠ payout_completed",
                "UI e API de histórico alinhados ao mesmo enum",
            ],
            "blocks_vectors": [
                "withdraw_ok_api_but_bo_denied",
                "false_withdraw_success",
            ],
            "effort": "medium",
            "team": "DEV + Payments",
        },
        {
            "priority": "P0",
            "owner": "risk",
            "title": "Documentar e expor motivo de DENIED ao canal CRM",
            "why": f"stuck_point observado: {stuck}. CRM precisa de código/razão para atendimento.",
            "implementation": [
                "Campo denyReasonCode + denyReasonMessage no withdrawal detail",
                "Macros CRM por código (KYC, risco, limite diário, bonus residual)",
                "Playbook: quando reprocessar vs pedir documento vs manter bloqueio",
            ],
            "blocks_vectors": ["repeated_bo_denied_on_cash_withdraw"],
            "effort": "low",
            "team": "CRM + Risk",
        },
        {
            "priority": "P1",
            "owner": "platform",
            "title": "Enforcement server-side de bonusGameTypes + maxBet",
            "why": "Launch high-EV com useBonusBalance pode ser aceito mesmo com bônus SLOTS-only.",
            "implementation": [
                "Recusar start.do useBonusBalance=true se gameType ∉ bonusGameTypes",
                "Recusar stake > maxSelectableBalanceBet no motor, não só no lobby",
                "Teste de aceitação: Mines/Aviator + bônus SLOTS → erro explícito",
            ],
            "blocks_vectors": [
                "high_ev_launch_ok_but_bonus_game_type_blocks_stake",
                "max_bet_bypass",
            ],
            "effort": "medium",
            "team": "DEV Platform",
        },
        {
            "priority": "P1",
            "owner": "product",
            "title": "Alinhar balance.do.bonusBalance com bonuses/balance.do",
            "why": "balance.do zera bonusBalance enquanto bônus ACTIVE ainda tem saldo — quebra oráculos e UI.",
            "implementation": [
                "Single source of truth para bonus wallet",
                "Expor remainingRollover e maxConvert no snapshot de balance",
            ],
            "blocks_vectors": ["wallet_signal_mismatch"],
            "effort": "medium",
            "team": "DEV",
        },
        {
            "priority": "P2",
            "owner": "product",
            "title": "Separar catálogo all-enabled (afiliado) de códigos resgatáveis",
            "why": "Redeem em massa retorna promocode_not_found — ruído operacional e falso discovery.",
            "implementation": [
                "Endpoint redeemable-for-user vs marketing codes",
                "CRM: não oferecer códigos de afiliado como bônus jogável",
            ],
            "blocks_vectors": ["promocode_not_redeemable"],
            "effort": "low",
            "team": "CRM + Product",
        },
    ]
    seen = {b["title"] for b in backlog}
    for row in proven:
        if row["title"] not in seen:
            backlog.append(row)
            seen.add(row["title"])

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    backlog.sort(key=lambda x: priority_order.get(str(x.get("priority") or "P3"), 9))

    vuln_titles = [
        v.get("vulnerability")
        for v in (matrix.get("vulnerabilities") or [])
        if isinstance(v, dict)
    ]

    return {
        "stuck_point": stuck,
        "dev_instructions": [
            "Tratar withdraw request SUCCESS e payout BO como estados distintos no contrato da API.",
            "Bloquear start.do com useBonusBalance quando gameType não está em bonusGameTypes.",
            "Unificar campos de rollover/maxConvert/bonusBalance nos endpoints de wallet.",
            "Adicionar testes de regressão: DENIED restaura saldo; SLOTS bonus ≠ Mines stake.",
            "Instrumentar métricas: withdraw_api_ok_bo_denied_rate, bonus_launch_game_type_mismatch.",
        ],
        "crm_instructions": [
            "Não informar cliente que o saque 'foi pago' só porque o pedido foi aceito.",
            "Usar histórico de status (DENIED/VERIFIED) + código de negação quando disponível.",
            "Se houver bônus ACTIVE com rollover, orientar conclusão do rollover antes de insistir em PIX do bônus.",
            "Códigos de afiliado/promocode da lista marketing não são bônus jogáveis — não prometer crédito.",
            f"Para este lab, ponto de travamento: {stuck}.",
        ],
        "backlog": backlog,
        "matrix_vulnerabilities": vuln_titles,
        "note": "Plano sem datas de calendário — priorização por P0–P3 e owner.",
    }


def build_auto_journey_markdown(payload: dict[str, Any]) -> str:
    rem = payload.get("remediation") or {}
    diag = payload.get("diagnosis") or {}
    platform = payload.get("platform") or "unknown"
    lines = [
        f"# {platform} · Relatório final — Jornada automática",
        "",
        f"- Run: `{payload.get('run_id')}`",
        f"- Plataforma: `{platform}`",
        f"- Objetivo: **multiplicar bônus e sacar 100% automatizado**",
        f"- Objetivo atingido: **{payload.get('automation_goal_met')}**",
        f"- Ponto de travamento: **`{payload.get('stuck_point')}`**",
        f"- Gerado em: `{payload.get('finished_at')}`",
        "",
        "## House Profile (recon)",
        "",
        "```json",
        json.dumps(payload.get("profile") or {}, ensure_ascii=False, indent=2, default=str)[:4000],
        "```",
        "",
        "## Diagnóstico de saque / saldo",
        "",
        str(diag.get("summary") or ""),
        "",
        f"- Bloqueios secundários: `{', '.join(diag.get('secondary_blockers') or []) or '—'}`",
        "",
        "```json",
        json.dumps(diag, ensure_ascii=False, indent=2, default=str),
        "```",
        "",
        "## Timeline da jornada",
        "",
    ]
    for s in payload.get("steps") or []:
        lines.append(
            f"### [{s.get('mode')}] `{s.get('id')}` — {s.get('title')} "
            f"{'OK' if s.get('ok') else 'FALHOU/PARCIAL'}"
        )
        lines.append("")
        if s.get("note"):
            lines.append(f"{s.get('note')}")
            lines.append("")
        ev = s.get("evidence") or {}
        if ev:
            lines.extend(
                [
                    "<details><summary>evidence</summary>",
                    "",
                    "```json",
                    json.dumps(ev, ensure_ascii=False, indent=2, default=str)[:18000],
                    "```",
                    "",
                    "</details>",
                    "",
                ]
            )

    lines.extend(
        [
            "## Kill-chain / vulnerabilidades",
            "",
            "```json",
            json.dumps(
                (payload.get("matrix") or {}).get("vulnerabilities") or [],
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "## Plano de remediação (sem datas de calendário)",
            "",
            rem.get("note") or "",
            "",
            "### Instruções — Time DEV",
            "",
        ]
    )
    for row in rem.get("dev_instructions") or []:
        lines.append(f"- {row}")
    lines.extend(["", "### Instruções — Time CRM", ""])
    for row in rem.get("crm_instructions") or []:
        lines.append(f"- {row}")
    lines.extend(["", "### Backlog priorizado", ""])
    for item in rem.get("backlog") or []:
        lines.append(
            f"#### [{item.get('priority')}] {item.get('title')} · owner={item.get('owner')} · "
            f"team={item.get('team') or item.get('owner')}"
        )
        if item.get("why"):
            lines.append(f"\n{item.get('why')}\n")
        impl = item.get("implementation") or []
        if impl:
            lines.append("**Implementação:**")
            for x in impl:
                lines.append(f"- {x}")
            lines.append("")
        if item.get("blocks_vectors"):
            lines.append(
                f"**Bloqueia:** {', '.join(map(str, item.get('blocks_vectors') or []))}\n"
            )

    deep = (payload.get("llm") or {}).get("deep") or {}
    if deep:
        llm = deep.get("llm") or {}
        lines.extend(
            [
                "## Deep attack (LLM)",
                "",
                f"- Título: {deep.get('title')}",
                f"- Model: {deep.get('model')}",
                "",
                str(llm.get("summary") or ""),
                "",
            ]
        )
        if llm.get("primary_kill_chain"):
            lines.extend(["**Kill chain:**", "", str(llm.get("primary_kill_chain")), ""])

    lines.extend(
        [
            "## Snapshots de carteira",
            "",
            "### Start",
            "",
            "```json",
            json.dumps(
                payload.get("wallet_start") or {}, ensure_ascii=False, indent=2, default=str
            )[:8000],
            "```",
            "",
            "### End",
            "",
            "```json",
            json.dumps(
                payload.get("wallet_end") or {}, ensure_ascii=False, indent=2, default=str
            )[:8000],
            "```",
            "",
            "---",
            "",
            "_BetBonus AI · auto-journey · lab autorizado Iron Red Team._",
            "",
        ]
    )
    return "\n".join(lines)


def _pick_llm_targets(
    offers: list[BonusOffer], primary: dict[str, Any], *, limit: int, platform: str = "unknown"
) -> list[BonusOffer]:
    ranked = sorted(
        offers,
        key=lambda o: (
            0 if o.title.startswith("[conta]") else 1 if o.title.startswith("[promo]") else 2,
            -(float(o.score or 0)),
        ),
    )
    out = ranked[: max(1, limit)]
    if primary and not any(o.title.startswith("[conta]") for o in out):
        synthetic = BonusOffer(
            platform=platform,
            title=f"[conta] {primary.get('name') or 'BONUS LIVE'}",
            amount=float(primary.get("balance_brl") or 0),
            currency="BRL",
            wagering_multiple=float(primary.get("wagering_multiple_est") or 10),
            max_bet_during_bonus=primary.get("max_bet_brl"),
            game_restrictions=list(primary.get("bonus_game_types") or []),
            raw_text=json.dumps(primary, ensure_ascii=False),
        )
        out = [synthetic] + out
    return out[: max(1, limit)]


def _enrich_offer_with_live_bonus(
    offer: BonusOffer, primary: dict[str, Any], bonus_state: dict[str, Any]
) -> BonusOffer:
    if not primary:
        return offer
    block = (
        "\n\n--- LIVE BONUS STATE ---\n"
        + json.dumps(primary, ensure_ascii=False, indent=2, default=str)
        + "\n--- STRATEGY ---\n"
        + json.dumps(bonus_state.get("strategy") or {}, ensure_ascii=False, indent=2)
    )
    return offer.model_copy(
        update={
            "raw_text": ((offer.raw_text or "") + block)[:12000],
            "amount": float(primary.get("balance_brl") or offer.amount or 0),
            "max_bet_during_bonus": primary.get("max_bet_brl") or offer.max_bet_during_bonus,
            "game_restrictions": list(primary.get("bonus_game_types") or [])
            or list(offer.game_restrictions or []),
        }
    )
