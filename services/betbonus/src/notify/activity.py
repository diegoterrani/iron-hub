from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ActivityEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: str
    message: str
    level: str = "info"  # info | success | warn | error
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActivityLog:
    def __init__(self, maxlen: int = 200):
        self._events: deque[ActivityEvent] = deque(maxlen=maxlen)
        self._lock = Lock()

    def add(
        self,
        kind: str,
        message: str,
        level: str = "info",
        meta: Optional[dict[str, Any]] = None,
    ) -> ActivityEvent:
        event = ActivityEvent(kind=kind, message=message, level=level, meta=meta or {})
        with self._lock:
            self._events.appendleft(event)
        return event

    def list(self, limit: int = 50) -> list[ActivityEvent]:
        with self._lock:
            return list(self._events)[:limit]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
