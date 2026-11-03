"""Diagnostic: compare BirdBrain's perception with simulator truth (evaluation only).

Drives the duck with the local policy and, at every camera frame, measures
each sighting's localization error against the true object it came from
(using the lab's privileged `Detection.name`, which the mind never sees).
"""
import math
import sys
from collections import defaultdict

import numpy as np
from microduck_local.brain.brain_env import POLICIES_DIR, onnx_infer
from microduck_local.brain.runtime import Senses
from microduck_local.world import World, make_playroom

from birdbrain.lab import BirdBrainBrain, observation

seed, seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 1, float(sys.argv[2]) if len(sys.argv) > 2 else 60
sc = make_playroom(seed=seed, n=6, brain=None)
w = World(sc, infer_for={"d0": onnx_infer(POLICIES_DIR / "alpha_walking.onnx")}, seed=seed)
d = w.ducks["d0"]
brain = BirdBrainBrain()
mind = brain.mind
held_samples = []
errs = defaultdict(list)       # (cls, range bucket, moving) -> errors
last_frame = -1.0
start_pose = w.odom(d)
true_start = d.trunk_pos(w.data)[:2].copy()
while w.t < seconds:
    tof, tof_age = w.senses_tof(d)
    det = d.detector.last if d.detector is not None else None
    s = Senses(t=w.t, tof=tof, tof_age=tof_age, det=det, det_age=None if det is None else w.t - det.t,
               speed=d.heading_speed(w.data), odom=w.odom(d), holding=d.holding is not None,
               skill=d.skill, bumped=w.bumped(d))
    if det is not None and det.t > last_frame:
        last_frame = det.t
        obs = observation(s)
        pose = mind.perception._pose_at(det.t) if mind.perception._odom else obs.odom
        for dd, sg in zip(det.detections, obs.frame.sightings):
            if not dd.name:
                continue
            held = dd.name == d.holding
            body = w.model.body(dd.name).id if dd.cls == "toy" else None
            if dd.cls == "toy":
                truth = w.data.xpos[w.pickables[dd.name]][:2]
            elif dd.cls == "basket":
                truth = np.array(w.basket.pos)
            else:
                continue
            m = mind.perception.locate(sg, obs.frame, pose, mind.perception.still(det.t))
            if m is None:
                continue
            rng = math.hypot(truth[0] - pose[0], truth[1] - pose[1])
            err = math.hypot(m.x - truth[0], m.y - truth[1])
            if held and len(held_samples) < 400:
                held_samples.append((obs.frame.cam_pitch - sg.elevation, sg.bearing, mind.perception._looks_held(sg, obs.frame)))
            key = ("held" if held else dd.cls, min(int(rng / 0.4), 4), not mind.perception.still(det.t))
            errs[key].append((err, m.sigma, math.hypot(m.x - pose[0], m.y - pose[1]) - rng))
    intent = brain.step(s)
    w.apply_intent(d, intent)
    if d.skill is None:
        d.set_cmd(w.data, intent.twist, intent.head)
    w.step()
print("odom vs truth offset at start:", start_pose, true_start)
print("cls    range_m  moving   n  med_err  p90_err  med_sigma  med_err/sigma  med_range_bias")
for k in sorted(errs):
    e = np.array(errs[k])
    print(f"{k[0]:6s} {k[1]*0.4:.1f}-{k[1]*0.4+0.4:.1f}  {k[2]!s:5s} {len(e):4d}  {np.median(e[:,0]):.3f}    {np.percentile(e[:,0],90):.3f}    {np.median(e[:,1]):.3f}      {np.median(e[:,0]/e[:,1]):.2f}          {np.median(e[:,2]):+.3f}")
print("(a calibrated sigma gives med_err/sigma near 1.18)")
hs = np.array([(a, b, c) for a, b, c in held_samples]) if held_samples else None
if hs is not None: print("held sightings: depression pct 5/50/95", np.percentile(hs[:,0],[5,50,95]).round(2), "bearing pct", np.percentile(hs[:,1],[5,50,95]).round(2), "filtered", hs[:,2].mean().round(2))
from birdbrain.relations import known

kb = mind.kb
live = {c: [e for e in kb.of_class(c) if known(kb, w.t, e)] for c in ("toy", "basket")}
true = {n: w.data.xpos[b][:2] for n, b in w.pickables.items() if n != d.holding}
matched = sum(any(math.hypot(kb.position(e).x - p[0], kb.position(e).y - p[1]) < 0.12 for e in live["toy"]) for p in true.values())
phantom = sum(min(math.hypot(kb.position(e).x - p[0], kb.position(e).y - p[1]) for p in true.values()) > 0.12 for e in live["toy"])
print(f"end: confident toys {len(live['toy'])} (true {len(true)}, matched {matched}, phantoms {phantom}) · confident baskets {len(live['basket'])} · ids created {len(kb.of_class('toy'))}")
