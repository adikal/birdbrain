"""Milestone 4: causal rules learned from outcomes (ledger E-017)."""

import random

from birdbrain.kr import SELF, KnowledgeBase, Position
from birdbrain.mind import Mind
from birdbrain.rules import RuleLearner, features

BOUNDS = (-1.5, -1.25, 1.5, 1.25)


def teach(learner, n, rate_by_value, feature="target by a wall", seed=0, noise_features=3):
    rng = random.Random(seed)
    for _ in range(n):
        value = rng.choice(sorted(rate_by_value))
        f = {feature: value, **{f"noise {k}": rng.choice("ab") for k in range(noise_features)}}
        learner.add("pick", f, float(rng.random() < rate_by_value[value]))


def credible(learner, skill="pick"):
    return {r["when"] for r in learner.rules() if r["skill"] == skill}


def test_a_condition_that_matters_becomes_a_credible_rule():
    learner = RuleLearner("its expected effect holds")
    teach(learner, 80, {"yes": 0.3, "no": 0.9})
    near, _, when = learner.predict("pick", {"target by a wall": "yes"})
    far, _, _ = learner.predict("pick", {"target by a wall": "no"})
    assert near < 0.5 and far > 0.7 and ("target by a wall", "yes") in when
    assert credible(learner) <= {"target by a wall yes", "target by a wall no"} and credible(learner)
    rule = next(r for r in learner.rules() if r["when"] == "target by a wall yes")
    assert learner.text(rule).startswith("pick when target by a wall yes: 1/")


def test_conditions_that_do_not_matter_stay_out_of_the_rules():
    learner = RuleLearner("its expected effect holds")
    teach(learner, 200, {"yes": 0.7, "no": 0.7}, noise_features=6)
    assert not credible(learner)
    assert abs(learner.predict("pick", {"target by a wall": "yes"})[0] - 0.7) < 0.1


def test_little_evidence_predicts_the_prior_and_moves_little():
    learner = RuleLearner("the duck falls", prior=(0.25, 9.75), sd_base=1.0)
    assert abs(learner.predict("pick", {})[0] - 0.025) < 1e-9
    teach(learner, 6, {"yes": 1.0, "no": 0.0})
    assert learner.predict("pick", {"target by a wall": "yes"})[0] < 0.5       # six trials are not a law
    teach(learner, 60, {"yes": 0.5, "no": 0.0}, seed=1)
    rate = learner.predict("pick", {"target by a wall": "yes"})[0]
    assert "target by a wall yes" in credible(learner) and 0.25 < rate < 0.7


def test_soft_outcomes_and_persistence():
    learner = RuleLearner("approved")
    for k in range(40):
        learner.add("deliver", {"x": "a" if k % 2 else "b"}, 1.0 if k % 2 else 0.0, w=0.5)
    again = RuleLearner.from_json(learner.to_json())
    assert again.predict("deliver", {"x": "a"})[0] == learner.predict("deliver", {"x": "a"})[0]
    assert again.predict("deliver", {"x": "a"})[0] > 0.6 and again.predict("deliver", {"x": "b"})[0] < 0.4


def test_features_describe_the_situation_from_beliefs():
    kb = KnowledgeBase()
    kb.tell("at", (SELF,), Position.round(0.0, 0.0, 0.01), t=0.0)
    kb.tell("bounds", (SELF,), BOUNDS, t=0.0)
    basket = kb.new_entity("basket", 0.0)
    kb.tell("at", (basket,), Position.round(1.15, 0.9, 0.02), t=0.0, conf=0.99)
    toy = kb.new_entity("toy", 0.0)
    kb.tell("at", (toy,), Position.round(1.0, 0.7, 0.02), t=0.0, conf=0.99)
    f = features(kb, 1.0, {"x": toy})
    assert f["target by the rim"] == "yes" and f["target distance"] == "far" and f["holding"] == "no"
    assert features(kb, 1.0, {})["basket"] == "precise" and "target is" not in features(kb, 1.0, {})


def test_every_action_is_predicted_before_it_runs_and_scored_after():
    mind = Mind(provider=None)
    log = []
    mind.log = lambda k, p: log.append((k, p))
    t = 0.0
    from birdbrain.body import Observation
    while not any(k == "OUTCOME" for k, _ in log):
        mind.step(Observation(t=t, odom=(0.0, 0.0, 0.0), speed=0.0, holding=False, reflex=None, bumped=False))
        t += 0.02
    decision = next(p for k, p in log if k == "DECISION")
    outcome = next(p for k, p in log if k == "OUTCOME")
    assert set(decision["predicted"]) == {"effect", "fell"} and "brier" in outcome
    assert mind.stats["brier_fell_n"] == 1 and "brier_effect_n" not in mind.stats   # rest cannot fail
    assert mind.rules["fell"].examples and not mind.rules["effect"].examples


def test_an_interrupted_action_is_neither_scored_nor_learned():
    mind = Mind(provider=None)
    from birdbrain.body import Observation
    mind.step(Observation(t=0.0, odom=(0.0, 0.0, 0.0), speed=0.0, holding=False, reflex=None, bumped=False))
    mind.close()                                                # the episode ends mid-action
    assert "brier_fell_n" not in mind.stats and not mind.rules["fell"].examples


def test_a_moderate_effect_is_recovered_as_a_contrast():
    """Review of E-017: per-value effects of a centred feature cannot become credible;
    the contrast against the other values can, and it estimates the odds ratio."""
    rng = random.Random(1)
    learner = RuleLearner("its expected effect holds")
    for _ in range(1000):
        rim = rng.random() < 0.3
        learner.add("pick", {"rim": "yes" if rim else "no"}, float(rng.random() < (0.35 if rim else 0.65)))
    rule = next(r for r in learner.rules() if r["when"] == "rim yes")
    assert 0.25 < rule["odds"] < 0.4                             # true odds ratio 0.29
