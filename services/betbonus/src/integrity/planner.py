"""LLM escolhe o próximo cenário do catálogo — não joga cassino e não prevê RNG."""

from __future__ import annotations

import json
from typing import Any, Optional

from src.integrity.catalog import load_catalog
from src.integrity.models import Catalog, IntegrityRun
from src.llm.client import IronLLMClient
from src.llm.json_extract import extract_json

SYSTEM = """Você é analista de integridade do produto Casino Online (lab autorizado do operador).
O catálogo cobre sessão, wallet, catálogo, slots, crash, mesa, timer, promo, jackpot e saque.
Bônus é UM eixo, não o produto.
NÃO sugira manipular RNG, prever crash/slots, reverse-engineer de provider, nem apostas esportivas.
Escolha o próximo cenário do catálogo (id exatamente igual) para fechar cobertura UNSUPPORTED/SEMI/BLOCKED.
Retorne APENAS JSON:
{
  "next_scenario_id": "string",
  "axis": "string",
  "rationale": "string",
  "house": "pagol_bet_br"|"4play_bet_br"|"4play"|null,
  "priority": "P0"|"P1"|"P2",
  "expected_mode": "AUTOMATED"|"SEMI_AUTO"|"UNSUPPORTED"
}
"""


def heuristic_next(run: Optional[IntegrityRun], catalog: Catalog) -> dict[str, Any]:
    """Fallback sem LLM: primeiro BLOCKED, depois UNSUPPORTED, depois SEMI_AUTO."""
    order = ("BLOCKED", "UNSUPPORTED", "SEMI_AUTO", "SKIPPED")
    results = list(run.results) if run else []
    for mode in order:
        for row in results:
            if row.mode == mode:
                spec = catalog.by_id(row.scenario_id)
                return {
                    "next_scenario_id": row.scenario_id,
                    "axis": row.axis,
                    "house": row.platform,
                    "priority": "P0" if mode == "BLOCKED" else "P1",
                    "expected_mode": mode,
                    "rationale": f"Heurística: atacar primeiro modo {mode} ({row.title}).",
                    "source": "heuristic",
                    "title": spec.title if spec else row.title,
                }
    if catalog.scenarios:
        spec = catalog.scenarios[0]
        return {
            "next_scenario_id": spec.id,
            "axis": spec.axis,
            "house": spec.houses[0] if spec.houses else None,
            "priority": "P2",
            "expected_mode": "AUTOMATED",
            "rationale": "Nenhuma falha anterior — começar pelo primeiro cenário do catálogo.",
            "source": "heuristic",
            "title": spec.title,
        }
    return {"next_scenario_id": None, "rationale": "Catálogo vazio", "source": "heuristic"}


class IntegrityPlanner:
    def __init__(self, client: Optional[IronLLMClient] = None, catalog: Optional[Catalog] = None):
        self.client = client or IronLLMClient()
        self.catalog = catalog or load_catalog()

    def plan(self, run: Optional[IntegrityRun] = None, *, use_llm: bool = True) -> dict[str, Any]:
        fallback = heuristic_next(run, self.catalog)
        if not use_llm or not self.client.config.configured:
            fallback["llm"] = False
            return fallback
        catalog_min = [
            {"id": s.id, "axis": s.axis, "title": s.title, "houses": s.houses}
            for s in self.catalog.scenarios
        ]
        results_min = []
        if run:
            for row in run.results[:80]:
                results_min.append(
                    {
                        "scenario_id": row.scenario_id,
                        "axis": row.axis,
                        "platform": row.platform,
                        "mode": row.mode,
                        "ok": row.ok,
                        "severity": row.severity,
                        "vulnerability": row.vulnerability,
                    }
                )
        user = json.dumps(
            {
                "product": "casino_online",
                "catalog": catalog_min,
                "last_run_coverage": run.coverage if run else {},
                "last_results": results_min,
                "heuristic": fallback,
            },
            ensure_ascii=False,
        )[:12000]
        try:
            content = self.client.chat(
                [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user},
                ],
                temperature=0.1,
                max_tokens=700,
                json_mode=True,
            )
            parsed = extract_json(content)
        except Exception as exc:  # noqa: BLE001
            fallback["llm"] = False
            fallback["llm_error"] = str(exc)[:240]
            return fallback
        if parsed.get("parse_error"):
            fallback["llm"] = False
            fallback["llm_error"] = "parse_error"
            fallback["llm_raw"] = parsed
            return fallback
        sid = str(parsed.get("next_scenario_id") or "")
        spec = self.catalog.by_id(sid)
        if not spec:
            fallback["llm"] = False
            fallback["llm_invalid_id"] = sid
            fallback["llm_raw"] = parsed
            return fallback
        return {
            "next_scenario_id": spec.id,
            "axis": spec.axis,
            "house": parsed.get("house") or (spec.houses[0] if spec.houses else None),
            "priority": parsed.get("priority") or "P1",
            "expected_mode": parsed.get("expected_mode"),
            "rationale": parsed.get("rationale") or "",
            "title": spec.title,
            "source": "llm",
            "llm": True,
        }
