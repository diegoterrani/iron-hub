from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JourneyLogEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    step: str = ""  # casa | scrape | auth | discover | wallet | abuse | system
    kind: str
    level: str = "info"  # info | success | warn | error | debug
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)


class JourneySession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    label: str = ""
    platform: str = ""
    house_name: str = ""
    house_url: str = ""
    scout_mode: str = ""
    status: str = "active"  # active | closed
    started_at: datetime = Field(default_factory=_utcnow)
    ended_at: Optional[datetime] = None
    meta: dict[str, Any] = Field(default_factory=dict)
    events: list[JourneyLogEvent] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def event_count(self) -> int:
        return len(self.events)


class JourneySessionStore:
    """
    Persistência de sessões de log da jornada BetBonus Red Team.
    Cada sessão agrupa o detalhamento completo Casa → Abuse.
    """

    def __init__(self, path: str | Path, max_sessions: int = 100, max_events: int = 2000):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_sessions = max_sessions
        self.max_events = max_events
        self._lock = Lock()
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict[str, Any]]:
        raw = self.path.read_text(encoding="utf-8") or "[]"
        data = json.loads(raw)
        return data if isinstance(data, list) else []

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self) -> list[JourneySession]:
        return [JourneySession.model_validate(row) for row in self._read()]

    def _save(self, sessions: list[JourneySession]) -> None:
        # newest first, cap history
        sessions = sorted(sessions, key=lambda s: s.started_at, reverse=True)[: self.max_sessions]
        self._write([s.model_dump(mode="json") for s in sessions])

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            sessions = self._load()[:limit]
        return [
            {
                "id": s.id,
                "label": s.label,
                "platform": s.platform,
                "house_name": s.house_name,
                "house_url": s.house_url,
                "scout_mode": s.scout_mode,
                "status": s.status,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "event_count": s.event_count,
                "last_message": s.events[0].message if s.events else "",
                "last_level": s.events[0].level if s.events else "info",
                "meta": s.meta,
            }
            for s in sessions
        ]

    def get(self, session_id: str) -> Optional[JourneySession]:
        with self._lock:
            for session in self._load():
                if session.id == session_id:
                    return session
        return None

    def active(self) -> Optional[JourneySession]:
        with self._lock:
            for session in self._load():
                if session.status == "active":
                    return session
        return None

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
    ) -> JourneySession:
        with self._lock:
            sessions = self._load()
            if close_previous:
                now = _utcnow()
                for session in sessions:
                    if session.status == "active":
                        session.status = "closed"
                        session.ended_at = now
                        session.events.insert(
                            0,
                            JourneyLogEvent(
                                step="system",
                                kind="session.auto_close",
                                level="warn",
                                message="Sessão anterior fechada ao iniciar nova jornada",
                                detail={"reason": "new_session"},
                            ),
                        )

            session = JourneySession(
                label=label
                or f"{house_name or platform or 'jornada'} · {_utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
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
                        message=f"Sessão de logs iniciada · {house_name or platform}",
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
            sessions.insert(0, session)
            self._save(sessions)
            return session

    def append(
        self,
        session_id: str,
        *,
        kind: str,
        message: str,
        step: str = "",
        level: str = "info",
        detail: Optional[dict[str, Any]] = None,
    ) -> JourneyLogEvent:
        with self._lock:
            sessions = self._load()
            for session in sessions:
                if session.id != session_id:
                    continue
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
                self._save(sessions)
                return event
        raise KeyError(f"session not found: {session_id}")

    def close(self, session_id: str, note: str = "") -> JourneySession:
        with self._lock:
            sessions = self._load()
            for session in sessions:
                if session.id != session_id:
                    continue
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
                self._save(sessions)
                return session
        raise KeyError(f"session not found: {session_id}")

    def delete(self, session_id: str) -> bool:
        with self._lock:
            sessions = self._load()
            next_sessions = [s for s in sessions if s.id != session_id]
            if len(next_sessions) == len(sessions):
                return False
            self._save(next_sessions)
            return True

    def clear(self) -> int:
        with self._lock:
            n = len(self._load())
            self._save([])
            return n
