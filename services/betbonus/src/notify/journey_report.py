from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from src.notify.journey_session import JourneySession


def build_journey_markdown(
    session: JourneySession,
    *,
    extras: Optional[dict[str, Any]] = None,
) -> str:
    """Monta relatório .md completo da sessão de teste red-team."""
    extras = extras or {}
    now = datetime.now(timezone.utc).isoformat()
    lines: list[str] = [
        f"# BetBonus Red Team — Relatório de Jornada",
        "",
        f"- Gerado em: `{now}`",
        f"- Sessão: `{session.id}`",
        f"- Status: **{session.status}**",
        f"- Casa: **{session.house_name or session.platform}**",
        f"- Platform: `{session.platform}`",
        f"- URL: {session.house_url or '—'}",
        f"- Scout: `{session.scout_mode or '—'}`",
        f"- Início: `{session.started_at.isoformat()}`",
        f"- Fim: `{session.ended_at.isoformat() if session.ended_at else 'em andamento'}`",
        f"- Eventos: **{session.event_count}**",
        "",
        "## Plano de evidência (obrigatório)",
        "",
        "| Plano | O que é | Pode confirmar V1/V2 / saque? |",
        "|---|---|---|",
        "| **platform_observed** | API/wallet/saque da casa | Sim — delta de saldo real |",
        "| **internal_sim** | `ledger.credit` / wallet.json do BetBonus | Não — não move a casa |",
        "| **llm_hypothesis** | Deep attack / vetores gerados por modelo | Não — hipótese até lab com saldo |",
        "| **offline_model** | Sims de mesa/crash | Não — EV teórico |",
        "",
        "`ledger.credit.start` / `ledger.credit.ok` nesta jornada = **internal_sim**. "
        "Não confundir com crédito de bônus na 4play.game.",
        "",
        "## Resumo operacional",
        "",
        str(extras.get("summary") or _auto_summary(session, extras)),
        "",
    ]

    conversion = extras.get("conversion")
    if conversion:
        lines.extend(
            [
                "## Snapshot de conversão",
                "",
                "```json",
                json.dumps(conversion, ensure_ascii=False, indent=2, default=str),
                "```",
                "",
            ]
        )

    abuse_items = extras.get("abuse_items") or []
    if abuse_items:
        lines.extend(["## Abuse scores", ""])
        for item in abuse_items:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- **{item.get('title', '?')}** — score={item.get('abuse_score')} · "
                f"severity={item.get('severity')}"
            )
        lines.append("")

    game_risk = extras.get("game_bonus_risk")
    if isinstance(game_risk, dict) and game_risk.get("items"):
        lines.extend(
            [
                "## Vetores jogos/bônus",
                "",
                f"Focus: {game_risk.get('focus')}",
                f"Count={game_risk.get('count')} · critical={game_risk.get('critical')} · "
                f"high={game_risk.get('high')}",
                "",
            ]
        )
        for v in game_risk.get("items") or []:
            if not isinstance(v, dict):
                continue
            lines.append(
                f"### [{v.get('severity')}] {v.get('title')}\n\n"
                f"{v.get('rationale')}\n\n"
                f"**Teste:** {v.get('test_idea')}\n"
            )

    llm_report = extras.get("llm_report")
    llm_vectors = extras.get("llm_vectors") or []
    if llm_report or llm_vectors:
        lines.extend(["## Análise LLM (padrão)", ""])
        if llm_report:
            lines.extend([str(llm_report), ""])
        for v in llm_vectors:
            if not isinstance(v, dict):
                continue
            lines.append(
                f"### [{v.get('severity')}] {v.get('title')}\n\n"
                f"{v.get('rationale')}\n\n"
                f"**Teste:** {v.get('test_idea')}\n"
            )

    deep = extras.get("deep_attack")
    if isinstance(deep, dict) and deep:
        lines.extend(
            [
                "## Deep attack (promo selecionada)",
                "",
                "> **Hipótese LLM** — não é achado confirmado. Confirmação exige delta de wallet "
                "na casa (platform_observed) e, para kill-chain de rollover/saque, saldo "
                "acima do mínimo de saque.",
                "",
                f"- Promo: **{deep.get('title') or '—'}**",
                f"- Offer ID: `{deep.get('offer_id') or '—'}`",
                f"- Mode: `{deep.get('mode') or 'deep_attack'}`",
                f"- Model: `{deep.get('model') or '—'}`",
                f"- Heuristic score: {deep.get('abuse_score_heuristic')}",
                "",
            ]
        )
        llm = deep.get("llm") if isinstance(deep.get("llm"), dict) else {}
        if llm.get("summary"):
            lines.extend(["### Summary", "", str(llm.get("summary")), ""])
        if llm.get("primary_kill_chain"):
            lines.extend(["### Kill chain", "", str(llm.get("primary_kill_chain")), ""])
        if llm.get("conversion_path"):
            lines.extend(["### Conversion path", "", str(llm.get("conversion_path")), ""])
        for key, title in [
            ("lab_runbook", "Lab runbook"),
            ("wallet_state_machine", "Wallet state machine"),
            ("api_hooks", "API hooks"),
            ("cashout_attacks", "Cashout attacks"),
            ("stacking_combos", "Stacking combos"),
            ("controls_to_verify", "Controls to verify"),
            ("blind_spots", "Blind spots"),
            ("false_negatives_to_force", "False negatives to force"),
        ]:
            vals = llm.get(key) or []
            if not vals:
                continue
            lines.extend([f"### {title}", ""])
            if isinstance(vals, list):
                for row in vals:
                    lines.append(f"- {row}")
            else:
                lines.append(str(vals))
            lines.append("")
        if llm.get("roi_estimate"):
            lines.extend(["### ROI estimate", "", str(llm.get("roi_estimate")), ""])

        protection = llm.get("protection_backlog") or llm.get("protection_plan") or []
        if protection:
            lines.extend(["### Plano de proteção / correções anti-abuso", ""])
            for item in protection:
                if not isinstance(item, dict):
                    lines.append(f"- {item}")
                    continue
                lines.append(
                    f"#### [{item.get('priority') or '?'}] {item.get('title') or 'Correção'}"
                )
                if item.get("why"):
                    lines.append(f"\n{item.get('why')}\n")
                fixes = item.get("implementation") or item.get("fixes") or []
                if fixes:
                    lines.append("**Implementação:**")
                    for row in fixes:
                        lines.append(f"- {row}")
                    lines.append("")
                if item.get("blocks_vectors"):
                    lines.append(
                        f"**Bloqueia vetores:** {', '.join(map(str, item.get('blocks_vectors') or []))}"
                    )
                    lines.append("")
                meta_bits = []
                if item.get("owner"):
                    meta_bits.append(f"owner={item.get('owner')}")
                if item.get("effort") or item.get("effort_days") is not None:
                    meta_bits.append(
                        f"effort={item.get('effort') or item.get('effort_days')}"
                    )
                if item.get("impact"):
                    meta_bits.append(f"impact={item.get('impact')}")
                if meta_bits:
                    lines.append(f"_{' · '.join(meta_bits)}_\n")

        for v in llm.get("abuse_vectors") or []:
            if not isinstance(v, dict):
                continue
            lines.append(
                f"### [{v.get('severity')}|{v.get('exploitability', '?')}] "
                f"{v.get('title')}\n"
            )
            if v.get("rationale"):
                lines.append(str(v.get("rationale")))
                lines.append("")
            if v.get("expected_edge"):
                lines.append(f"**Edge:** {v.get('expected_edge')}")
                lines.append("")
            steps = v.get("steps") or []
            if steps:
                lines.append("**Steps:**")
                for i, step in enumerate(steps, 1):
                    lines.append(f"{i}. {step}")
                lines.append("")
            if v.get("kill_control"):
                lines.append(f"**Kill control:** {v.get('kill_control')}")
                lines.append("")
            rem = v.get("remediation") if isinstance(v.get("remediation"), dict) else None
            if rem:
                lines.append(
                    f"**Correção [{rem.get('priority') or '?'} / {rem.get('owner') or '?'}]:** "
                    f"{rem.get('fix') or ''}"
                )
                if rem.get("engineering_change"):
                    lines.append(f"- Engenharia: {rem.get('engineering_change')}")
                if rem.get("config_change"):
                    lines.append(f"- Config: {rem.get('config_change')}")
                if rem.get("detection_rule"):
                    lines.append(f"- Detecção: {rem.get('detection_rule')}")
                if rem.get("acceptance_test"):
                    lines.append(f"- Aceite: {rem.get('acceptance_test')}")
                lines.append("")
            if v.get("test_idea"):
                lines.append(f"**Teste:** {v.get('test_idea')}")
                lines.append("")

    offers = extras.get("offers") or []
    if offers:
        lines.extend(["## Offers no escopo", ""])
        for o in offers:
            if not isinstance(o, dict):
                continue
            lines.append(
                f"- `{o.get('id', '')[:8]}` **{o.get('title')}** · "
                f"{o.get('bonus_type')} · {o.get('amount')} {o.get('currency')} · "
                f"{o.get('wagering_multiple')}x · score={o.get('score')}"
            )
        lines.append("")

    withdraw = extras.get("withdraw_result")
    if withdraw:
        lines.extend(
            [
                "## Oracle / saque",
                "",
                "```json",
                json.dumps(withdraw, ensure_ascii=False, indent=2, default=str),
                "```",
                "",
            ]
        )

    lines.extend(["## Timeline completa da sessão", ""])
    # events are newest-first in store append? check append order
    events = list(session.events)
    # chronological
    events_sorted = sorted(events, key=lambda e: e.created_at)
    for ev in events_sorted:
        ts = ev.created_at.isoformat()
        lines.append(f"### [{ts}] `{ev.step or '-'}` · `{ev.kind}` · **{ev.level}**")
        lines.append("")
        lines.append(ev.message)
        lines.append("")
        if ev.kind.startswith("ledger.credit"):
            lines.append(
                "> **internal_sim** — este evento escreve o ledger BetBonus, não o saldo da casa."
            )
            lines.append("")
        if ev.detail:
            lines.extend(
                [
                    "<details><summary>detail</summary>",
                    "",
                    "```json",
                    json.dumps(ev.detail, ensure_ascii=False, indent=2, default=str)[:20000],
                    "```",
                    "",
                    "</details>",
                    "",
                ]
            )

    if session.meta:
        lines.extend(
            [
                "## Meta da sessão",
                "",
                "```json",
                json.dumps(session.meta, ensure_ascii=False, indent=2, default=str),
                "```",
                "",
            ]
        )

    lines.extend(
        [
            "---",
            "",
            "_Relatório gerado pelo BetBonus AI · Iron Red Team lab autorizado._",
            "",
        ]
    )
    return "\n".join(lines)


def _auto_summary(session: JourneySession, extras: dict[str, Any]) -> str:
    bits = [
        f"Teste red-team em {session.house_name or session.platform}.",
        f"{session.event_count} eventos registrados.",
    ]
    conv = extras.get("conversion") or {}
    if isinstance(conv, dict) and conv.get("status"):
        bits.append(f"Conversão: {conv.get('status')}.")
    deep = extras.get("deep_attack") or {}
    if isinstance(deep, dict) and deep.get("title"):
        bits.append(f"Deep attack em: {deep.get('title')}.")
    return " ".join(bits)
