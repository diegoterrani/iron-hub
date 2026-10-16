"""
Per-account and per-campaign profit/loss tracking.

Tracks: bonus acquired, wagered amount, house edge loss, net extractable,
withdrawal amount, withdrawal status, total P&L.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Per-account P&L
# ---------------------------------------------------------------------------

@dataclass
class AccountPnL:
    """Profit/loss record for a single account within a campaign."""
    account_id: str
    platform: str
    identity_name: str
    bonus_acquired: float = 0.0
    wagered: float = 0.0
    house_edge_loss: float = 0.0
    net_extractable: float = 0.0
    withdrawn: float = 0.0
    withdrawal_status: str = "pending"   # "pending" | "materialized" | "denied"
    deposit_cost: float = 0.0
    proxy_cost: float = 0.0
    total_cost: float = 0.0
    net_profit: float = 0.0
    timestamps: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


# ---------------------------------------------------------------------------
# Campaign-level P&L
# ---------------------------------------------------------------------------

class CampaignPnL:
    """Aggregates P&L across all accounts in a campaign.

    Usage:
        pnl = CampaignPnL(campaign_id="op-2026-09-14")
        pnl.add_account(AccountPnL(...))
        summary = pnl.summary()
    """

    def __init__(self, campaign_id: str = ""):
        self.campaign_id = campaign_id
        self.accounts: list[AccountPnL] = []

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add_account(self, account: AccountPnL) -> None:
        """Add an account's P&L record to the campaign."""
        self.accounts.append(account)

    def remove_account(self, account_id: str) -> bool:
        """Remove an account by id. Returns True if found and removed."""
        before = len(self.accounts)
        self.accounts = [a for a in self.accounts if a.account_id != account_id]
        return len(self.accounts) < before

    def update_account(
        self,
        account_id: str,
        **kwargs: Any,
    ) -> Optional[AccountPnL]:
        """Update fields on an existing account. Returns the account or None."""
        for acct in self.accounts:
            if acct.account_id == account_id:
                for k, v in kwargs.items():
                    if hasattr(acct, k):
                        setattr(acct, k, v)
                return acct
        return None

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    @property
    def total_accounts(self) -> int:
        return len(self.accounts)

    @property
    def total_bonus_acquired(self) -> float:
        return sum(a.bonus_acquired for a in self.accounts)

    @property
    def total_wagered(self) -> float:
        return sum(a.wagered for a in self.accounts)

    @property
    def total_house_edge_loss(self) -> float:
        return sum(a.house_edge_loss for a in self.accounts)

    @property
    def total_extractable(self) -> float:
        """Sum of net_extractable across accounts."""
        return sum(a.net_extractable for a in self.accounts)

    @property
    def total_extracted(self) -> float:
        """Sum of withdrawn amounts for accounts with materialized withdrawals."""
        return sum(
            a.withdrawn for a in self.accounts
            if a.withdrawal_status == "materialized"
        )

    @property
    def total_cost(self) -> float:
        """Sum of total_cost across all accounts."""
        return sum(a.total_cost for a in self.accounts)

    @property
    def net_profit(self) -> float:
        """Total extracted minus total cost."""
        return self.total_extracted - self.total_cost

    @property
    def success_rate(self) -> float:
        """Fraction of accounts with materialized withdrawals."""
        if not self.accounts:
            return 0.0
        materialized = sum(
            1 for a in self.accounts if a.withdrawal_status == "materialized"
        )
        return materialized / len(self.accounts)

    @property
    def pending_count(self) -> int:
        return sum(1 for a in self.accounts if a.withdrawal_status == "pending")

    @property
    def denied_count(self) -> int:
        return sum(1 for a in self.accounts if a.withdrawal_status == "denied")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a JSON-friendly summary dict."""
        return {
            "campaign_id": self.campaign_id,
            "total_accounts": self.total_accounts,
            "total_bonus_acquired": round(self.total_bonus_acquired, 2),
            "total_wagered": round(self.total_wagered, 2),
            "total_house_edge_loss": round(self.total_house_edge_loss, 2),
            "total_extractable": round(self.total_extractable, 2),
            "total_extracted": round(self.total_extracted, 2),
            "total_cost": round(self.total_cost, 2),
            "net_profit": round(self.net_profit, 2),
            "success_rate": self.success_rate,
            "pending": self.pending_count,
            "denied": self.denied_count,
        }

    def to_dict(self) -> dict[str, Any]:
        """Full serialization including per-account detail."""
        return {
            "campaign_id": self.campaign_id,
            "summary": self.summary(),
            "accounts": [a.to_dict() for a in self.accounts],
        }
