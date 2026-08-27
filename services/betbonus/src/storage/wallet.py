from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class WalletCredit(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    platform: str
    bonus_id: str = ""
    title: str
    amount: float = 0.0
    currency: str = "CRC"
    source: str = "manual"  # promo | account | manual
    status: str = "credited"  # credited | pending | failed
    reality: str = "internal_sim"  # internal_sim | platform_observed
    note: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = Field(default_factory=lambda: str(uuid4()))
    platform: str
    bonus_id: str = ""
    title: str
    amount: float = 0.0
    currency: str = "CRC"
    source: str = "manual"  # promo | account | manual
    status: str = "credited"  # credited | pending | failed
    note: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WalletLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def load(self) -> list[WalletCredit]:
        raw = json.loads(self.path.read_text(encoding="utf-8") or "[]")
        return [WalletCredit.model_validate(item) for item in raw]

    def save(self, items: list[WalletCredit]) -> None:
        payload = [i.model_dump(mode="json") for i in items]
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def credit(self, item: WalletCredit) -> WalletCredit:
        items = self.load()
        # dedupe by platform+bonus_id+title
        for existing in items:
            if (
                existing.platform == item.platform
                and existing.bonus_id
                and existing.bonus_id == item.bonus_id
            ):
                return existing
            if (
                existing.platform == item.platform
                and not item.bonus_id
                and existing.title == item.title
                and existing.amount == item.amount
            ):
                return existing
        items.insert(0, item)
        self.save(items)
        return item

    def credit_many(self, credits: list[WalletCredit]) -> list[WalletCredit]:
        return [self.credit(c) for c in credits]

    def summary(self) -> dict[str, Any]:
        items = self.load()
        by_currency: dict[str, float] = {}
        for item in items:
            if item.status != "credited":
                continue
            by_currency[item.currency] = by_currency.get(item.currency, 0.0) + item.amount
        return {
            "ledger": "betbonus_ops",
            "reality": "internal_sim",
            "disclaimer": (
                "Este ledger é simulação interna do BetBonus. "
                "credit() NÃO altera balance/bonus/rollover da casa. "
                "Saldo real = house_wallet / snapshot da API."
            ),
            "total_entries": len(items),
            "credited": sum(1 for i in items if i.status == "credited"),
            "internal_sim": sum(1 for i in items if i.reality == "internal_sim"),
            "platform_observed": sum(1 for i in items if i.reality == "platform_observed"),
            "totals_by_currency": by_currency,
            "items": [i.model_dump(mode="json") for i in items[:100]],
        }

    def clear(self) -> int:
        n = len(self.load())
        self.save([])
        return n
