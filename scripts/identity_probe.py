"""Diagnostic: why sightings start new entities (evaluation only, reads Detection.name).

For every entity creation, finds the existing entity that the same true object was last
attributed to and reports the gap: distance, Mahalanobis distance, sighting range, motion.
"""
import collections
import math
import sys

from microduck_local.brain.brain_env import POLICIES_DIR, onnx_infer
from microduck_local.brain.runtime import Senses
from microduck_local.world import World, make_playroom

from birdbrain.lab import BirdBrainBrain, observation

seed, seconds = int(sys.argv[1]), float(sys.argv[2])
sc = make_playroom(seed=seed, n=6, brain=None)
w = World(sc, infer_for={"d0": onnx_infer(POLICIES_DIR / "alpha_walking.onnx")}, seed=seed)
d = w.ducks["d0"]
brain = BirdBrainBrain()
mind, P, kb = brain.mind, brain.mind.perception, brain.mind.kb
owner = {}                    # true name -> entity it was last attributed to
reasons = collections.Counter()
last = -1.0
while w.t < seconds:
    tof, tof_age = w.senses_tof(d)
    det = d.detector.last
    s = Senses(t=w.t, tof=tof, tof_age=tof_age, det=det, det_age=None if det is None else w.t - det.t,
               speed=d.heading_speed(w.data), odom=w.odom(d), holding=d.holding is not None,
               skill=d.skill, bumped=w.bumped(d))
    fresh = det is not None and det.t > last
    before = set(kb.entities)
    pre = {e: P._predicted(e, det.t) for e in kb.entities} if fresh else {}
    intent = brain.step(s)
    if fresh:
        last = det.t
        view = P.last_view or {"sightings": []}
        for dd, seen in zip(det.detections, view["sightings"]):
            ent = seen.get("as")
            if not dd.name or not ent or ent.startswith(("held", "not")):
                continue
            prev = owner.get(dd.name)
            if ent not in before and prev is not None and pre.get(prev) is not None:
                obs = observation(s)
                sg = next(x for x in obs.frame.sightings if abs(x.bearing - dd.bearing) < 1e-9)
                m = P.locate(sg, obs.frame, P._pose_at(det.t), P.still(det.t))
                old = pre[prev]
                rng = math.hypot(m.x - s.odom[0], m.y - s.odom[1])
                d2 = old.mahalanobis2(m, P.p.gate_floor)
                conf = kb.get("at", prev).conf if kb.get("at", prev) else None
                why = ("gate" if d2 > P.p.gate_chi2 else "taken by another sighting" if prev in
                       [x.get("as") for x in view["sightings"]] else "excluded/held/other")
                reasons[why] += 1
                bx, by = w.basket.pos
                tp = w.data.xpos[w.pickables[dd.name]][:2] if dd.cls == "toy" else (bx, by)
                where = "in basket" if dd.cls == "toy" and w.in_basket(dd.name) else "near basket" if math.hypot(tp[0]-bx, tp[1]-by) < 0.35 else "open floor"
                reasons[where] += 1
                if sum(reasons.values()) <= 12:
                    print(f"t={w.t:5.1f} {dd.cls} {dd.name}: new {ent}, was {prev} | gap {old.distance(m):.2f} m "
                          f"d2 {d2:.1f} | range {rng:.2f} | sig old {old.sigma:.2f} new {m.sigma:.2f} | "
                          f"conf {conf} | still {P.still(det.t)} -> {why}")
            owner[dd.name] = kb.value("same_as", ent) or ent
    w.apply_intent(d, intent)
    if d.skill is None:
        d.set_cmd(w.data, intent.twist, intent.head)
    w.step()
print("why new entities were created for already-known objects:", dict(reasons))
print("entity ids:", {c: len(kb.of_class(c)) for c in ("toy", "basket")})
