import dataclasses
import types

import numpy as np
from conftest import needs_lab


def test_observation_drops_the_true_identity_of_detections():
    from birdbrain.body import Sighting
    from birdbrain.lab import observation
    det = types.SimpleNamespace(cls="toy", name="t3", bearing=0.1, elevation=-0.5, width=0.03,
                                range_est=0.5, conf=0.9, color=None)
    frame = types.SimpleNamespace(t=1.0, detections=[det], cam_z=0.2, cam_pitch=0.6, cam_yaw=0.0)
    senses = types.SimpleNamespace(t=1.0, odom=(0.0, 0.0, 0.0), speed=0.0, holding=False, skill=None,
                                   bumped=False, det=frame, tof=None)
    obs = observation(senses)
    assert len(obs.frame.sightings) == 1
    assert "name" not in {f.name for f in dataclasses.fields(Sighting)}
    assert "t3" not in repr(obs)


def test_mind_modules_never_import_the_simulator():
    import ast
    import pathlib

    import birdbrain
    root = pathlib.Path(birdbrain.__file__).parent
    # Adapters, evaluation and world code, never the mind.
    allowed = {"lab.py", "run.py", "record.py", "camera.py", "world2.py"}
    for path in root.rglob("*.py"):
        if path.name in allowed:
            continue
        tree = ast.parse(path.read_text())
        imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        # World code holds truth the mind must not see: the world itself, and the owner's preference.
        assert not any(m.startswith(("microduck_local", "mujoco", "birdbrain.world2", "birdbrain.owner"))
                       for m in imported), path


@needs_lab
def test_a_short_playroom_run_reads_only_senses():
    from microduck_local.brain.runtime import REGISTRY, attach_world

    from birdbrain.lab import BirdBrainBrain, register
    from birdbrain.run import run_one
    register()
    brain = REGISTRY.make("birdbrain")
    assert isinstance(brain, BirdBrainBrain)
    attach_world(brain, object(), "d0")
    assert not hasattr(brain, "world") and not hasattr(brain, "robot_id")
    row = run_one(1, seconds=20)
    assert row["decisions"] >= 1 and row["invalid"] == 0 and np.isfinite(row["simSeconds"])
