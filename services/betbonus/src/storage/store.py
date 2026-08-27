from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.models.bonus import BonusOffer


class JsonBonusStore:
    """Simple JSON persistence for local MVP (swap for Postgres/Redis later)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def load(self) -> list[BonusOffer]:
        raw = json.loads(self.path.read_text(encoding="utf-8") or "[]")
        return [BonusOffer.model_validate(item) for item in raw]

    def save(self, offers: list[BonusOffer]) -> None:
        payload = [o.model_dump(mode="json") for o in offers]
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, bonus_id: str) -> Optional[BonusOffer]:
        for offer in self.load():
            if offer.id == bonus_id:
                return offer
        return None

    def delete(self, bonus_id: str) -> bool:
        offers = self.load()
        kept = [o for o in offers if o.id != bonus_id]
        if len(kept) == len(offers):
            return False
        self.save(kept)
        return True

    def clear(self) -> int:
        count = len(self.load())
        self.save([])
        return count

    def upsert(self, offers: list[BonusOffer]) -> list[BonusOffer]:
        existing = {o.id: o for o in self.load()}
        for offer in offers:
            key_match = None
            for eid, eoffer in existing.items():
                if (
                    eoffer.platform == offer.platform
                    and eoffer.title == offer.title
                    and eoffer.amount == offer.amount
                    and eoffer.wagering_multiple == offer.wagering_multiple
                ):
                    key_match = eid
                    break
            if key_match:
                offer.id = key_match
            existing[offer.id] = offer
        merged = list(existing.values())
        self.save(merged)
        return merged
