"""Relatório markdown da jornada de integridade (casa ou jogo específico)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


HOUSE_LABEL = {
    "pagol_bet_br": "pagol.bet.br",
    "4play_bet_br": "4play.bet.br",
    "4play": "4play.game",
}

AXIS_LABEL = {
    "session": "Sessão",
    "wallet": "Wallet",
    "catalog": "Catálogo",
    "slots": "Slots",
    "crash": "Crash",
    "table": "Mesa",
    "timer": "Timer",
    "promo": "Promo",
    "jackpot": "Jackpot",
    "withdraw": "Saque",
}

MODE_LABEL = {
    "AUTOMATED": "Agente concluiu na API da casa (sem spin no provider).",
    "SEMI_AUTO": "Falta ação humana no cliente do provider.",
    "UNSUPPORTED": "A casa não expõe API para este eixo.",
    "BLOCKED": "Não rodou (sessão inválida, recusa da casa ou erro).",
    "SKIPPED": "Fora deste run.",
    "DRY": "Simulação local — não chamou a casa.",
}


def _house(hid: str) -> str:
    return HOUSE_LABEL.get(hid, hid)


OFFLINE_SCENARIOS = frozenset({"crash.cashout_model", "table.offline_ev"})


def _evidence_plane(row: dict[str, Any]) -> str:
    mode = str(row.get("mode") or "")
    sid = str(row.get("scenario_id") or "")
    if mode == "DRY" or sid in OFFLINE_SCENARIOS:
        return "offline_model"
    if mode in {"UNSUPPORTED", "SKIPPED"}:
        return "not_applicable"
    if mode in {"AUTOMATED", "SEMI_AUTO", "BLOCKED"}:
        return "platform_observed"
    return "unknown"


def build_integrity_markdown(run: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc).isoformat()
    target = run.get("target_game") if isinstance(run.get("target_game"), dict) else {}
    kind = str(run.get("kind") or ("game_session" if target.get("game_id") is not None else "house"))
    houses = [ _house(h) for h in (run.get("houses") or []) ]
    cov = run.get("coverage") if isinstance(run.get("coverage"), dict) else {}
    counts = cov.get("mode_counts") if isinstance(cov.get("mode_counts"), dict) else {}
    results = run.get("results") if isinstance(run.get("results"), list) else []
    game_title = str(target.get("name") or target.get("game_id") or "—")
    title = (
        f"Casino Integrity — sessão {game_title}"
        if kind == "game_session"
        else "Casino Integrity — run de casa"
    )
    lines = [
        f"# {title}",
        "",
        f"- Gerado em: `{now}`",
        f"- Run: `{run.get('id')}`",
        f"- Modo: **{run.get('run_mode')}**",
        f"- Tipo: `{kind}`",
        f"- Casas: {', '.join(houses) or '—'}",
        f"- Início: `{run.get('started_at')}`",
        f"- Fim: `{run.get('finished_at') or '—'}`",
        "",
    ]
    if target.get("game_id") is not None:
        lines.extend(
            [
                "## Jogo alvo",
                "",
                f"- Nome: **{target.get('name') or '—'}**",
                f"- game_id: `{target.get('game_id')}`",
                f"- Provider: {target.get('provider') or '—'}",
                f"- Casa: {_house(str(target.get('house') or (run.get('houses') or ['—'])[0]))}",
                "",
                "Launch FREE/REAL e wallet-after-launch usam **este** título. "
                "Spin/cashout no provider permanece SEMI_AUTO (sem RNG).",
                "",
            ]
        )
    lines.extend(
        [
            "## Resumo",
            "",
            f"- Cenários: **{len(results)}**",
            f"- AUTOMATED: {counts.get('AUTOMATED', 0)}",
            f"- SEMI_AUTO: {counts.get('SEMI_AUTO', 0)}",
            f"- UNSUPPORTED: {counts.get('UNSUPPORTED', 0)}",
            f"- BLOCKED: {counts.get('BLOCKED', 0)}",
            f"- DRY/SKIPPED: {(counts.get('DRY') or 0) + (counts.get('SKIPPED') or 0)}",
            "",
            "## Plano de evidência",
            "",
            "- **platform_observed**: API da casa (wallet, launch, saque).",
            "- **internal_sim**: ledger BetBonus (`ledger.credit`) — não move a casa.",
            "- **offline_model**: sims de mesa/crash (`crash.cashout_model`, `table.offline_ev`).",
            "",
        ]
    )
    plane_n = {"platform_observed": 0, "offline_model": 0, "not_applicable": 0}
    for row in results:
        if not isinstance(row, dict):
            continue
        plane_n[_evidence_plane(row)] = plane_n.get(_evidence_plane(row), 0) + 1
    lines.extend(
        [
            f"- Neste run: platform_observed={plane_n.get('platform_observed', 0)} · "
            f"offline_model={plane_n.get('offline_model', 0)} · "
            f"N/A={plane_n.get('not_applicable', 0)}",
            "",
        ]
    )
    notes = run.get("notes") if isinstance(run.get("notes"), list) else []
    if notes:
        lines.extend(["## Notas do harness", ""])
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    lines.extend(["## Por eixo", ""])
    by_axis: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        if not isinstance(row, dict):
            continue
        by_axis.setdefault(str(row.get("axis") or "?"), []).append(row)
    for axis, rows in by_axis.items():
        lines.append(f"### {AXIS_LABEL.get(axis, axis)}")
        lines.append("")
        for row in rows:
            mode = str(row.get("mode") or "")
            flag = "ok" if row.get("ok") else "falhou"
            lines.append(
            f"- `{row.get('scenario_id')}` · **{mode}** · {flag} · "
            f"plano={_evidence_plane(row)} · "
            f"sev={row.get('severity')} · {row.get('vulnerability') or row.get('note') or ''}"
            )
        lines.append("")

    hot = [
        r
        for r in results
        if isinstance(r, dict) and str(r.get("severity")) in {"high", "critical"} and r.get("mode") not in {"DRY", "SKIPPED"}
    ]
    chain_row = None
    by_sid = {
        str(r.get("scenario_id")): r
        for r in results
        if isinstance(r, dict) and isinstance(r.get("evidence"), dict)
    }
    for sid in ("slots.provider_map", "slots.lab_play"):
        row = by_sid.get(sid)
        if not row:
            continue
        ev = row.get("evidence") or {}
        if ev.get("hosts") or ev.get("endpoints") or ev.get("chain"):
            chain_row = row
            break
    if chain_row:
        ev = chain_row.get("evidence") or {}
        chain = ev.get("chain") if isinstance(ev.get("chain"), dict) else {}
        lines.extend(
            [
                "## Cadeia iframe / provedor",
                "",
                f"- Origem: `{chain_row.get('scenario_id')}`",
                f"- Launch: `{ev.get('launch_host') or '—'}`",
                f"- Slug Salsa: `{chain.get('salsa_game') or ev.get('salsa_game') or '—'}`",
                f"- Catálogo Lucky: {chain.get('catalog_provider') or '—'}",
                f"- Cliente iframe: **{ev.get('game_client') or chain.get('game_client') or '—'}**",
                f"- Mismatch catálogo×iframe: {'sim' if chain.get('mismatch') else 'não'}",
            ]
        )
        if ev.get("launch_error"):
            lines.extend(["", f"- Erro Salsa: {ev.get('launch_error')}"])
        lines.append("")
        hosts = ev.get("hosts") if isinstance(ev.get("hosts"), list) else []
        if hosts:
            lines.append("### Hosts")
            lines.append("")
            for host in hosts[:16]:
                if not isinstance(host, dict):
                    continue
                paths = ", ".join(str(p) for p in (host.get("paths") or [])[:4]) or "—"
                ws = " · WS" if host.get("ws") else ""
                lines.append(
                    f"- `{host.get('host')}` · {host.get('role')}{ws} · {paths}"
                )
            lines.append("")
        endpoints = ev.get("endpoints") if isinstance(ev.get("endpoints"), list) else []
        if endpoints:
            lines.append("### Endpoints (query omitida)")
            lines.append("")
            for ep in endpoints[:20]:
                if not isinstance(ep, dict):
                    continue
                lines.append(
                    f"- `{ep.get('scheme') or 'https'}://{ep.get('host')}{ep.get('path')}` · {ep.get('role')}"
                )
            lines.append("")
        iframes = ev.get("iframes") if isinstance(ev.get("iframes"), list) else []
        if iframes:
            lines.append("### Iframes")
            lines.append("")
            for src in iframes[:8]:
                lines.append(f"- `{src}`")
            lines.append("")
        hop = ev.get("softswiss") if isinstance(ev.get("softswiss"), dict) else {}
        if hop.get("provider_url"):
            lines.extend(
                [
                    "### Hop SoftSwiss/a8r",
                    "",
                    f"- `game_url`: `{hop.get('provider_url')}`",
                    f"- game: `{hop.get('game') or '—'}`",
                    "",
                ]
            )

    if hot:
        lines.extend(["## Achados high/critical", ""])
        for row in hot:
            lines.append(
                f"### [{row.get('severity')}] {row.get('title')}\n\n"
                f"- Cenário: `{row.get('scenario_id')}`\n"
                f"- Modo: {row.get('mode')}\n"
                f"- Vetor: `{row.get('vulnerability')}`\n"
                f"- Nota: {row.get('note')}\n"
            )
        lines.append("")

    lines.extend(
        [
            "## Legenda",
            "",
        ]
    )
    for mode, text in MODE_LABEL.items():
        lines.append(f"- **{mode}**: {text}")
    lines.extend(
        [
            "",
            "## Limites",
            "",
            "- Lab autorizado, contas de teste.",
            "- Sem stake no provider, sem saque real, sem manipulação de RNG.",
            "- Relatório não contém tokens.",
            "- `ledger.credit` (se citado) é simulação interna — não é crédito na casa.",
            "",
        ]
    )
    return "\n".join(lines)
