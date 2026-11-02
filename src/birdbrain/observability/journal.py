"""Thread-safe in-memory event journal with replay support."""

from __future__ import annotations

from collections import deque
from threading import Condition
from typing import Any
from uuid import uuid4

from birdbrain.observability.events import EventEnvelope


class EventJournal:
    """Retain a bounded, ordered trace and wake live subscribers."""

    def __init__(self, *, run_id: str | None = None, capacity: int = 10_000) -> None:
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.run_id = run_id or f"sim-{uuid4().hex[:12]}"
        self.capacity = capacity
        self._events: deque[EventEnvelope] = deque(maxlen=capacity)
        self._sequence = 0
        self._condition = Condition()

    @property
    def latest_sequence(self) -> int:
        with self._condition:
            return self._sequence

    def publish(
        self,
        event_type: str,
        *,
        sim_time: float,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        with self._condition:
            self._sequence += 1
            event = EventEnvelope.create(
                run_id=self.run_id,
                sequence=self._sequence,
                sim_time=sim_time,
                event_type=event_type,
                payload=payload,
            )
            self._events.append(event)
            self._condition.notify_all()
            return event

    def since(self, sequence: int) -> list[EventEnvelope]:
        with self._condition:
            return [event for event in self._events if event.sequence > sequence]

    def wait_since(
        self, sequence: int, *, timeout: float = 15.0
    ) -> list[EventEnvelope]:
        with self._condition:
            if self._sequence <= sequence:
                self._condition.wait(timeout=timeout)
            return [event for event in self._events if event.sequence > sequence]

    def latest(self, event_type: str | None = None) -> EventEnvelope | None:
        with self._condition:
            for event in reversed(self._events):
                if event_type is None or event.type == event_type:
                    return event
            return None
