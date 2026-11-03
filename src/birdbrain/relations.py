"""Relations computed from the knowledge base when queried.

Each function takes the knowledge base, the current time, and entity ids.
`FUNCTIONS` is the vocabulary that skill conditions, queries, and
predictions may use (see `birdbrain.expr`).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from birdbrain.body import MICRODUCK
from birdbrain.kr import SELF, KnowledgeBase, Position
from birdbrain.perception import CONFIRMED


def known(kb: KnowledgeBase, t: float, x: str, precision: float = 0.5) -> bool:
    """We believe we know where `x` is, confidently and to within `precision` (m)."""
    a = kb.get("at", x)
    return (a is not None and isinstance(a.value, Position) and a.conf >= CONFIRMED
            and a.value.sigma <= precision)


def distance(kb: KnowledgeBase, t: float, a: str, b: str) -> float:
    pa, pb = kb.position(a), kb.position(b)
    return math.inf if pa is None or pb is None else pa.distance(pb)


def near(kb: KnowledgeBase, t: float, a: str, b: str, d: float = 0.3) -> bool:
    return distance(kb, t, a, b) <= d


def bearing(kb: KnowledgeBase, t: float, x: str) -> float:
    """Bearing of `x` off the duck's nose (rad, +left)."""
    me, there = kb.position(SELF), kb.position(x)
    if me is None or there is None:
        return math.nan
    yaw = kb.value("heading", SELF, default=0.0)
    return math.atan2(math.sin(math.atan2(there.y - me.y, there.x - me.x) - yaw),
                      math.cos(math.atan2(there.y - me.y, there.x - me.x) - yaw))


def facing(kb: KnowledgeBase, t: float, x: str, tolerance: float = 0.1) -> bool:
    b = bearing(kb, t, x)
    return not math.isnan(b) and abs(b) <= tolerance


def inside(kb: KnowledgeBase, t: float, x: str, container: str, margin: float = 0.03) -> bool:
    """`x` lies within the footprint of `container`, or within `margin` of its rim."""
    px, pc = kb.position(x), kb.position(container)
    half = MICRODUCK.class_half_width.get(kb.cls(container) or "", 0.0) + margin
    return (px is not None and pc is not None and abs(px.x - pc.x) < half
            and abs(px.y - pc.y) < half)


def beyond(kb: KnowledgeBase, t: float, x: str, origin: str, d: float) -> str | None:
    """A place `d` metres past `x` on the ray from `origin` through `x`.

    Places are entities (class `place`), so skills can walk to them. The id
    is derived from the arguments, which makes the query idempotent.
    """
    px, po = kb.position(x), kb.position(origin)
    if px is None or po is None:
        return None
    r = px.distance(po)
    if r < 1e-6:
        return None
    place = kb.ensure_entity(f"place:{x}>{origin}", "place", t)
    kb.tell("at", (place,), Position.round(px.x + d * (px.x - po.x) / r, px.y + d * (px.y - po.y) / r,
                                           px.sigma), t=t, source="derived", provenance="derived")
    return place


def holding(kb: KnowledgeBase, t: float, who: str = SELF, x: str | None = None) -> bool:
    held = kb.value("holding", who)
    return held is not None and (x is None or held == x)


def attempts(kb: KnowledgeBase, t: float, skill: str, x: str, outcome: str | None = None) -> int:
    """How many times `skill` was tried on `x` (optionally: with this outcome)."""
    return sum(1 for e in kb.find_events("action", x)
               if e.data.get("skill") == skill
               and (outcome is None or e.data.get("outcome") == outcome))


def failures(kb: KnowledgeBase, t: float, skill: str, x: str) -> int:
    """How many times `skill` on `x` ended without success (failed or timed out).
    Runs stopped by their caller are not failures of the skill."""
    return sum(1 for e in kb.find_events("action", x)
               if e.data.get("skill") == skill and e.data.get("outcome") in {"failed", "timeout"})


def seen_since(kb: KnowledgeBase, t: float, x: str) -> float:
    """Seconds since `x` was last observed."""
    a = kb.get("at", x)
    return math.inf if a is None else t - a.t_obs


FUNCTIONS: dict[str, Callable[..., Any]] = {
    "known": known,
    "distance": distance,
    "near": near,
    "bearing": bearing,
    "facing": facing,
    "inside": inside,
    "holding": holding,
    "beyond": beyond,
    "attempts": attempts,
    "failures": failures,
    "seen_since": seen_since,
}
