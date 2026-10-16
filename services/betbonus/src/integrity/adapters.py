"""Adapters das 3 casas Lucky Gaming — paridade de superfície, UNSUPPORTED explícito."""

from __future__ import annotations

from typing import Any, Callable, Optional

from src.integrity.house import HouseAdapter, UnsupportedCapability
from src.models.abuse import WalletSnapshot
from src.scrapers.fourplay_br_scraper import FourPlayBrScraper
from src.scrapers.fourplay_scraper import CASINO_CATEGORY, FourPlayScraper
from src.scrapers.pagol_scraper import PagolScraper


CATEGORY_TERMS = {
    "slots": ("slot", "olympus", "bonanza", "gates of"),
    "crash": ("mines", "aviator", "crash", "plinko", "dice"),
    "table": ("blackjack", "roulette", "baccarat", "roleta"),
    "live": ("live casino", "roleta ao vivo", "blackjack ao vivo"),
    "jackpot": ("jackpot", "progressive"),
    "instant": ("mines", "plinko", "dice", "limbo"),
}

CATALOG_SEEDS = (
    "slot",
    "mega",
    "gold",
    "wild",
    "sweet",
    "crash",
    "mines",
    "plinko",
    "aviator",
    "roule",
    "black",
    "live",
)


def _game_row(raw: dict[str, Any]) -> dict[str, Any]:
    gid = raw.get("gameId") or raw.get("game_id") or raw.get("id")
    return {
        "game_id": gid,
        "name": raw.get("name") or "",
        "slug": raw.get("slug"),
        "provider": raw.get("gameProviderName") or raw.get("provider"),
        "vertical_ids": raw.get("verticalIds"),
    }


def _fourplay_game_row(raw: dict[str, Any]) -> dict[str, Any]:
    gid = raw.get("id") or raw.get("game_id") or raw.get("gameId")
    return {
        "game_id": gid,
        "name": raw.get("gameName") or raw.get("name") or "",
        "slug": raw.get("gameCode") or raw.get("slug"),
        "provider": raw.get("provider"),
        "aggregator": raw.get("aggregator"),
        "category": raw.get("category"),
        "category_hint": str(raw.get("category") or "").lower() or None,
        "game_code": raw.get("gameCode"),
        "live": bool(raw.get("live")),
        "banner": raw.get("banner"),
        "source": "casino/games",
    }


class PagolHouse(HouseAdapter):
    platform = "pagol_bet_br"
    stack = "salsa"

    def __init__(self, scraper: PagolScraper):
        self.scraper = scraper

    def validate_session(self) -> dict[str, Any]:
        data = self.scraper.validate_token()
        data["platform"] = self.platform
        data["stack"] = self.stack
        return data

    def wallet_snapshot(self) -> WalletSnapshot:
        return self.scraper.get_wallet_snapshot(include_bonus_state=True)

    def list_games(self, category: str, *, limit: int = 8) -> list[dict[str, Any]]:
        cat = (category or "slots").lower()
        terms = CATEGORY_TERMS.get(cat, (cat if len(cat) >= 3 else "slot",))
        by_id: dict[Any, dict[str, Any]] = {}
        for term in terms:
            try:
                result = self.scraper.search_games(term, page=0, page_size=30)
            except Exception:  # noqa: BLE001
                continue
            for row in result.get("items") or []:
                if not isinstance(row, dict):
                    continue
                parsed = _game_row(row)
                gid = parsed.get("game_id")
                if gid is None:
                    continue
                by_id.setdefault(gid, parsed)
            if len(by_id) >= limit:
                break
        return list(by_id.values())[:limit]

    def list_catalog(self, *, query: str = "", limit: int = 120) -> list[dict[str, Any]]:
        q = (query or "").strip()
        terms = (q,) if len(q) >= 3 else CATALOG_SEEDS
        by_id: dict[Any, dict[str, Any]] = {}
        for term in terms:
            try:
                result = self.scraper.search_games(term, page=0, page_size=50)
            except Exception:  # noqa: BLE001
                continue
            for row in result.get("items") or []:
                if not isinstance(row, dict):
                    continue
                parsed = _game_row(row)
                gid = parsed.get("game_id")
                if gid is None:
                    continue
                if q and len(q) < 3:
                    blob = f"{parsed.get('name') or ''} {gid} {parsed.get('provider') or ''}".lower()
                    if q.lower() not in blob:
                        continue
                by_id.setdefault(gid, parsed)
            if len(by_id) >= limit:
                break
        return list(by_id.values())[:limit]

    def start_game(
        self,
        game_id: int | str,
        *,
        mode: str = "REAL",
        use_bonus: Optional[bool] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.scraper.start_game(game_id, mode=mode, use_bonus_balance=use_bonus)

    def bonus_inventory(self) -> dict[str, Any]:
        return self.scraper.get_bonus_conversion_state()

    def freespin_inventory(self) -> dict[str, Any]:
        items = []
        try:
            bonuses = self.scraper.list_my_bonuses()
        except Exception as exc:  # noqa: BLE001
            return {"items": [], "count": 0, "error": str(exc)[:240]}
        for row in bonuses:
            if not isinstance(row, dict):
                continue
            fs = row.get("freeSpins") or row.get("fsCount") or row.get("spins") or row.get("freeSpinCount")
            name = str(row.get("name") or row.get("bonusType") or "")
            if fs or "spin" in name.lower() or "fs" in name.lower():
                items.append(
                    {
                        "id": row.get("id"),
                        "name": row.get("name"),
                        "status": row.get("status"),
                        "free_spins": fs,
                        "bonus_type": row.get("bonusType"),
                    }
                )
        return {"items": items, "count": len(items), "scanned": len(bonuses)}

    def jackpot_state(self) -> dict[str, Any]:
        games = self.list_games("jackpot", limit=6)
        return {"games": games, "count": len(games), "source": "catalog_search"}

    def withdraw_preflight(self) -> dict[str, Any]:
        return self.scraper.withdraw_preflight()

    def auto_bet(
        self,
        game_id: int | str,
        *,
        clicks: int = 1,
        use_bonus: bool = False,
        mode: str = "REAL",
        timeout_ms: int = 45000,
    ) -> dict[str, Any]:
        """Place N real bets at the provider game client (SEMI_AUTO stake)."""
        return self.scraper.auto_bet(
            game_id,
            clicks=clicks,
            use_bonus_balance=use_bonus,
            mode=mode,
            timeout_ms=timeout_ms,
        )


class FourPlayBrHouse(HouseAdapter):
    platform = "4play_bet_br"
    stack = "softbet"

    def __init__(self, scraper: FourPlayBrScraper):
        self.scraper = scraper

    def validate_session(self) -> dict[str, Any]:
        data = self.scraper.validate_token()
        data["platform"] = self.platform
        data["stack"] = self.stack
        return data

    def wallet_snapshot(self) -> WalletSnapshot:
        return self.scraper.get_wallet_snapshot()

    def list_games(self, category: str, *, limit: int = 8) -> list[dict[str, Any]]:
        try:
            ids = self.scraper.list_wagering_game_ids()
        except Exception as exc:  # noqa: BLE001
            raise UnsupportedCapability(
                "list_games",
                self.platform,
                f"SoftBet /api/games/wagering-game-ids falhou: {exc}"[:240],
            ) from exc
        rows = []
        for gid in ids[:limit]:
            rows.append({"game_id": gid, "name": "", "category_hint": category, "source": "wagering-game-ids"})
        if not rows:
            raise UnsupportedCapability(
                "list_games",
                self.platform,
                "SoftBet não devolveu catálogo jogável (IDs vazios / IP do lab)",
            )
        return rows

    def list_catalog(self, *, query: str = "", limit: int = 120) -> list[dict[str, Any]]:
        rows = self.list_games("slots", limit=max(limit, 1))
        q = (query or "").strip().lower()
        if q:
            rows = [r for r in rows if q in str(r.get("game_id", "")).lower()]
        return rows[:limit]

    def bonus_inventory(self) -> dict[str, Any]:
        items = self.scraper.list_my_bonuses()
        return {"items": items[:20], "count": len(items)}

    def freespin_inventory(self) -> dict[str, Any]:
        inv = self.bonus_inventory()
        fs = []
        for row in inv.get("items") or []:
            if not isinstance(row, dict):
                continue
            blob = " ".join(str(row.get(k) or "") for k in ("name", "type", "bonusType", "title"))
            if any(k in blob.lower() for k in ("spin", "fs", "free")):
                fs.append(row)
        return {"items": fs, "count": len(fs), "scanned": inv.get("count")}

    def withdraw_preflight(self) -> dict[str, Any]:
        snap = self.wallet_snapshot()
        return {
            "wallet": snap.model_dump(mode="json"),
            "note": "SoftBet: preflight PIX/saque não mapeado nesta API — só snapshot",
            "unsupported_full_preflight": True,
        }

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
        """Place N real bets at the provider game client via SoftBet SPA."""
        return self.scraper.auto_bet(
            game_id,
            clicks=clicks,
            use_bonus=use_bonus,
            mode=mode,
            timeout_ms=timeout_ms,
            game_name=str(kwargs.get("game_name") or kwargs.get("name") or ""),
        )


class FourPlayHouse(HouseAdapter):
    platform = "4play"
    stack = "4play.game"

    def __init__(self, scraper: FourPlayScraper):
        self.scraper = scraper

    def validate_session(self) -> dict[str, Any]:
        data = self.scraper.validate_token()
        data["platform"] = self.platform
        data["stack"] = self.stack
        return data

    def wallet_snapshot(self) -> WalletSnapshot:
        return self.scraper.get_wallet_snapshot()

    def bonus_inventory(self) -> dict[str, Any]:
        items = self.scraper.list_my_bonuses()
        return {"items": items[:20], "count": len(items)}

    def freespin_inventory(self) -> dict[str, Any]:
        inv = self.bonus_inventory()
        fs = []
        for row in inv.get("items") or []:
            if not isinstance(row, dict):
                continue
            blob = str(row).lower()
            if "spin" in blob or "fs" in blob:
                fs.append({"id": row.get("id"), "raw_keys": list(row.keys())[:12]})
        return {"items": fs, "count": len(fs), "scanned": inv.get("count")}

    def list_games(self, category: str, *, limit: int = 8) -> list[dict[str, Any]]:
        cat = (category or "slots").strip().lower()
        kwargs: dict[str, Any] = {}
        if cat in {"live", "live casino"}:
            kwargs["live"] = True
        elif cat == "jackpot":
            kwargs["search"] = "jackpot"
        elif cat in CASINO_CATEGORY:
            mapped = CASINO_CATEGORY[cat]
            if mapped == "Live":
                kwargs["live"] = True
            else:
                kwargs["category"] = mapped
        elif len(cat) >= 2:
            kwargs["search"] = cat
        return self._collect_casino_games(limit=limit, **kwargs)

    def list_catalog(self, *, query: str = "", limit: int = 120) -> list[dict[str, Any]]:
        q = (query or "").strip()
        if len(q) >= 2:
            rows = self._collect_casino_games(limit=limit, search=q)
            if rows:
                return rows
        # Sem busca: recomendações (lobby) + populares, depois primeira página.
        by_id: dict[Any, dict[str, Any]] = {}
        for kwargs in ({"recommended": True}, {"popular": True}, {}):
            for row in self._collect_casino_games(limit=limit, **kwargs):
                gid = row.get("game_id")
                if gid is None:
                    continue
                by_id.setdefault(gid, row)
                if len(by_id) >= limit:
                    return list(by_id.values())[:limit]
        rows = list(by_id.values())[:limit]
        if not rows:
            raise UnsupportedCapability(
                "list_catalog",
                self.platform,
                "GET /casino/games não devolveu títulos",
            )
        return rows

    def _collect_casino_games(self, *, limit: int, **filters: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        seen: set[Any] = set()
        per_page = min(100, max(20, limit))
        while len(rows) < limit and page <= 8:
            batch = self.scraper.list_casino_games(page=page, per_page=per_page, **filters)
            items = [x for x in (batch.get("items") or []) if isinstance(x, dict)]
            if not items:
                break
            for raw in items:
                parsed = _fourplay_game_row(raw)
                gid = parsed.get("game_id")
                if gid is None or gid in seen:
                    continue
                seen.add(gid)
                rows.append(parsed)
                if len(rows) >= limit:
                    return rows
            total = int(batch.get("total") or 0)
            if page * per_page >= total:
                break
            page += 1
        return rows

    def withdraw_preflight(self) -> dict[str, Any]:
        snap = self.wallet_snapshot()
        return {
            "wallet": snap.model_dump(mode="json"),
            "min_withdraw": getattr(self.scraper, "MIN_WITHDRAW_AMOUNT", None),
            "note": "4play.game: preflight sem pedido de saque (integrity default)",
        }

    def start_game(
        self,
        game_id: int | str,
        *,
        mode: str = "REAL",
        use_bonus: Optional[bool] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.scraper.start_game(
            game_id,
            mode=mode,
            use_bonus_balance=use_bonus,
            game_code=str(kwargs.get("game_code") or kwargs.get("slug") or ""),
            aggregator=str(kwargs.get("aggregator") or ""),
            game_name=str(kwargs.get("game_name") or kwargs.get("name") or ""),
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
        """Place N real bets at the provider game client (SEMI_AUTO stake)."""
        return self.scraper.auto_bet(
            game_id,
            clicks=clicks,
            use_bonus_balance=use_bonus,
            mode=mode,
            timeout_ms=timeout_ms,
            game_code=str(kwargs.get("game_code") or kwargs.get("slug") or ""),
            aggregator=str(kwargs.get("aggregator") or ""),
            game_name=str(kwargs.get("game_name") or kwargs.get("name") or ""),
        )


HouseFactory = Callable[[str], HouseAdapter]


def build_house(platform: str, scraper: Any) -> HouseAdapter:
    if platform == "pagol_bet_br":
        if not isinstance(scraper, PagolScraper):
            raise TypeError("pagol_bet_br exige PagolScraper")
        return PagolHouse(scraper)
    if platform == "4play_bet_br":
        if not isinstance(scraper, FourPlayBrScraper):
            raise TypeError("4play_bet_br exige FourPlayBrScraper")
        return FourPlayBrHouse(scraper)
    if platform == "4play":
        if not isinstance(scraper, FourPlayScraper):
            raise TypeError("4play exige FourPlayScraper")
        return FourPlayHouse(scraper)
    raise ValueError(f"Casa não suportada no produto cassino: {platform}")
