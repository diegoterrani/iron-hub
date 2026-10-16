"""
Temporal event scheduler for staggered multi-account campaigns.

Ensures accounts register, deposit, wager, and withdraw at realistic
times of day, spread over days. No two accounts do the same action
in the same 30-min window.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Event dataclass
# ---------------------------------------------------------------------------

@dataclass
class ScheduledEvent:
    """A single scheduled action for one account."""
    event_id: str
    account_id: str
    action: str              # "register" | "deposit" | "wager" | "withdraw"
    scheduled_at: datetime
    priority: int = 0
    metadata: dict = field(default_factory=dict)
    completed: bool = False


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class TimingScheduler:
    """Staggered temporal event scheduler for multi-account campaigns.

    Parameters:
        timezone: IANA timezone name for local-time windows (default America/Sao_Paulo)
        min_gap_minutes: minimum gap between same-action events for different
                         accounts (default 30 min)
    """

    def __init__(
        self,
        timezone: str = "America/Sao_Paulo",
        min_gap_minutes: int = 30,
        seed: Optional[int] = None,
    ):
        self.tz = ZoneInfo(timezone)
        self.min_gap = timedelta(minutes=min_gap_minutes)
        self.rng = random.Random(seed)
        self._events: list[ScheduledEvent] = []
        self._lock = threading.Lock()
        self._counter = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_event_id(self) -> str:
        self._counter += 1
        return f"evt-{self._counter:06d}"

    def _add(self, event: ScheduledEvent) -> None:
        with self._lock:
            self._events.append(event)

    def _local_hour(self, dt: datetime) -> float:
        """Return the local hour (0-23) of a datetime."""
        return dt.astimezone(self.tz).hour + dt.astimezone(self.tz).minute / 60.0

    def _next_slot_after(
        self,
        base_dt: datetime,
        action: str,
        window_start_hour: Optional[int] = None,
        window_end_hour: Optional[int] = None,
    ) -> datetime:
        """Find the next time >= base_dt that doesn't conflict with existing
        same-action events and (optionally) falls within a local-time window.

        Window is inclusive of start hour, exclusive of end hour. If
        window_end <= window_start, the window wraps overnight.
        """
        candidate = base_dt
        # Nudge forward slightly to avoid exact collisions
        candidate += timedelta(seconds=self.rng.randint(1, 120))

        for _ in range(500):
            # Check window constraint
            if window_start_hour is not None and window_end_hour is not None:
                local_h = self._local_hour(candidate)
                if window_start_hour < window_end_hour:
                    in_window = window_start_hour <= local_h < window_end_hour
                else:
                    # Overnight window
                    in_window = local_h >= window_start_hour or local_h < window_end_hour
                if not in_window:
                    # Advance to next window start
                    candidate = self._advance_to_window_start(
                        candidate, window_start_hour, window_end_hour
                    )
                    continue

            # Check min-gap against existing same-action events
            conflict = False
            with self._lock:
                for other in self._events:
                    if other.action != action or other.completed:
                        continue
                    if abs((candidate - other.scheduled_at).total_seconds()) < self.min_gap.total_seconds():
                        conflict = True
                        break
            if not conflict:
                return candidate

            # Conflict: push forward by min_gap
            candidate += self.min_gap

        return candidate

    def _advance_to_window_start(
        self,
        dt: datetime,
        start_hour: int,
        end_hour: int,
    ) -> datetime:
        """Advance dt to the next moment that enters the [start_hour, end_hour) window."""
        local = dt.astimezone(self.tz)
        local_h = local.hour + local.minute / 60.0

        if start_hour < end_hour:
            # Same-day window
            if local_h < start_hour:
                target = local.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            elif local_h >= end_hour:
                target = (local + timedelta(days=1)).replace(
                    hour=start_hour, minute=0, second=0, microsecond=0
                )
            else:
                return dt  # already in window
        else:
            # Overnight window
            if local_h >= start_hour or local_h < end_hour:
                return dt  # already in window
            target = local.replace(hour=start_hour, minute=0, second=0, microsecond=0)

        return target.astimezone(dt.tzinfo or timezone.utc)

    # ------------------------------------------------------------------
    # Scheduling methods
    # ------------------------------------------------------------------

    def schedule_registration(
        self,
        account_ids: list[str],
        start: Optional[datetime] = None,
    ) -> list[ScheduledEvent]:
        """Stagger registrations 5-15 min apart, weekday 14:00-22:00 local."""
        if start is None:
            start = datetime.now(timezone.utc)

        events: list[ScheduledEvent] = []
        cursor = start
        for aid in account_ids:
            gap = timedelta(minutes=self.rng.randint(5, 15))
            candidate = cursor + gap
            # Ensure weekday (Mon-Fri) 14:00-22:00 local
            candidate = self._force_weekday_window(candidate, 14, 22)
            candidate = self._next_slot_after(candidate, "register")
            evt = ScheduledEvent(
                event_id=self._next_event_id(),
                account_id=aid,
                action="register",
                scheduled_at=candidate,
            )
            self._add(evt)
            events.append(evt)
            cursor = candidate
        return events

    def _force_weekday_window(
        self,
        dt: datetime,
        start_hour: int,
        end_hour: int,
    ) -> datetime:
        """Advance dt to the next weekday within [start_hour, end_hour) local time."""
        local = dt.astimezone(self.tz)
        # Push to next weekday if weekend
        if local.weekday() >= 5:
            days_ahead = (7 - local.weekday()) + 1  # skip to Monday
            local = (local + timedelta(days=days_ahead)).replace(
                hour=start_hour, minute=0, second=0, microsecond=0
            )
        else:
            local_h = local.hour + local.minute / 60.0
            if local_h < start_hour:
                local = local.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            elif local_h >= end_hour:
                local = (local + timedelta(days=1)).replace(
                    hour=start_hour, minute=0, second=0, microsecond=0
                )
        return local.astimezone(dt.tzinfo or timezone.utc)

    def schedule_first_deposit(
        self,
        account_ids: list[str],
        registered_at: dict[str, datetime],
    ) -> list[ScheduledEvent]:
        """Schedule first deposit 1-6 hours after registration."""
        events: list[ScheduledEvent] = []
        for aid in account_ids:
            reg_dt = registered_at.get(aid)
            if reg_dt is None:
                continue
            delay = timedelta(hours=self.rng.uniform(1, 6))
            candidate = reg_dt + delay
            candidate = self._next_slot_after(candidate, "deposit")
            evt = ScheduledEvent(
                event_id=self._next_event_id(),
                account_id=aid,
                action="deposit",
                scheduled_at=candidate,
                metadata={"registered_at": reg_dt.isoformat()},
            )
            self._add(evt)
            events.append(evt)
        events.sort(key=lambda e: e.scheduled_at)
        return events

    def schedule_wagering(
        self,
        account_ids: list[str],
        bonus_activated_at: dict[str, datetime],
    ) -> list[ScheduledEvent]:
        """Schedule wagering 20-72 hours after bonus activation."""
        events: list[ScheduledEvent] = []
        for aid in account_ids:
            act_dt = bonus_activated_at.get(aid)
            if act_dt is None:
                continue
            delay = timedelta(hours=self.rng.uniform(20, 72))
            candidate = act_dt + delay
            candidate = self._next_slot_after(candidate, "wager")
            evt = ScheduledEvent(
                event_id=self._next_event_id(),
                account_id=aid,
                action="wager",
                scheduled_at=candidate,
                metadata={"bonus_activated_at": act_dt.isoformat()},
            )
            self._add(evt)
            events.append(evt)
        events.sort(key=lambda e: e.scheduled_at)
        return events

    def schedule_withdrawal(
        self,
        account_ids: list[str],
        rollover_cleared_at: dict[str, datetime],
    ) -> list[ScheduledEvent]:
        """Schedule withdrawal 24-96 hours after rollover, 10:00-16:00 local.

        No two withdrawals land in the same 30-min window.
        """
        events: list[ScheduledEvent] = []
        for aid in account_ids:
            cleared_dt = rollover_cleared_at.get(aid)
            if cleared_dt is None:
                continue
            delay = timedelta(hours=self.rng.uniform(24, 96))
            candidate = cleared_dt + delay
            candidate = self._next_slot_after(
                candidate, "withdraw", window_start_hour=10, window_end_hour=16
            )
            evt = ScheduledEvent(
                event_id=self._next_event_id(),
                account_id=aid,
                action="withdraw",
                scheduled_at=candidate,
                metadata={"rollover_cleared_at": cleared_dt.isoformat()},
            )
            self._add(evt)
            events.append(evt)
        # Ensure chronological ordering (window forcing can cause reordering)
        events.sort(key=lambda e: e.scheduled_at)
        return events

    # ------------------------------------------------------------------
    # Query / lifecycle
    # ------------------------------------------------------------------

    def pending_events(self) -> list[ScheduledEvent]:
        """All pending (not completed) events, sorted by scheduled_at."""
        with self._lock:
            pending = [e for e in self._events if not e.completed]
        pending.sort(key=lambda e: (e.scheduled_at, -e.priority))
        return pending

    def next_event(self) -> Optional[ScheduledEvent]:
        """Return the next pending event (earliest scheduled_at), or None."""
        pending = self.pending_events()
        return pending[0] if pending else None

    def complete_event(self, event_id: str) -> None:
        """Mark an event as completed."""
        with self._lock:
            for evt in self._events:
                if evt.event_id == event_id:
                    evt.completed = True
                    return

    def cancel_event(self, event_id: str) -> None:
        """Remove an event from the queue entirely."""
        with self._lock:
            self._events = [e for e in self._events if e.event_id != event_id]

    def campaign_timeline(self) -> dict:
        """Summary: total events, first/last event, events per day."""
        with self._lock:
            all_events = list(self._events)

        if not all_events:
            return {
                "total_events": 0,
                "first_event": None,
                "last_event": None,
                "events_per_day": {},
            }

        sorted_events = sorted(all_events, key=lambda e: e.scheduled_at)
        per_day: dict[str, int] = {}
        for evt in sorted_events:
            day_key = evt.scheduled_at.astimezone(self.tz).strftime("%Y-%m-%d")
            per_day[day_key] = per_day.get(day_key, 0) + 1

        return {
            "total_events": len(all_events),
            "first_event": sorted_events[0].scheduled_at.isoformat(),
            "last_event": sorted_events[-1].scheduled_at.isoformat(),
            "events_per_day": per_day,
        }

    def wait_for_next(self, timeout_s: float = 3600) -> Optional[ScheduledEvent]:
        """Block until the next event is due (scheduled_at <= now), then return it.

        Returns None if timeout expires before any event is due.
        """
        deadline = time.monotonic() + timeout_s
        while True:
            nxt = self.next_event()
            if nxt is None:
                return None
            now = datetime.now(timezone.utc)
            if nxt.scheduled_at <= now:
                return nxt
            sleep_s = min(
                (nxt.scheduled_at - now).total_seconds(),
                max(0.0, deadline - time.monotonic()),
            )
            if sleep_s <= 0:
                return None
            time.sleep(sleep_s)
