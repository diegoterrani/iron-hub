from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class BonusType(str, Enum):
    DEPOSIT_MATCH = "deposit_match"
    NO_DEPOSIT = "no_deposit"
    FREE_SPINS = "free_spins"
    CASHBACK = "cashback"
    WELCOME_BONUS = "welcome"
    LOYALTY = "loyalty"
    UNKNOWN = "unknown"


class BonusCategory(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    AVOID = "avoid"


class BonusOffer(BaseModel):
    """Canonical bonus offer extracted from a promo page / T&Cs."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    platform: str
    bonus_type: BonusType = BonusType.UNKNOWN
    title: str = ""
    amount: float = 0.0
    currency: str = "USD"
    match_percent: Optional[float] = None
    free_spins: Optional[int] = None
    wagering_multiple: float = 30.0
    min_deposit: float = 0.0
    max_bet_during_bonus: Optional[float] = None
    expiry_days: int = 30
    expiry_hours: Optional[int] = None
    game_restrictions: list[str] = Field(default_factory=list)
    terms_url: str = ""
    source_url: str = ""
    raw_text: str = ""
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    score: float = 0.0
    category: BonusCategory = BonusCategory.AVERAGE
    score_breakdown: dict[str, float] = Field(default_factory=dict)

    @field_validator("scraped_at", mode="before")
    @classmethod
    def _default_scraped_at(cls, value: object) -> object:
        return value or datetime.now(timezone.utc)

    @property
    def effective_expiry_days(self) -> float:
        if self.expiry_hours is not None:
            return max(self.expiry_hours / 24.0, 0.04)
        return float(max(self.expiry_days, 0))


class ScrapeResult(BaseModel):
    platform: str
    source_url: str
    offers: list[BonusOffer] = Field(default_factory=list)
    ok: bool = True
    error: Optional[str] = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
