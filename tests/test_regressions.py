"""Regression tests for the bugs found in review (ledger E-011)."""
import json
import math
import threading
import urllib.error
import urllib.request

import pytest
from test_perception import sighting_of
from test_skills import drive, make_ctx, program

from birdbrain.body import Frame, Observation
from birdbrain.evaluation import load, t975
from birdbrain.kr import SELF, KnowledgeBase, Position
from birdbrain.mind import Mind
from birdbrain.perception import Perception
from birdbrain.skills import FAILED, INTERRUPTED, Library


def obs(t, frame=None, holding=False, odom=(0.0, 0.0, 0.0)):
    return Observation(t, odom, 0.0, holding, None, False, frame=frame)


def test_two_toys_in_one_frame_stay_two_beliefs():
    kb = KnowledgeBase()
    perception = Perception(kb)
    for gap in (0.04, 0.08, 0.12):
        kb.__init__()
        perception.__init__(kb)
        a, frame = sighting_of(0.6, -gap / 2, 0.015, (0.0, 0.0, 0.0))
        b, _ = sighting_of(0.6, gap / 2, 0.015, (0.0, 0.0, 0.0))
        for k in range(5):
            perception.update(obs(k * 0.1, Frame(k * 0.1, (a, b), frame.cam_z, frame.cam_pitch, 0.0)))
        believed = [e for e in kb.of_class("toy") if kb.position(e) is not None]
        assert len(believed) == 2, f"gap {gap}"


def test_a_grasp_only_claims_a_toy_within_reach():
    kb = KnowledgeBase()
    perception = Perception(kb)
    far = kb.new_entity("toy", 0.0)
    kb.tell("at", (far,), Position.round(0.75, 0.0, 0.02), t=0.0)
    perception.update(obs(0.0))
    perception.update(obs(0.02, holding=True))
    assert kb.position(far) is not None                    # the far toy keeps its place
    assert kb.value("holding", SELF) not in (None, far)    # something new is in the beak


def test_local_policy_never_crashes_on_a_reduced_tool_set():
    mind = Mind(tools=("pick", "deliver"))
    command = mind.step(obs(0.0))
    assert command.twist == (0.0, 0.0, 0.0)


def test_unbound_names_and_unknown_arguments_are_rejected_at_load():
    with pytest.raises(ValueError, match="unbound"):
        Library({"typo": program([{"if": "holdng_flag", "then": []}])})
    with pytest.raises(ValueError, match="no parameter"):
        Library({"typo": program([{"call": "stand", "args": {"secnds": 1}}])})


def test_a_runtime_expression_error_fails_the_skill_not_the_mind():
    ctx, _ = make_ctx()
    lib = Library({"bad": program([{"call": "stand", "args": {"seconds": "distance(self, 'toy#99') + 'x'"}}])})
    from birdbrain.skills import start
    outcome, _ = drive(ctx, start(ctx, lib, "bad", {}))
    assert outcome.status == FAILED


def test_children_stopped_by_their_caller_are_interrupted_not_failed():
    ctx, _ = make_ctx()
    lib = Library({"inner": program([{"call": "stand", "args": {"seconds": 5}}]),
                   "outer": program([{"call": "inner", "until": "holding(self)"}])})
    from birdbrain.skills import start
    run = start(ctx, lib, "outer", {})
    next(run)
    ctx.kb.tell("holding", (SELF,), "toy#1", t=0.02)
    drive(ctx, run)
    inner = next(e for e in ctx.kb.find_events("action") if e.data["skill"] == "inner")
    assert inner.data["outcome"] == INTERRUPTED


def test_timeouts_count_toward_giving_up():
    from birdbrain.relations import failures
    kb = KnowledgeBase()
    for outcome in ("timeout", "failed", "interrupted", "done"):
        e = kb.begin("action", 0.0, ["toy#1"], skill="pick")
        kb.end(e, 1.0, outcome=outcome)
    assert failures(kb, 1.0, "pick", "toy#1") == 2


def test_real_latency_is_charged_even_when_the_cloud_fails():
    from birdbrain.mind import ProviderError

    class Slow:
        name = "slow"
        def choose(self, request):
            raise ProviderError("timeout", latency_s=1.0)

    mind = Mind(provider=Slow(), latency="real")
    notes = [mind.step(obs(k * 0.02)).note for k in range(10)]
    assert all(n == "waiting for the cloud brain" for n in notes[:5])


def test_derived_places_stay_out_of_the_briefing():
    mind = Mind()
    mind.step(obs(0.0))
    toy, basket = mind.kb.new_entity("toy", 0.0), mind.kb.new_entity("basket", 0.0)
    mind.kb.tell("at", (toy,), Position.round(0.5, 0.0, 0.02), t=0.0)
    mind.kb.tell("at", (basket,), Position.round(1.0, 0.0, 0.02), t=0.0)
    place = mind.ctx.evaluator.eval("beyond(x, basket, 0.45)", {"x": toy}, 0.0)
    assert place in mind.kb.entities and place not in mind.briefing()
    assert mind.ctx.evaluator.eval("beyond(x, basket, 0.45)", {"x": None}, 0.0) is None


def test_a_static_basket_keeps_its_place_against_a_far_outlier():
    kb = KnowledgeBase()
    perception = Perception(kb)
    s, frame = sighting_of(0.5, 0.0, 0.08, (0.0, 0.0, 0.0), cls="basket")
    for k in range(5):
        perception.update(obs(k * 0.1, Frame(k * 0.1, (s,), frame.cam_z, frame.cam_pitch, 0.0)))
    basket = kb.of_class("basket")[0]
    # 60 s later, from 2 m away, a sighting that says the basket is 0.6 m closer than it is.
    pose = (-1.9, 0.0, 0.0)
    wrong, f2 = sighting_of(-0.1, 0.0, 0.08, pose, cls="basket")
    perception.update(obs(60.0, odom=pose))
    perception.update(obs(60.1, Frame(60.1, (wrong,), f2.cam_z, f2.cam_pitch, 0.0), odom=pose))
    assert kb.position(basket).distance(Position.round(0.5, 0.0, 0.0)) < 0.15
    assert len([e for e in kb.of_class("basket") if kb.get("at", e) and kb.get("at", e).conf >= 0.5]) == 1


def test_t_quantile_is_conservative_between_table_entries():
    assert t975(21) == pytest.approx(2.086) and t975(16) == pytest.approx(2.120)


def test_duplicate_seeds_in_one_arm_are_an_error(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text(json.dumps({"seed": 1, "inBasket": 4}) + "\n" + json.dumps({"seed": 1, "inBasket": 5}) + "\n")
    with pytest.raises(ValueError, match="more than once"):
        load(path)


def test_store_writes_summaries_at_boundaries_and_reads_while_running(tmp_path):
    from birdbrain.observability import EventJournal, JsonlRunStore
    store = JsonlRunStore(tmp_path, summary_every=3)
    journal = EventJournal(run_id="r1", store=store)
    journal.publish("RUN_STARTED", sim_time=0.0, payload={"seed": 1})
    for k in range(4):
        journal.publish("TICK", sim_time=k, payload={})
    assert [e["type"] for e in store.read_events("r1")][:2] == ["RUN_STARTED", "TICK"]
    assert store.get_summary("r1")["status"] == "running"
    journal.publish("RUN_STOPPED", sim_time=5.0, payload={"result": {"inBasket": 3}})
    summary = json.loads((tmp_path / "r1" / "summary.json").read_text())
    assert summary["status"] == "completed" and summary["result"] == {"inBasket": 3}
    assert summary["event_count"] == 6


def test_server_rejects_foreign_host_headers(tmp_path):
    from pathlib import Path

    from birdbrain.observability import JsonlRunStore
    from birdbrain.observability.server import DashboardServer
    dashboard = Path(__file__).resolve().parents[1] / "dashboard"
    server = DashboardServer(("127.0.0.1", 0), dashboard, JsonlRunStore(tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        assert urllib.request.urlopen(base + "/api/status").status == 200
        request = urllib.request.Request(base + "/api/status", headers={"Host": "evil.example:80"})
        with pytest.raises(urllib.error.HTTPError) as info:
            urllib.request.urlopen(request)
        assert info.value.code == 421
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "/api/runs/r1/camera/../../x.jpg")
        with pytest.raises(ValueError):
            DashboardServer(("0.0.0.0", 0), dashboard, JsonlRunStore(tmp_path))
    finally:
        server.shutdown()
        server.server_close()
    assert math.isfinite(1.0)
