"""What the duck believes earns its owner's approval (Milestone 3b, ledger E-015).

The owner says whether she likes something, never what. The duck explains each
reaction by the actions that could have caused it, and keeps, for every kind of
action, a belief about how likely it is to be followed by approval and by
disapproval.

Kinds of action are the duck's own: the skill, and for a pick, where the toy was
(in the basket, against a wall, in the open). Every kind starts with the same
prior, Beta(1, 2) for each of approval and disapproval: no kind is assumed to
please her.

Credit assignment is a soft, Bayesian one. A reaction answers a change in the
room, and the duck changes the room at moments it senses itself: when it grasps a
toy, releases one, or bumps into something. A reaction at time t could have been
caused by any such moment in the window [t - window, t - min_delay] (she needs a
moment to react), by the end of an action that changed nothing, or by nothing the
duck did (ledger E-016). The earlier rule, any action under way in the window
(E-015), is kept as `credit="underway"` for comparison. Each candidate is credited in proportion to its kind's
probability of that reaction, and "nothing" in proportion to a small background
rate. Credit and probabilities depend on each other, so every reaction keeps its
candidates and the whole history is re-explained by expectation-maximization
whenever a new one arrives. So a kind that keeps being followed by approval comes to
explain it, and coincident kinds are explained away, even for reactions heard before
the duck knew better.

`ConditionReactionModel` learns the same thing over the conditions the duck
believes hold when it acts (the features of `rules.py`), in place of hand-chosen
kinds: a Bayesian logistic model per skill for approval and one for disapproval,
fitted to the credit EM gives each action (ledger E-018, H-017).

Choosing what to try uses Thompson sampling: each decision values every kind of
action by one draw from its posterior. A kind the duck knows little about sometimes
draws high and gets tried; one that has been tried often without approval rarely
does. Exploration fades as the evidence comes in, with no separate exploration bonus.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from typing import Any

PRIOR_HIT, PRIOR_MISS = 1.0, 2.0


@dataclass
class KindBelief:
    trials: float = 0.0
    approved: float = 0.0          # expected count of approvals this kind caused
    disapproved: float = 0.0

    def p(self, valence: int) -> float:
        hits = self.approved if valence > 0 else self.disapproved
        return (PRIOR_HIT + hits) / (PRIOR_HIT + PRIOR_MISS + max(self.trials, hits))

    def var(self, valence: int) -> float:
        a, b = self._ab(valence)
        return a * b / ((a + b) ** 2 * (a + b + 1.0))

    def _ab(self, valence: int) -> tuple[float, float]:
        hits = self.approved if valence > 0 else self.disapproved
        return PRIOR_HIT + hits, PRIOR_MISS + max(self.trials - hits, 0.0)

    def sample(self, rng: random.Random) -> tuple[float, float]:
        """One draw of (p approval, p disapproval) from the posterior (Thompson sampling)."""
        return rng.betavariate(*self._ab(1)), rng.betavariate(*self._ab(-1))

    @property
    def expected(self) -> float:
        """Expected valence of the owner's reaction to one action of this kind."""
        return self.p(+1) - self.p(-1)

    @property
    def uncertainty(self) -> float:
        """Standard deviation of `expected`, as a fraction of its value before any trial."""
        prior = KindBelief()
        return math.sqrt(self.var(1) + self.var(-1)) / math.sqrt(prior.var(1) + prior.var(-1))


@dataclass
class ReactionModel:
    window_s: float = 8.0
    min_delay_s: float = 0.5
    background: float = 0.05        # weight of "nothing I did caused this"
    kinds: dict[str, KindBelief] = field(default_factory=dict)
    #: Every reaction heard: (valence, the kinds of action that could have caused it).
    history: list[tuple[int, list[str]]] = field(default_factory=list)
    em_iterations: int = 20
    credit: str = "moments"          # "moments" (E-016) or "underway" (E-015)
    #: Recent actions: [kind, t0, t1 or None while running, effect moments].
    _actions: list[list] = field(default_factory=list)

    def belief(self, kind: str) -> KindBelief:
        return self.kinds.get(kind, KindBelief())

    def started(self, kind: str, t: float, **context: Any) -> None:
        self._actions.append([kind, t, None, []])

    def moment(self, t: float) -> None:
        """The running action changed the room now (a grasp, a release, a bump)."""
        if self._actions and self._actions[-1][2] is None:
            self._actions[-1][3].append(t)

    def ended(self, kind: str, t: float) -> None:
        """The running action of `kind` ended: it is one more trial of its kind."""
        for a in reversed(self._actions):
            if a[0] == kind and a[2] is None:
                a[2] = t
                break
        self.kinds.setdefault(kind, KindBelief()).trials += 1
        horizon = t - self.window_s - 60.0
        self._actions = [a for a in self._actions if a[2] is None or a[2] >= horizon]

    def candidates(self, t: float) -> list[str]:
        lo, hi = t - self.window_s, t - self.min_delay_s
        if self.credit == "underway":
            return [k for k, t0, t1, _ in self._actions if t0 <= hi and (t1 is None or t1 >= lo)]
        out = []
        for kind, _, t1, moments in self._actions:
            times = moments or ([t1] if t1 is not None else [])
            if any(lo <= m <= hi for m in times):            # once per action, however many moments
                out.append(kind)
        return out

    def react(self, valence: int, t: float) -> dict[str, float]:
        """Credit one reaction to its possible causes; returns each cause's share."""
        causes = self.candidates(t)
        for kind in causes:
            self.kinds.setdefault(kind, KindBelief())
        self.history.append((valence, causes))
        self._explain()
        return self._shares(valence, causes)

    def _shares(self, valence: int, causes: list[str]) -> dict[str, float]:
        weights = [self.belief(k).p(valence) for k in causes]
        total = sum(weights) + self.background
        shares: dict[str, float] = {"(nothing I did)": self.background / total}
        for kind, w in zip(causes, weights, strict=True):
            shares[kind] = shares.get(kind, 0.0) + w / total
        return {k: round(v, 3) for k, v in shares.items()}

    def _explain(self) -> None:
        """Re-explain every reaction heard (EM): credit given the probabilities, then the
        probabilities given the credit."""
        for _ in range(self.em_iterations):
            credit = {k: [0.0, 0.0] for k in self.kinds}
            for valence, causes in self.history:
                weights = [self.belief(k).p(valence) for k in causes]
                total = sum(weights) + self.background
                for kind, w in zip(causes, weights, strict=True):
                    credit[kind][0 if valence > 0 else 1] += w / total
            for kind, (approved, disapproved) in credit.items():
                b = self.kinds[kind]
                b.approved, b.disapproved = approved, disapproved

    def summary(self) -> dict[str, dict[str, float]]:
        return {k: {"trials": round(b.trials, 1), "approved": round(b.approved, 2),
                    "disapproved": round(b.disapproved, 2), "p_approve": round(b.p(1), 3),
                    "p_disapprove": round(b.p(-1), 3), "expected": round(b.expected, 3)}
                for k, b in sorted(self.kinds.items())}

    def to_json(self) -> str:
        kinds = {k: {"trials": b.trials, "approved": b.approved, "disapproved": b.disapproved}
                 for k, b in sorted(self.kinds.items())}
        return json.dumps({"kinds": kinds, "history": self.history}, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, text: str) -> ReactionModel:
        raw: dict[str, Any] = json.loads(text)
        return cls(kinds={k: KindBelief(**v) for k, v in raw["kinds"].items()},
                   history=[(int(v), list(c)) for v, c in raw["history"]])


@dataclass
class ConditionReactionModel(ReactionModel):
    """Reactions explained by the conditions of each action (ledger E-018, H-017).

    Every action the duck starts is logged with its skill and features. A reaction's
    possible causes are logged actions, chosen by the same timing rule. EM alternates
    between credit (each candidate's share, in proportion to its predicted probability
    of that reaction) and a refit of two `RuleLearner`s, approval and disapproval, on
    every logged action with its total credit as a soft outcome. The prior rate of
    each reaction is 1/3, as for kinds."""

    actions: list[dict[str, Any]] = field(default_factory=list)       # kind, skill, features, ended
    em_iterations: int = 8
    _learners: dict[int, Any] = field(default_factory=dict)

    def started(self, kind: str, t: float, **context: Any) -> None:
        self.actions.append({"kind": kind, "skill": context.get("skill", kind),
                             "features": dict(context.get("features", {})), "ended": False})
        self._actions.append([len(self.actions) - 1, t, None, []])

    def ended(self, kind: str, t: float) -> None:
        for a in reversed(self._actions):
            if a[2] is None:
                a[2] = t
                self.actions[a[0]]["ended"] = True
                break
        horizon = t - self.window_s - 60.0
        self._actions = [a for a in self._actions if a[2] is None or a[2] >= horizon]

    def candidates(self, t: float) -> list[int]:                       # indices into `actions`
        return super().candidates(t)

    def learner(self, valence: int) -> Any:
        from birdbrain.rules import RuleLearner
        if valence not in self._learners:
            self._learners[valence] = RuleLearner("she approves" if valence > 0 else "she disapproves",
                                                  prior=(PRIOR_HIT, PRIOR_MISS))
        return self._learners[valence]

    def p(self, valence: int, skill: str, features: dict[str, str]) -> float:
        return self.learner(valence).predict(skill, features)[0]

    def react(self, valence: int, t: float) -> dict[str, float]:
        causes = self.candidates(t)
        self.history.append((valence, causes))
        self._explain()
        weights = [self.p(valence, self.actions[i]["skill"], self.actions[i]["features"]) for i in causes]
        total = sum(weights) + self.background
        shares: dict[str, float] = {"(nothing I did)": self.background / total}
        for i, w in zip(causes, weights, strict=True):
            kind = self.actions[i]["kind"]
            shares[kind] = shares.get(kind, 0.0) + w / total
        return {k: round(v, 3) for k, v in shares.items()}

    def _explain(self) -> None:
        from birdbrain.rules import RuleLearner
        for _ in range(self.em_iterations):
            credit = {+1: [0.0] * len(self.actions), -1: [0.0] * len(self.actions)}
            for valence, causes in self.history:
                weights = [self.p(valence, self.actions[i]["skill"], self.actions[i]["features"]) for i in causes]
                total = sum(weights) + self.background
                for i, w in zip(causes, weights, strict=True):
                    credit[valence][i] += w / total
            for valence in (+1, -1):
                learner = RuleLearner(self.learner(valence).outcome, prior=(PRIOR_HIT, PRIOR_MISS))
                for i, a in enumerate(self.actions):
                    if a["ended"] or credit[valence][i] > 0:
                        learner.add(a["skill"], a["features"], min(1.0, credit[valence][i]))
                self._learners[valence] = learner

    def summary(self) -> dict[str, dict[str, float]]:
        """Per kind, for comparison with the kinds model: the mean predicted reaction over
        that kind's actions."""
        by_kind: dict[str, list[tuple[float, float]]] = {}
        for a in self.actions:
            if a["ended"]:
                by_kind.setdefault(a["kind"], []).append(
                    (self.p(1, a["skill"], a["features"]), self.p(-1, a["skill"], a["features"])))
        out = {}
        for kind, ps in sorted(by_kind.items()):
            up, down = sum(p for p, _ in ps) / len(ps), sum(q for _, q in ps) / len(ps)
            out[kind] = {"trials": len(ps), "p_approve": round(up, 3), "p_disapprove": round(down, 3),
                         "expected": round(up - down, 3)}
        return out

    def rules(self) -> list[str]:
        out = []
        for valence in (+1, -1):
            learner = self.learner(valence)
            out += [learner.text(r) for r in learner.rules()]
        return out

    def to_json(self) -> str:
        return json.dumps({"over": "conditions", "actions": self.actions, "history": self.history},
                          sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, text: str) -> ConditionReactionModel:
        raw: dict[str, Any] = json.loads(text)
        model = cls(actions=raw["actions"], history=[(int(v), [int(i) for i in c]) for v, c in raw["history"]])
        model._explain()
        return model
