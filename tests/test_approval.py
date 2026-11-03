"""Milestone 3b: the owner, the approval need, and learning what earns approval (ledger E-015)."""

import random

from birdbrain.body import Observation
from birdbrain.goals import approval_candidates
from birdbrain.kr import SELF, KnowledgeBase, Position
from birdbrain.mind import Mind
from birdbrain.needs import Needs
from birdbrain.owner import Owner, Room
from birdbrain.reactions import ReactionModel
from birdbrain.records import SkillRecord
from birdbrain.relations import near_wall, wall_spot, where

BOUNDS = (-1.5, -1.25, 1.5, 1.25)


def room(toys, in_basket=(), held=None):
    return Room(toys=toys, in_basket={t: t in in_basket for t in toys}, held=held, bounds=BOUNDS)


def run_owner(owner, states, until=12.0, dt=0.25):
    """Step the owner through room states (each held until the next start time)."""
    said, t, k = [], 0.0, 0
    while t <= until:
        while k + 1 < len(states) and states[k + 1][0] <= t:
            k += 1
        heard, _petted = owner.step(t, states[k][1], duck=(0.0, 0.0))
        said += heard
        t += dt
    return said


def test_the_owner_reacts_to_changes_she_cares_about_after_a_delay():
    owner = Owner("basket", seed=1, react_p=1.0, mishear_p=0.0)
    toys = {"t0": (0.5, 0.5)}
    said = run_owner(owner, [(0.0, room(toys)), (2.0, room(toys, in_basket={"t0"}))])
    assert len(said) == 1 and owner.phrases.valence(said[0]) == 1
    t_said = owner.log[0][0]
    assert 3.0 <= t_said <= 7.25                       # 1 to 5 s after the change at 2 s


def test_each_preference_judges_the_room_its_own_way():
    toys = {"t0": (1.4, 0.0), "t1": (0.0, 0.0)}        # t0 against a wall, t1 where it started
    r = room(toys)
    assert Owner("wall").satisfied(r) == 1
    leave = Owner("leave")
    leave.step(0.0, r, (0.0, 0.0))
    assert leave.satisfied(r) == 2
    assert leave.satisfied(room({"t0": (1.4, 0.0), "t1": (0.5, 0.0)})) == 1
    assert Owner("basket").satisfied(room(toys, in_basket={"t1"}, held="t1")) == 0   # a held toy is not in it


def test_some_reactions_are_misheard_and_she_stays_silent_on_what_she_ignores():
    owner = Owner("wall", seed=3, react_p=1.0, mishear_p=1.0)
    toys = {"t0": (0.0, 0.0)}
    said = run_owner(owner, [(0.0, room(toys)), (1.0, room({"t0": (1.4, 0.0)}))])
    assert [owner.phrases.valence(s) for s in said] == [-1]          # meant approval, heard otherwise
    quiet = Owner("wall", seed=3, react_p=1.0)
    assert run_owner(quiet, [(0.0, room(toys)), (1.0, room({"t0": (0.3, 0.0)}))]) == []


def test_credit_goes_to_the_kind_that_keeps_being_followed_by_approval():
    model = ReactionModel()
    t = 0.0
    for _ in range(12):
        model.started("deliver", t)
        model.moment(t + 8.0)                      # the toy drops into the basket
        model.ended("deliver", t + 10.0)
        model.started("look_around", t + 10.0)
        model.react(+1, t + 12.0)                  # her approval lands during the next action
        model.ended("look_around", t + 20.0)
        model.started("explore", t + 20.0)
        model.ended("explore", t + 30.0)           # looking and exploring also happen without her
        model.started("look_around", t + 30.0)
        model.ended("look_around", t + 40.0)
        t += 40.0
    assert model.belief("deliver").expected > 0.35          # some credit is lost to coincidence...
    assert model.belief("look_around").expected < 0.1      # ...but the coincident kind is explained away
    assert model.belief("explore").expected < 0.05


def test_a_reaction_is_credited_to_the_change_it_answers():
    """E-016: she disapproves of a grasp 2 s after it, while the put that follows is
    under way. Crediting actions under way (E-015) blames the put too; crediting the
    duck's own changes to the room blames only the pick."""
    shares = {}
    for credit in ("underway", "moments"):
        model = ReactionModel(credit=credit)
        model.started("pick from wall", 0.0)
        model.moment(9.5)                          # grasped
        model.ended("pick from wall", 10.0)
        model.started("put_by_wall", 10.0)
        shares[credit] = model.react(-1, 11.5)
        model.moment(25.0)                         # released, long after
        model.ended("put_by_wall", 28.0)
    assert shares["underway"].get("put_by_wall", 0) > 0.3
    assert "put_by_wall" not in shares["moments"] and shares["moments"]["pick from wall"] > 0.8


def test_an_action_that_changed_nothing_is_a_candidate_at_its_end():
    model = ReactionModel()
    model.started("rest", 0.0)
    model.ended("rest", 10.0)
    model.started("look_around", 10.0)
    assert "rest" in model.react(+1, 12.0) and "look_around" not in model.react(+1, 12.5)


def test_the_approval_need_moves_with_her_reactions_and_relaxes():
    kb = KnowledgeBase()
    needs = Needs(social="approval")
    needs.update(kb, 0.0, moving=False, resting=False, exploring=False, fell=False)
    assert needs.pressure["approval"] == 0.25 and "tidiness" not in needs.pressure
    needs.hear(+1)
    needs.update(kb, 0.1, moving=False, resting=False, exploring=False, fell=False)
    assert needs.pressure["approval"] < 0.15
    needs.update(kb, 1000.0, moving=False, resting=False, exploring=False, fell=False)
    assert abs(needs.pressure["approval"] - 0.25) < 0.01


def test_approval_is_worth_more_when_she_is_displeased_than_when_delighted():
    """Valence depends on the creature's state (review of E-015; Bennett's affect)."""
    needs = Needs(social="approval")
    neutral = needs.approval_value(1.0, 0.0)
    needs.mood = 0.9
    delighted = needs.approval_value(1.0, 0.0)
    needs.mood = -0.6
    displeased = needs.approval_value(1.0, 0.0)
    assert displeased > neutral > delighted > 0
    needs.mood = 0.0
    assert needs.approval_value(0.0, 1.0) < -neutral            # her displeasure weighs more


def test_one_pet_at_a_time():
    owner = Owner("basket", seed=0, react_p=1.0, pet_p=1.0, position=(0.0, 0.0))
    toys = {"t0": (0.5, 0.5), "t1": (0.6, 0.5)}
    pets, t = [], 0.0
    while t <= 12.0:
        r = room(toys) if t < 1.0 else room(toys, in_basket={"t0", "t1"})
        pets.append(owner.step(t, r, duck=(0.0, 0.0))[1])
        t += 0.25
    assert sum(pets) == 2 == sum(1 for *_, said in owner.log if said == "pet")


def test_draws_last_while_the_duck_holds_a_toy():
    mind = Mind(needs="approval", room=BOUNDS)
    first = mind._thompson_draws()
    first["deliver"] = (0.9, 0.0)
    mind.kb.tell("holding", (SELF,), "toy#1", t=0.0)
    assert mind._thompson_draws() is first
    mind.kb.untell("holding", (SELF,), t=1.0)
    assert mind._thompson_draws() == {}


def test_kind_records_persist_across_episodes(tmp_path):
    from birdbrain.records import SkillRecord
    mind = Mind(needs="approval", room=BOUNDS, memory_dir=tmp_path)
    mind.kind_records["pick from wall"] = SkillRecord(trials=4, effect_held=1, done=1, seconds=40.0, falls=2)
    mind.close()
    again = Mind(needs="approval", room=BOUNDS, memory_dir=tmp_path)
    assert again.kind_records["pick from wall"].falls == 2


def test_the_analysis_names_the_kind_a_belief_singles_out():
    import importlib.util
    import pathlib
    path = pathlib.Path(__file__).parents[1] / "scripts" / "lifetimes.py"
    spec = importlib.util.spec_from_file_location("lifetimes", path)
    lifetimes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lifetimes)
    model = {"deliver": {"expected": 0.3}, "pick from open": {"expected": -0.2}, "drop": {"expected": 0.0}}
    assert lifetimes.singles_out(model, "top", "deliver")
    assert lifetimes.singles_out(model, "bottom", "pick from")
    assert not lifetimes.singles_out(model, "top", "put_by_wall")


def kb_with_toy(at=(0.5, 0.0)):
    kb = KnowledgeBase()
    kb.tell("at", (SELF,), Position.round(0.0, 0.0, 0.01), t=0.0)
    kb.tell("bounds", (SELF,), BOUNDS, t=0.0)
    basket = kb.new_entity("basket", 0.0)
    kb.tell("at", (basket,), Position.round(1.15, 0.9, 0.02), t=0.0, conf=0.99)
    toy = kb.new_entity("toy", 0.0)
    kb.tell("at", (toy,), Position.round(*at, 0.02), t=0.0, conf=0.99)
    return kb, basket, toy


def test_walls_give_places_and_descriptions():
    kb, _basket, toy = kb_with_toy((0.5, -1.1))
    assert where(kb, 0.0, toy) == "wall" and near_wall(kb, 0.0, toy)
    spot = wall_spot(kb, 0.0, SELF)
    p = kb.position(spot)
    assert min(p.x - BOUNDS[0], BOUNDS[2] - p.x, p.y - BOUNDS[1], BOUNDS[3] - p.y) < 0.3
    assert ((p.x - 1.15) ** 2 + (p.y - 0.9) ** 2) ** 0.5 > 0.5          # never at the basket


def test_learned_disapproval_of_picking_stops_picks_and_approval_of_a_put_starts_them():
    kb, _, _toy = kb_with_toy()
    tools = {"pick", "deliver", "put_by_wall", "drop", "look_around", "explore", "rest"}
    needs = Needs(social="approval")
    needs._explored_t = 1.0                            # just explored: curiosity is satisfied
    needs.update(kb, 1.0, moving=False, resting=False, exploring=False, fell=False)

    def model(kind, valence, n=30):
        m = ReactionModel()
        for k in range(n):
            m.started(kind, 10.0 * k)
            m.ended(kind, 10.0 * k + 5.0)
            m.react(valence, 10.0 * k + 6.0)
        for other in ("deliver", "put_by_wall", "drop", "rest", "look_around", "explore", "pick from open"):
            for k in range(n):
                m.started(other, 1000.0 + 10.0 * k)
                m.ended(other, 1005.0 + 10.0 * k)
        return m

    # Picks and deliveries that usually work, as measured over a life.
    records = {s: SkillRecord(trials=20, effect_held=16, done=16, seconds=300.0) for s in ("pick", "deliver")}

    def top(m):
        rng = random.Random(0)
        picks = 0
        for _ in range(50):
            goals = approval_candidates(kb, 1.0, needs, records, m, tools, rng)
            picks += goals[0].kind == "pick"
        return picks

    assert top(model("pick from open", -1)) == 0
    assert top(model("deliver", +1)) >= 45


def test_the_mind_hears_phrases_and_credits_them():
    log = []
    mind = Mind(needs="approval", room=BOUNDS, log=lambda k, p: log.append((k, p)))
    assert "tidiness" not in mind.briefing() and "basket" not in mind.goal
    for k in range(200):
        heard = ("Well done!",) if k == 150 else ()
        mind.step(Observation(t=k * 0.02, odom=(0.0, 0.0, 0.0), speed=0.0, holding=False, reflex=None,
                              bumped=False, heard=heard))
    heard = [p for k, p in log if k == "HEARD"]
    assert heard and heard[0]["valence"] == 1 and mind.stats["approvals"] == 1
    assert mind.needs.mood > 0 and sum(heard[0]["causes"].values()) > 0.99


def test_owner_beliefs_persist_across_episodes(tmp_path):
    mind = Mind(needs="approval", room=BOUNDS, memory_dir=tmp_path)
    mind.reactions.started("deliver", 0.0)
    mind.reactions.ended("deliver", 5.0)
    mind.reactions.react(+1, 6.0)
    mind.close()
    again = Mind(needs="approval", room=BOUNDS, memory_dir=tmp_path)
    assert again.reactions.belief("deliver").approved > 0.8
