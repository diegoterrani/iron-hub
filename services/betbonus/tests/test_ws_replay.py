"""Tests for WSReplayClient and WSCapture (Phase 1)."""

from __future__ import annotations

import pytest

from src.integrity.ws_replay import WSMessage, WSCapture, WSReplayClient


# --- WSMessage ---

def test_ws_message_to_dict():
    msg = WSMessage(
        direction="in",
        payload={"action": "spin", "stake": 1.0},
        timestamp=1000.0,
        ws_url="wss://example.com/ws",
    )
    d = msg.to_dict()
    assert d["direction"] == "in"
    assert d["payload"]["action"] == "spin"
    assert d["timestamp"] == 1000.0
    assert d["ws_url"] == "wss://example.com/ws"


# --- WSCapture ---

def _make_capture():
    msgs = [
        WSMessage(direction="in", payload={"token": "tok-abc-12345"}, timestamp=1.0, ws_url="wss://e.com"),
        WSMessage(direction="in", payload={"sessionId": "sess-1", "gameId": "g-1"}, timestamp=2.0, ws_url="wss://e.com"),
        WSMessage(direction="out", payload={"action": "spin", "stake": 1.0}, timestamp=3.0, ws_url="wss://e.com"),
        WSMessage(direction="in", payload={"type": "result", "win": 5.0}, timestamp=4.0, ws_url="wss://e.com"),
    ]
    return WSCapture(ws_url="wss://example.com/game", messages=msgs, headers={"Authorization": "tok-abc"})


def test_capture_extract_auth_token():
    cap = _make_capture()
    assert cap.extract_auth_token() == "tok-abc"


def test_capture_extract_game_session():
    cap = _make_capture()
    session = cap.extract_game_session()
    assert session.get("session_id") == "sess-1"
    assert session.get("game_id") == "g-1"


def test_capture_identify_stake_field():
    cap = _make_capture()
    field = cap._identify_stake_field({"stake": 1.0, "action": "spin"})
    assert field == "stake"


def test_capture_identify_stake_field_bet():
    cap = _make_capture()
    assert cap._identify_stake_field({"betAmount": 2.0}) == "betAmount"
    assert cap._identify_stake_field({"bet": 3.0}) == "bet"


def test_capture_extract_spin_schema():
    cap = _make_capture()
    schema = cap.extract_spin_schema()
    assert schema["stake_field"] == "stake"
    assert schema["template"]["action"] == "spin"


def test_capture_build_replay_client():
    cap = _make_capture()
    client = cap.build_replay_client()
    assert isinstance(client, WSReplayClient)
    assert client.ws_url == "wss://example.com/game"
    assert client.auth_token == "tok-abc"


def test_capture_to_dict_roundtrip():
    cap = _make_capture()
    d = cap.to_dict()
    assert d["ws_url"] == "wss://example.com/game"
    assert d["message_count"] == 4
    restored = WSCapture.from_dict(d)
    assert restored.ws_url == cap.ws_url
    assert len(restored.messages) == 4
    assert restored.messages[0].direction == "in"
    assert restored.headers == cap.headers


def test_capture_empty():
    cap = WSCapture(ws_url="wss://example.com", messages=[])
    assert cap.extract_auth_token() is None
    assert cap.extract_game_session() == {}
    assert cap.extract_spin_schema() == {}


# --- WSReplayClient ---

def test_client_not_connected_spin():
    client = WSReplayClient(
        ws_url="wss://e.com", auth_token="tok",
        game_session={}, spin_template={"action": "spin"},
    )
    result = client.send_spin(1.0)
    assert result["ok"] is False
    assert result["error"] == "not_connected"


def test_client_session_stats():
    client = WSReplayClient(
        ws_url="wss://e.com", auth_token="tok",
        game_session={}, spin_template={"action": "spin"},
    )
    stats = client.session_stats()
    assert stats["spins_sent"] == 0
    assert stats["connected"] is False
    assert stats["ws_url"] == "wss://e.com"


def test_client_send_spin_connected():
    client = WSReplayClient(
        ws_url="wss://e.com", auth_token="tok",
        game_session={}, spin_template={"action": "spin", "stake": 0.0},
        stake_field="stake",
    )
    client._connected = True

    class _FakeWS:
        def __init__(self):
            self.sent = []
        def send(self, raw):
            self.sent.append(raw)
        def close(self):
            pass
    client._ws = _FakeWS()
    client._last_response = '{"win": 10}'

    result = client.send_spin(2.0)
    assert result["ok"] is True
    assert result["stake"] == 2.0
    assert client._ws.sent[0].__contains__('"stake": 2.0')
    assert client.session_stats()["spins_sent"] == 1


def test_client_close():
    client = WSReplayClient(
        ws_url="wss://e.com", auth_token="tok",
        game_session={}, spin_template={},
    )
    client._connected = True
    client.close()
    assert client._connected is False
