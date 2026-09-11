"""Postgres + Redis storage layer (optional, env-gated).

Every store mirrors its JSON-file counterpart's API on top of a
Postgres table.  ``make_*()`` factories return the Postgres store when
``BETBONUS_DATABASE_URL`` is set, otherwise the JSON store — callers
never need to know which one they got.

Env vars
--------
- ``BETBONUS_DATABASE_URL``  e.g. ``postgresql://user:pass@host/db``
- ``BETBONUS_REDIS_URL``     e.g. ``redis://localhost:6379/0``
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from src.models.bonus import BonusOffer
from src.storage.store import JsonBonusStore


def _connect(dsn: str):
    import psycopg

    return psycopg.connect(dsn, autocommit=False)


def database_url() -> str:
    return (os.environ.get("BETBONUS_DATABASE_URL") or "").strip()


def redis_url() -> str:
    return (os.environ.get("BETBONUS_REDIS_URL") or "").strip()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS bonus_offers (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    bonus_type TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    match_percent DOUBLE PRECISION,
    free_spins INTEGER,
    wagering_multiple DOUBLE PRECISION NOT NULL DEFAULT 30,
    min_deposit DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_bet_during_bonus DOUBLE PRECISION,
    expiry_days INTEGER NOT NULL DEFAULT 30,
    expiry_hours INTEGER,
    game_restrictions JSONB NOT NULL DEFAULT '[]',
    terms_url TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    raw_text TEXT NOT NULL DEFAULT '',
    scraped_at TIMESTAMPTZ NOT NULL,
    score DOUBLE PRECISION NOT NULL DEFAULT 0,
    category TEXT NOT NULL DEFAULT 'average',
    score_breakdown JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_bonus_offers_platform
    ON bonus_offers (platform);
CREATE INDEX IF NOT EXISTS idx_bonus_offers_scraped_at
    ON bonus_offers (scraped_at DESC);

CREATE TABLE IF NOT EXISTS wallet_credits (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    bonus_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'CRC',
    source TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'credited',
    reality TEXT NOT NULL DEFAULT 'internal_sim',
    note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wallet_credits_platform
    ON wallet_credits (platform);
CREATE INDEX IF NOT EXISTS idx_wallet_credits_created_at
    ON wallet_credits (created_at DESC);

CREATE TABLE IF NOT EXISTS abuse_findings (
    id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL DEFAULT '',
    tool TEXT NOT NULL DEFAULT '',
    platform TEXT NOT NULL,
    vector TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'info',
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'unverified',
    abuse_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    offer_id TEXT NOT NULL DEFAULT '',
    evidence JSONB NOT NULL DEFAULT '{}',
    reproducible BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_abuse_findings_platform
    ON abuse_findings (platform);
CREATE INDEX IF NOT EXISTS idx_abuse_findings_created_at
    ON abuse_findings (created_at DESC);

CREATE TABLE IF NOT EXISTS integrity_runs (
    id TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    run_mode TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_integrity_runs_started_at
    ON integrity_runs (started_at DESC);

CREATE TABLE IF NOT EXISTS journey_sessions (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT '',
    platform TEXT NOT NULL DEFAULT '',
    house_name TEXT NOT NULL DEFAULT '',
    house_url TEXT NOT NULL DEFAULT '',
    scout_mode TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    meta JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_journey_sessions_status
    ON journey_sessions (status);
CREATE INDEX IF NOT EXISTS idx_journey_sessions_started_at
    ON journey_sessions (started_at DESC);

CREATE TABLE IF NOT EXISTS journey_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES journey_sessions(id)
        ON DELETE CASCADE,
    step TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL DEFAULT '',
    detail JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL,
    seq INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_journey_events_session
    ON journey_events (session_id, seq);

CREATE TABLE IF NOT EXISTS house_profiles (
    platform TEXT PRIMARY KEY,
    generated_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'
);
"""

# --- bonus_offers ----------------------------------------------------------

_OFFERS_TABLE = "bonus_offers"

_INSERT_OFFER = f"""
INSERT INTO {_OFFERS_TABLE}
    (id, platform, bonus_type, title, amount, currency,
     match_percent, free_spins, wagering_multiple, min_deposit,
     max_bet_during_bonus, expiry_days, expiry_hours,
     game_restrictions, terms_url, source_url, raw_text,
     scraped_at, score, category, score_breakdown)
VALUES
    (%(id)s, %(platform)s, %(bonus_type)s, %(title)s, %(amount)s,
     %(currency)s, %(match_percent)s, %(free_spins)s,
     %(wagering_multiple)s, %(min_deposit)s, %(max_bet_during_bonus)s,
     %(expiry_days)s, %(expiry_hours)s, %(game_restrictions)s,
     %(terms_url)s, %(source_url)s, %(raw_text)s, %(scraped_at)s,
     %(score)s, %(category)s, %(score_breakdown)s)
ON CONFLICT (id) DO UPDATE SET
    platform = EXCLUDED.platform,
    bonus_type = EXCLUDED.bonus_type,
    title = EXCLUDED.title,
    amount = EXCLUDED.amount,
    currency = EXCLUDED.currency,
    match_percent = EXCLUDED.match_percent,
    free_spins = EXCLUDED.free_spins,
    wagering_multiple = EXCLUDED.wagering_multiple,
    min_deposit = EXCLUDED.min_deposit,
    max_bet_during_bonus = EXCLUDED.max_bet_during_bonus,
    expiry_days = EXCLUDED.expiry_days,
    expiry_hours = EXCLUDED.expiry_hours,
    game_restrictions = EXCLUDED.game_restrictions,
    terms_url = EXCLUDED.terms_url,
    source_url = EXCLUDED.source_url,
    raw_text = EXCLUDED.raw_text,
    scraped_at = EXCLUDED.scraped_at,
    score = EXCLUDED.score,
    category = EXCLUDED.category,
    score_breakdown = EXCLUDED.score_breakdown
"""


def _offer_params(offer: BonusOffer) -> dict[str, object]:
    data = offer.model_dump(mode="json")
    data["bonus_type"] = data["bonus_type"].value
    data["category"] = data["category"].value
    data["game_restrictions"] = json.dumps(
        data.get("game_restrictions") or [], ensure_ascii=False
    )
    data["score_breakdown"] = json.dumps(
        data.get("score_breakdown") or {}, ensure_ascii=False
    )
    return data


_OFFER_KEYS = (
    "id", "platform", "bonus_type", "title", "amount", "currency",
    "match_percent", "free_spins", "wagering_multiple", "min_deposit",
    "max_bet_during_bonus", "expiry_days", "expiry_hours",
    "game_restrictions", "terms_url", "source_url", "raw_text",
    "scraped_at", "score", "category", "score_breakdown",
)


def _row_to_offer(row: tuple) -> BonusOffer:
    data = dict(zip(_OFFER_KEYS, row))
    data["game_restrictions"] = (
        json.loads(data["game_restrictions"])
        if isinstance(data["game_restrictions"], str)
        else (data["game_restrictions"] or [])
    )
    data["score_breakdown"] = (
        json.loads(data["score_breakdown"])
        if isinstance(data["score_breakdown"], str)
        else (data["score_breakdown"] or {})
    )
    return BonusOffer.model_validate(data)


class PostgresBonusStore:
    """Postgres persistence with the same surface as JsonBonusStore."""

    def __init__(self, dsn: str, conn: Optional[object] = None):
        self.dsn = dsn
        if conn is None:
            conn = _connect(dsn)
        self.conn = conn
        with self.conn.cursor() as cur:
            cur.execute(_SCHEMA)
        self.conn.commit()

    def _fetch_all(self) -> list[BonusOffer]:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {_OFFERS_TABLE}")
            rows = cur.fetchall()
        return [_row_to_offer(row) for row in rows]

    def load(self) -> list[BonusOffer]:
        return self._fetch_all()

    def save(self, offers: list[BonusOffer]) -> None:
        with self.conn.cursor() as cur:
            for offer in offers:
                cur.execute(_INSERT_OFFER, _offer_params(offer))
        self.conn.commit()

    def get(self, bonus_id: str) -> Optional[BonusOffer]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_OFFERS_TABLE} WHERE id = %s", (bonus_id,)
            )
            row = cur.fetchone()
        return _row_to_offer(row) if row else None

    def delete(self, bonus_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {_OFFERS_TABLE} WHERE id = %s", (bonus_id,)
            )
            deleted = cur.rowcount > 0
        self.conn.commit()
        return deleted

    def clear(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {_OFFERS_TABLE}")
            count = cur.fetchone()[0]
            cur.execute(f"DELETE FROM {_OFFERS_TABLE}")
        self.conn.commit()
        return count

    def upsert(self, offers: list[BonusOffer]) -> list[BonusOffer]:
        existing = {
            (o.platform, o.title, o.amount, o.wagering_multiple): o.id
            for o in self._fetch_all()
        }
        for offer in offers:
            key = (
                offer.platform, offer.title, offer.amount,
                offer.wagering_multiple,
            )
            offer.id = existing.get(key, offer.id)
            existing[key] = offer.id
        self.save(offers)
        return self._fetch_all()

    def close(self) -> None:
        self.conn.close()


# --- wallet_credits --------------------------------------------------------

_WALLET_TABLE = "wallet_credits"

_INSERT_WALLET = f"""
INSERT INTO {_WALLET_TABLE}
    (id, platform, bonus_id, title, amount, currency,
     source, status, reality, note, created_at)
VALUES
    (%(id)s, %(platform)s, %(bonus_id)s, %(title)s, %(amount)s,
     %(currency)s, %(source)s, %(status)s, %(reality)s,
     %(note)s, %(created_at)s)
ON CONFLICT (id) DO UPDATE SET
    platform = EXCLUDED.platform,
    bonus_id = EXCLUDED.bonus_id,
    title = EXCLUDED.title,
    amount = EXCLUDED.amount,
    currency = EXCLUDED.currency,
    source = EXCLUDED.source,
    status = EXCLUDED.status,
    reality = EXCLUDED.reality,
    note = EXCLUDED.note,
    created_at = EXCLUDED.created_at
"""

_WALLET_KEYS = (
    "id", "platform", "bonus_id", "title", "amount", "currency",
    "source", "status", "reality", "note", "created_at",
)


def _row_to_wallet(row: tuple):
    from src.storage.wallet import WalletCredit

    data = dict(zip(_WALLET_KEYS, row))
    return WalletCredit.model_validate(data)


class PostgresWalletLedger:
    """Postgres persistence mirroring WalletLedger."""

    def __init__(self, dsn: str, conn: Optional[object] = None):
        self.dsn = dsn
        if conn is None:
            conn = _connect(dsn)
        self.conn = conn

    def load(self) -> list:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_WALLET_TABLE} ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
        return [_row_to_wallet(r) for r in rows]

    def save(self, items: list) -> None:
        with self.conn.cursor() as cur:
            for item in items:
                params = item.model_dump(mode="json")
                cur.execute(_INSERT_WALLET, params)
        self.conn.commit()

    def credit(self, item) -> object:
        from src.storage.wallet import WalletCredit

        items = self.load()
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

    def credit_many(self, credits: list) -> list:
        return [self.credit(c) for c in credits]

    def summary(self) -> dict[str, Any]:
        items = self.load()
        by_currency: dict[str, float] = {}
        for item in items:
            if item.status != "credited":
                continue
            by_currency[item.currency] = (
                by_currency.get(item.currency, 0.0) + item.amount
            )
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
            "internal_sim": sum(
                1 for i in items if i.reality == "internal_sim"
            ),
            "platform_observed": sum(
                1 for i in items if i.reality == "platform_observed"
            ),
            "totals_by_currency": by_currency,
            "items": [i.model_dump(mode="json") for i in items[:100]],
        }

    def clear(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {_WALLET_TABLE}")
            count = cur.fetchone()[0]
            cur.execute(f"DELETE FROM {_WALLET_TABLE}")
        self.conn.commit()
        return count

    def close(self) -> None:
        self.conn.close()


# --- abuse_findings --------------------------------------------------------

_FINDINGS_TABLE = "abuse_findings"

_INSERT_FINDING = f"""
INSERT INTO {_FINDINGS_TABLE}
    (id, schema_version, tool, platform, vector, severity,
     title, status, abuse_score, offer_id, evidence,
     reproducible, created_at)
VALUES
    (%(id)s, %(schema_version)s, %(tool)s, %(platform)s,
     %(vector)s, %(severity)s, %(title)s, %(status)s,
     %(abuse_score)s, %(offer_id)s, %(evidence)s,
     %(reproducible)s, %(created_at)s)
ON CONFLICT (id) DO UPDATE SET
    schema_version = EXCLUDED.schema_version,
    tool = EXCLUDED.tool,
    platform = EXCLUDED.platform,
    vector = EXCLUDED.vector,
    severity = EXCLUDED.severity,
    title = EXCLUDED.title,
    status = EXCLUDED.status,
    abuse_score = EXCLUDED.abuse_score,
    offer_id = EXCLUDED.offer_id,
    evidence = EXCLUDED.evidence,
    reproducible = EXCLUDED.reproducible,
    created_at = EXCLUDED.created_at
"""

_FINDING_KEYS = (
    "id", "schema_version", "tool", "platform", "vector",
    "severity", "title", "status", "abuse_score", "offer_id",
    "evidence", "reproducible", "created_at",
)


def _finding_params(finding) -> dict[str, object]:
    data = finding.model_dump(mode="json")
    data["evidence"] = json.dumps(
        data.get("evidence") or {}, ensure_ascii=False
    )
    return data


def _row_to_finding(row: tuple):
    from src.models.abuse import AbuseFinding

    data = dict(zip(_FINDING_KEYS, row))
    data["evidence"] = (
        json.loads(data["evidence"])
        if isinstance(data["evidence"], str)
        else (data["evidence"] or {})
    )
    return AbuseFinding.model_validate(data)


class PostgresAbuseFindingStore:
    """Postgres persistence mirroring AbuseFindingStore."""

    def __init__(self, dsn: str, conn: Optional[object] = None):
        self.dsn = dsn
        if conn is None:
            conn = _connect(dsn)
        self.conn = conn

    def load(self) -> list:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_FINDINGS_TABLE} ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
        return [_row_to_finding(r) for r in rows]

    def save(self, items: list) -> None:
        with self.conn.cursor() as cur:
            for item in items:
                cur.execute(_INSERT_FINDING, _finding_params(item))
        self.conn.commit()

    def add(self, finding) -> object:
        items = self.load()
        items.insert(0, finding)
        self.save(items[:500])
        return finding

    def list(self, limit: int = 100) -> list:
        return self.load()[:limit]

    def get(self, finding_id: str):
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_FINDINGS_TABLE} WHERE id = %s",
                (finding_id,),
            )
            row = cur.fetchone()
        return _row_to_finding(row) if row else None

    def clear(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {_FINDINGS_TABLE}")
            count = cur.fetchone()[0]
            cur.execute(f"DELETE FROM {_FINDINGS_TABLE}")
        self.conn.commit()
        return count

    def close(self) -> None:
        self.conn.close()


# --- integrity_runs --------------------------------------------------------

_INTEGRITY_TABLE = "integrity_runs"

_INSERT_INTEGRITY = f"""
INSERT INTO {_INTEGRITY_TABLE}
    (id, started_at, finished_at, run_mode, payload)
VALUES
    (%(id)s, %(started_at)s, %(finished_at)s,
     %(run_mode)s, %(payload)s)
ON CONFLICT (id) DO UPDATE SET
    started_at = EXCLUDED.started_at,
    finished_at = EXCLUDED.finished_at,
    run_mode = EXCLUDED.run_mode,
    payload = EXCLUDED.payload
"""


def _integrity_params(item: dict) -> dict[str, object]:
    payload = {
        k: v
        for k, v in item.items()
        if k not in ("id", "started_at", "finished_at", "run_mode")
    }
    return {
        "id": item.get("id", ""),
        "started_at": item.get("started_at"),
        "finished_at": item.get("finished_at"),
        "run_mode": item.get("run_mode", ""),
        "payload": json.dumps(payload, ensure_ascii=False),
    }


def _row_to_integrity(row: tuple) -> dict:
    data = {
        "id": row[0],
        "started_at": row[1].isoformat() if row[1] else None,
        "finished_at": row[2].isoformat() if row[2] else None,
        "run_mode": row[3],
    }
    payload = row[4]
    if isinstance(payload, str):
        payload = json.loads(payload)
    data.update(payload or {})
    return data


class PostgresIntegrityRunStore:
    """Postgres persistence mirroring IntegrityRunStore."""

    def __init__(self, dsn: str, conn: Optional[object] = None):
        self.dsn = dsn
        if conn is None:
            conn = _connect(dsn)
        self.conn = conn

    def load(self) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_INTEGRITY_TABLE} "
                "ORDER BY started_at DESC"
            )
            rows = cur.fetchall()
        return [_row_to_integrity(r) for r in rows]

    def save(self, items: list[dict[str, Any]]) -> None:
        with self.conn.cursor() as cur:
            for item in items[:50]:
                cur.execute(_INSERT_INTEGRITY, _integrity_params(item))
        self.conn.commit()

    def add(self, run) -> dict[str, Any]:
        if hasattr(run, "to_dict"):
            payload = run.to_dict()
        else:
            payload = run
        items = self.load()
        items.insert(0, payload)
        self.save(items)
        return payload

    def latest(self) -> Optional[dict[str, Any]]:
        items = self.load()
        return items[0] if items else None

    def summaries(self, limit: int = 20) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in self.load()[: max(1, min(limit, 50))]:
            cov = (
                item.get("coverage")
                if isinstance(item.get("coverage"), dict)
                else {}
            )
            results = (
                item.get("results")
                if isinstance(item.get("results"), list)
                else []
            )
            out.append(
                {
                    "id": item.get("id"),
                    "started_at": item.get("started_at"),
                    "finished_at": item.get("finished_at"),
                    "run_mode": item.get("run_mode"),
                    "houses": item.get("houses") or [],
                    "axes": item.get("axes") or [],
                    "scenario_count": cov.get("scenario_count")
                    or len(results),
                    "mode_counts": cov.get("mode_counts") or {},
                    "automated_ratio": cov.get("automated_ratio"),
                    "planner": (item.get("planner") or {}).get(
                        "next_scenario_id"
                    ),
                    "kind": item.get("kind") or "house",
                    "target_game": item.get("target_game") or {},
                }
            )
        return out

    def get(self, run_id: str) -> Optional[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_INTEGRITY_TABLE} WHERE id = %s",
                (run_id,),
            )
            row = cur.fetchone()
        return _row_to_integrity(row) if row else None

    def close(self) -> None:
        self.conn.close()


# --- journey_sessions + journey_events -------------------------------------

_SESSIONS_TABLE = "journey_sessions"
_EVENTS_TABLE = "journey_events"

_INSERT_SESSION = f"""
INSERT INTO {_SESSIONS_TABLE}
    (id, label, platform, house_name, house_url,
     scout_mode, status, started_at, ended_at, meta)
VALUES
    (%(id)s, %(label)s, %(platform)s, %(house_name)s,
     %(house_url)s, %(scout_mode)s, %(status)s,
     %(started_at)s, %(ended_at)s, %(meta)s)
ON CONFLICT (id) DO UPDATE SET
    label = EXCLUDED.label,
    platform = EXCLUDED.platform,
    house_name = EXCLUDED.house_name,
    house_url = EXCLUDED.house_url,
    scout_mode = EXCLUDED.scout_mode,
    status = EXCLUDED.status,
    started_at = EXCLUDED.started_at,
    ended_at = EXCLUDED.ended_at,
    meta = EXCLUDED.meta
"""

_INSERT_EVENT = f"""
INSERT INTO {_EVENTS_TABLE}
    (id, session_id, step, kind, level, message, detail,
     created_at, seq)
VALUES
    (%(id)s, %(session_id)s, %(step)s, %(kind)s, %(level)s,
     %(message)s, %(detail)s, %(created_at)s, %(seq)s)
ON CONFLICT (id) DO UPDATE SET
    session_id = EXCLUDED.session_id,
    step = EXCLUDED.step,
    kind = EXCLUDED.kind,
    level = EXCLUDED.level,
    message = EXCLUDED.message,
    detail = EXCLUDED.detail,
    created_at = EXCLUDED.created_at,
    seq = EXCLUDED.seq
"""

_SESSION_KEYS = (
    "id", "label", "platform", "house_name", "house_url",
    "scout_mode", "status", "started_at", "ended_at", "meta",
)

_EVENT_KEYS = (
    "id", "session_id", "step", "kind", "level", "message",
    "detail", "created_at", "seq",
)


def _session_params(session) -> dict[str, object]:
    data = session.model_dump(mode="json")
    data["meta"] = json.dumps(
        data.get("meta") or {}, ensure_ascii=False
    )
    return data


def _row_to_session(row: tuple):
    from src.notify.journey_session import JourneySession

    data = dict(zip(_SESSION_KEYS, row))
    data["meta"] = (
        json.loads(data["meta"])
        if isinstance(data["meta"], str)
        else (data["meta"] or {})
    )
    return JourneySession.model_validate(data)


def _event_params(event, session_id: str, seq: int) -> dict[str, object]:
    data = event.model_dump(mode="json")
    data["session_id"] = session_id
    data["seq"] = seq
    data["detail"] = json.dumps(
        data.get("detail") or {}, ensure_ascii=False
    )
    return data


def _row_to_event(row: tuple):
    from src.notify.journey_session import JourneyLogEvent

    data = dict(zip(_EVENT_KEYS, row))
    data["detail"] = (
        json.loads(data["detail"])
        if isinstance(data["detail"], str)
        else (data["detail"] or {})
    )
    return JourneyLogEvent.model_validate(data)


class PostgresJourneySessionStore:
    """Postgres persistence mirroring JourneySessionStore."""

    def __init__(self, dsn: str, conn: Optional[object] = None,
                 max_sessions: int = 100, max_events: int = 2000):
        self.dsn = dsn
        if conn is None:
            conn = _connect(dsn)
        self.conn = conn
        self.max_sessions = max_sessions
        self.max_events = max_events

    def _fetch_events(self, session_id: str) -> list:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_EVENTS_TABLE} "
                "WHERE session_id = %s ORDER BY seq DESC",
                (session_id,),
            )
            rows = cur.fetchall()
        return [_row_to_event(r) for r in rows]

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_SESSIONS_TABLE} "
                "ORDER BY started_at DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
        out = []
        for row in rows:
            session = _row_to_session(row)
            events = self._fetch_events(session.id)
            out.append(
                {
                    "id": session.id,
                    "label": session.label,
                    "platform": session.platform,
                    "house_name": session.house_name,
                    "house_url": session.house_url,
                    "scout_mode": session.scout_mode,
                    "status": session.status,
                    "started_at": session.started_at.isoformat(),
                    "ended_at": (
                        session.ended_at.isoformat()
                        if session.ended_at
                        else None
                    ),
                    "event_count": len(events),
                    "last_message": events[0].message
                    if events
                    else "",
                    "last_level": events[0].level
                    if events
                    else "info",
                    "meta": session.meta,
                }
            )
        return out

    def get(self, session_id: str):
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_SESSIONS_TABLE} WHERE id = %s",
                (session_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        session = _row_to_session(row)
        session.events = self._fetch_events(session_id)
        return session

    def active(self):
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_SESSIONS_TABLE} "
                "WHERE status = 'active' ORDER BY started_at DESC"
            )
            row = cur.fetchone()
        if not row:
            return None
        session = _row_to_session(row)
        session.events = self._fetch_events(session.id)
        return session

    def start(
        self,
        *,
        platform: str,
        house_name: str = "",
        house_url: str = "",
        scout_mode: str = "",
        label: str = "",
        meta: Optional[dict[str, Any]] = None,
        close_previous: bool = True,
    ):
        from src.notify.journey_session import (
            JourneyLogEvent,
            JourneySession,
            _utcnow,
        )

        if close_previous:
            active = self.active()
            if active:
                active.status = "closed"
                active.ended_at = _utcnow()
                active.events.insert(
                    0,
                    JourneyLogEvent(
                        step="system",
                        kind="session.auto_close",
                        level="warn",
                        message=(
                            "Sessão anterior fechada ao iniciar nova "
                            "jornada"
                        ),
                        detail={"reason": "new_session"},
                    ),
                )
                self._save_session(active)
                self._save_events(active.id, active.events)

        session = JourneySession(
            label=label
            or f"{house_name or platform or 'jornada'} · "
            f"{_utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            platform=platform,
            house_name=house_name,
            house_url=house_url,
            scout_mode=scout_mode,
            meta=meta or {},
            events=[
                JourneyLogEvent(
                    step="system",
                    kind="session.start",
                    level="success",
                    message=(
                        f"Sessão de logs iniciada · "
                        f"{house_name or platform}"
                    ),
                    detail={
                        "platform": platform,
                        "house_name": house_name,
                        "house_url": house_url,
                        "scout_mode": scout_mode,
                        **(meta or {}),
                    },
                )
            ],
        )
        self._save_session(session)
        self._save_events(session.id, session.events)
        return session

    def _save_session(self, session) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                _INSERT_SESSION, _session_params(session)
            )
        self.conn.commit()

    def _save_events(self, session_id: str, events: list) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {_EVENTS_TABLE} "
                "WHERE session_id = %s",
                (session_id,),
            )
            for idx, event in enumerate(events):
                cur.execute(
                    _INSERT_EVENT,
                    _event_params(event, session_id, idx),
                )
        self.conn.commit()

    def append(
        self,
        session_id: str,
        *,
        kind: str,
        message: str,
        step: str = "",
        level: str = "info",
        detail: Optional[dict[str, Any]] = None,
    ):
        from src.notify.journey_session import JourneyLogEvent

        session = self.get(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id}")
        event = JourneyLogEvent(
            step=step,
            kind=kind,
            level=level,
            message=message,
            detail=detail or {},
        )
        session.events.insert(0, event)
        if len(session.events) > self.max_events:
            session.events = session.events[: self.max_events]
        self._save_events(session_id, session.events)
        return event

    def close(self, session_id: str, note: str = ""):
        from src.notify.journey_session import JourneyLogEvent, _utcnow

        session = self.get(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id}")
        if session.status != "closed":
            session.status = "closed"
            session.ended_at = _utcnow()
            session.events.insert(
                0,
                JourneyLogEvent(
                    step="system",
                    kind="session.close",
                    level="info",
                    message=note or "Sessão de logs encerrada",
                    detail={"note": note},
                ),
            )
        self._save_session(session)
        self._save_events(session_id, session.events)
        return session

    def delete(self, session_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {_SESSIONS_TABLE} WHERE id = %s",
                (session_id,),
            )
            deleted = cur.rowcount > 0
        self.conn.commit()
        return deleted

    def clear(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {_SESSIONS_TABLE}")
            count = cur.fetchone()[0]
            cur.execute(f"DELETE FROM {_SESSIONS_TABLE}")
        self.conn.commit()
        return count

    def close(self) -> None:
        self.conn.close()


# --- house_profiles --------------------------------------------------------

_PROFILES_TABLE = "house_profiles"

_INSERT_PROFILE = f"""
INSERT INTO {_PROFILES_TABLE}
    (platform, generated_at, payload)
VALUES
    (%(platform)s, %(generated_at)s, %(payload)s)
ON CONFLICT (platform) DO UPDATE SET
    generated_at = EXCLUDED.generated_at,
    payload = EXCLUDED.payload
"""


def _profile_params(platform: str, generated_at, payload: dict) -> dict:
    return {
        "platform": platform,
        "generated_at": generated_at,
        "payload": json.dumps(payload, ensure_ascii=False),
    }


def _row_to_profile(row: tuple) -> dict:
    payload = row[2]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return {
        "platform": row[0],
        "generated_at": row[1].isoformat() if row[1] else None,
        "payload": payload or {},
    }


class PostgresHouseProfileStore:
    """Postgres persistence for HouseRecon profiles."""

    def __init__(self, dsn: str, conn: Optional[object] = None):
        self.dsn = dsn
        if conn is None:
            conn = _connect(dsn)
        self.conn = conn

    def get(self, platform: str) -> Optional[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_PROFILES_TABLE} WHERE platform = %s",
                (platform,),
            )
            row = cur.fetchone()
        return _row_to_profile(row) if row else None

    def save(
        self, platform: str, generated_at, payload: dict
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                _INSERT_PROFILE,
                _profile_params(platform, generated_at, payload),
            )
        self.conn.commit()

    def list(self) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_PROFILES_TABLE} "
                "ORDER BY generated_at DESC"
            )
            rows = cur.fetchall()
        return [_row_to_profile(r) for r in rows]

    def delete(self, platform: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {_PROFILES_TABLE} WHERE platform = %s",
                (platform,),
            )
            deleted = cur.rowcount > 0
        self.conn.commit()
        return deleted

    def clear(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {_PROFILES_TABLE}")
            count = cur.fetchone()[0]
            cur.execute(f"DELETE FROM {_PROFILES_TABLE}")
        self.conn.commit()
        return count

    def close(self) -> None:
        self.conn.close()


# --- RedisCache ------------------------------------------------------------


class RedisCache:
    """Generic Redis cache with TTL support."""

    def __init__(self, url: str, key_prefix: str = "betbonus"):
        import redis

        self.client = redis.Redis.from_url(
            url, decode_responses=True
        )
        self.key_prefix = key_prefix

    def _key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def get(self, key: str) -> Optional[str]:
        return self.client.get(self._key(key))

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        if ttl:
            self.client.setex(self._key(key), ttl, value)
        else:
            self.client.set(self._key(key), value)

    def delete(self, key: str) -> bool:
        return self.client.delete(self._key(key)) > 0

    def clear(self) -> int:
        count = 0
        for k in self.client.scan_iter(
            pattern=f"{self.key_prefix}:*"
        ):
            self.client.delete(k)
            count += 1
        return count

    def set_offer(self, offer: BonusOffer, ttl: int = 300) -> None:
        self.set(
            f"offer:{offer.id}",
            json.dumps(offer.model_dump(mode="json"), ensure_ascii=False),
            ttl,
        )

    def get_offer(self, offer_id: str) -> Optional[BonusOffer]:
        raw = self.get(f"offer:{offer_id}")
        if raw is None:
            return None
        return BonusOffer.model_validate(
            json.loads(raw)
        )

    def delete_offer(self, offer_id: str) -> bool:
        return self.delete(f"offer:{offer_id}")

    def close(self) -> None:
        self.client.close()


# --- Factory functions -----------------------------------------------------


def make_store(path: Path) -> object:
    """Return PostgresBonusStore if BETBONUS_DATABASE_URL is set, else Json."""
    dsn = database_url()
    if dsn:
        try:
            return PostgresBonusStore(dsn)
        except Exception:
            pass
    return JsonBonusStore(path)


def make_wallet(path: Path) -> object:
    """Return PostgresWalletLedger if BETBONUS_DATABASE_URL is set, else JSON."""
    from src.storage.wallet import WalletLedger

    dsn = database_url()
    if dsn:
        try:
            return PostgresWalletLedger(dsn)
        except Exception:
            pass
    return WalletLedger(path)


def make_findings(path: Path) -> object:
    """Return PostgresAbuseFindingStore if DB set, else JSON."""
    from src.abuse.store import AbuseFindingStore

    dsn = database_url()
    if dsn:
        try:
            return PostgresAbuseFindingStore(dsn)
        except Exception:
            pass
    return AbuseFindingStore(path)


def make_integrity(path: Path) -> object:
    """Return PostgresIntegrityRunStore if DB set, else JSON."""
    from src.integrity.store import IntegrityRunStore

    dsn = database_url()
    if dsn:
        try:
            return PostgresIntegrityRunStore(dsn)
        except Exception:
            pass
    return IntegrityRunStore(path)


def make_journey_sessions(
    path: Path, max_sessions: int = 100, max_events: int = 2000
) -> object:
    """Return PostgresJourneySessionStore if DB set, else JSON."""
    from src.notify.journey_session import JourneySessionStore

    dsn = database_url()
    if dsn:
        try:
            return PostgresJourneySessionStore(
                dsn, max_sessions=max_sessions, max_events=max_events
            )
        except Exception:
            pass
    return JourneySessionStore(
        path, max_sessions=max_sessions, max_events=max_events
    )


def make_house_profiles(path: Path) -> object:
    """Return PostgresHouseProfileStore if DB set, else JSON."""
    dsn = database_url()
    if dsn:
        try:
            return PostgresHouseProfileStore(dsn)
        except Exception:
            pass
    return None


def make_redis() -> Optional[RedisCache]:
    """Return RedisCache if BETBONUS_REDIS_URL is set, else None."""
    url = redis_url()
    if not url:
        return None
    try:
        return RedisCache(url)
    except Exception:
        return None
