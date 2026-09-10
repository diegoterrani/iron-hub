"""Account factory / multi-account scale layer for BetBonus AI.

Provides synthetic identity generation, per-platform registration clients,
proxy rotation, and a batch orchestrator to run the kill chain across many
accounts simultaneously.
"""

from src.factory.identity import Identity, IdentityGenerator
from src.factory.proxy import ProxyPool
from src.factory.account_factory import AccountFactory, FactoryResult

__all__ = [
    "Identity",
    "IdentityGenerator",
    "ProxyPool",
    "AccountFactory",
    "FactoryResult",
]
