"""Diagnostic: for every pick decision, compare the believed target with simulator truth."""
import math
import sys

from microduck_local.brain.brain_env import POLICIES_DIR, onnx_infer
from microduck_local.brain.runtime import Senses
from microduck_local.world import World, make_playroom

from birdbrain.lab import BirdBrainBrain

seed, seconds = int(sys.argv[1]), float(sys.argv[2])
sc = make_playroom(seed=seed, n=6, brain=None)
w = World(sc, infer_for={"d0": onnx_infer(POLICIES_DIR / "alpha_walking.onnx")}, seed=seed)
d = w.ducks["d0"]
events = []
brain = BirdBrainBrain(log=lambda k, p: events.append((w.t, k, p)))
kb = brain.mind.kb
seen = 0
def truth():
    return {n: (w.data.xpos[b][:2].copy(), w.in_basket(n)) for n, b in w.pickables.items()}
while w.t < seconds:
    tof, tof_age = w.senses_tof(d)
    det = d.detector.last if d.detector is not None else None
    s = Senses(t=w.t, tof=tof, tof_age=tof_age, det=det, det_age=None if det is None else w.t - det.t,
               speed=d.heading_speed(w.data), odom=w.odom(d), holding=d.holding is not None,
               skill=d.skill, bumped=w.bumped(d))
    intent = brain.step(s)
    for t, k, p in events[seen:]:
        if k == "DECISION" and p["skill"] in ("pick", "deliver"):
            T = truth()
            if p["skill"] == "pick":
                e = p["args"]["x"]; pos = kb.position(e); a = kb.get("at", e)
                near = min(T.items(), key=lambda kv: math.hypot(kv[1][0][0]-pos.x, kv[1][0][1]-pos.y))
                dist = math.hypot(near[1][0][0]-pos.x, near[1][0][1]-pos.y)
                first = next(ev for ev in kb.history if ev.rel == "at" and ev.args == (e,))
                print(f"t={t:6.1f} pick {e:7s} belief ({pos.x:+.2f},{pos.y:+.2f}) s={pos.sigma:.2f} conf={a.conf:.2f} "
                      f"seen {t-a.t_obs:4.1f}s ago src={a.sources[-1]} | nearest true {near[0]} {dist:.2f} m in_basket={near[1][1]}")
            else:
                held = kb.value("holding", "self")
                print(f"t={t:6.1f} deliver held={held} true held={d.holding}")
        if k == "OUTCOME" and p["skill"] in ("pick", "deliver"):
            print(f"         -> {p['skill']} {p['status']} {p['reason']} effect_held={p['effect_held']}  in basket now={w.tidy_score()['inBasket']}")
    seen = len(events)
    w.apply_intent(d, intent)
    if d.skill is None:
        d.set_cmd(w.data, intent.twist, intent.head)
    w.step()
b = [e for e in kb.of_class("basket")]
print("baskets:", [(e, kb.position(e)) for e in b], "true", w.basket.pos)
