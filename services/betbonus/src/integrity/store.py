from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from src.integrity.models import IntegrityRun


class IntegrityRunStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            return []
        return raw if isinstance(raw, list) else []

    def save(self, items: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(items[:50], indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, run: IntegrityRun | dict[str, Any]) -> dict[str, Any]:
        payload = run.to_dict() if isinstance(run, IntegrityRun) else run
        items = self.load()
        items.insert(0, payload)
        self.save(items)
        return payload

    def latest(self) -> Optional[dict[str, Any]]:
        items = self.load()
        return items[0] if items else None

    def summaries(self, limit: int = 20) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in self.load()[: max(1, min(limit, 50))]:
            cov = item.get("coverage") if isinstance(item.get("coverage"), dict) else {}
            results = item.get("results") if isinstance(item.get("results"), list) else []
            out.append(
                {
                    "id": item.get("id"),
                    "started_at": item.get("started_at"),
                    "finished_at": item.get("finished_at"),
                    "run_mode": item.get("run_mode"),
                    "houses": item.get("houses") or [],
                    "axes": item.get("axes") or [],
                    "scenario_count": cov.get("scenario_count") or len(results),
                    "mode_counts": cov.get("mode_counts") or {},
                    "automated_ratio": cov.get("automated_ratio"),
                    "planner": (item.get("planner") or {}).get("next_scenario_id"),
                    "kind": item.get("kind") or "house",
                    "target_game": item.get("target_game") or {},
                }
            )
        return out

    def get(self, run_id: str) -> Optional[dict[str, Any]]:
        for item in self.load():
            if str(item.get("id")) == run_id:
                return item
        return None
