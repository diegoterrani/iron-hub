"""
Jornada automática PAGOL end-to-end.

Auth → Discovery → Claim/Redeem → Arm Mines/Slots + poll → LLM T&Cs →
High-EV probe → Kill-chain matrix → Oracle → Settle/diagnóstico → Relatório.

Objetivo do lab: maximizar bônus e materializar saque com o máximo de automação.
Spin/bet no provider (Spribe/Pragmatic) continua SEMI quando o WS/game API
não está implementado — a jornada registra o gap e segue.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

from src.abuse.matrix import KillChainMatrix
from src.abuse.oracle import WithdrawalOracle
from src.llm.abuse_assist import AbuseLLMAssist
from src.models.abuse import AbuseFinding, AbuseSeverity, ConversionStatus
from src.models.bonus import BonusOffer
from src.scrapers.pagol_scraper import PagolScraper
from src.storage.wallet import WalletCredit, WalletLedger


StepLogger = Callable[[str, str, str, str, dict[str, Any]], None]


class AutoJourneyRunner:
    def __init__(
        self,
        scraper: PagolScraper,
        *,
        oracle: Optional[WithdrawalOracle] = None,
        findings: Any = None,
        ledger: Optional[WalletLedger] = None,
        offer_store: Any = None,
        process_offers: Optional[Callable[[list[BonusOffer]], list[BonusOffer]]] = None,
        reports_dir: str | Path = "data/reports",
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
    ) -> dict[str, Any]:
        run_id = str(uuid4())
        started = datetime.now(timezone.utc)
        steps: list[dict[str, Any]] = []
        stuck_point = "not_started"
        wallet_start = None
        wallet_end = None

        def add_step(
            sid: str,
            title: str,
            *,
            ok: bool,
            mode: str = "AUTOMATED",
            note: str = "",
            evidence: Optional[dict[str, Any]] = None,
            level: str = "info",
        ) -> None:
            row = {
                "id": sid,
                "title": title,
                "ok": ok,
                "mode": mode,
                "note": note,
                "evidence": evidence or {},
            }
            steps.append(row)
            self._emit(
                "auto",
                f"auto.{sid}",
                f"{title} · ok={ok} · {note}"[:220],
                "success" if ok else ("warn" if mode == "SEMI_AUTO" else "error"),
                row,
            )

        # ---------- 1) AUTH ----------
        try:
            auth = self.scraper.validate_token()
            add_step(
                "auth",
                "Login / Auth token",
                ok=True,
                note=f"user_id={auth.get('user_id')}",
                evidence=auth,
            )
            stuck_point = "post_auth"
        except Exception as exc:  # noqa: BLE001
            add_step("auth", "Login / Auth token", ok=False, note=str(exc)[:300])
            return self._finalize(
                run_id,
                started,
                steps,
                stuck_point="auth_failed",
                confirm_real_withdraw=confirm_real_withdraw,
            )

        wallet_start = self.scraper.get_wallet_snapshot(include_bonus_state=True)

        # ---------- 2) DISCOVERY ----------
        offers: list[BonusOffer] = []
        try:
            scrape = self.scraper.scrape_live(
                include_account=True,
                include_promocodes=True,
                promocode_limit=max(promocode_limit, 40),
            )
            offers = list(scrape.offers or [])
            if self.process_offers:
                offers = self.process_offers(offers)
            elif self.offer_store and hasattr(self.offer_store, "upsert"):
                self.offer_store.upsert(offers)
            if self.ledger and offers:
                credits = [
                    WalletCredit(
                        platform=self.scraper.platform,
                        bonus_id=str(o.id),
                        title=o.title,
                        amount=float(o.amount or 0),
                        currency=o.currency or "BRL",
                        source="account" if o.title.startswith("[conta]") else "promo",
                        reality="internal_sim",
                        note="Auto-journey discovery — ledger interno, não credita a casa",
                    )
                    for o in offers
                ]
                self.ledger.credit_many(credits)
            add_step(
                "discovery",
                "Discovery de bônus (conta + promocodes)",
                ok=bool(scrape.ok),
                note=str(scrape.error or f"offers={len(offers)}"),
                evidence={"offers": len(offers), "titles": [o.title[:60] for o in offers[:12]]},
            )
            stuck_point = "post_discovery"
        except Exception as exc:  # noqa: BLE001
            add_step("discovery", "Discovery de bônus", ok=False, note=str(exc)[:300])
            stuck_point = "discovery_failed"

        # ---------- 3) CLAIM / REDEEM ALL ----------
        claim_evidence = self._claim_all_bonuses(
            offers,
            confirm_redeem=confirm_redeem,
            promocode_limit=promocode_limit,
        )
        add_step(
            "claim_all",
            "Claim / redeem de todos os bônus possíveis",
            ok=bool(claim_evidence.get("any_success") or claim_evidence.get("active_bonus")),
            mode="AUTOMATED" if confirm_redeem else "SKIPPED",
            note=claim_evidence.get("note", ""),
            evidence=claim_evidence,
        )
        stuck_point = "post_claim"

        # ---------- 4) ARM REDEEM + MINES + POLL + SLOTS ----------
        arm_ev: dict[str, Any] = {}
        try:
            primary = self.scraper.get_bonus_conversion_state().get("primary") or {}
            stake = min(
                float(primary.get("max_bet_brl") or PagolScraper.DEFAULT_LAB_STAKE_BRL),
                PagolScraper.MAX_LAB_STAKE_BRL,
            )
            if confirm_real_bet:
                lab = self.scraper.run_bonus_multiplier_lab(
                    stake_brl=stake,
                    confirm_redeem=False,
                    confirm_real_bet=True,
                    use_bonus_balance=True,
                    poll_seconds=poll_seconds,
                )
                arm_ev["mines_lab"] = {
                    "bet_armed": lab.get("bet_armed"),
                    "provider_url": lab.get("provider_url"),
                    "gates": lab.get("gates"),
                    "poll": lab.get("poll"),
                    "auto_bet_implemented": lab.get("auto_bet_implemented"),
                }
            slots = self.scraper.probe_slots_for_bonus(
                limit=3,
                use_bonus_balance=bool(primary),
            )
            arm_ev["slots_probe"] = slots
            changed = bool((arm_ev.get("mines_lab") or {}).get("poll", {}).get("changed"))
            add_step(
                "arm_play_poll",
                "Armar redeem + Mines + poll + slots launch",
                ok=bool((arm_ev.get("mines_lab") or {}).get("bet_armed") or slots.get("launches_ok")),
                mode="SEMI_AUTO",
                note=(
                    "Auto-bet provider NÃO implementado (Spribe/Pragmatic). "
                    f"poll_changed={changed} slots_ok={slots.get('launches_ok')}"
                ),
                evidence=arm_ev,
            )
            if not changed:
                stuck_point = "awaiting_provider_stake_or_spin"
            else:
                stuck_point = "post_play"
        except Exception as exc:  # noqa: BLE001
            add_step(
                "arm_play_poll",
                "Armar Mines/slots + poll",
                ok=False,
                mode="SEMI_AUTO",
                note=str(exc)[:300],
            )
            stuck_point = "arm_play_failed"

        # ---------- 5) LLM Maverick + T&Cs (+ deep) ----------
        llm_ev: dict[str, Any] = {"items": [], "deep": None, "errors": []}
        if llm_limit <= 0 and not run_deep_attack:
            add_step(
                "llm_analyze",
                "LLM Maverick · analisar T&Cs + deep attack",
                ok=True,
                mode="SKIPPED",
                note="llm_limit=0 e deep desligado",
            )
        else:
            try:
                assist = AbuseLLMAssist()
                bonus_state = self.scraper.get_bonus_conversion_state()
                primary = bonus_state.get("primary") or {}
                targets = (
                    _pick_llm_targets(offers, primary, limit=max(llm_limit, 1))
                    if llm_limit > 0 or run_deep_attack
                    else []
                )
                analyze_n = max(llm_limit, 0)
                self._emit(
                    "auto",
                    "auto.llm_analyze.progress",
                    f"LLM iniciando · targets={len(targets)} analyze={analyze_n} deep={run_deep_attack}",
                    "info",
                    {"targets": [t.title[:80] for t in targets[:4]]},
                )
                for offer in targets[:analyze_n]:
                    try:
                        self._emit(
                            "auto",
                            "auto.llm_analyze.progress",
                            f"LLM analyze · {offer.title[:80]}",
                            "info",
                            {"offer_id": offer.id},
                        )
                        enriched = _enrich_offer_with_live_bonus(offer, primary, bonus_state)
                        # timeout curto para não segurar a jornada / proxy
                        item = assist.analyze_offer(enriched, timeout=90.0)
                        llm_ev["items"].append(item)
                    except Exception as exc:  # noqa: BLE001
                        llm_ev["errors"].append(
                            {"title": offer.title, "error": str(exc)[:240]}
                        )
                if run_deep_attack and targets:
                    try:
                        self._emit(
                            "auto",
                            "auto.llm_analyze.progress",
                            f"LLM deep attack · {targets[0].title[:80]}",
                            "info",
                            {"offer_id": targets[0].id},
                        )
                        deep_offer = _enrich_offer_with_live_bonus(
                            targets[0], primary, bonus_state
                        )
                        prior = llm_ev["items"][0] if llm_ev["items"] else {}
                        llm_ev["deep"] = assist.analyze_offer_deep(
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
                        llm_ev["errors"].append({"deep": str(exc)[:240]})
                parse_fails = [
                    i
                    for i in (llm_ev["items"] + ([llm_ev["deep"]] if llm_ev["deep"] else []))
                    if ((i or {}).get("llm") or {}).get("parse_error")
                ]
                for fail in parse_fails:
                    llm_ev["errors"].append(
                        {
                            "title": (fail or {}).get("title"),
                            "error": "parse_error",
                        }
                    )
                usable_n = sum(
                    1
                    for i in llm_ev["items"]
                    if isinstance(((i.get("llm") or {}).get("abuse_vectors")), list)
                    and not (i.get("llm") or {}).get("parse_error")
                )
                deep_ok = bool(
                    llm_ev["deep"]
                    and isinstance(
                        ((llm_ev["deep"].get("llm") or {}).get("abuse_vectors")), list
                    )
                    and not (llm_ev["deep"].get("llm") or {}).get("parse_error")
                )
                add_step(
                    "llm_analyze",
                    "LLM Maverick · analisar T&Cs + deep attack",
                    ok=bool(usable_n or deep_ok),
                    note=(
                        f"analyzed={len(llm_ev['items'])} deep={bool(llm_ev['deep'])} "
                        f"errors={len(llm_ev['errors'])} parse_error={len(parse_fails)}"
                    ),
                    evidence={
                        "count": len(llm_ev["items"]),
                        "deep_title": (llm_ev["deep"] or {}).get("title"),
                        "errors": llm_ev["errors"][:5],
                        "summaries": [
                            str((i.get("llm") or {}).get("summary") or "")[:280]
                            for i in llm_ev["items"][:3]
                        ],
                    },
                )
            except Exception as exc:  # noqa: BLE001
                add_step("llm_analyze", "LLM Maverick", ok=False, note=str(exc)[:300])

        # ---------- 6) HIGH-EV PROBE ----------
        hev: dict[str, Any] = {}
        try:
            hev = self.scraper.probe_high_ev_contribution(limit=4, include_bonus_flag=True)
            add_step(
                "high_ev_probe",
                "High-EV discovery + soft-probe",
                ok=int(hev.get("probed") or 0) > 0,
                note=str(hev.get("note") or ""),
                evidence={
                    "probed": hev.get("probed"),
                    "findings": hev.get("findings"),
                    "probes": (hev.get("probes") or [])[:6],
                },
            )
        except Exception as exc:  # noqa: BLE001
            add_step("high_ev_probe", "High-EV probe", ok=False, note=str(exc)[:300])

        # ---------- 7) KILL-CHAIN MATRIX ----------
        matrix: dict[str, Any] = {}
        try:
            matrix = KillChainMatrix(
                self.scraper,
                oracle=self.oracle,
                findings=self.findings if persist_findings else None,
            ).run(
                confirm_redeem=False,
                confirm_real_withdraw=False,  # oracle dedicado abaixo
                settle_withdraw=False,
                probe_high_ev=False,  # já rodou
                probe_slots=False,
                arm_wager_poll=False,
                persist_findings=persist_findings,
            )
            add_step(
                "kill_chain_matrix",
                "Kill-chain matrix · cercar automação",
                ok=True,
                note=str((matrix.get("verdict") or {}).get("summary") or ""),
                evidence={
                    "run_id": matrix.get("run_id"),
                    "verdict": matrix.get("verdict"),
                    "vulnerabilities": matrix.get("vulnerabilities"),
                    "coverage": matrix.get("coverage"),
                },
            )
        except Exception as exc:  # noqa: BLE001
            add_step("kill_chain_matrix", "Kill-chain matrix", ok=False, note=str(exc)[:300])

        # ---------- 8) ORACLE WITHDRAW ----------
        withdraw_result: dict[str, Any] | None = None
        withdrawal_id = None
        if confirm_real_withdraw:
            try:
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
                add_step(
                    "oracle_withdraw",
                    "Oracle · saque máximo (API)",
                    ok=bool(result.ok),
                    note=f"code={result.code} amount={result.amount} id={withdrawal_id}",
                    evidence={
                        "amount": result.amount,
                        "code": result.code,
                        "status": result.status.value,
                        "gates": result.gates,
                        "withdrawal_id": withdrawal_id,
                    },
                )
                stuck_point = "post_oracle_api" if result.ok else "oracle_api_rejected"
            except Exception as exc:  # noqa: BLE001
                add_step("oracle_withdraw", "Oracle saque", ok=False, note=str(exc)[:300])
                stuck_point = "oracle_exception"
        else:
            pre = {}
            try:
                pre = self.scraper.withdraw_preflight()
            except Exception as exc:  # noqa: BLE001
                pre = {"error": str(exc)[:200]}
            would = WithdrawalOracle.resolve_max_amount(
                self.scraper.get_wallet_snapshot(include_bonus_state=False).balance,
                PagolScraper.MAX_WITHDRAW_AMOUNT,
                cents=True,
            )
            add_step(
                "oracle_withdraw",
                "Oracle · saque máximo",
                ok=True,
                mode="SKIPPED",
                note=f"confirm_real_withdraw=false · would_amount=R${would}",
                evidence={"would_amount": would, "preflight": {
                    k: pre.get(k)
                    for k in (
                        "have_opened",
                        "withdrawal_allowed",
                        "methods",
                        "day_totals_brl",
                        "min_withdraw",
                    )
                }},
            )

        # ---------- 9) SETTLE / VALIDATE ----------
        settle: dict[str, Any] = {}
        if confirm_real_withdraw and settle_withdraw and withdraw_result and withdraw_result.get("ok"):
            try:
                settle = self.scraper.poll_withdrawal_settlement(
                    withdrawal_id=withdrawal_id,
                    timeout_s=settle_timeout_s,
                    interval_s=5.0,
                    expect_amount_brl=float(withdraw_result.get("amount") or 0) or None,
                )
            except Exception as exc:  # noqa: BLE001
                settle = {"error": str(exc)[:300]}
        else:
            try:
                hist = self.scraper.list_withdrawals(0, 10)
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

        wallet_end = self.scraper.get_wallet_snapshot(include_bonus_state=True)
        diagnosis = diagnose_withdraw_stuck(
            wallet_start=wallet_start.model_dump(mode="json") if wallet_start else {},
            wallet_end=wallet_end.model_dump(mode="json") if wallet_end else {},
            withdraw_result=withdraw_result,
            settle=settle,
            bonus_state=(wallet_end.raw or {}).get("bonus_state") if wallet_end else {},
            arm_evidence=arm_ev,
            confirm_real_withdraw=confirm_real_withdraw,
        )
        stuck_point = diagnosis.get("stuck_point") or stuck_point
        add_step(
            "settle_validate",
            "Validar saque / acréscimo de saldo · onde travou",
            ok=bool(diagnosis.get("pix_materialized") or diagnosis.get("balance_increased")),
            note=diagnosis.get("summary", ""),
            evidence=diagnosis,
        )

        # ---------- 10) REPORT ----------
        report = self._finalize(
            run_id,
            started,
            steps,
            stuck_point=stuck_point,
            confirm_real_withdraw=confirm_real_withdraw,
            extra={
                "wallet_start": wallet_start.model_dump(mode="json") if wallet_start else None,
                "wallet_end": wallet_end.model_dump(mode="json") if wallet_end else None,
                "claim": claim_evidence,
                "arm_play": arm_ev,
                "llm": {
                    "count": len(llm_ev.get("items") or []),
                    "deep": llm_ev.get("deep"),
                    "items": llm_ev.get("items"),
                    "errors": llm_ev.get("errors"),
                },
                "high_ev": {
                    "probed": hev.get("probed"),
                    "findings": hev.get("findings"),
                },
                "matrix": {
                    "run_id": matrix.get("run_id"),
                    "verdict": matrix.get("verdict"),
                    "vulnerabilities": matrix.get("vulnerabilities"),
                    "coverage": matrix.get("coverage"),
                    "stages": matrix.get("stages"),
                },
                "withdraw_result": withdraw_result,
                "settle": settle,
                "diagnosis": diagnosis,
            },
            persist_findings=persist_findings,
            llm_deep=llm_ev.get("deep"),
        )
        return report

    def _claim_all_bonuses(
        self,
        offers: list[BonusOffer],
        *,
        confirm_redeem: bool,
        promocode_limit: int,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        activated: list[dict[str, Any]] = []
        codes: list[str] = []
        for o in offers:
            if o.title.startswith("[promocode]"):
                code = o.title.replace("[promocode]", "", 1).strip()
                if code:
                    codes.append(code)
        # also pull fresh enabled list
        try:
            for item in self.scraper.list_enabled_promocodes()[:promocode_limit]:
                c = str(item.get("code") or item.get("promocode") or "").strip()
                if c and c not in codes:
                    codes.append(c)
        except Exception:  # noqa: BLE001
            pass
        codes = codes[:promocode_limit]

        if confirm_redeem:
            for code in codes:
                try:
                    results.append(
                        self.scraper.redeem_promocode(code, confirm_redeem=True)
                    )
                except Exception as exc:  # noqa: BLE001
                    results.append({"ok": False, "promocode": code, "error": str(exc)[:200]})

        # activate/claim READY/ACTIVE bonuses via known endpoints (204 often = noop)
        try:
            bonuses = self.scraper.list_bonuses(
                statuses=("READY", "PENDING", "ACTIVE"), page_size=20, max_pages=2
            )
        except Exception:  # noqa: BLE001
            bonuses = []
        for b in bonuses:
            bid = b.get("id") or b.get("bonusId")
            if not bid:
                continue
            activated.append(self.scraper.claim_or_activate_bonus(int(bid)))

        state = {}
        try:
            state = self.scraper.get_bonus_conversion_state()
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
        payload = {
            "ok": stuck_point not in {"auth_failed", "discovery_failed"},
            "run_id": run_id,
            "platform": self.scraper.platform,
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
        json_path = self.reports_dir / f"pagol-auto-journey-{run_id[:8]}.json"
        md_path = self.reports_dir / f"pagol-auto-journey-{run_id[:8]}.md"
        latest_md = self.reports_dir / "pagol-auto-journey-latest.md"
        latest_json = self.reports_dir / "pagol-auto-journey-latest.json"
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
        payload["report_filename"] = f"betbonus-auto-journey-{run_id[:8]}.md"

        if persist_findings and self.findings is not None:
            self.findings.add(
                AbuseFinding(
                    platform=self.scraper.platform,
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
    remaining = float(primary.get("remaining_rollover_brl") or (wallet_end or {}).get("rollover") or 0)
    poll = ((arm_evidence or {}).get("mines_lab") or {}).get("poll") or {}
    play_changed = bool(poll.get("changed"))

    pix_materialized = bool(settle.get("materialized"))
    bo_denied = bool(settle.get("bo_denied"))
    api_ok = bool(withdraw_result and withdraw_result.get("ok"))
    balance_increased = bal1 > bal0 + 0.009
    balance_restored_after_deny = bo_denied and bal1 >= bal0 - 0.01

    secondary: list[str] = []
    if not play_changed and not ((arm_evidence or {}).get("mines_lab") or {}).get(
        "auto_bet_implemented"
    ):
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
        # Prioridade: sem auto-bet não dá para multiplicar; depois rollover; depois BO.
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
            f"Δbalance={round(bal1-bal0,2)} Δbonus={round(bonus1-bonus0,2)} "
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

    # unique secondary preserving order
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

    # From deep LLM if present
    deep_llm = {}
    if isinstance(llm_deep, dict):
        deep_llm = llm_deep.get("llm") or {}
        for item in deep_llm.get("protection_backlog") or deep_llm.get("protection_plan") or []:
            if not isinstance(item, dict):
                continue
            backlog.append(
                {
                    "priority": item.get("priority") or "P1",
                    "owner": item.get("owner") or "product",
                    "title": item.get("title") or "Correção LLM",
                    "why": item.get("why") or "",
                    "implementation": item.get("implementation")
                    or item.get("fixes")
                    or [],
                    "blocks_vectors": item.get("blocks_vectors") or [],
                    "effort": item.get("effort") or item.get("effort_days"),
                }
            )

    # Lab-proven controls
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
            "blocks_vectors": ["withdraw_ok_api_but_bo_denied", "false_withdraw_success"],
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
    # merge unique by title
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
    lines = [
        "# PAGOL · Relatório final — Jornada automática",
        "",
        f"- Run: `{payload.get('run_id')}`",
        f"- Plataforma: `{payload.get('platform')}`",
        f"- Objetivo: **multiplicar bônus e sacar 100% automatizado**",
        f"- Objetivo atingido: **{payload.get('automation_goal_met')}**",
        f"- Ponto de travamento: **`{payload.get('stuck_point')}`**",
        f"- Gerado em: `{payload.get('finished_at')}`",
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
            json.dumps(payload.get("wallet_start") or {}, ensure_ascii=False, indent=2, default=str)[
                :8000
            ],
            "```",
            "",
            "### End",
            "",
            "```json",
            json.dumps(payload.get("wallet_end") or {}, ensure_ascii=False, indent=2, default=str)[
                :8000
            ],
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
    offers: list[BonusOffer], primary: dict[str, Any], *, limit: int
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
        # synthesize offer from live bonus
        synthetic = BonusOffer(
            platform="pagol_bet_br",
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
