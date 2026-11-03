"""Diagnostic: detection probability of toys and the basket by distance, head pose, and motion.

Evaluation only. For every camera frame and every true object inside the camera's
field of view (by truth geometry), records whether the detector reported it.
"""
import collections
import math
import sys

import mujoco
import numpy as np
from microduck_local.brain.brain_env import POLICIES_DIR, onnx_infer
from microduck_local.brain.runtime import Senses
from microduck_local.world import World, make_playroom

from birdbrain.lab import BirdBrainBrain

table = collections.defaultdict(lambda: [0, 0])
for seed in [int(s) for s in sys.argv[1].split(",")]:
    sc = make_playroom(seed=seed, n=6, brain=None)
    w = World(sc, infer_for={"d0": onnx_infer(POLICIES_DIR / "alpha_walking.onnx")}, seed=seed)
    d = w.ducks["d0"]
    brain = BirdBrainBrain()
    spec = d.detector.spec
    hf, vf = math.radians(spec.fov_h_deg) / 2, math.radians(spec.fov_v_deg) / 2
    last = -1.0
    while w.t < float(sys.argv[2]):
        tof, tof_age = w.senses_tof(d)
        det = d.detector.last
        s = Senses(t=w.t, tof=tof, tof_age=tof_age, det=det, det_age=None if det is None else w.t - det.t,
                   speed=d.heading_speed(w.data), odom=w.odom(d), holding=d.holding is not None,
                   skill=d.skill, bumped=w.bumped(d))
        intent = brain.step(s)
        if det is not None and det.t > last and len(det.cam_pose) == 7:
            last = det.t
            x, y, z, qw, qx, qy, qz = det.cam_pose
            R = np.zeros(9)
            mujoco.mju_quat2Mat(R, np.array([qw, qx, qy, qz]))
            R = R.reshape(3, 3)
            seen = {dd.name for dd in det.detections}
            moving = abs(s.speed) > 0.05
            head_down = intent.head[1] > 0.3
            targets = [(n, w.data.xpos[b], "toy") for n, b in w.pickables.items() if n != d.holding and not w.in_basket(n)]
            targets.append(("basket", np.array([*w.basket.pos, 0.08]), "basket"))
            for name, p, cls in targets:
                local = R.T @ (np.asarray(p) - np.array([x, y, z]))
                if local[0] <= 0.05:
                    continue
                if abs(math.atan2(local[1], local[0])) > hf - 0.05 or abs(math.atan2(local[2], math.hypot(local[0], local[1]))) > vf - 0.05:
                    continue
                rng = float(np.hypot(local[0], local[1]))
                key = (cls, min(int(rng / 0.25), 7), moving, head_down)
                table[key][0] += 1
                table[key][1] += name in seen
        w.apply_intent(d, intent)
        if d.skill is None:
            d.set_cmd(w.data, intent.twist, intent.head)
        w.step()
print("cls     range_m     moving head_down   in_view  detected  rate")
for k in sorted(table):
    n, hit = table[k]
    if n >= 15:
        print(f"{k[0]:6s}  {k[1]*0.25:.2f}-{k[1]*0.25+0.25:.2f}   {k[2]!s:5s}  {k[3]!s:5s}     {n:6d}  {hit:6d}   {hit/n:.2f}")
