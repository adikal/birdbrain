"""Milestone 3: needs, goals and the scorecard (ledger E-014)."""

from birdbrain.goals import candidates
from birdbrain.kr import SELF, KnowledgeBase, Position
from birdbrain.mind import Choice, Mind
from birdbrain.needs import Needs
from birdbrain.records import SkillRecord
from birdbrain.relations import inside

TOOLS = {"pick", "deliver", "look_around", "explore", "rest"}


def room(toys=((1.0, 0.0), (2.0, 0.0)), toy_sigma=0.02):
    kb = KnowledgeBase()
    kb.tell("at", (SELF,), Position.round(0.0, 0.0, 0.01), t=0.0)
    kb.tell("heading", (SELF,), 0.0, t=0.0)
    basket = kb.new_entity("basket", 0.0)
    kb.tell("at", (basket,), Position.round(0.0, 1.0, 0.02), t=0.0, conf=0.99)
    ids = []
    for x, y in toys:
        toy = kb.new_entity("toy", 0.0)
        kb.tell("at", (toy,), Position.round(x, y, toy_sigma), t=0.0, conf=0.99)
        ids.append(toy)
    return kb, basket, ids


def needs_at(kb, t=1.0, **state):
    needs = Needs()
    for name, value in state.items():
        setattr(needs, name, value)
    needs.update(kb, t, moving=False, resting=False, exploring=False, fell=False)
    return needs


def test_battery_drains_with_activity_and_recharges_with_rest():
    kb, _, _ = room()
    needs = Needs()
    needs.update(kb, 0.0, moving=True, resting=False, exploring=False, fell=False)
    needs.update(kb, 100.0, moving=True, resting=False, exploring=False, fell=False)
    assert abs(needs.battery - 0.75) < 1e-9
    needs.update(kb, 110.0, moving=False, resting=True, exploring=False, fell=False)
    assert abs(needs.battery - 1.0) < 1e-9
    assert needs.pressure["tidiness"] == 2.0          # both known toys are outside the basket


def test_nearer_toy_ranks_first():
    kb, _, (near, far) = room()
    goals = candidates(kb, 1.0, needs_at(kb), {}, TOOLS)
    tidy = [g.id for g in goals if g.kind == "tidy"]
    assert tidy == [f"tidy:{near}", f"tidy:{far}"]


def test_one_fall_does_not_stop_tidying():
    """Round 1 of E-014: one fall in one trial read as a 33% risk and the duck never tidied again."""
    kb, _, _ = room()
    records = {"deliver": SkillRecord(trials=1, effect_held=0, seconds=20.0, falls=1)}
    needs = needs_at(kb, safety_level=0.6, _explored_t=1.0)
    goals = candidates(kb, 1.0, needs, records, TOOLS)
    assert goals[0].kind == "tidy"


def test_rest_gets_no_value_from_the_safety_need():
    kb, _, _ = room(toys=())
    goals = {g.id: g for g in candidates(kb, 1.0, needs_at(kb, safety_level=0.9), {}, TOOLS)}
    assert goals["rest"].terms["dV"] == 0.0             # a full battery: nothing to recharge


def test_each_way_of_exploring_habituates_on_its_own():
    kb, _, _ = room(toys=())
    needs = needs_at(kb)
    explore = next(g for g in candidates(kb, 1.0, needs, {}, TOOLS) if g.kind == "explore")
    assert explore.tools[0][0] == "look_around"        # cheaper while both are untried
    for _ in range(4):
        needs.observe_exploration("look_around", 0)
    explore = next(g for g in candidates(kb, 1.0, needs, {}, TOOLS) if g.kind == "explore")
    assert explore.tools[0][0] == "explore"


def test_inside_allows_for_uncertainty_but_not_for_distance():
    kb, basket, (rim, vague, far) = room(toys=((0.17, 1.0), (0.3, 1.0), (0.6, 1.0)), toy_sigma=0.02)
    kb.tell("at", (vague,), Position.round(0.3, 1.0, 0.08), t=0.0, conf=0.99)
    assert inside(kb, 0.0, rim, basket)                # within the margin of the rim
    assert inside(kb, 0.0, vague, basket)              # might be inside: leave it be
    assert not inside(kb, 0.0, far, basket)


def test_cloud_action_must_serve_a_candidate_goal():
    """A toy believed in the basket serves no goal, so it is not offered and picking it is
    rejected; a mislabelled goal is corrected to the goal the action serves."""
    from birdbrain.body import Observation

    def run(toy_at):
        log = []

        class Scripted:
            name = "s"

            def choose(self, request):
                return Choice("pick", {"x": "toy#1"}, "?", provider="s", goal="explore")

        mind = Mind(provider=Scripted(), needs=True, log=lambda k, p: log.append((k, p)))
        basket = mind.kb.new_entity("basket", 0.0)
        mind.kb.tell("at", (basket,), Position.round(1.0, 0.0, 0.02), t=0.0, conf=0.99)
        toy = mind.kb.new_entity("toy", 0.0)
        mind.kb.tell("at", (toy,), Position.round(*toy_at, 0.02), t=0.0, conf=0.99)
        mind.step(Observation(t=0.0, odom=(0.0, 0.0, 0.0), speed=0.0, holding=False, reflex=None, bumped=False))
        offered = any("toy#1" in t.params.get("x", []) for t in mind.request().tools)
        return log, next(p for k, p in log if k == "DECISION"), offered

    log, decision, offered = run((1.0, 0.05))              # in the basket
    assert not offered
    problems = [p["problem"] for k, p in log if k == "CHOICE_REJECTED"]
    assert problems == ["'pick' is not an available tool"]          # no goal is served by picking
    assert decision["provider"] == "local"
    log, decision, offered = run((0.5, 0.5))               # outside it
    assert offered
    assert decision["provider"] == "s" and decision["goal"] == "tidy:toy#1"
