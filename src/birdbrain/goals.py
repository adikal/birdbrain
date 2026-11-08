"""Self-generated goals and their measured scorecard (docs/design.md section 4.2).

Candidate goals come from the needs and the beliefs: every toy believed
outside the basket is a tidying goal, holding a toy makes delivering it one,
curiosity makes exploring one, and resting is always available. Each goal
names the tools that can serve it.

The scorecard follows the design's form

    U(g) = alpha * dV + beta * LP + gamma * IG - delta * C - epsilon * R

with every term computed from beliefs and counted outcomes:

- dV: expected reduction in need pressure if g succeeds, times the measured
  probability that it succeeds;
- LP: recent learning progress on the skills g uses (change in success rate);
- IG: how uncertain the beliefs g would test are; only exploring tests beliefs
  on purpose (rewarding it in tidy goals sent the duck to its least certain
  toys first and cost 0.56 toys a run, ledger E-014);
- C: expected time over the horizon: the skills' measured mean time, plus the
  walk this particular goal needs (so a near toy costs less than a far one);
- R: risk, the expected rise in the safety need: the measured rate of falls
  during the skills g uses (with a prior from the base rate) times what one
  fall adds, weighed more while the safety need is already raised. A recent
  fall makes the duck cautious; it does not make resting useful, because the
  safety need fades with time whatever the duck does.

The scorecard is evidence for the cloud brain, which chooses; the local needs
policy takes the top-scoring goal.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from birdbrain.body import MICRODUCK
from birdbrain.kr import SELF, KnowledgeBase
from birdbrain.needs import energy_pressure
from birdbrain.records import SkillRecord
from birdbrain.relations import failures, inside, known, where

WEIGHTS = {"alpha": 1.0, "beta": 0.5, "gamma": 0.3, "delta": 0.5, "epsilon": 1.0}
HORIZON_S = 600.0


@dataclass(frozen=True)
class Goal:
    id: str
    kind: str                         # tidy | deliver | explore | rest | pick | put
    source: str                       # the need it serves
    statement: str                    # the desired state, as an expression
    tools: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]   # (tool, ((param, entity), ...))
    terms: dict[str, float] = field(default_factory=dict)

    @property
    def utility(self) -> float:
        w = WEIGHTS
        t = self.terms
        return (w["alpha"] * t["dV"] + w["beta"] * t["LP"] + w["gamma"] * t["IG"]
                - w["delta"] * t["C"] - w["epsilon"] * t["R"])

    def serves(self, tool: str, args: dict[str, Any]) -> bool:
        return any(name == tool and dict(params) == dict(args) for name, params in self.tools)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "source": self.source, "statement": self.statement,
                "U": round(self.utility, 3), **{k: round(v, 3) for k, v in self.terms.items()}}


#: predict(skill, args) -> (probability the expected effect holds, probability of a fall),
#: from causal rules learned under conditions (Milestone 4, `rules.py`).
Predict = Callable[[str, dict[str, Any]], tuple[float, float]]


def candidates(kb: KnowledgeBase, t: float, needs: Any, records: dict[str, Any],
               tools: set[str], give_up_after: int = 3, predict: Predict | None = None) -> list[Goal]:
    """Every goal the duck could pursue now, scored."""
    pressure = needs.pressure
    _, doubted = needs.beliefs(kb, t)
    relief = needs.p.tidiness_weight / max(needs.known_toys(kb), 1)     # one more toy in the basket
    baskets = kb.of_class("basket")
    held = kb.value("holding", SELF)
    here = kb.position(SELF)
    basket = max(baskets, key=lambda b: kb.get("at", b).conf if kb.get("at", b) else 0.0, default=None)
    out: list[Goal] = []

    def walk(*points: Any) -> float:
        """Time to walk through `points` from here, as a fraction of the horizon."""
        path, last = 0.0, here
        for p in points:
            if p is not None and last is not None:
                path += last.distance(p)
            last = p if p is not None else last
        return path / MICRODUCK.walk_speed / HORIZON_S

    def stats(skill: str, args: dict[str, Any] | None = None) -> tuple[float, float, float, float]:
        r = records.get(skill)
        if r is None:
            r = SkillRecord()
        p, fall = predict(skill, args or {}) if predict is not None else (r.p, r.fall_rate)
        return (p, r.progress, (r.seconds / r.trials if r.trials else 30.0) / HORIZON_S,
                fall * needs.p.safety_per_fall * (1.0 + pressure["safety"]))

    if held is not None and "deliver" in tools:
        p, lp, c, risk = stats("deliver")
        out.append(Goal(f"deliver:{held}", "deliver", "tidiness", f"inside({held!r}, basket)",
                        (("deliver", ()),),
                        {"dV": relief * p, "LP": lp, "IG": 0.0, "C": c, "R": risk}))
    if held is None and "pick" in tools:
        p_del, lp_del, c_del, r_del = stats("deliver")
        for e in kb.of_class("toy"):
            a = kb.get("at", e)
            if a is None or not known(kb, t, e) or any(inside(kb, t, e, b) for b in baskets):
                continue
            if failures(kb, t, "pick", e) >= give_up_after:
                continue
            p_pick, lp_pick, c_pick, r_pick = stats("pick", {"x": e})
            travel = walk(a.value, kb.position(basket) if basket else None)
            out.append(Goal(f"tidy:{e}", "tidy", "tidiness", f"inside({e!r}, basket)",
                            (("pick", (("x", e),)),),
                            {"dV": relief * p_pick * p_del, "LP": max(lp_pick, lp_del), "IG": 0.0,
                             "C": c_pick + c_del + travel, "R": max(r_pick, r_del)}))
    # One exploring goal, served by every way of exploring. Its value is that of its best
    # means now, and its tools are listed best first: each means habituates on its own.
    means = []
    for name in ("look_around", "explore"):
        if name in tools:
            p, lp, c, risk = stats(name)
            y = needs.yield_of(name)
            terms = {"dV": pressure["curiosity"] * p * y, "LP": lp, "IG": y * min(1.0, doubted / 3.0),
                     "C": c, "R": risk}
            means.append((Goal("explore", "explore", "curiosity", "true", ((name, ()),), terms), name))
    if means:
        means.sort(key=lambda m: -m[0].utility)
        out.append(Goal("explore", "explore", "curiosity", "true", tuple((name, ()) for _, name in means),
                        means[0][0].terms))
    if "rest" in tools:
        p, lp, c, _ = stats("rest")
        after = min(1.0, needs.battery + needs.p.recharge * 10.0)          # ten seconds of rest
        rested = pressure["energy"] - energy_pressure(after)
        out.append(Goal("rest", "rest", "energy", "true", (("rest", ()),),
                        {"dV": rested, "LP": 0.0, "IG": 0.0, "C": c * 0.5, "R": 0.0}))
    return sorted(out, key=lambda g: -g.utility)


#: The ways of putting a held toy down (Milestone 3b), offered side by side.
PUTS = ("deliver", "put_by_wall", "drop")


#: owner(skill, args) -> (p approval, p disapproval, uncertainty): one posterior draw of the
#: owner's reaction to this action (Thompson sampling), from `reactions.py`.
Owner = Callable[[str, dict[str, Any]], tuple[float, float, float]]


def kinds_owner(reactions: Any, rng: Any, draws: dict[str, Any], kind_of: Callable[[str, dict[str, Any]], str]) -> Owner:
    """The owner's reactions by kind of action (E-015): one Beta draw per kind, kept in
    `draws` so a pick and the put that follows it use the same beliefs."""
    def owner(skill: str, args: dict[str, Any]) -> tuple[float, float, float]:
        kind = kind_of(skill, args)
        b = reactions.belief(kind)
        if kind not in draws:
            draws[kind] = b.sample(rng)
        return (*draws[kind], b.uncertainty)
    return owner


def approval_candidates(kb: KnowledgeBase, t: float, needs: Any, records: dict[str, Any],
                        tools: set[str], owner_p: Owner, kind_records: dict[str, Any] | None = None,
                        give_up_after: int = 3, predict: Predict | None = None,
                        kind_of: Callable[[str, dict[str, Any]], str] | None = None) -> list[Goal]:
    """Goals when the social need is approval (Milestone 3b, design section 4.3).

    No goal names a state of the room. Each goal is a way of acting, valued by what the
    duck has learned about its owner's reactions to that kind of action, plus whatever
    other need it serves. A pick is valued with the best way of putting the toy down
    afterwards, since a pick is always followed by one. The owner's reaction to each kind
    of action is valued by one draw from its posterior (Thompson sampling, `reactions.py`):
    that is how the duck tries what it knows little about, and stops trying what never
    pleases her. The draws last a pick and the put that follows it, so both are chosen
    with the same beliefs (`owner_p` keeps them). Risk and success are counted per kind of action where it matters: a pick by a wall is
    not a pick in the open.
    """
    kind_records = kind_records or {}
    pressure = needs.pressure
    held = kb.value("holding", SELF)
    here = kb.position(SELF)
    out: list[Goal] = []

    def stats(skill: str, args: dict[str, Any] | None = None) -> tuple[float, float, float, float]:
        r = kind_records.get(skill) or records.get(skill) or SkillRecord()
        if predict is not None:
            p, fall = predict(skill, args or {})
            r = records.get(skill) or SkillRecord()
            return (p, r.progress, (r.seconds / r.trials if r.trials else 30.0) / HORIZON_S,
                    fall * needs.p.safety_per_fall * (1.0 + pressure["safety"]))
        return (r.p, r.progress, (r.seconds / r.trials if r.trials else 30.0) / HORIZON_S,
                r.fall_rate * needs.p.safety_per_fall * (1.0 + pressure["safety"]))

    def owner(skill: str, args: dict[str, Any] | None = None) -> tuple[float, float]:
        """(value of the owner's reaction, one posterior draw; uncertainty, reported)."""
        up, down, unsure = owner_p(skill, args or {})
        return needs.approval_value(up, down), unsure

    def kind_stats(kind: str, skill: str, args: dict[str, Any]) -> tuple[float, float, float, float]:
        if predict is not None:
            return stats(skill, args)
        return stats(kind) if kind in kind_records and kind_records[kind].trials else stats(skill)

    # The owner's reaction to a kind of action is learned per action of that kind, whether
    # it worked or not, so it already prices failure in: it is not multiplied by the
    # chance of success again (E-027). A pick's own reaction is its own; the put's
    # reaction follows only if the pick worked.
    puts = [(name, *owner(name), *stats(name)) for name in PUTS if name in tools]
    if held is not None:
        for name, value, unsure, _, lp, c, risk in puts:
            out.append(Goal(f"approval:{name}", "put", "approval", "true", ((name, ()),),
                            {"dV": value, "LP": lp, "IG": 0.0, "C": c, "R": risk, "sd": unsure}))
    elif "pick" in tools and puts:
        # A pick is followed by the put that looks best: its value, cost and risk.
        _, best_value, _, _, _, put_cost, put_risk = max(puts, key=lambda m: m[1])
        for e in kb.of_class("toy"):
            a = kb.get("at", e)
            if a is None or not known(kb, t, e) or failures(kb, t, "pick", e) >= give_up_after:
                continue
            kind = kind_of("pick", {"x": e}) if kind_of is not None else f"pick from {where(kb, t, e)}"
            value, unsure = owner("pick", {"x": e})
            p_pick, lp_pick, c_pick, r_pick = kind_stats(kind, "pick", {"x": e})
            travel = 0.0 if here is None else here.distance(a.value) / MICRODUCK.walk_speed / HORIZON_S
            out.append(Goal(f"approval:pick:{e}", "pick", "approval", "true", (("pick", (("x", e),)),),
                            {"dV": value + p_pick * best_value, "LP": lp_pick, "IG": 0.0,
                             "C": c_pick + put_cost + travel, "R": r_pick + put_risk, "sd": unsure}))
    for goal in candidates(kb, t, needs, records, tools & {"look_around", "explore", "rest"}, predict=predict):
        # Exploring and resting also carry whatever the owner has been seen to think of them.
        kinds = [name for name, _ in goal.tools]
        value = max(owner(k)[0] for k in kinds)
        out.append(Goal(goal.id, goal.kind, goal.source, goal.statement, goal.tools,
                        {**goal.terms, "dV": goal.terms["dV"] + value}))
    return sorted(out, key=lambda g: -g.utility)
