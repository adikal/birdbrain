"""Simulator-agnostic environment boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class Observation:
    timestamp: float
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Action:
    name: str
    parameters: dict[str, Any] = field(default_factory=dict)


class EnvironmentAdapter(Protocol):
    """Contract implemented by MuJoCo and future hardware adapters."""

    def reset(self, *, seed: int | None = None) -> Observation: ...

    def observe(self) -> Observation: ...

    def act(self, action: Action) -> Observation: ...

    def close(self) -> None: ...

