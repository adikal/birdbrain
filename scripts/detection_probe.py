"""Measure detection rates on frames the perception model calls visible, in World 2
rooms: the basket's by range (ledger E-022, re-measured after the E-025 review), and
objects' by apparent width (E-028).

    .venv/bin/python scripts/detection_probe.py [--rooms 24] [--seed0 90100] [--jobs 8]

The duck runs the task-driven local policy. For every camera frame the mind takes in,
the basket's TRUE position goes through the mind's own visibility test (field of view,
then the range sensor's occlusion test, `Perception.occluded`); a frame that passes counts
as a hit if it holds a basket sighting. This is the rate the miss model needs: occluded
frames are not counted as misses, so they must not lower the rate either.
"""

import argparse
import math
import multiprocessing as mp
from collections import defaultdict


def _room(a: tuple) -> dict[int, list[int]]:
    seed, step, seconds = a
    from birdbrain.perception import OWN_FOOTPRINT_M
    from birdbrain.run import PlayroomSession

    s = PlayroomSession(seed, world="world2", kinds="dev")
    per, body = s.mind.perception, s.mind.perception.body
    bx, by = s.scenario.basket.pos
    counts: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    toys: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    from microduck_local.world.scenario import PICKABLE_KINDS
    radius = {n: max(PICKABLE_KINDS[k]["size"]) / 2 for n, k in s.world.pickable_kind.items()}
    height = {n: PICKABLE_KINDS[k]["size"][2] / 2 for n, k in s.world.pickable_kind.items()}
    last = -math.inf
    while s.t < seconds:
        s.step()
        view = per.last_view
        if view is None or view["t"] <= last or per._range is None:
            continue
        last = view["t"]
        x, y, yaw = per._pose_at(view["t"])
        cx, cy = x + body.cam_ahead * math.cos(yaw), y + body.cam_ahead * math.sin(yaw)
        horizontal = math.hypot(bx - cx, by - cy)
        from birdbrain.body import Frame
        frame = Frame(view["t"], (), view["cam_z"], view["cam_pitch"], view["cam_yaw"])
        det = s.duck.detector.last
        if det is not None and abs(det.t - view["t"]) < 1e-6:
            found = {d.name for d in det.detections}          # truth, for this probe only
            for name, b in s.world.pickables.items():
                if name == s.duck.holding or s.world.in_basket(name):
                    continue
                tx, ty = float(s.world.data.xpos[b][0]), float(s.world.data.xpos[b][1])
                h = math.hypot(tx - cx, ty - cy)
                tb = math.atan2(ty - cy, tx - cx) - yaw - view["cam_yaw"]
                tb = math.atan2(math.sin(tb), math.cos(tb))
                if h < 0.08 or abs(tb) > body.fov_h / 2 - per.p.fov_margin:
                    continue
                drop = frame.cam_z - height[name]
                below = math.atan2(drop, h) - frame.cam_pitch
                if abs(below) >= body.fov_v / 2 - per.p.fov_margin:
                    continue
                # In sight as the mind judges it (its range sensor and its map), with the
                # object's true position: the rate a miss model needs is the rate given the
                # model's own judgement that it should have been seen (E-034).
                slant = math.hypot(h, drop)
                if per.occluded(frame, tb, below, slant) or not per.map.clear(
                        (cx, cy), (tx, ty), spare=OWN_FOOTPRINT_M, grown=False):
                    continue
                # The width the mind computes: from the duck's position, horizontally.
                trunk = s.duck.trunk_pos(s.world.data)
                rng = math.hypot(tx - float(trunk[0]), ty - float(trunk[1]))
                width = math.degrees(2 * math.atan2(radius[name], max(rng, 1e-3)))
                k = min(int(width / 0.5), 40)
                toys[k][1] += 1
                toys[k][0] += name in found
        bearing = math.atan2(by - cy, bx - cx) - yaw - view["cam_yaw"]
        bearing = math.atan2(math.sin(bearing), math.cos(bearing))
        if horizontal < 0.08 or abs(bearing) > body.fov_h / 2 - per.p.fov_margin:
            continue
        drop = frame.cam_z - body.class_height["basket"]
        below = math.atan2(drop, horizontal) - frame.cam_pitch
        if abs(below) >= body.fov_v / 2 - per.p.fov_margin:
            continue
        if per.occluded(frame, bearing, below, math.hypot(horizontal, drop)) or not per.map.clear(
                (cx, cy), (bx, by), spare=OWN_FOOTPRINT_M, grown=False):
            continue
        k = int(horizontal / step)
        counts[k][1] += 1
        counts[k][0] += any(v["cls"] == "basket" for v in view["sightings"])
    s.close()
    return {"basket": dict(counts), "toys": dict(toys)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rooms", type=int, default=24)
    ap.add_argument("--seed0", type=int, default=90100)
    ap.add_argument("--seconds", type=float, default=300.0)
    ap.add_argument("--step", type=float, default=0.25)
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()
    total = {"basket": defaultdict(lambda: [0, 0]), "toys": defaultdict(lambda: [0, 0])}
    with mp.get_context("spawn").Pool(args.jobs) as pool:
        for counts in pool.imap_unordered(_room, [(args.seed0 + i, args.step, args.seconds) for i in range(args.rooms)]):
            for what, table in counts.items():
                for k, (hit, n) in table.items():
                    total[what][k][0] += hit
                    total[what][k][1] += n
    print(f"basket detection rate on frames called visible, {args.rooms} World 2 rooms:")
    for k in sorted(total["basket"]):
        hit, n = total["basket"][k]
        print(f"  {k * args.step:4.2f} to {(k + 1) * args.step:4.2f} m: {hit:5d} of {n:5d} = {hit / n:.2f}")
    print("object detection rate by apparent width, on frames called visible:")
    for k in sorted(total["toys"]):
        hit, n = total["toys"][k]
        print(f"  {k * 0.5:4.1f} to {(k + 1) * 0.5:4.1f} deg: {hit:5d} of {n:5d} = {hit / n:.2f}")


if __name__ == "__main__":
    main()
