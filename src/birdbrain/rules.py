"""Causal rules learned from outcomes (Milestone 4, ledger E-017).

A rule says how a condition changes the chance of an outcome of a skill: "pick, when
the toy is by the basket rim: the odds that its expected effect holds fall 6-fold".
Conditions are discrete features of the situation when the action starts, computed
from beliefs (`features`).

For each skill and outcome the duck holds a Bayesian logistic model: the log-odds of
the outcome are a base rate plus one effect per condition that holds,

    logit p(outcome | skill, f) = b_skill + Σ_c w_skill,c (1[c holds in f] − mean_c),
    b ~ N(logit(prior rate), sd_base²),   w ~ N(0, sd_effect²),

fitted at its posterior mode (Newton's method) after each outcome, with a Laplace
approximation for each effect's uncertainty. The prior keeps every effect at zero
until the evidence moves it, so a skill with little experience predicts its base
rate, and a condition with little evidence changes little. A rule is *credible* when
a value's effect against the other values of its feature is at least
`CREDIBLE_SD` posterior standard deviations from zero. Effects are
estimated from every outcome of the skill at once, which matters in a life of a few
dozen picks: a tree that must split its data to find a condition rarely had enough
(ledger E-017, development). Outcomes may carry fractional weight.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from birdbrain.kr import SELF, KnowledgeBase
from birdbrain.relations import failures, seen_since, wall_distance, where

Features = dict[str, str]

#: A condition is a credible rule when its effect is this many posterior sds from zero:
#: three, since a skill is tested against a dozen or so conditions at once.
CREDIBLE_SD = 3.0


def features(kb: KnowledgeBase, t: float, args: dict[str, Any]) -> Features:
    """The situation as the duck believes it: its target (the first entity argument),
    itself, and the basket, each in a few coarse values."""
    out: Features = {}
    here = kb.position(SELF)
    baskets = [b for b in kb.of_class("basket") if kb.get("at", b) is not None]
    basket = max(baskets, key=lambda b: kb.get("at", b).conf, default=None)
    pb = None if basket is None else kb.position(basket)
    target = next((v for v in args.values() if isinstance(v, str) and kb.position(v) is not None), None)
    if target is not None:
        p = kb.position(target)
        out["target is"] = where(kb, t, target)
        out["target distance"] = _bin(None if here is None else here.distance(p), (0.6, 1.2), ("near", "mid", "far"))
        out["target position"] = "precise" if p.sigma < 0.05 else "vague"
        out["target last seen"] = "recently" if seen_since(kb, t, target) < 3.0 else "a while ago"
        out["target tried before"] = "yes" if failures(kb, t, "pick", target) else "no"
        out["target by the rim"] = _bin(None if pb is None else p.distance(pb), (0.35,), ("yes", "no"))
        out["target by a wall"] = _bin(wall_distance(kb, t, target), (0.3,), ("yes", "no"))
    out["holding"] = "yes" if kb.value("holding", SELF) is not None else "no"
    out["basket"] = "unknown" if pb is None else ("precise" if pb.sigma < 0.05 else "vague")
    out["basket distance"] = _bin(None if pb is None or here is None else here.distance(pb),
                                  (0.6, 1.5), ("near", "mid", "far"))
    out["self by a wall"] = _bin(wall_distance(kb, t, SELF), (0.4,), ("yes", "no"))
    return out


def _bin(x: float | None, edges: tuple[float, ...], names: tuple[str, ...]) -> str:
    if x is None or math.isinf(x):
        return "unknown"
    return next((n for e, n in zip(edges, names, strict=False) if x < e), names[-1])


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


@dataclass
class Model:
    """One skill's fitted model. Conditions are centred indicators: each weight is a
    deviation from the average situation the duck has met, and a feature not described
    counts as average. `cov` is the Laplace posterior covariance of the weights."""

    base: float
    keys: list[str]                                # "feature=value", in weight order
    w: np.ndarray
    cov: np.ndarray
    means: np.ndarray                              # how often each value held, among rows with the feature
    n: float

    def logit(self, f: Features) -> float:
        return self.base + float(self.w @ self.row(f))

    def row(self, f: Features) -> np.ndarray:
        x = np.zeros(len(self.keys))
        for i, key in enumerate(self.keys):
            feat, value = key.split("=", 1)
            if feat in f:
                x[i] = float(f[feat] == value) - self.means[i]
        return x

    def contrast(self, key: str) -> tuple[float, float]:
        """Effect on the log-odds of this value against the other values of its feature
        (weighted by how often they held), with its posterior sd."""
        feat = key.split("=", 1)[0]
        others = [i for i, k in enumerate(self.keys) if k.split("=", 1)[0] == feat and k != key]
        a = np.zeros(len(self.keys))
        a[self.keys.index(key)] = 1.0
        total = sum(self.means[i] for i in others)
        for i in others:
            a[i] = -self.means[i] / total if total > 0 else 0.0
        return float(a @ self.w), float(np.sqrt(max(a @ self.cov @ a, 0.0)))


@dataclass
class RuleLearner:
    """Rules for one outcome of every skill."""

    outcome: str                                  # e.g. "the expected effect held", "fell"
    prior: tuple[float, float] = (1.0, 1.0)       # Beta pseudo-counts: the prior base rate
    sd_base: float = 2.0
    sd_effect: float = 0.5
    examples: dict[str, list[tuple[Features, float, float]]] = field(default_factory=dict)  # skill -> (f, y, w)
    _models: dict[str, Model] = field(default_factory=dict)

    @property
    def prior_logit(self) -> float:
        a, b = self.prior
        return math.log(a / b)

    def add(self, skill: str, f: Features, y: float, w: float = 1.0) -> None:
        self.examples.setdefault(skill, []).append((dict(f), float(y), float(w)))
        self._models.pop(skill, None)

    def model(self, skill: str) -> Model:
        if skill not in self._models:
            self._models[skill] = self._fit(self.examples.get(skill, []))
        return self._models[skill]

    def predict(self, skill: str, f: Features) -> tuple[float, float, tuple]:
        """(probability of the outcome, trials behind it, the credible conditions that applied)."""
        m = self.model(skill)
        applied = tuple((k, v) for k, v in f.items() if f"{k}={v}" in m.keys and self._credible(m, f"{k}={v}"))
        return _sigmoid(m.logit(f)), m.n, applied

    @staticmethod
    def _credible(m: Model, key: str) -> bool:
        effect, sd = m.contrast(key)
        return sd > 0 and abs(effect) >= CREDIBLE_SD * sd

    def _fit(self, ex: list) -> Model:
        if not ex:
            return Model(self.prior_logit, [], np.zeros(0), np.zeros((0, 0)), np.zeros(0), 0.0)
        keys = sorted({f"{k}={v}" for f, _, _ in ex for k, v in f.items()})
        feats = [k.split("=", 1) for k in keys]
        weight = np.array([e[2] for e in ex])
        y = np.array([e[1] for e in ex])
        has = np.array([[feat in f for feat, _ in feats] for f, _, _ in ex], dtype=float)
        on = np.array([[f.get(feat) == value for feat, value in feats] for f, _, _ in ex], dtype=float)
        # Centred among the rows that describe the feature; rows that do not describe it
        # count as average, as in prediction.
        means = (weight @ on) / np.maximum(weight @ has, 1e-12)
        x = np.ones((len(ex), len(keys) + 1))
        x[:, 1:] = (on - means) * has
        mean0 = np.zeros(len(keys) + 1)
        mean0[0] = self.prior_logit
        precision = np.full(len(keys) + 1, 1.0 / self.sd_effect ** 2)
        precision[0] = 1.0 / self.sd_base ** 2

        def log_post(w: np.ndarray) -> float:
            z = x @ w
            return float(weight @ (y * z - np.logaddexp(0.0, z)) - 0.5 * precision @ (w - mean0) ** 2)

        w = mean0.copy()
        for _ in range(50):                       # damped Newton's method on the log posterior
            p = 1.0 / (1.0 + np.exp(-np.clip(x @ w, -30.0, 30.0)))
            grad = x.T @ (weight * (y - p)) - precision * (w - mean0)
            hess = (x * (weight * p * (1.0 - p))[:, None]).T @ x + np.diag(precision)
            step = np.linalg.solve(hess, grad)
            now, scale = log_post(w), 1.0
            while log_post(w + scale * step) < now and scale > 1e-4:
                scale /= 2.0
            w = w + scale * step
            if float(np.max(np.abs(scale * step))) < 1e-7:
                break
        p = 1.0 / (1.0 + np.exp(-np.clip(x @ w, -30.0, 30.0)))
        hess = (x * (weight * p * (1.0 - p))[:, None]).T @ x + np.diag(precision)
        cov = np.linalg.inv(hess)
        return Model(float(w[0]), keys, w[1:], cov[1:, 1:], means, float(weight.sum()))

    def rules(self) -> list[dict[str, Any]]:
        """Every credible condition of every skill, with its effect on the odds against
        the other values of the same feature."""
        out = []
        for skill in sorted(self.examples):
            m = self.model(skill)
            ex = self.examples[skill]
            effects = [(key, *m.contrast(key)) for key in m.keys]
            for key, effect, sd in sorted(effects, key=lambda e: -abs(e[1])):
                if not (sd > 0 and abs(effect) >= CREDIBLE_SD * sd):
                    continue
                feat, value = key.split("=", 1)
                under = [(y, w) for f, y, w in ex if f.get(feat) == value]
                out.append({"skill": skill, "when": f"{feat} {value}", "odds": round(math.exp(effect), 2),
                            "sd": round(sd, 2), "hits": round(sum(y * w for y, w in under), 1),
                            "n": round(sum(w for _, w in under), 1)})
        return out

    def text(self, rule: dict[str, Any]) -> str:
        change = f"{rule['odds']:.1f} times the odds" if rule["odds"] >= 1 else f"1/{1 / rule['odds']:.1f} the odds"
        return (f"{rule['skill']} when {rule['when']}: {change} that {self.outcome} "
                f"({rule['hits']:g} of {rule['n']:g})")

    def to_json(self) -> str:
        return json.dumps({"outcome": self.outcome, "examples": self.examples}, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, text: str, **kwargs: Any) -> RuleLearner:
        raw = json.loads(text)
        learner = cls(raw["outcome"], **kwargs)
        learner.examples = {k: [(dict(f), y, w) for f, y, w in v] for k, v in raw["examples"].items()}
        return learner
