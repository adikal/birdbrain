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


def features(kb: KnowledgeBase, t: float, args: dict[str, Any], held: str | None = None) -> Features:
    """The situation as the duck believes it: its target (the first entity argument),
    what it holds, itself, and the basket, each in a few coarse values. `held` asks
    about a situation in which the duck holds that object (to judge a pick by how its
    delivery would go)."""
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
        out["target from the wall"] = _bin(wall_distance(kb, t, target), (0.1, 0.2, 0.3, 0.5),
                                           ("under 0.1 m", "0.1 to 0.2 m", "0.2 to 0.3 m", "0.3 to 0.5 m",
                                            "over 0.5 m"))
        out.update(_looks(kb, target, "target"))
    holding = held if held is not None else kb.value("holding", SELF)
    out["holding"] = "yes" if holding is not None else "no"
    if holding is not None:
        out.update(_looks(kb, holding, "held"))
    out["basket"] = "unknown" if pb is None else ("precise" if pb.sigma < 0.05 else "vague")
    out["basket distance"] = _bin(None if pb is None or here is None else here.distance(pb),
                                  (0.6, 1.5), ("near", "mid", "far"))
    out["self by a wall"] = _bin(wall_distance(kb, t, SELF), (0.4,), ("yes", "no"))
    return out


def _looks(kb: KnowledgeBase, x: str, role: str) -> Features:
    """How an object looks (ledger E-023): its colour, and its size in coarse bins."""
    return {f"{role} colour": kb.value("color", x, default="unknown"),
            f"{role} size": _bin(kb.value("size", x), (0.03, 0.05, 0.075),
                                 ("under 3 cm", "3 to 5 cm", "5 to 7.5 cm", "over 7.5 cm"))}


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
    counts as average. `full_cov` is the Laplace posterior covariance of (base, weights)."""

    base: float
    keys: list[str]                                # "feature=value", in weight order
    w: np.ndarray
    full_cov: np.ndarray
    means: np.ndarray                              # how often each value held, among rows with the feature
    n: float

    @property
    def cov(self) -> np.ndarray:
        return self.full_cov[1:, 1:]

    def logit_sd(self, f: Features) -> float:
        """Posterior sd of the log-odds in situation `f`."""
        a = np.concatenate(([1.0], self.row(f)))
        return float(np.sqrt(max(a @ self.full_cov @ a, 0.0)))

    def draw(self, rng: np.random.Generator) -> Model:
        """One model drawn from the Laplace posterior (Thompson sampling, ledger E-018)."""
        theta = rng.multivariate_normal(np.concatenate(([self.base], self.w)), self.full_cov, method="cholesky")
        return Model(float(theta[0]), self.keys, theta[1:], self.full_cov, self.means, self.n)

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
    #: The prior on each condition's effect: "gaussian" (sd `sd_effect`), or "cauchy",
    #: heavy-tailed with the same curvature at zero, so a weak effect is shrunk as much
    #: and a strong one much less (ledger E-026).
    effect_prior: str = "cauchy"
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

    def against(self, skill: str, applied: tuple, sign: int) -> bool:
        """Some of the `applied` credible conditions moves the outcome's odds in the
        direction of `sign` (+1 up, -1 down)."""
        m = self.model(skill)
        return any(sign * m.contrast(f"{k}={v}")[0] > 0 for k, v in applied)

    @staticmethod
    def _credible(m: Model, key: str) -> bool:
        effect, sd = m.contrast(key)
        return sd > 0 and abs(effect) >= CREDIBLE_SD * sd

    def _fit(self, ex: list) -> Model:
        if not ex:
            return Model(self.prior_logit, [], np.zeros(0), np.array([[self.sd_base ** 2]]), np.zeros(0), 0.0)
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
        cauchy = self.effect_prior == "cauchy"
        scale2 = 2.0 * self.sd_effect ** 2         # Cauchy scale with the Gaussian's curvature at zero
        base_precision = 1.0 / self.sd_base ** 2

        def precisions(w: np.ndarray) -> np.ndarray:
            """Prior precision of each weight. For the Cauchy prior, the precision of the
            Gaussian that bounds it at `w` (a scale mixture, iterated to the mode)."""
            out = (2.0 / (scale2 + w ** 2)) if cauchy else np.full(len(w), 1.0 / self.sd_effect ** 2)
            out[0] = base_precision
            return out

        def log_prior(w: np.ndarray) -> float:
            d = w - mean0
            if cauchy:
                return float(-0.5 * base_precision * d[0] ** 2 - np.sum(np.log1p(d[1:] ** 2 / scale2)))
            return float(-0.5 * precisions(w) @ d ** 2)

        def log_post(w: np.ndarray) -> float:
            z = x @ w
            return float(weight @ (y * z - np.logaddexp(0.0, z))) + log_prior(w)

        w = mean0.copy()
        for _ in range(50):                       # damped Newton's method on the log posterior
            precision = precisions(w)
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
        hess = (x * (weight * p * (1.0 - p))[:, None]).T @ x + np.diag(precisions(w))
        cov = np.linalg.inv(hess)
        cov = (cov + cov.T) / 2.0
        return Model(float(w[0]), keys, w[1:], cov, means, float(weight.sum()))

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
                out.append({"skill": skill, "when": f"{feat} {value}", "odds": float(f"{math.exp(effect):.3g}"),
                            "sd": round(sd, 2), "hits": round(sum(y * w for y, w in under), 1),
                            "n": round(sum(w for _, w in under), 1)})
        return out

    def text(self, rule: dict[str, Any]) -> str:
        change = (f"{rule['odds']:.3g} times the odds" if rule["odds"] >= 1
                  else f"1/{1 / rule['odds']:.3g} the odds")
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
