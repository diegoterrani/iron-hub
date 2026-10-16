"""
WebSocket protocol replay for game spin automation.

Captures WS handshake + message schema from a live Chromium session,
then replays N spins via a standalone WS client. No browser in the loop
after initial capture.

Supports: Spribe SmartFox, Pragmatic gs2c, Patagonia.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class WSMessage:
    """Single WebSocket message captured during a live session."""

    direction: str  # "in" (server→client) | "out" (client→server)
    payload: dict[str, Any]
    timestamp: float
    ws_url: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WSCapture:
    """
    Captured WebSocket session: handshake info + ordered messages.

    Use `extract_*` methods to derive replay parameters, or
    `build_replay_client()` to get a ready-to-fire client.
    """

    ws_url: str
    messages: list[WSMessage] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    captured_at: float = field(default_factory=time.time)

    def extract_auth_token(self) -> Optional[str]:
        """Look for auth token in handshake headers or first messages."""
        # Check headers first
        for key in ("authorization", "x-auth-token", "token", "session-token"):
            val = self.headers.get(key) or self.headers.get(key.capitalize())
            if val:
                # Strip "Bearer " prefix if present
                return val.replace("Bearer ", "").strip()

        # Check first 10 messages for token-like fields
        for msg in self.messages[:10]:
            payload = msg.payload
            for key in ("token", "authToken", "sessionToken", "accessToken", "jwt"):
                if key in payload and isinstance(payload[key], str) and len(payload[key]) > 10:
                    return payload[key]
            # Nested: payload.data.token
            data = payload.get("data")
            if isinstance(data, dict):
                for key in ("token", "authToken", "sessionToken"):
                    if key in data and isinstance(data[key], str) and len(data[key]) > 10:
                        return data[key]
        return None

    def extract_game_session(self) -> dict[str, Any]:
        """Extract session ID, game ID, player ID from captured messages."""
        session: dict[str, Any] = {}
        for msg in self.messages:
            p = msg.payload
            # Common keys across Spribe, Pragmatic, Patagonia
            if "sessionId" in p:
                session["session_id"] = p["sessionId"]
            if "gameId" in p or "game_id" in p:
                session["game_id"] = p.get("gameId") or p.get("game_id")
            if "playerId" in p or "player_id" in p or "userId" in p:
                session["player_id"] = p.get("playerId") or p.get("player_id") or p.get("userId")
            # Pragmatic gs2c style
            if "gameSession" in p and isinstance(p["gameSession"], dict):
                session.setdefault("session_id", p["gameSession"].get("id"))
                session.setdefault("game_id", p["gameSession"].get("gameId"))
            # Spribe SmartFox style
            if "gameId" in p and "roundId" in p:
                session.setdefault("game_id", p["gameId"])
                session["round_id"] = p["roundId"]
            # Patagonia style
            if "player" in p and isinstance(p["player"], dict):
                session.setdefault("player_id", p["player"].get("id"))
            if "game" in p and isinstance(p["game"], dict):
                session.setdefault("game_id", p["game"].get("id"))
            # Early exit if we have the essentials
            if session.get("session_id") and session.get("game_id"):
                break
        return session

    def extract_spin_schema(self) -> dict[str, Any]:
        """
        Find the spin/bet message pattern.

        Looks for outbound messages containing keys like "spin", "bet",
        "stake", "action", "round" to identify the spin command template.
        """
        spin_keys = {"spin", "bet", "stake", "action", "round", "placeBet", "betAmount"}

        # First pass: find messages that look like spin commands
        candidates: list[dict[str, Any]] = []
        for msg in self.messages:
            if msg.direction != "out":
                continue
            p = msg.payload
            keys_lower = {k.lower() for k in p.keys()}
            overlap = keys_lower & {k.lower() for k in spin_keys}
            if len(overlap) >= 2:
                candidates.append(p)

        # Also check nested "action" objects
        for msg in self.messages:
            if msg.direction != "out":
                continue
            p = msg.payload
            action = p.get("action") or p.get("cmd") or p.get("command")
            if isinstance(action, dict):
                akeys = {k.lower() for k in action.keys()}
                if akeys & {k.lower() for k in spin_keys}:
                    candidates.append(action)

        if not candidates:
            return {}

        # Use the most recent candidate (likely the last spin before capture)
        template = candidates[-1]
        # Identify the stake field
        stake_field = self._identify_stake_field(template)
        return {
            "template": template,
            "stake_field": stake_field,
            "source_msg_index": len(self.messages) - 1,
            "all_candidates": len(candidates),
        }

    def _identify_stake_field(self, payload: dict[str, Any]) -> str:
        """Identify which field holds the stake/bet amount."""
        priority = ["stake", "betAmount", "bet_amount", "amount", "bet", "wager"]
        for key in priority:
            if key in payload:
                return key
        # Fallback: find a numeric field that looks like a bet
        for k, v in payload.items():
            if isinstance(v, (int, float)) and v > 0 and "amount" in k.lower():
                return k
        return "stake"

    def build_replay_client(self) -> "WSReplayClient":
        """Create a WSReplayClient pre-loaded with captured session data."""
        auth_token = self.extract_auth_token() or ""
        game_session = self.extract_game_session()
        spin_schema = self.extract_spin_schema()
        template = spin_schema.get("template", {})
        stake_field = spin_schema.get("stake_field", "stake")
        return WSReplayClient(
            ws_url=self.ws_url,
            auth_token=auth_token,
            game_session=game_session,
            spin_template=template,
            stake_field=stake_field,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize for persistence (JSON-safe)."""
        return {
            "ws_url": self.ws_url,
            "headers": self.headers,
            "captured_at": self.captured_at,
            "message_count": len(self.messages),
            "messages": [m.to_dict() for m in self.messages[:200]],
            "auth_token": self.extract_auth_token(),
            "game_session": self.extract_game_session(),
            "spin_schema": self.extract_spin_schema(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WSCapture":
        """Deserialize from a persisted dict."""
        messages = [
            WSMessage(
                direction=m["direction"],
                payload=m["payload"],
                timestamp=m["timestamp"],
                ws_url=m["ws_url"],
            )
            for m in data.get("messages", [])
        ]
        return cls(
            ws_url=data["ws_url"],
            messages=messages,
            headers=data.get("headers", {}),
            captured_at=data.get("captured_at", 0.0),
        )

    @staticmethod
    def capture_from_playwright(page: Any, timeout_ms: int = 30_000) -> Optional["WSCapture"]:
        """
        Hook into a Playwright page to capture WS traffic.

        Listens for `websocket` events on the page, collects messages
        until the WS closes or timeout. Returns the first captured WSCapture.
        """
        captures: list[WSCapture] = []
        current: dict[str, Any] = {}

        def on_websocket(ws: Any) -> None:
            cap = WSCapture(ws_url=str(ws.url))
            captures.append(cap)

            def on_message(event: Any) -> None:
                try:
                    raw = event.data
                    payload = json.loads(raw) if isinstance(raw, str) else {"raw": str(raw)[:500]}
                except (json.JSONDecodeError, TypeError):
                    payload = {"raw": str(raw)[:500]}
                cap.messages.append(
                    WSMessage(
                        direction="in",
                        payload=payload,
                        timestamp=time.time(),
                        ws_url=str(ws.url),
                    )
                )

            def on_frame_sent(event: Any) -> None:
                try:
                    raw = event.payload
                    payload = json.loads(raw) if isinstance(raw, (str, bytes)) else {"raw": str(raw)[:500]}
                except (json.JSONDecodeError, TypeError):
                    payload = {"raw": str(raw)[:500]}
                cap.messages.append(
                    WSMessage(
                        direction="out",
                        payload=payload,
                        timestamp=time.time(),
                        ws_url=str(ws.url),
                    )
                )

            ws.on("framereceived", on_message)
            ws.on("framesent", on_frame_sent)

        page.on("websocket", on_websocket)
        time.sleep(timeout_ms / 1000.0)

        if captures:
            return captures[0]
        return None


class WSReplayClient:
    """
    Standalone WebSocket client that replays spin commands without a browser.

    Uses `websocket-client` (sync) if available, falls back to `websockets`
    (async, run in a thread).
    """

    def __init__(
        self,
        ws_url: str,
        auth_token: str,
        game_session: dict[str, Any],
        spin_template: dict[str, Any],
        stake_field: str = "stake",
    ) -> None:
        self.ws_url = ws_url
        self.auth_token = auth_token
        self.game_session = game_session
        self.spin_template = spin_template
        self.stake_field = stake_field
        self._ws: Any = None
        self._connected = False
        self._stats: dict[str, Any] = {
            "spins_sent": 0,
            "responses_received": 0,
            "errors": 0,
            "connected_at": 0.0,
        }

    def connect(self) -> bool:
        """Open WebSocket connection. Returns True on success."""
        try:
            import websocket  # websocket-client (sync)
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            self._ws = websocket.WebSocketApp(
                self.ws_url,
                header=headers,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            # Run in a daemon thread for background reads
            import threading
            self._thread = threading.Thread(target=self._ws.run_forever, daemon=True)
            self._thread.start()
            # Wait for connection
            for _ in range(50):
                if self._connected:
                    break
                time.sleep(0.1)
            self._stats["connected_at"] = time.time()
            return self._connected
        except ImportError:
            pass
        except Exception:  # noqa: BLE001
            self._stats["errors"] += 1
            return False

        # Fallback: websockets (async)
        try:
            import asyncio
            import websockets  # type: ignore

            self._loop = asyncio.new_event_loop()

            async def _connect() -> None:
                extra_headers = {}
                if self.auth_token:
                    extra_headers["Authorization"] = f"Bearer {self.auth_token}"
                self._ws = await websockets.connect(self.ws_url, extra_headers=extra_headers)
                self._connected = True
                # Start background reader
                asyncio.ensure_future(self._read_loop())

            self._loop.run_until_complete(_connect())
            self._stats["connected_at"] = time.time()
            return self._connected
        except Exception:  # noqa: BLE001
            self._stats["errors"] += 1
            return False

    def _on_open(self, ws: Any) -> None:
        self._connected = True
        # Send initial session handshake if we have one
        if self.game_session:
            handshake = {
                "action": "join",
                "sessionId": self.game_session.get("session_id"),
                "gameId": self.game_session.get("game_id"),
            }
            ws.send(json.dumps(handshake))

    def _on_message(self, ws: Any, data: Any) -> None:
        self._stats["responses_received"] += 1
        self._last_response = data

    def _on_error(self, ws: Any, error: Any) -> None:
        self._stats["errors"] += 1
        self._last_error = str(error)[:200]

    def _on_close(self, ws: Any, close_status: Any, msg: Any) -> None:
        self._connected = False

    async def _read_loop(self) -> None:
        try:
            async for msg in self._ws:
                self._stats["responses_received"] += 1
                self._last_response = msg
        except Exception:  # noqa: BLE001
            self._connected = False

    def send_spin(self, stake: float) -> dict[str, Any]:
        """Send one spin with the given stake. Returns response or error."""
        if not self._connected:
            return {"ok": False, "error": "not_connected"}

        msg = dict(self.spin_template)
        msg[self.stake_field] = stake
        raw = json.dumps(msg)

        try:
            self._ws.send(raw)
            self._stats["spins_sent"] += 1
        except Exception as exc:  # noqa: BLE001
            self._stats["errors"] += 1
            return {"ok": False, "error": str(exc)[:200]}

        # Read response
        resp = self.read_response()
        return {"ok": True, "stake": stake, "response": resp}

    def send_batch(self, stakes: list[float], delay_ms: int = 500) -> list[dict[str, Any]]:
        """Send N spins with delay between each. Returns list of results."""
        results: list[dict[str, Any]] = []
        for stake in stakes:
            results.append(self.send_spin(stake))
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
        return results

    def read_response(self, timeout: float = 5.0) -> dict[str, Any]:
        """Read next WS response. Returns parsed dict or error marker."""
        start = time.time()
        while time.time() - start < timeout:
            if hasattr(self, "_last_response") and self._last_response is not None:
                raw = self._last_response
                self._last_response = None  # consume
                try:
                    return json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                except (json.JSONDecodeError, TypeError):
                    return {"raw": str(raw)[:300]}
            time.sleep(0.05)
        return {"timeout": True}

    def close(self) -> None:
        """Close the WebSocket connection."""
        self._connected = False
        try:
            if self._ws:
                self._ws.close()
        except Exception:  # noqa: BLE001
            pass

    def session_stats(self) -> dict[str, Any]:
        """Return session statistics."""
        return {
            "spins_sent": self._stats["spins_sent"],
            "responses_received": self._stats["responses_received"],
            "errors": self._stats["errors"],
            "connected": self._connected,
            "ws_url": self.ws_url,
            "uptime_s": round(time.time() - self._stats["connected_at"], 2)
            if self._stats["connected_at"]
            else 0.0,
        }
