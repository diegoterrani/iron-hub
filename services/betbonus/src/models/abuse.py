from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ConversionStatus(str, Enum):
    """Estado da conversão bônus → saldo sacável."""

    UNKNOWN = "unknown"
    NO_BONUS = "no_bonus"
    CLAIMED = "claimed"
    WAGERING = "wagering"
    WITHDRAWABLE = "withdrawable"
    BLOCKED = "blocked"
    WITHDRAW_ATTEMPTED = "withdraw_attempted"
    WITHDRAW_OK = "withdraw_ok"
    WITHDRAW_DENIED = "withdraw_denied"


class AbuseSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RulesCanon(BaseModel):
    """Regras canônicas de uma campanha / oferta (fonte da verdade do runner)."""

    platform: str = "4play"
    offer_id: str = ""
    title: str = ""
    wagering_multiple: float = 30.0
    min_deposit: float = 0.0
    max_bet_during_bonus: Optional[float] = None
    game_restrictions: list[str] = Field(default_factory=list)
    expiry_days: float = 30.0
    currency: str = "CRC"
    amount: float = 0.0
    sticky_bonus: bool = False
    notes: str = ""


class WalletSnapshot(BaseModel):
    platform: str = "4play"
    balance: float = 0.0
    bonus: float = 0.0
    rollover: float = 0.0
    raw: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversionSnapshot(BaseModel):
    platform: str = "4play"
    status: ConversionStatus = ConversionStatus.UNKNOWN
    wallet: WalletSnapshot
    account_bonuses: int = 0
    gates: list[str] = Field(default_factory=list)
    notes: str = ""
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AbuseFinding(BaseModel):
    """Finding de abuso / barreira de conversão (JSONL-friendly)."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    schema_version: str = "1"
    tool: str = "betbonus-abuse"
    platform: str = "4play"
    vector: str = "conversion_oracle"
    severity: AbuseSeverity = AbuseSeverity.INFO
    title: str
    status: ConversionStatus = ConversionStatus.UNKNOWN
    abuse_score: float = 0.0
    offer_id: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    reproducible: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WithdrawOracleResult(BaseModel):
    ok: bool = False
    attempted: bool = False
    preflight_only: bool = False
    status: ConversionStatus = ConversionStatus.UNKNOWN
    http_status: Optional[int] = None
    code: str = ""
    message: str = ""
    amount: float = 0.0
    currency: str = "CRC"
    method: str = ""
    wallet_before: Optional[WalletSnapshot] = None
    wallet_after: Optional[WalletSnapshot] = None
    gates: list[str] = Field(default_factory=list)
    response_data: dict[str, Any] = Field(default_factory=dict)
    finding_id: str = ""
