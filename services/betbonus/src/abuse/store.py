from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.models.abuse import AbuseFinding


class AbuseFindingStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def load(self) -> list[AbuseFinding]:
        raw = json.loads(self.path.read_text(encoding="utf-8") or "[]")
        return [AbuseFinding.model_validate(item) for item in raw]

    def save(self, items: list[AbuseFinding]) -> None:
        payload = [i.model_dump(mode="json") for i in items]
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, finding: AbuseFinding) -> AbuseFinding:
        items = self.load()
        items.insert(0, finding)
        self.save(items[:500])
        return finding

    def list(self, limit: int = 100) -> list[AbuseFinding]:
        return self.load()[:limit]

    def get(self, finding_id: str) -> Optional[AbuseFinding]:
        for item in self.load():
            if item.id == finding_id:
                return item
        return None

    def clear(self) -> int:
        n = len(self.load())
        self.save([])
        return n
