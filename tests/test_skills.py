import pytest

from birdbrain.body import Observation
from birdbrain.expr import Evaluator
from birdbrain.kr import SELF, KnowledgeBase, Position
from birdbrain.skills import DONE, FAILED, TIMEOUT, Context, Library, start


def make_ctx():
    kb = KnowledgeBase()
    kb.tell("at", (SELF,), Position.round(0.0, 0.0, 0.01), t=0.0)
    kb.tell("heading", (SELF,), 0.0, t=0.0)
    log = []
    ctx = Context(kb, Evaluator(kb, {"toy", "basket"}), log=lambda k, p: log.append((k, p)))
    ctx.observe(Observation(t=0.0, odom=(0.0, 0.0, 0.0), speed=0.0, holding=False, reflex=None, bumped=False))
    return ctx, log


def drive(ctx, run, dt=0.02, limit=10_000):
    """Advance a skill run tick by tick, as the mind does."""
    commands = []
    for _ in range(limit):
        try:
            commands.append(next(run))
        except StopIteration as stop:
            return stop.value, commands
        obs = ctx.obs
        ctx.observe(Observation(t=obs.t + dt, odom=obs.odom, speed=0.0, holding=obs.holding,
                                reflex=None, bumped=False))
    raise AssertionError("skill did not terminate")


def program(body, budget=30, params=None):
    return {"doc": "test", "params": params or {}, "budget": budget, "body": body}


def test_sequence_runs_steps_in_order():
    ctx, log = make_ctx()
    lib = Library({"two": program([{"call": "stand", "args": {"seconds": 0.1}},
                                   {"call": "stand", "args": {"seconds": 0.2}}])})
    outcome, commands = drive(ctx, start(ctx, lib, "two", {}))
    assert outcome.status == DONE and 14 <= len(commands) <= 16
    assert [p["path"] for k, p in log if k == "SKILL_STEP_STARTED"] == ["two[0]", "two[1]"]


def test_if_bind_and_repeat_with_until():
    ctx, _ = make_ctx()
    toy = ctx.kb.new_entity("toy", 0.0)
    ctx.kb.tell("at", (toy,), Position.round(0.5, 0.0, 0.02), t=0.0)
    lib = Library({"loop": program([
        {"bind": "x", "to": "nearest(toy)"},
        {"if": "x is none", "then": [{"call": "require", "args": {"condition": "false"}}]},
        {"repeat": [{"call": "stand", "args": {"seconds": 0.05}}], "until": "false", "max": 3}])})
    outcome, _ = drive(ctx, start(ctx, lib, "loop", {}))
    assert outcome.status == FAILED and "after 3 iterations" in outcome.reason


def test_until_on_a_call_stops_it_early():
    ctx, _ = make_ctx()
    lib = Library({"wait": program([{"call": "stand", "args": {"seconds": 5}, "until": "holding(self)"}])})
    run = start(ctx, lib, "wait", {})
    next(run)
    ctx.kb.tell("holding", (SELF,), "toy#9", t=0.02)
    outcome, commands = drive(ctx, run)
    assert outcome.status == DONE and len(commands) <= 2


def test_timeout_budget_and_on_fail():
    ctx, _ = make_ctx()
    lib = Library({
        "slow": program([{"call": "stand", "args": {"seconds": 5}, "timeout": 0.2}]),
        "rescued": program([{"call": "stand", "args": {"seconds": 5}, "timeout": 0.2, "on_fail": []}]),
        "over": program([{"call": "stand", "args": {"seconds": 5}}], budget=0.3),
    })
    assert drive(ctx, start(ctx, lib, "slow", {}))[0].status == TIMEOUT
    assert drive(ctx, start(ctx, lib, "rescued", {}))[0].status == DONE
    assert drive(ctx, start(ctx, lib, "over", {}))[0].status == TIMEOUT


def test_recursion_is_bounded():
    ctx, _ = make_ctx()
    lib = Library({"forever": program([{"call": "forever"}])})
    outcome, _ = drive(ctx, start(ctx, lib, "forever", {}))
    assert outcome.status == FAILED and "recursion" in outcome.reason


def test_compound_runs_are_recorded_as_action_events():
    ctx, _ = make_ctx()
    lib = Library({"noop": program([{"call": "stand", "args": {"seconds": 0.05}}])})
    drive(ctx, start(ctx, lib, "noop", {}))
    (event,) = ctx.kb.find_events("action")
    assert event.data["skill"] == "noop" and event.data["outcome"] == DONE and event.t1 is not None


@pytest.mark.parametrize("bad", [
    [{"call": "no_such_skill"}],
    [{"repeat": [], "until": "true"}],
    [{"call": "stand", "if": "true"}],
    [{"call": "stand", "until": "__import__('os')"}],
])
def test_invalid_programs_are_rejected(bad):
    with pytest.raises(ValueError):
        Library({"bad": program(bad)})


def test_builtin_library_loads_and_checks():
    lib = Library()
    assert {"pick", "deliver", "look_around", "explore", "rest", "tidy_room", "back_off"} <= set(lib.skills)
    assert lib["pick"].params == {"x": "toy"} and lib["pick"].expect == "holding(self, x)"
