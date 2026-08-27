from pathlib import Path

from src.notify.journey_session import JourneySessionStore


def test_journey_session_lifecycle(tmp_path: Path):
    store = JourneySessionStore(tmp_path / "sessions.json", max_sessions=10)
    session = store.start(
        platform="4play",
        house_name="4Play.game",
        house_url="https://4play.game/promotions",
        scout_mode="live",
    )
    assert session.status == "active"
    assert store.active() is not None

    event = store.append(
        session.id,
        step="scrape",
        kind="scout.result",
        message="3 bônus",
        level="success",
        detail={"count": 3},
    )
    assert event.kind == "scout.result"

    loaded = store.get(session.id)
    assert loaded is not None
    assert loaded.event_count >= 2

    closed = store.close(session.id, note="fim")
    assert closed.status == "closed"
    assert store.active() is None

    summary = store.list(limit=5)
    assert summary[0]["id"] == session.id
    assert summary[0]["event_count"] >= 3
