"""Serializable state shared by cognition, memory, and observability layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Mode(StrEnum):
    IDLE = "idle"
    EXPLORING = "exploring"
    ACTING = "acting"
    REFLECTING = "reflecting"
    RECOVERING = "recovering"


@dataclass(slots=True)
class AgentState:
    """A compact, dashboard-friendly snapshot of the agent's mind."""

    mode: Mode = Mode.IDLE
    goal: str | None = None
    subgoal: str | None = None
    attention: str | None = None
    confidence: float = 0.0
    observations: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible snapshot."""
        return asdict(self)

