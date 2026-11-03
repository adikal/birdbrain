import math

from birdbrain.kr import SELF, KnowledgeBase, Position, same_place


def test_tell_refreshes_same_fact_and_closes_changed_fact():
    events = []
    kb = KnowledgeBase(lambda kind, payload: events.append(kind))
    toy = kb.new_entity("toy", 0.0)
    first = kb.tell("at", (toy,), Position.round(1.0, 0.0, 0.02), t=1.0, same=same_place())
    again = kb.tell("at", (toy,), Position.round(1.01, 0.0, 0.02), t=2.0, same=same_place())
    assert again is first and first.t_obs == 2.0 and first.open
    moved = kb.tell("at", (toy,), Position.round(2.0, 0.0, 0.02), t=3.0, same=same_place())
    assert moved is not first and first.t_end == 3.0 and moved.t_start == 3.0
    assert kb.held_at("at", (toy,), 1.5) is first and kb.held_at("at", (toy,), 3.5) is moved
    assert events.count("ASSERTION_OPENED") == 2 and events.count("ASSERTION_CLOSED") == 1


def test_untell_and_events():
    kb = KnowledgeBase()
    kb.tell("holding", (SELF,), "toy#1", t=0.0)
    kb.untell("holding", (SELF,), t=1.0)
    assert kb.value("holding", SELF) is None
    event = kb.begin("action", 2.0, ["toy#1"], skill="pick")
    kb.end(event, 3.0, outcome="done")
    assert kb.find_events("action", "toy#1")[0].data["outcome"] == "done"


def test_fuse_matches_scalar_kalman_for_isotropic_estimates():
    a, b = Position.round(0.0, 0.0, 0.1), Position.round(1.0, 0.0, 0.2)
    fused = a.fuse(b)
    w = 0.1**2 / (0.1**2 + 0.2**2)
    assert math.isclose(fused.x, w * 1.0, rel_tol=1e-9)
    assert math.isclose(fused.sigma, math.sqrt(0.1**2 * 0.2**2 / (0.1**2 + 0.2**2)), rel_tol=1e-9)


def test_anisotropic_fusion_trusts_each_axis_separately():
    along_x = Position(0.0, 0.0, 1.0, 0.0, 1e-4)        # unsure in x, sure in y
    along_y = Position(1.0, 1.0, 1e-4, 0.0, 1.0)        # sure in x, unsure in y
    fused = along_x.fuse(along_y)
    assert abs(fused.x - 1.0) < 1e-3 and abs(fused.y) < 1e-3


def test_mahalanobis_gate_is_wider_along_the_uncertain_axis():
    p = Position(0.0, 0.0, 0.25, 0.0, 0.0001)
    assert p.mahalanobis2(Position.round(0.5, 0.0, 0.0)) < p.mahalanobis2(Position.round(0.0, 0.05, 0.0))
