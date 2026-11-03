"""BirdBrain's knowledge representation: entities, assertions, and events.

A small general core (docs/design.md section 7). Every fact is an assertion
`relation(args) = value` that holds over a time interval and carries its
sources. Facts are never overwritten: when one stops holding, its interval
closes and a new assertion opens, so history stays queryable. Events record
what happened over an interval and who took part.

Spatial relations (near, facing, inside) are not stored. They are computed
from positions when queried (`birdbrain.relations`), so they cannot go stale.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass, field
from typing import Any

SELF = "self"

Listener = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True, slots=True)
class Entity:
    id: str
    cls: str


@dataclass(slots=True)
class Assertion:
    """`rel(args) = value`, holding from `t_start` until `t_end` (None: still holds)."""

    id: int
    rel: str
    args: tuple[str, ...]
    value: Any
    t_start: float
    t_end: float | None
    t_obs: float
    conf: float
    sources: tuple[str, ...]
    provenance: str

    @property
    def open(self) -> bool:
        return self.t_end is None

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["args"] = list(self.args)
        if isinstance(self.value, tuple):
            out["value"] = list(self.value)
        return out


@dataclass(slots=True)
class Event:
    """Something that happened over `[t0, t1]` with participants and an outcome."""

    id: str
    kind: str
    t0: float
    t1: float | None = None
    participants: tuple[str, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["participants"] = list(self.participants)
        return out


@dataclass(frozen=True, slots=True)
class Position:
    """A point in the odometry frame with a 2-D covariance (m^2).

    `sigma` is the standard deviation along the most uncertain direction.
    """

    x: float
    y: float
    sxx: float
    sxy: float = 0.0
    syy: float | None = None

    def __post_init__(self) -> None:
        if self.syy is None:
            object.__setattr__(self, "syy", self.sxx)

    @classmethod
    def round(cls, x: float, y: float, sigma: float) -> Position:
        """An isotropic position with standard deviation `sigma`."""
        return cls(x, y, sigma * sigma, 0.0, sigma * sigma)

    @property
    def sigma(self) -> float:
        half_trace = (self.sxx + self.syy) / 2
        spread = math.sqrt(max(((self.sxx - self.syy) / 2) ** 2 + self.sxy**2, 0.0))
        return math.sqrt(max(half_trace + spread, 0.0))

    def distance(self, other: Position) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def mahalanobis2(self, other: Position, floor: float = 0.0) -> float:
        """Squared Mahalanobis distance under the summed covariances (plus `floor`^2)."""
        a = self.sxx + other.sxx + floor * floor
        b = self.sxy + other.sxy
        c = self.syy + other.syy + floor * floor
        det = a * c - b * b
        dx, dy = other.x - self.x, other.y - self.y
        return (c * dx * dx - 2 * b * dx * dy + a * dy * dy) / det if det > 1e-12 else math.inf

    def fuse(self, other: Position) -> Position:
        """Kalman update of this estimate with an independent measurement `other`."""
        a, b, c = self.sxx + other.sxx, self.sxy + other.sxy, self.syy + other.syy
        det = a * c - b * b
        if det <= 1e-12:
            return other
        ia, ib, ic = c / det, -b / det, a / det                    # inverse of the innovation covariance
        kxx = self.sxx * ia + self.sxy * ib                        # gain K = P S^-1
        kxy = self.sxx * ib + self.sxy * ic
        kyx = self.sxy * ia + self.syy * ib
        kyy = self.sxy * ib + self.syy * ic
        dx, dy = other.x - self.x, other.y - self.y
        return Position(
            self.x + kxx * dx + kxy * dy,
            self.y + kyx * dx + kyy * dy,
            (1 - kxx) * self.sxx - kxy * self.sxy,
            (1 - kxx) * self.sxy - kxy * self.syy,
            -kyx * self.sxy + (1 - kyy) * self.syy,
        )

    def scaled(self, factor: float) -> Position:
        """This estimate with its covariance multiplied by `factor`."""
        return Position(self.x, self.y, self.sxx * factor, self.sxy * factor, self.syy * factor)

    def floored(self, sigma: float) -> Position:
        """This estimate, with each axis variance at least `sigma`^2."""
        v = sigma * sigma
        if self.sxx >= v and self.syy >= v:
            return self
        return Position(self.x, self.y, max(self.sxx, v), self.sxy, max(self.syy, v))

    def grown(self, sigma: float) -> Position:
        """This estimate with isotropic process noise `sigma` added."""
        v = sigma * sigma
        return Position(self.x, self.y, self.sxx + v, self.sxy, self.syy + v)


class KnowledgeBase:
    """Current and past assertions, entities, and events, with change notification.

    `listener(kind, payload)` receives every entity, assertion, and event
    change, which is how the KB reaches the event log and the dashboard.
    """

    def __init__(self, listener: Listener | None = None) -> None:
        self._listener = listener
        self.entities: dict[str, Entity] = {SELF: Entity(SELF, "duck")}
        self._current: dict[tuple[str, tuple[str, ...]], Assertion] = {}
        self.history: list[Assertion] = []
        self.events: list[Event] = []
        self._ids = itertools.count(1)
        self._per_class: dict[str, itertools.count] = {}
        self._event_ids = itertools.count(1)

    # -- entities -------------------------------------------------------------
    def new_entity(self, cls: str, t: float) -> str:
        counter = self._per_class.setdefault(cls, itertools.count(1))
        entity = Entity(f"{cls}#{next(counter)}", cls)
        self.entities[entity.id] = entity
        self._emit("ENTITY_CREATED", {"entity": entity.id, "cls": cls, "t": t})
        return entity.id

    def ensure_entity(self, entity: str, cls: str, t: float) -> str:
        """Create an entity with a given id if it does not exist (for derived places)."""
        if entity not in self.entities:
            self.entities[entity] = Entity(entity, cls)
            self._emit("ENTITY_CREATED", {"entity": entity, "cls": cls, "t": t})
        return entity

    def of_class(self, cls: str) -> list[str]:
        return [e.id for e in self.entities.values() if e.cls == cls]

    def cls(self, entity: str) -> str | None:
        found = self.entities.get(entity)
        return None if found is None else found.cls

    # -- assertions -----------------------------------------------------------
    def tell(
        self,
        rel: str,
        args: Iterable[str],
        value: Any = True,
        *,
        t: float,
        conf: float = 1.0,
        source: str = "",
        provenance: str = "perception",
        same: Callable[[Any, Any], bool] | None = None,
    ) -> Assertion:
        """Assert `rel(args) = value` at time `t`.

        If an open assertion already says the same thing (by `same`, default
        equality), it is refreshed in place: its observation time, confidence,
        value, and sources update without opening a new interval. Otherwise the
        old interval closes at `t` and a new assertion opens.
        """
        key = (rel, tuple(args))
        old = self._current.get(key)
        if old is not None and (same or _equal)(old.value, value):
            old.value, old.t_obs, old.conf = value, t, conf
            if source and source not in old.sources:
                old.sources = (*old.sources[-7:], source)
            return old
        if old is not None:
            self._close(old, t)
        new = Assertion(
            id=next(self._ids),
            rel=rel,
            args=key[1],
            value=value,
            t_start=t,
            t_end=None,
            t_obs=t,
            conf=conf,
            sources=(source,) if source else (),
            provenance=provenance,
        )
        self._current[key] = new
        self.history.append(new)
        self._emit("ASSERTION_OPENED", new.to_dict())
        return new

    def untell(self, rel: str, args: Iterable[str], *, t: float, reason: str = "") -> None:
        """Close `rel(args)` at `t`: it no longer holds (or is no longer known)."""
        old = self._current.get((rel, tuple(args)))
        if old is not None:
            self._close(old, t, reason)

    def get(self, rel: str, *args: str) -> Assertion | None:
        return self._current.get((rel, args))

    def value(self, rel: str, *args: str, default: Any = None) -> Any:
        found = self._current.get((rel, args))
        return default if found is None else found.value

    def current(self, rel: str | None = None) -> Iterator[Assertion]:
        for assertion in self._current.values():
            if rel is None or assertion.rel == rel:
                yield assertion

    def held_at(self, rel: str, args: tuple[str, ...], t: float) -> Assertion | None:
        """The assertion about `rel(args)` that held at time `t`, if any."""
        for assertion in reversed(self.history):
            if assertion.rel == rel and assertion.args == args and assertion.t_start <= t and (
                assertion.t_end is None or t < assertion.t_end
            ):
                return assertion
        return None

    def position(self, entity: str) -> Position | None:
        value = self.value("at", entity)
        return value if isinstance(value, Position) else None

    # -- events ---------------------------------------------------------------
    def begin(self, kind: str, t: float, participants: Iterable[str] = (), **data: Any) -> Event:
        event = Event(f"ev{next(self._event_ids)}", kind, t, None, tuple(participants), dict(data))
        self.events.append(event)
        self._emit("EVENT_STARTED", event.to_dict())
        return event

    def end(self, event: Event, t: float, **data: Any) -> Event:
        event.t1 = t
        event.data.update(data)
        self._emit("EVENT_ENDED", event.to_dict())
        return event

    def find_events(self, kind: str, participant: str | None = None) -> list[Event]:
        return [
            e
            for e in self.events
            if e.kind == kind and (participant is None or participant in e.participants)
        ]

    # -- internals ------------------------------------------------------------
    def _close(self, assertion: Assertion, t: float, reason: str = "") -> None:
        assertion.t_end = t
        del self._current[(assertion.rel, assertion.args)]
        self._emit(
            "ASSERTION_CLOSED",
            {"id": assertion.id, "rel": assertion.rel, "args": list(assertion.args),
             "t_end": t, "reason": reason},
        )

    def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        if self._listener is not None:
            self._listener(kind, payload)


def _equal(a: Any, b: Any) -> bool:
    return a == b


def same_place(tolerance: float = 0.05) -> Callable[[Any, Any], bool]:
    """Positions within `tolerance` (or within two sigma) count as the same fact."""

    def compare(old: Any, new: Any) -> bool:
        if not (isinstance(old, Position) and isinstance(new, Position)):
            return old == new
        return old.distance(new) <= max(tolerance, 2.0 * new.sigma)

    return compare
