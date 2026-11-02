import math

import mujoco
import pytest

from birdbrain.adapters import Action
from birdbrain.sim import MujocoMicroduckAdapter

EXPECTED_BODIES = {"microduck", "head", "left_foot", "right_foot"}
EXPECTED_ARENA_OBJECTS = {"blue_block", "red_ball"}


def test_microduck_model_contains_articulation_arena_and_sensors() -> None:
    adapter = MujocoMicroduckAdapter()

    body_names = {
        mujoco.mj_id2name(adapter.model, mujoco.mjtObj.mjOBJ_BODY, index)
        for index in range(adapter.model.nbody)
    }

    assert EXPECTED_BODIES <= body_names
    assert EXPECTED_ARENA_OBJECTS <= body_names
    assert adapter.model.nu == 5
    assert adapter.model.nsensor >= 7


def test_microduck_steps_headlessly_and_reports_named_objects() -> None:
    adapter = MujocoMicroduckAdapter(frame_skip=10)
    initial = adapter.reset(seed=7)
    observation = adapter.act(
        Action(
            "set_joint_targets",
            {"neck_motor": 0.25, "left_hip_motor": 0.1},
        )
    )

    assert observation.timestamp > initial.timestamp
    assert set(EXPECTED_ARENA_OBJECTS) <= observation.values.keys()
    assert observation.values["actuator_targets"]["neck_motor"] == pytest.approx(0.25)
    assert all(
        math.isfinite(value)
        for body in ("duck", "head", "blue_block", "red_ball")
        for value in observation.values[body]["position"]
    )


def test_seeded_object_placement_is_reproducible() -> None:
    adapter = MujocoMicroduckAdapter()

    first = adapter.reset(seed=42)
    second = adapter.reset(seed=42)

    assert first.values["blue_block"]["position"] == pytest.approx(
        second.values["blue_block"]["position"]
    )


def test_adapter_rejects_unknown_actuator() -> None:
    adapter = MujocoMicroduckAdapter()

    with pytest.raises(ValueError, match="unknown actuator"):
        adapter.act(Action("set_joint_targets", {"tail_motor": 0.5}))
