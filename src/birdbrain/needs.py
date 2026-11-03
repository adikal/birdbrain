"""Needs: the duck's internal pressures (docs/design.md section 4.1).

Each need is a pressure: 0 when satisfied, 1 when urgent (tidiness carries the
owner's weight of 2, so it runs to 2). Local code
updates them from the body and from beliefs; they are the only source of value
in the duck's choices.

- energy: a battery that drains with activity and recharges while resting;
- tidiness (Milestone 3): the owner's preference for toys in the basket, from
  believed clutter; or, in its place,
- approval (Milestone 3b): the duck's estimate of its owner's mood, raised by her
  approval and lowered by her disapproval, relaxing to neutral; what earns it is
  learned (`reactions.py`);
- curiosity: grows while the duck has not explored, and habituates where
  exploring finds nothing new;
- safety: rises after a fall and fades; while raised, risky goals cost more.

When the battery is empty the duck must rest: a homeostatic reflex that does
not consult the mind.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from birdbrain.kr import SELF, KnowledgeBase
from birdbrain.perception import CONFIRMED
from birdbrain.relations import inside


@dataclass(frozen=True)
class NeedParams:
    drain_active: float = 1.0 / 400.0     # battery per second while moving
    drain_idle: float = 1.0 / 2000.0      # ... while standing
    recharge: float = 1.0 / 40.0          # ... gained per second of rest
    exhausted: float = 0.03               # below this the duck must rest
    tidiness_weight: float = 2.0          # the owner's preference: a toy in the basket is worth a lot
    curiosity_time: float = 240.0         # s without exploring until curiosity is 63%
    safety_per_fall: float = 0.6
    safety_fade: float = 60.0             # s
    # Approval (Milestone 3b): the duck's estimate of its owner's mood, in [-1, 1].
    approval_step: float = 0.3            # one reaction moves the mood this far
    approval_fade: float = 120.0          # s for the mood to relax most of the way to neutral
    approval_weight: float = 4.0          # how much the owner's approval matters, against other needs


def energy_pressure(battery: float) -> float:
    """Convex: a nearly full battery is no concern, a low one is urgent."""
    return (1.0 - battery) ** 2


def tidiness_pressure(clutter: int, known: int, weight: float) -> float:
    """The fraction of known toys outside the basket: every toy counts the same."""
    return weight * clutter / max(known, 1)


def approval_pressure(mood: float) -> float:
    """0 when the owner is believed delighted, 0.25 when neutral, 1 when displeased.
    Convex, like energy: more approval matters less once she is pleased, and her
    displeasure weighs more than her pleasure (ledger E-015, review)."""
    return ((1.0 - mood) / 2.0) ** 2


class Needs:
    """`social` is the need that connects the duck to its owner: "tidiness" (Milestone 3,
    the owner's preference entered directly) or "approval" (Milestone 3b, what pleases
    her is learned)."""

    def __init__(self, params: NeedParams | None = None, social: str = "tidiness") -> None:
        if social not in {"tidiness", "approval"}:
            raise ValueError(f"unknown social need {social!r}")
        self.p = params or NeedParams()
        self.social = social
        self.NAMES = ("energy", social, "curiosity", "safety")
        self.mood = 0.0
        self.battery = 1.0
        self.safety_level = 0.0
        self._last_t: float | None = None
        self._explored_t = -math.inf          # a newborn duck has seen nothing: fully curious
        self.pressure: dict[str, float] = dict.fromkeys(self.NAMES, 0.0)
        #: What each way of exploring has been found to yield: a running average of
        #: objects newly confirmed per trial, optimistic at birth (ledger E-014). Looking
        #: around the same spot habituates when it finds nothing; walking somewhere new
        #: keeps its value while it keeps finding things.
        self.explore_yield: dict[str, float] = {}

    def update(self, kb: KnowledgeBase, t: float, moving: bool, resting: bool,
               exploring: bool, fell: bool) -> dict[str, float]:
        dt = 0.0 if self._last_t is None else max(0.0, t - self._last_t)
        self._last_t = t
        if resting:
            self.battery = min(1.0, self.battery + self.p.recharge * dt)
        else:
            self.battery = max(0.0, self.battery - (self.p.drain_active if moving else self.p.drain_idle) * dt)
        if exploring:
            self._explored_t = t
        if fell:
            self.safety_level = min(1.0, self.safety_level + self.p.safety_per_fall)
        self.safety_level *= math.exp(-dt / self.p.safety_fade)
        self.mood *= math.exp(-dt / self.p.approval_fade)
        if self.social == "tidiness":
            clutter, _ = self.beliefs(kb, t)
            social = tidiness_pressure(clutter, self.known_toys(kb), self.p.tidiness_weight)
        else:
            social = approval_pressure(self.mood)
        self.pressure = {
            "energy": round(energy_pressure(self.battery), 4),
            self.social: round(social, 4),
            "curiosity": round(1.0 - math.exp(-(t - self._explored_t) / self.p.curiosity_time), 4),
            "safety": round(self.safety_level, 4),
        }
        return self.pressure

    @staticmethod
    def known_toys(kb: KnowledgeBase) -> int:
        toys = sum(1 for e in kb.of_class("toy") if kb.get("at", e) is not None and kb.get("at", e).conf >= CONFIRMED)
        return toys + (kb.value("holding", SELF) is not None)

    @staticmethod
    def beliefs(kb: KnowledgeBase, t: float) -> tuple[int, int]:
        """(toys believed outside the basket, entities whose existence is in doubt)."""
        baskets = kb.of_class("basket")
        clutter = doubted = 0
        for e in kb.of_class("toy"):
            a = kb.get("at", e)
            if a is None:
                continue
            if a.conf < CONFIRMED:
                doubted += a.conf > 0.1
                continue
            if not any(inside(kb, t, e, b) for b in baskets):
                clutter += 1
        if kb.value("holding", SELF) is not None:
            clutter += 1
        return clutter, doubted

    def hear(self, valence: int) -> None:
        """The owner approved (+1) or disapproved (-1)."""
        self.mood = max(-1.0, min(1.0, self.mood + self.p.approval_step * valence))

    def approval_value(self, p_approve: float, p_disapprove: float) -> float:
        """Expected relief of the approval need from an action that earns approval and
        disapproval with these probabilities, given the duck's current estimate of her
        mood: the same reaction is worth more when she is displeased than when she is
        delighted. In the scorecard's units."""
        now, step = approval_pressure(self.mood), self.p.approval_step
        gain = now - approval_pressure(min(1.0, self.mood + step))
        loss = approval_pressure(max(-1.0, self.mood - step)) - now
        return self.p.approval_weight * (p_approve * gain - p_disapprove * loss)

    def yield_of(self, skill: str) -> float:
        return self.explore_yield.get(skill, 1.0)

    def observe_exploration(self, skill: str, newly_confirmed: int) -> None:
        """Update what exploring with `skill` yields, from one trial's result."""
        gain = min(1.0, newly_confirmed / 2.0)
        self.explore_yield[skill] = 0.5 * self.yield_of(skill) + 0.5 * gain

    @staticmethod
    def confirmed(kb: KnowledgeBase) -> set[str]:
        return {e for e in kb.entities if kb.cls(e) in {"toy", "basket"}
                and kb.get("at", e) is not None and kb.get("at", e).conf >= CONFIRMED}

    @property
    def exhausted(self) -> bool:
        return self.battery <= self.p.exhausted

    def snapshot(self) -> dict[str, Any]:
        return {"pressure": dict(self.pressure), "battery": round(self.battery, 3), "mood": round(self.mood, 3),
                "explore_yield": {k: round(v, 3) for k, v in self.explore_yield.items()}}
