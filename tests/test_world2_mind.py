"""The mind's World 2 mechanisms (ledger E-022 to E-033), and its known defects.

Known defects are strict expected failures that fail on their assertion (`raises=
AssertionError`): if one starts to pass, or fails for another reason, the suite says so.
"""

import math
import types

import numpy as np
import pytest

from birdbrain.body import MICRODUCK, Frame, Observation, Sighting
from birdbrain.goals import approval_candidates
from birdbrain.kr import SELF, KnowledgeBase, Position
from birdbrain.mind import Mind
from birdbrain.needs import Needs
from birdbrain.occupancy import CELL, OccupancyMap, cell_of
from birdbrain.perception import Perception
from birdbrain.reactions import ConditionReactionModel, ReactionModel
from birdbrain.records import SkillRecord
from birdbrain.rules import RuleLearner, features


def observe(mind, t, reflex=None):
    return mind.step(Observation(t=t, odom=(0.0, 0.0, 0.0), speed=0.0, holding=False, reflex=reflex, bumped=False))


def toy(mind, x, y=0.0, colour=None, size=0.04):
    e = mind.kb.new_entity("toy", 0.0)
    mind.kb.tell("at", (e,), Position.round(x, y, 0.02), t=0.0, conf=1.0)
    if colour:
        mind.kb.tell("color", (e,), colour, t=0.0)
    mind.kb.tell("size", (e,), size, t=0.0)
    return e


def teach(mind, target, works, n=30, skill="pick"):
    f = features(mind.kb, mind.ctx.t, {"x": target})
    for _ in range(n):
        mind.rules["effect"].add(skill, f, works)


# -- reconsidering a pick (E-023, E-024) ------------------------------------------------

def test_a_pick_is_stopped_on_the_way_when_a_credible_rule_turns_against_it():
    mind = Mind()
    observe(mind, 0.0)
    bad, good = toy(mind, 1.5, colour="black"), toy(mind, 1.6, y=0.3, colour="red")
    teach(mind, bad, 0.0)
    teach(mind, good, 1.0)
    choice = mind.local.choose(mind.request())
    assert choice.args == {"x": good}                      # the good one first
    mind._start("pick", {"x": bad}, choice, None, mind.request())   # as if chosen before the rule
    mind._reconsider(1.0)
    assert mind._action is None and mind.stats.get("reconsidered") == 1
    assert mind.records.get("pick") is None                # a stop is no trial of the skill


def test_no_pick_is_stopped_once_the_pick_reflex_is_asked_for():
    mind = Mind()
    observe(mind, 0.0)
    bad, _good = toy(mind, 1.5, colour="black"), toy(mind, 1.6, y=0.3, colour="red")
    teach(mind, bad, 0.0)
    mind._start("pick", {"x": bad}, mind.local.choose(mind.request()), None, mind.request())
    mind._action["reflexed"] = True
    mind._reconsider(1.0)
    assert mind._action is not None


def test_with_an_owner_a_pick_stops_when_the_toy_is_seen_to_be_another_colour():
    mind = Mind(needs="approval", room=(-2.0, -2.0, 2.0, 2.0))
    observe(mind, 0.0)
    t = toy(mind, 1.0)                                      # colour not yet seen
    from birdbrain.mind import Choice
    mind._start("pick", {"x": t}, Choice("pick", {"x": t}, "test"), None, mind.request())
    assert mind._action["kind"] == "pick from open"
    mind.kb.tell("color", (t,), "blue", t=0.5)
    mind._reconsider(1.0)
    assert mind._action is None


# -- a stopped action teaches the owner model nothing (E-024, E-025 review) ---------------

@pytest.mark.parametrize("model", [ReactionModel, ConditionReactionModel])
def test_a_stopped_action_is_neither_a_trial_nor_a_cause(model):
    m = model()
    m.started("pick from open", 0.0, skill="pick", features={})
    m.ended("pick from open", 1.0, counted=False)
    assert m.candidates(3.0) == []
    if model is ReactionModel:
        assert m.belief("pick from open").trials == 0


# -- the owner's reactions priced once (E-027) ---------------------------------------------

def test_a_pick_is_worth_its_own_reaction_plus_the_chance_it_works_times_the_put():
    kb = KnowledgeBase()
    kb.tell("at", (SELF,), Position.round(0.0, 0.0, 0.01), t=0.0)
    e = kb.new_entity("toy", 0.0)
    kb.tell("at", (e,), Position.round(0.5, 0.0, 0.02), t=0.0, conf=1.0)
    needs = Needs(social="approval")
    needs.update(kb, 1.0, moving=False, resting=False, exploring=False, fell=False)
    reaction = {"pick": (0.0, 0.2), "deliver": (0.6, 0.0)}

    def owner(skill, args):
        up, down = reaction.get(skill, (0.0, 0.0))
        return up, down, 0.0
    records = {"pick": SkillRecord(trials=10, effect_held=5, done=5, seconds=100.0),
               "deliver": SkillRecord(trials=10, effect_held=8, done=8, seconds=100.0)}
    goals = approval_candidates(kb, 1.0, needs, records, {"pick", "deliver"}, owner)
    pick = next(g for g in goals if g.kind == "pick")
    expected = needs.approval_value(0.0, 0.2) + 0.5 * needs.approval_value(0.6, 0.0)
    assert math.isclose(pick.terms["dV"], expected, rel_tol=1e-9)


# -- appearance (E-023) ------------------------------------------------------------------

def test_an_object_is_sized_by_the_median_of_its_sightings_and_coloured_by_the_majority():
    kb = KnowledgeBase()
    p = Perception(kb)
    p._odom.append((0.0, (0.0, 0.0, 0.0)))
    e = kb.new_entity("toy", 0.0)
    m = Position.round(1.0, 0.0, 0.02)
    frame = Frame(0.0, (), 0.24, 0.0, 0.0)
    slant = math.hypot(1.0 - MICRODUCK.cam_ahead, 0.24 - MICRODUCK.class_height["toy"])
    for k, (size, colour) in enumerate([(0.06, "red"), (0.06, "red"), (0.2, "blue"), (0.06, "red")]):
        s = Sighting("toy", 0.0, -0.2, 2 * math.atan(size / 2 / slant), 0.9, colour)
        p._appearance(e, s, m, Frame(k * 0.1, (), frame.cam_z, 0.0, 0.0), (0.0, 0.0, 0.0))
    assert abs(kb.value("size", e) - 0.06) < 0.002 and kb.value("color", e) == "red"


# -- strong effects believed (E-026) -----------------------------------------------------

def _two_colours(learner, black=(0, 10), red=(8, 10)):
    for hits, n in (black, red):
        colour = "black" if (hits, n) == black else "red"
        for k in range(n):
            learner.add("pick", {"target colour": colour}, float(k < hits))
    return learner.model("pick").contrast("target colour=black")


def test_the_cauchy_prior_lets_a_strong_effect_be_stronger_than_the_normal_prior_does():
    cauchy, _ = _two_colours(RuleLearner("works"))
    normal, _ = _two_colours(RuleLearner("works", effect_prior="gaussian"))
    assert cauchy < normal < 0


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="known (H-024): the fit stops at the symmetric split of a feature's collinear "
                          "indicators, a saddle point; the mode's contrast is near -3.9")
def test_the_cauchy_fit_reaches_the_mode():
    contrast, _ = _two_colours(RuleLearner("works"))
    assert contrast < -3.5


# -- the map (E-030, E-031): known defects ----------------------------------------------

def _wall(m, x, y0, y1):
    k = 0
    while y0 + k * CELL <= y1 + 1e-9:
        m._add(cell_of(x, y0 + k * CELL), 4.0)
        k += 1


def _seen_floor(m, x0, x1, y0, y1):
    for i in range(math.floor(x0 / CELL), math.floor(x1 / CELL) + 1):
        for j in range(math.floor(y0 / CELL), math.floor(y1 / CELL) + 1):
            if (i, j) not in m.occupied_cells:
                m._add((i, j), -2.0)


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="known (E-035 review): the frontier has no exemption round the duck, so beside a "
                          "wall exploring falls back to wandering")
def test_the_frontier_is_found_from_beside_a_wall():
    m = OccupancyMap()
    _wall(m, 0.0, -2.0, 2.0)
    _seen_floor(m, 0.1, 1.5, -1.0, 1.0)
    assert m.frontier((0.15, 0.05)) is not None


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="known (E-035 review): a credible rule about the situation (here: the basket "
                          "unknown) makes every toy a poor prospect at once")
def test_a_rule_about_the_situation_does_not_defer_every_toy():
    mind = Mind()
    observe(mind, 0.0)
    a, b = toy(mind, 0.5, colour="red"), toy(mind, 0.6, y=0.3, colour="green")
    for basket, works in (("unknown", 0.0), ("precise", 1.0)):
        for _ in range(30):
            mind.rules["effect"].add("deliver", {"holding": "yes", "basket": basket}, works)
    assert not (mind.local.worth(a)[1] and mind.local.worth(b)[1])


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="known (E-034 review): routing round a mapped obstacle drops the detour round the "
                          "basket, whose low rim is not on the map")
def test_a_routed_walk_still_keeps_clear_of_the_basket(monkeypatch):
    from birdbrain import skills
    from birdbrain.expr import Evaluator
    kb = KnowledgeBase()
    kb.tell("at", (SELF,), Position.round(0.0, 0.0, 0.01), t=0.0)
    kb.tell("heading", (SELF,), 0.0, t=0.0)
    goal, basket = kb.new_entity("toy", 0.0), kb.new_entity("basket", 0.0)
    kb.tell("at", (goal,), Position.round(2.0, 0.0, 0.02), t=0.0, conf=1.0)
    kb.tell("at", (basket,), Position.round(0.5, 0.4, 0.02), t=0.0, conf=1.0)
    m = OccupancyMap()
    _wall(m, 1.0, -0.5, 0.5)                                   # a box straight ahead: the walk is routed
    asked = []
    real = skills._detour_point
    monkeypatch.setattr(skills, "_detour_point", lambda *a: asked.append(a) or real(*a))
    ctx = skills.Context(kb, Evaluator(kb, {"toy", "basket"}), map=m)
    ctx.observe(Observation(t=0.0, odom=(0.0, 0.0, 0.0), speed=0.0, holding=False, reflex=None, bumped=False))
    next(skills.walk_toward(ctx, goal, avoid=basket, avoid_r=0.4))
    assert asked                                               # the basket is considered on the way


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="known (E-034 review): map occlusion ignores height, so a low box hides what the "
                          "camera sees over it")
def test_a_low_box_does_not_hide_a_toy_the_camera_sees_over():
    kb = KnowledgeBase()
    p = Perception(kb)
    p._odom.append((0.0, (0.0, 0.0, 0.0)))
    kb.tell("at", (SELF,), Position.round(0.0, 0.0, 0.01), t=0.0)
    t = kb.new_entity("toy", 0.0)
    kb.tell("at", (t,), Position.round(1.5, 0.0, 0.02), t=0.0, conf=1.0)
    kb.tell("size", (t,), 0.09, t=0.0)                     # a stick: wide enough to see at 1.5 m
    frame = Frame(0.0, (), 0.24, math.atan2(0.225, 1.5 - MICRODUCK.cam_ahead), 0.0)
    p.map.odds.clear()
    p.map.occupied_cells.clear()
    assert p._should_see(t, frame, (0.0, 0.0, 0.0))          # in view with nothing mapped
    p.map._add(cell_of(0.6, 0.0), 4.0)                     # something low, 0.6 m ahead (a 7 cm box)
    assert p._should_see(t, frame, (0.0, 0.0, 0.0))


# -- World 2's truth measures (world code) -------------------------------------------------

def test_world2_measures_count_from_truth():
    from birdbrain import world2
    kinds = {"t0": world2.KINDS["black cube"], "t1": world2.KINDS["red big"], "t2": world2.KINDS["blue block"]}
    xpos = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
    world = types.SimpleNamespace(pickables={"t0": 0, "t1": 1, "t2": 2}, data=types.SimpleNamespace(xpos=xpos),
                                  in_basket=lambda n: n == "t0", ducks={"d0": types.SimpleNamespace(holding=None)})
    rules = types.SimpleNamespace(kind=kinds, refused=2, slipped=1, falls_holding={"heavy": 1},
                                  grasped={"heavy": 1})
    kb = KnowledgeBase()
    e = kb.new_entity("toy", 0.0)
    kb.tell("at", (e,), Position.round(0.0, 1.05, 0.02), t=0.0, conf=1.0)    # t1 is known, t2 is not
    out = world2.measures(world, kb, rules, {"t0": (1.0, 0.0), "t1": (0.0, 1.0), "t2": (-1.0, 0.3)})
    assert out["w2_heavy_in"] == 1 and out["w2_possible_n"] == 2 and out["w2_impossible_n"] == 1
    assert out["w2_unfound"] == 1 and out["hers_n"] == 1 and out["hers_moved"] == 1
    assert out["w2_refused"] == 2 and out["w2_falls_holding_heavy"] == 1
