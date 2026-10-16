"""Account factory / multi-account scale layer for BetBonus AI.

Provides synthetic identity generation, per-platform registration clients,
proxy rotation, and a batch orchestrator to run the kill chain across many
accounts simultaneously.
"""

from src.factory.identity import Identity, IdentityGenerator
from src.factory.proxy import ProxyPool
from src.factory.account_factory import AccountFactory, FactoryResult
from src.factory.behavior import BehavioralFingerprint, BehavioralProfile
from src.factory.scheduler import TimingScheduler, ScheduledEvent
from src.factory.pnl import CampaignPnL, AccountPnL

__all__ = [
    "Identity",
    "IdentityGenerator",
    "ProxyPool",
    "AccountFactory",
    "FactoryResult",
    "BehavioralFingerprint",
    "BehavioralProfile",
    "TimingScheduler",
    "ScheduledEvent",
    "CampaignPnL",
    "AccountPnL",
]
