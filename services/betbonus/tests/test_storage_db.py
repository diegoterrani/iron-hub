from src.models.bonus import BonusOffer
from src.storage import db as db_mod
from src.storage.db import (
    PostgresAbuseFindingStore,
    PostgresBonusStore,
    PostgresHouseProfileStore,
    PostgresIntegrityRunStore,
    PostgresJourneySessionStore,
    PostgresWalletLedger,
    RedisCache,
    make_findings,
    make_house_profiles,
    make_integrity,
    make_journey_sessions,
    make_redis,
    make_store,
    make_wallet,
)
from src.storage.store import JsonBonusStore
from src.storage.wallet import WalletCredit


def _offer(platform: str = "4play", title: str = "Welcome", **kw) -> BonusOffer:
    return BonusOffer(platform=platform, title=title, **kw)


def test_make_store_defaults_to_json(monkeypatch):
    monkeypatch.delenv("BETBONUS_DATABASE_URL", raising=False)
    store = make_store("data/bonuses.json")
    assert isinstance(store, JsonBonusStore)


def test_make_store_returns_postgres_when_configured(monkeypatch):
    fake = object()
    monkeypatch.setenv("BETBONUS_DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setattr(db_mod, "PostgresBonusStore", lambda dsn: fake)
    assert make_store("data/bonuses.json") is fake


def test_make_store_falls_back_on_postgres_error(monkeypatch, tmp_path):
    monkeypatch.setenv("BETBONUS_DATABASE_URL", "postgresql://bad@host/db")

    def _boom(dsn, conn=None):
        raise RuntimeError("no pg")

    monkeypatch.setattr(db_mod, "PostgresBonusStore", _boom)
    store = make_store(tmp_path / "bonuses.json")
    assert isinstance(store, JsonBonusStore)


def _fake_conn(rows: list[tuple]):
    """Minimal psycopg-like fake: cursor with execute/fetchall/fetchone."""
    class _Cursor:
        def __init__(self):
            self.rowcount = 0

        def execute(self, sql, params=None):
            self._sql = sql
            self._params = params
            if sql.strip().upper().startswith("SELECT *"):
                self._result = list(rows)
            elif "count(*)" in sql:
                self._result = [(len(rows),)]
            elif sql.strip().upper().startswith("DELETE"):
                self.rowcount = 1
            else:
                self._result = []

        def fetchall(self):
            return self._result

        def fetchone(self):
            return self._result[0] if self._result else None

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Conn:
        def cursor(self):
            return _Cursor()

        def commit(self):
            pass

        def close(self):
            pass

    return _Conn()


def _row_for(offer: BonusOffer) -> tuple:
    data = offer.model_dump(mode="json")
    return (
        offer.id,
        offer.platform,
        data["bonus_type"],
        offer.title,
        offer.amount,
        offer.currency,
        offer.match_percent,
        offer.free_spins,
        offer.wagering_multiple,
        offer.min_deposit,
        offer.max_bet_during_bonus,
        offer.expiry_days,
        offer.expiry_hours,
        "[]",
        offer.terms_url,
        offer.source_url,
        offer.raw_text,
        data["scraped_at"],
        offer.score,
        data["category"],
        "{}",
    )


def test_postgres_store_roundtrip():
    offer = _offer(amount=100.0, wagering_multiple=25.0)
    row = _row_for(offer)
    store = PostgresBonusStore("postgresql://fake", conn=_fake_conn([row]))

    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].id == offer.id
    assert loaded[0].amount == 100.0
    assert loaded[0].wagering_multiple == 25.0

    got = store.get(offer.id)
    assert got is not None and got.title == "Welcome"
    assert store.delete(offer.id) is True
    assert store.clear() == 1


def test_redis_cache_roundtrip():
    class _FakeRedis:
        def __init__(self):
            self.store = {}

        @classmethod
        def from_url(cls, url, decode_responses=False):
            return cls()

        def set(self, key, value):
            self.store[key] = value

        def setex(self, key, ttl, value):
            self.store[key] = value

        def get(self, key):
            return self.store.get(key)

        def delete(self, *keys):
            n = 0
            for k in keys:
                if k in self.store:
                    del self.store[k]
                    n += 1
            return n

        def scan_iter(self, pattern):
            return iter([k for k in self.store if k.startswith("betbonus:")])

        def close(self):
            pass

    fake = _FakeRedis()
    cache = RedisCache.__new__(RedisCache)
    cache.client = fake
    cache.key_prefix = "betbonus"

    offer = _offer(amount=50.0)
    cache.set_offer(offer)
    got = cache.get_offer(offer.id)
    assert got is not None
    assert got.amount == 50.0
    assert cache.delete_offer(offer.id) is True
    assert cache.get_offer(offer.id) is None
    assert cache.clear() == 0


def test_make_wallet_defaults_to_json(monkeypatch, tmp_path):
    monkeypatch.delenv("BETBONUS_DATABASE_URL", raising=False)
    wallet = make_wallet(tmp_path / "wallet.json")
    from src.storage.wallet import WalletLedger
    assert isinstance(wallet, WalletLedger)


def test_make_wallet_returns_postgres_when_configured(monkeypatch):
    fake = object()
    monkeypatch.setenv("BETBONUS_DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setattr(db_mod, "PostgresWalletLedger", lambda dsn: fake)
    wallet = make_wallet("data/wallet.json")
    assert wallet is fake


def test_make_findings_defaults_to_json(monkeypatch, tmp_path):
    monkeypatch.delenv("BETBONUS_DATABASE_URL", raising=False)
    store = make_findings(tmp_path / "findings.json")
    from src.abuse.store import AbuseFindingStore
    assert isinstance(store, AbuseFindingStore)


def test_make_findings_returns_postgres_when_configured(monkeypatch):
    fake = object()
    monkeypatch.setenv("BETBONUS_DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setattr(db_mod, "PostgresAbuseFindingStore", lambda dsn: fake)
    store = make_findings("data/findings.json")
    assert store is fake


def test_make_integrity_defaults_to_json(monkeypatch, tmp_path):
    monkeypatch.delenv("BETBONUS_DATABASE_URL", raising=False)
    store = make_integrity(tmp_path / "integrity.json")
    from src.integrity.store import IntegrityRunStore
    assert isinstance(store, IntegrityRunStore)


def test_make_integrity_returns_postgres_when_configured(monkeypatch):
    fake = object()
    monkeypatch.setenv("BETBONUS_DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setattr(db_mod, "PostgresIntegrityRunStore", lambda dsn: fake)
    store = make_integrity("data/integrity.json")
    assert store is fake


def test_make_journey_sessions_defaults_to_json(monkeypatch, tmp_path):
    monkeypatch.delenv("BETBONUS_DATABASE_URL", raising=False)
    store = make_journey_sessions(tmp_path / "journey.json")
    from src.notify.journey_session import JourneySessionStore
    assert isinstance(store, JourneySessionStore)


def test_make_journey_sessions_returns_postgres_when_configured(monkeypatch):
    fake = object()
    monkeypatch.setenv("BETBONUS_DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setattr(
        db_mod, "PostgresJourneySessionStore",
        lambda dsn, **kw: fake,
    )
    store = make_journey_sessions("data/journey.json")
    assert store is fake


def test_make_redis_returns_none_when_not_configured(monkeypatch):
    monkeypatch.delenv("BETBONUS_REDIS_URL", raising=False)
    assert make_redis() is None


def test_make_redis_returns_cache_when_configured(monkeypatch):
    fake = object()
    monkeypatch.setenv("BETBONUS_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(db_mod, "RedisCache", lambda url: fake)
    cache = make_redis()
    assert cache is fake


def test_make_house_profiles_returns_none_when_not_configured(monkeypatch):
    monkeypatch.delenv("BETBONUS_DATABASE_URL", raising=False)
    assert make_house_profiles("data/profiles.json") is None


def test_make_house_profiles_returns_postgres_when_configured(monkeypatch):
    fake = object()
    monkeypatch.setenv("BETBONUS_DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setattr(db_mod, "PostgresHouseProfileStore", lambda dsn: fake)
    store = make_house_profiles("data/profiles.json")
    assert store is fake


def _wallet_row(credit: WalletCredit) -> tuple:
    data = credit.model_dump(mode="json")
    return (
        credit.id,
        credit.platform,
        credit.bonus_id,
        credit.title,
        credit.amount,
        credit.currency,
        credit.source,
        credit.status,
        credit.reality,
        credit.note,
        data["created_at"],
    )


def test_postgres_wallet_roundtrip():
    credit = WalletCredit(
        platform="4play",
        title="Test Credit",
        amount=100.0,
        currency="CRC",
    )
    row = _wallet_row(credit)
    store = PostgresWalletLedger("postgresql://fake", conn=_fake_conn([row]))

    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].id == credit.id
    assert loaded[0].amount == 100.0

    summary = store.summary()
    assert summary["total_entries"] == 1
    assert summary["credited"] == 1
    assert summary["totals_by_currency"].get("CRC") == 100.0

    assert store.clear() == 1
