#!/usr/bin/env python3
"""Migrate JSON data files to Postgres.

Usage:
    python scripts/migrate_json_to_postgres.py [--dry-run]

Requires BETBONUS_DATABASE_URL to be set.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def _load_json(path: Path) -> list | dict:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8") or "[]"
    data = json.loads(raw)
    return data if isinstance(data, list) else []


def migrate_bonuses(dsn: str, dry_run: bool = False) -> int:
    from src.storage.db import PostgresBonusStore, _SCHEMA
    import psycopg

    path = DATA_DIR / "bonuses.json"
    items = _load_json(path)
    if not items:
        print(f"  bonuses: no data to migrate")
        return 0

    if dry_run:
        print(f"  bonuses: {len(items)} items (dry run)")
        return len(items)

    conn = psycopg.connect(dsn, autocommit=False)
    with conn.cursor() as cur:
        cur.execute(_SCHEMA)
    conn.commit()

    store = PostgresBonusStore(dsn, conn=conn)
    from src.models.bonus import BonusOffer

    offers = [BonusOffer.model_validate(item) for item in items]
    store.save(offers)
    store.close()
    print(f"  bonuses: {len(offers)} migrated")
    return len(offers)


def migrate_wallet(dsn: str, dry_run: bool = False) -> int:
    from src.storage.db import PostgresWalletLedger
    import psycopg

    path = DATA_DIR / "wallet.json"
    items = _load_json(path)
    if not items:
        print(f"  wallet: no data to migrate")
        return 0

    if dry_run:
        print(f"  wallet: {len(items)} items (dry run)")
        return len(items)

    conn = psycopg.connect(dsn, autocommit=False)
    store = PostgresWalletLedger(dsn, conn=conn)
    from src.storage.wallet import WalletCredit

    credits = [WalletCredit.model_validate(item) for item in items]
    store.save(credits)
    store.close()
    print(f"  wallet: {len(credits)} migrated")
    return len(credits)


def migrate_findings(dsn: str, dry_run: bool = False) -> int:
    from src.storage.db import PostgresAbuseFindingStore
    import psycopg

    path = DATA_DIR / "abuse_findings.json"
    items = _load_json(path)
    if not items:
        print(f"  findings: no data to migrate")
        return 0

    if dry_run:
        print(f"  findings: {len(items)} items (dry run)")
        return len(items)

    conn = psycopg.connect(dsn, autocommit=False)
    store = PostgresAbuseFindingStore(dsn, conn=conn)
    from src.models.abuse import AbuseFinding

    findings = [AbuseFinding.model_validate(item) for item in items]
    store.save(findings)
    store.close()
    print(f"  findings: {len(findings)} migrated")
    return len(findings)


def migrate_integrity(dsn: str, dry_run: bool = False) -> int:
    from src.storage.db import PostgresIntegrityRunStore
    import psycopg

    path = DATA_DIR / "integrity_runs.json"
    items = _load_json(path)
    if not items:
        print(f"  integrity: no data to migrate")
        return 0

    if dry_run:
        print(f"  integrity: {len(items)} items (dry run)")
        return len(items)

    conn = psycopg.connect(dsn, autocommit=False)
    store = PostgresIntegrityRunStore(dsn, conn=conn)
    store.save(items)
    store.close()
    print(f"  integrity: {len(items)} migrated")
    return len(items)


def migrate_journey(dsn: str, dry_run: bool = False) -> int:
    from src.storage.db import PostgresJourneySessionStore
    import psycopg

    path = DATA_DIR / "journey_sessions.json"
    items = _load_json(path)
    if not items:
        print(f"  journey: no data to migrate")
        return 0

    if dry_run:
        print(f"  journey: {len(items)} sessions (dry run)")
        return len(items)

    conn = psycopg.connect(dsn, autocommit=False)
    store = PostgresJourneySessionStore(dsn, conn=conn)
    from src.notify.journey_session import JourneySession

    for item in items:
        session = JourneySession.model_validate(item)
        store._save_session(session)
        if session.events:
            store._save_events(session.id, session.events)

    store.close()
    print(f"  journey: {len(items)} sessions migrated")
    return len(items)


def main() -> int:
    import os

    dsn = (os.environ.get("BETBONUS_DATABASE_URL") or "").strip()
    if not dsn:
        print("Error: BETBONUS_DATABASE_URL is not set")
        return 1

    dry_run = "--dry-run" in sys.argv

    print(f"Migrating JSON → Postgres (dry_run={dry_run})")
    print(f"  DSN: {dsn.split('@')[-1] if '@' in dsn else dsn}")

    total = 0
    total += migrate_bonuses(dsn, dry_run)
    total += migrate_wallet(dsn, dry_run)
    total += migrate_findings(dsn, dry_run)
    total += migrate_integrity(dsn, dry_run)
    total += migrate_journey(dsn, dry_run)

    print(f"\nTotal: {total} items migrated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
