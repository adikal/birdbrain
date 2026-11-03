"""Diagnostic: context of each fall (truth): distance to the basket rim and to the nearest toy."""
import math
import sys
from collections import deque

from microduck_local.brain.brain_env import POLICIES_DIR, onnx_infer
from microduck_local.brain.runtime import Senses
from microduck_local.world import World, make_playroom

from birdbrain.lab import BirdBrainBrain

for seed in map(int, sys.argv[1].split(",")):
    sc = make_playroom(seed=seed, n=6, brain=None)
    w = World(sc, infer_for={"d0": onnx_infer(POLICIES_DIR / "alpha_walking.onnx")}, seed=seed)
    d = w.ducks["d0"]
    brain = BirdBrainBrain()
    hist = deque(maxlen=150)
    falls = 0
    while w.t < float(sys.argv[2]):
        tof, tof_age = w.senses_tof(d)
        det = d.detector.last if d.detector is not None else None
        s = Senses(t=w.t, tof=tof, tof_age=tof_age, det=det, det_age=None if det is None else w.t - det.t,
                   speed=d.heading_speed(w.data), odom=w.odom(d), holding=d.holding is not None,
                   skill=d.skill, bumped=w.bumped(d))
        intent = brain.step(s)
        p = d.trunk_pos(w.data)
        bx, by = w.basket.pos
        rim = max(abs(p[0] - bx), abs(p[1] - by)) - 0.15
        toy = min(math.hypot(*(w.data.xpos[b][:2] - p[:2])) for b in w.pickables.values())
        hist.append((round(w.t, 2), intent.note, [round(v, 2) for v in intent.twist], round(rim, 2), round(toy, 2), round(float(p[2]), 3)))
        w.apply_intent(d, intent)
        if d.skill is None:
            d.set_cmd(w.data, intent.twist, intent.head)
        w.step()
        if d.falls > falls:
            falls = d.falls
            print(f"seed {seed} FALL #{falls} at t={w.t:.1f}")
            for h in list(hist)[::15]:
                print("   ", h)
