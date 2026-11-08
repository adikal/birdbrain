import random
import types

from conftest import needs_lab

from birdbrain import world2
from birdbrain.owner import PREFERENCES, Room


def test_kinds_follow_their_appearance_and_development_keeps_every_colour_and_shape():
    kinds = world2.KINDS
    assert len(kinds) == 24 and sum(k.held_out for k in kinds.values()) == 8
    dev = [kinds[k] for k in world2.DEV_KINDS]
    assert {k.colour for k in dev} == set(world2.COLOURS)
    assert {k.shape for k in dev} == set(world2.SHAPES)
    for k in kinds.values():
        assert k.heavy == (k.colour == "black") and k.slippery == (k.colour == "white")
        assert k.too_wide == (k.shape == "big")
    assert world2.kinds_for("late", 10) == world2.DEV_KINDS
    assert world2.kinds_for("late", 11) == world2.ALL_KINDS


def test_the_colour_sensor_reads_colour_only_for_objects_within_range():
    near = types.SimpleNamespace(cls="toy", name="t0", range_est=0.5, color=None)
    far = types.SimpleNamespace(cls="toy", name="t1", range_est=1.5, color=None)
    ghost = types.SimpleNamespace(cls="toy", name="", range_est=0.3, color=None)
    import dataclasses

    @dataclasses.dataclass
    class D:
        cls: str
        name: str
        range_est: float
        color: str | None

    @dataclasses.dataclass
    class F:
        detections: list

    frame = F([D(**vars(d)) for d in (near, far, ghost)])
    kinds = {"t0": world2.KINDS["red cube"], "t1": world2.KINDS["red cube"]}
    seen = [world2.colour_sensor(frame, kinds, random.Random(s)).detections for s in range(200)]
    assert all(d[1].color is None for d in seen)                 # too far to say
    assert all(d[2].color is not None for d in seen)             # a ghost is given a colour too
    right = sum(d[0].color == "red" for d in seen) / len(seen)
    assert 0.9 < right <= 1.0
    assert frame.detections[0].color is None            # the lab's frame is not changed


def test_her_things_are_to_be_left_and_the_rest_put_away():
    hers = PREFERENCES["hers"]
    room = Room(toys={"a": (0.0, 0.0), "b": (1.0, 1.0)}, in_basket={"a": False, "b": False}, held=None,
                bounds=(-2, -2, 2, 2), colours={"a": "blue", "b": "red"})
    start = {"a": (0.0, 0.05), "b": (1.0, 1.0)}
    assert hers(room, "a", start, 0.2) and not hers(room, "b", start, 0.2)


@needs_lab
def test_a_world2_room_builds_and_a_wide_object_is_not_held():
    from microduck_local.brain.brain_env import POLICIES_DIR, onnx_infer
    from microduck_local.world import World
    world2.register()
    world2.register()                                     # idempotent
    sc = world2.make_world(3, world2.ALL_KINDS)
    assert sc == world2.make_world(3, world2.ALL_KINDS)  # deterministic in the seed
    w = World(sc, infer_for={"d0": onnx_infer(POLICIES_DIR / "alpha_walking.onnx")}, seed=3)
    duck = w.ducks["d0"]
    rules = world2.WorldRules(w, duck, 3)
    wide = next((n for n, k in rules.kind.items() if k.too_wide), None)
    if wide is not None:
        duck.holding = wide
        w.release = lambda d: setattr(d, "holding", None)
        rules.step(0.02)
        assert duck.holding is None and rules.refused == 1
