from datetime import datetime, timezone

from src.integrity.house import HouseAdapter, UnsupportedCapability
from src.models.abuse import WalletSnapshot


class FakeHouse(HouseAdapter):
    platform = "pagol_bet_br"
    stack = "fake"

    def __init__(self, *, scale_cents: bool = True, games: bool = True, start: bool = True):
        self.scale_cents = scale_cents
        self._games = games
        self._start = start
        self.balance = 100.0
        self.bonus = 20.0
        self.rollover = 50.0

    def validate_session(self) -> dict:
        return {"user_id": 1, "currency": "BRL", "platform": self.platform}

    def wallet_snapshot(self) -> WalletSnapshot:
        raw_bal = int(self.balance * 100) if self.scale_cents else self.balance
        return WalletSnapshot(
            platform=self.platform,
            balance=self.balance,
            bonus=self.bonus,
            rollover=self.rollover,
            raw={"balance": raw_bal, "bonusBalance": int(self.bonus * 100)},
            fetched_at=datetime.now(timezone.utc),
        )

    def list_games(self, category: str, *, limit: int = 8):
        if not self._games:
            raise UnsupportedCapability("list_games", self.platform, "fake off")
        return [
            {"game_id": 1624, "name": f"Fake {category} 1", "provider": "lab"},
            {"game_id": 99, "name": f"Fake {category} 2", "provider": "lab"},
        ][:limit]

    def list_catalog(self, *, query: str = "", limit: int = 120):
        rows = []
        for cat in ("slots", "crash", "table"):
            rows.extend(self.list_games(cat, limit=2))
        q = (query or "").strip().lower()
        if q:
            rows = [
                r
                for r in rows
                if q in str(r.get("name") or "").lower() or q in str(r.get("game_id"))
            ]
        seen: set = set()
        out = []
        for row in rows:
            gid = row.get("game_id")
            if gid in seen:
                continue
            seen.add(gid)
            out.append(row)
        return out[:limit]

    def start_game(self, game_id, *, mode: str = "REAL", use_bonus=None, **kwargs):
        if not self._start:
            raise UnsupportedCapability("start_game", self.platform, "fake off")
        return {
            "url": "https://salsa.example/launch?type=CHARGED&game=x",
            "mode": mode,
            "use_bonus_balance": use_bonus,
            "launch": {"host": "salsa.example", "type": "CHARGED", "game": "x"},
        }

    def bonus_inventory(self) -> dict:
        return {
            "count": 1,
            "primary": {
                "remaining_rollover_brl": self.rollover,
                "max_bet_brl": 3.0,
                "bonusGameTypes": ["SLOTS"],
            },
        }

    def freespin_inventory(self) -> dict:
        return {"items": [{"id": 1, "free_spins": 10}], "count": 1, "scanned": 1}

    def jackpot_state(self) -> dict:
        return {"games": [{"game_id": 7, "name": "Jackpot Lab"}], "count": 1}

    def withdraw_preflight(self) -> dict:
        return {"withdrawal_allowed": True, "min_withdraw": 20.0, "have_opened": False}
