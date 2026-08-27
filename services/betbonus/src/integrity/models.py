from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


AXES = (
    "session",
    "wallet",
    "catalog",
    "slots",
    "crash",
    "table",
    "timer",
    "promo",
    "jackpot",
    "withdraw",
)

HOUSES = ("pagol_bet_br", "4play_bet_br", "4play")

MODES = ("AUTOMATED", "SEMI_AUTO", "UNSUPPORTED", "SKIPPED", "BLOCKED", "DRY")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SafetyCaps:
    default_mode: str = "PROBE"
    max_lab_stake_brl: float = 5.0
    confirm_real_bet_default: bool = False
    confirm_real_withdraw_default: bool = False
    kill_switch: dict[str, bool] = field(default_factory=dict)

    def killed(self, platform: str) -> bool:
        return bool(self.kill_switch.get(platform))


@dataclass
class ScenarioSpec:
    id: str
    axis: str
    title: str
    worker: str
    mode: str = "PROBE"
    houses: list[str] = field(default_factory=list)
    requires_stake: bool = False
    requires_withdraw: bool = False
    evidence: str = ""
    note: str = ""

    def applies_to(self, platform: str) -> bool:
        if not self.houses:
            return True
        return platform in self.houses


@dataclass
class Catalog:
    safety: SafetyCaps
    axes: list[str]
    houses: list[str]
    scenarios: list[ScenarioSpec]

    def for_house(self, platform: str) -> list[ScenarioSpec]:
        return [s for s in self.scenarios if s.applies_to(platform)]

    def by_id(self, scenario_id: str) -> ScenarioSpec | None:
        for row in self.scenarios:
            if row.id == scenario_id:
                return row
        return None


@dataclass
class ScenarioResult:
    id: str
    scenario_id: str
    axis: str
    platform: str
    title: str
    mode: str
    ok: bool
    severity: str = "info"
    vulnerability: str = ""
    note: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IntegrityRun:
    id: str = field(default_factory=lambda: str(uuid4()))
    started_at: str = field(default_factory=lambda: _now().isoformat())
    finished_at: str = ""
    run_mode: str = "PROBE"
    confirm_real_bet: bool = False
    confirm_real_withdraw: bool = False
    houses: list[str] = field(default_factory=list)
    axes: list[str] = field(default_factory=list)
    results: list[ScenarioResult] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    planner: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    target_game: dict[str, Any] = field(default_factory=dict)
    kind: str = "house"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "run_mode": self.run_mode,
            "confirm_real_bet": self.confirm_real_bet,
            "confirm_real_withdraw": self.confirm_real_withdraw,
            "houses": self.houses,
            "axes": self.axes,
            "results": [r.to_dict() for r in self.results],
            "coverage": self.coverage,
            "planner": self.planner,
            "notes": self.notes,
            "target_game": self.target_game,
            "kind": self.kind,
            "schema_version": "1",
            "tool": "casino-integrity",
            "product": "casino_online",
        }


def build_coverage(results: list[ScenarioResult], houses: list[str], axes: list[str]) -> dict[str, Any]:
    cells: dict[str, dict[str, dict[str, Any]]] = {}
    mode_counts: dict[str, int] = {m: 0 for m in MODES}
    sev_rank = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}

    for house in houses:
        cells[house] = {}
        for axis in axes:
            rows = [r for r in results if r.platform == house and r.axis == axis]
            if not rows:
                cells[house][axis] = {
                    "mode": "SKIPPED",
                    "ok": None,
                    "severity": "info",
                    "count": 0,
                    "title": "",
                }
                continue
            modes = {r.mode for r in rows}
            if "BLOCKED" in modes:
                mode = "BLOCKED"
            elif "UNSUPPORTED" in modes and not any(r.mode == "AUTOMATED" for r in rows):
                mode = "UNSUPPORTED"
            elif "SEMI_AUTO" in modes:
                mode = "SEMI_AUTO"
            elif "DRY" in modes:
                mode = "DRY"
            elif "AUTOMATED" in modes:
                mode = "AUTOMATED"
            else:
                mode = next(iter(modes))
            worst = max(rows, key=lambda r: sev_rank.get(r.severity, 0))
            cells[house][axis] = {
                "mode": mode,
                "ok": all(r.ok for r in rows if r.mode not in {"SKIPPED", "DRY"}),
                "severity": worst.severity,
                "count": len(rows),
                "title": worst.vulnerability or worst.title,
            }

    for row in results:
        mode_counts[row.mode] = mode_counts.get(row.mode, 0) + 1

    automated = mode_counts.get("AUTOMATED", 0)
    total = max(1, len(results))
    return {
        "cells": cells,
        "mode_counts": mode_counts,
        "scenario_count": len(results),
        "automated_ratio": round(automated / total, 3),
        "note": (
            "Cobertura = eixos do produto cassino (AUTOMATED vs SEMI vs UNSUPPORTED), "
            "não conversão de bônus."
        ),
    }
