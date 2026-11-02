"""Versioned event envelopes shared by the runtime and dashboard."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "birdbrain.event.v1"


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    schema_version: str
    run_id: str
    sequence: int
    wall_time: str
    sim_time: float
    type: str
    payload: dict[str, Any]

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        sequence: int,
        sim_time: float,
        event_type: str,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        return cls(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            sequence=sequence,
            wall_time=datetime.now(UTC).isoformat(),
            sim_time=float(sim_time),
            type=event_type,
            payload=payload,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
