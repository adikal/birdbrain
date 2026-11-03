"""Diagnostic for H-012: why pick decisions fail with "no longer where it was believed".

Evaluation only: reads simulator truth (`Detection.name`, true toy positions).
For each failed pick it reports which true toy the target entity stood for, how far
that toy truly moved during the approach, and what happened to its sightings in the
frames before the failure: not detected at all, detected and attributed to the
target, or detected and attributed to another entity.
"""
import collections
import math
import sys

from microduck_local.brain.brain_env import POLICIES_DIR, onnx_infer
from microduck_local.brain.runtime import Senses
from microduck_local.world import World, make_playroom

from birdbrain.lab import BirdBrainBrain

seeds = [int(s) for s in sys.argv[1].split(",")]
seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 300
summary = collections.Counter()
for seed in seeds:
    sc = make_playroom(seed=seed, n=6, brain=None)
    w = World(sc, infer_for={"d0": onnx_infer(POLICIES_DIR / "alpha_walking.onnx")}, seed=seed)
    d = w.ducks["d0"]
    events = []
    brain = BirdBrainBrain(log=lambda k, p, events=events, w=w: events.append((w.t, k, p)))
    mind, P = brain.mind, brain.mind.perception
    votes = collections.defaultdict(collections.Counter)    # entity -> true names attributed to it
    frames = collections.deque(maxlen=40)                   # recent (t, detected names, attributions)
    start = {}                                              # pick decision -> (target, true pos at start)
    last_det, seen = -1.0, 0
    while w.t < seconds:
        tof, tof_age = w.senses_tof(d)
        det = d.detector.last
        s = Senses(t=w.t, tof=tof, tof_age=tof_age, det=det, det_age=None if det is None else w.t - det.t,
                   speed=d.heading_speed(w.data), odom=w.odom(d), holding=d.holding is not None,
                   skill=d.skill, bumped=w.bumped(d))
        intent = brain.step(s)
        if det is not None and det.t > last_det and P.last_view and abs(P.last_view["t"] - det.t) < 1e-9:
            last_det = det.t
            attributions = {}
            for dd, sg in zip(det.detections, P.last_view["sightings"], strict=False):
                if dd.cls == "toy" and dd.name:
                    attributions[dd.name] = sg.get("as")
                    if sg.get("as", "").startswith("toy#"):
                        votes[sg["as"]][dd.name] += 1
            frames.append((det.t, attributions))
        for t, kind, p in events[seen:]:
            if kind == "DECISION" and p["skill"] == "pick":
                target = p["args"]["x"]
                name = votes[target].most_common(1)[0][0] if votes[target] else None
                pos = None if name is None else w.data.xpos[w.pickables[name]][:2].copy()
                start["current"] = (target, name, pos, t)
            elif kind == "OUTCOME" and p["skill"] == "pick" and p["status"] != "done":
                target, name, pos, t0 = start.get("current", (None, None, None, t))
                if "no longer" not in p["reason"]:
                    summary["other failure"] += 1
                    continue
                if name is None:
                    summary["target stood for no real toy"] += 1
                    continue
                moved = math.dist(pos, w.data.xpos[w.pickables[name]][:2])
                recent = [a for ft, a in frames if ft >= t - 3.0]
                detected = [a[name] for a in recent if name in a]
                if moved > 0.05:
                    why = "toy really moved"
                elif not detected:
                    why = "not detected in the last 3 s"
                elif all(x == target for x in detected):
                    why = "detected and attributed to the target"
                else:
                    why = "detected but attributed elsewhere"
                summary[why] += 1
                elsewhere = collections.Counter(x for x in detected if x != target)
                print(f"seed {seed} t={t:5.1f} {target} ({name}) moved {moved:.3f} m · frames 3 s {len(recent)} "
                      f"· detected {len(detected)} · elsewhere {dict(elsewhere)} -> {why}")
        seen = len(events)
        w.apply_intent(d, intent)
        if d.skill is None:
            d.set_cmd(w.data, intent.twist, intent.head)
        w.step()
print("summary:", dict(summary))
