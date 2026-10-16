"""Contrato comum de casa para o produto Casino Online."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from src.models.abuse import WalletSnapshot


class UnsupportedCapability(Exception):
    """A casa não expõe esta superfície via API do operador (ainda)."""

    def __init__(self, capability: str, platform: str, note: str = ""):
        self.capability = capability
        self.platform = platform
        self.note = note
        msg = f"{platform}: {capability} UNSUPPORTED"
        if note:
            msg = f"{msg} — {note}"
        super().__init__(msg)


def wallet_delta(before: WalletSnapshot, after: WalletSnapshot) -> dict[str, Any]:
    d_bal = round(float(after.balance) - float(before.balance), 4)
    d_bonus = round(float(after.bonus) - float(before.bonus), 4)
    d_roll = round(float(after.rollover) - float(before.rollover), 4)
    return {
        "balance": d_bal,
        "bonus": d_bonus,
        "rollover": d_roll,
        "changed": any(abs(x) > 1e-9 for x in (d_bal, d_bonus, d_roll)),
        "before": {
            "balance": before.balance,
            "bonus": before.bonus,
            "rollover": before.rollover,
        },
        "after": {
            "balance": after.balance,
            "bonus": after.bonus,
            "rollover": after.rollover,
        },
    }


class HouseAdapter(ABC):
    """Uma responsabilidade: traduzir a API da casa para o harness de cassino."""

    platform: str = "unknown"
    stack: str = "unknown"

    @abstractmethod
    def validate_session(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def wallet_snapshot(self) -> WalletSnapshot:
        raise NotImplementedError

    def list_games(self, category: str, *, limit: int = 8) -> list[dict[str, Any]]:
        raise UnsupportedCapability(
            "list_games",
            self.platform,
            f"catálogo '{category}' não exposto nesta stack ({self.stack})",
        )

    def list_catalog(self, *, query: str = "", limit: int = 120) -> list[dict[str, Any]]:
        """Lista jogável para o modal de sessão. Default: agrega categorias."""
        by_id: dict[Any, dict[str, Any]] = {}
        q = (query or "").strip().lower()
        for cat in ("slots", "crash", "table", "jackpot"):
            try:
                rows = self.list_games(cat, limit=max(8, min(limit, 40)))
            except UnsupportedCapability:
                continue
            except Exception:  # noqa: BLE001
                continue
            for row in rows:
                gid = row.get("game_id")
                if gid is None:
                    continue
                name = str(row.get("name") or "")
                if q and q not in name.lower() and q not in str(gid).lower():
                    continue
                by_id.setdefault(gid, {**row, "category_hint": cat})
            if len(by_id) >= limit:
                break
        if not by_id:
            raise UnsupportedCapability("list_catalog", self.platform, "catálogo vazio ou não exposto")
        return list(by_id.values())[:limit]

    def start_game(
        self,
        game_id: int | str,
        *,
        mode: str = "REAL",
        use_bonus: Optional[bool] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        raise UnsupportedCapability(
            "start_game",
            self.platform,
            "launch de jogo exige API Salsa/aggregator — não reverse-engineer de provider",
        )

    def auto_bet(
        self,
        game_id: int | str,
        *,
        clicks: int = 1,
        use_bonus: bool = False,
        mode: str = "REAL",
        timeout_ms: int = 45000,
        **kwargs: Any,
    ) -> dict[str, Any]:
        raise UnsupportedCapability(
            "auto_bet",
            self.platform,
            "stake no provider exige launch + browser spin — não mapeado nesta stack",
        )

    def bonus_inventory(self) -> dict[str, Any]:
        raise UnsupportedCapability("bonus_inventory", self.platform)

    def freespin_inventory(self) -> dict[str, Any]:
        raise UnsupportedCapability(
            "freespin_inventory",
            self.platform,
            "inventário FS não mapeado nesta API",
        )

    def jackpot_state(self) -> dict[str, Any]:
        raise UnsupportedCapability("jackpot_state", self.platform)

    def withdraw_preflight(self) -> dict[str, Any]:
        raise UnsupportedCapability("withdraw_preflight", self.platform)

    def capabilities(self) -> dict[str, bool]:
        names = (
            "validate_session",
            "wallet_snapshot",
            "list_games",
            "list_catalog",
            "start_game",
            "auto_bet",
            "bonus_inventory",
            "freespin_inventory",
            "jackpot_state",
            "withdraw_preflight",
        )
        out: dict[str, bool] = {}
        for name in names:
            impl = getattr(type(self), name, None)
            base = getattr(HouseAdapter, name, None)
            out[name] = impl is not None and impl is not base
        return out
