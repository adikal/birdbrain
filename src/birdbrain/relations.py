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


def inside(kb: KnowledgeBase, t: float, x: str, container: str, margin: float = 0.03,
           sigmas: float = 2.0) -> bool:
    """`x` may lie within the footprint of `container` (or within `margin` of its rim),
    allowing `sigmas` standard deviations of the two positions' combined uncertainty.
    The default reads "inside unless clearly outside", so an ambiguous toy is not taken
    out of the basket (ledger E-014); `sigmas=0` asks whether the best estimates say
    inside, which is what an action's expected effect should be judged by."""
    px, pc = kb.position(x), kb.position(container)
    if px is None or pc is None:
        return False
    half = (MICRODUCK.class_half_width.get(kb.cls(container) or "", 0.0) + margin
            + sigmas * math.hypot(px.sigma, pc.sigma))
    return abs(px.x - pc.x) < half and abs(px.y - pc.y) < half


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


def _bounds(kb: KnowledgeBase) -> tuple[float, float, float, float] | None:
    """The room's wall faces (xmin, ymin, xmax, ymax) in the odometry frame, if known."""
    return kb.value("bounds", SELF)


def wall_distance(kb: KnowledgeBase, t: float, x: str) -> float:
    """Distance from `x` to the nearest wall (inf if the walls are not known)."""
    b, p = _bounds(kb), kb.position(x)
    if b is None or p is None:
        return math.inf
    return min(p.x - b[0], b[2] - p.x, p.y - b[1], b[3] - p.y)


#: What "against a wall" means to the duck: its descriptions of picks and the expected
#: effect of `put_by_wall` use the same distance (m from the wall face).
WALL_NEAR = 0.25


def near_wall(kb: KnowledgeBase, t: float, x: str, d: float = WALL_NEAR) -> bool:
    return wall_distance(kb, t, x) <= d


def wall_spot(kb: KnowledgeBase, t: float, x: str = SELF, offset: float = 0.24,
              keep_clear_of: str | None = "basket") -> str | None:
    """A place `offset` metres in from the wall nearest to `x`, level with `x`.

    Spots within 0.5 m of the best-known basket are skipped, so a toy put by a wall is
    not put at the basket. The place is an entity (class `place`), re-derived on each
    query.
    """
    b, p = _bounds(kb), kb.position(x)
    if b is None or p is None:
        return None
    lo_x, hi_x = b[0] + offset, b[2] - offset
    lo_y, hi_y = b[1] + offset, b[3] - offset
    cx, cy = min(max(p.x, lo_x), hi_x), min(max(p.y, lo_y), hi_y)
    spots = [(lo_x, cy), (hi_x, cy), (cx, lo_y), (cx, hi_y)]
    clear = None
    if keep_clear_of is not None:
        baskets = [e for e in kb.of_class("basket") if kb.position(e) is not None]
        best = max(baskets, key=lambda e: kb.get("at", e).conf, default=None)
        clear = None if best is None else kb.position(best)
    spots = [s for s in spots if clear is None or math.hypot(s[0] - clear.x, s[1] - clear.y) > 0.5]
    if not spots:
        return None
    sx, sy = min(spots, key=lambda s: math.hypot(s[0] - p.x, s[1] - p.y))
    place = kb.ensure_entity(f"place:wall<{x}", "place", t)
    kb.tell("at", (place,), Position.round(sx, sy, 0.02), t=t, source="derived", provenance="derived")
    return place


def where(kb: KnowledgeBase, t: float, x: str) -> str:
    """Where a toy is, in the duck's own terms: in the basket, against a wall, or in the open."""
    if any(inside(kb, t, x, b) for b in kb.of_class("basket")):
        return "basket"
    return "wall" if near_wall(kb, t, x) else "open"


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
    "near_wall": near_wall,
    "wall_distance": wall_distance,
    "wall_spot": wall_spot,
    "attempts": attempts,
    "failures": failures,
    "seen_since": seen_since,
}
