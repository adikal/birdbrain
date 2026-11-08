"""Feasibility probe: can the duck pick up and deliver objects other than the lab's three toys?

    .venv/bin/python scripts/grasp_probe.py [--seeds 8] [--jobs 8] [--seconds 300]

Each kind fills a room (6 of it) and the task-driven local policy tidies it. New kinds
are boxes added to the lab's PICKABLE_KINDS table at runtime: in the lab only pickables
can be grasped, and pickables are boxes. This patches the lab from outside, for this
probe only; no experiment should rest on it.
"""

import argparse
import multiprocessing as mp
import statistics as st

# name: full extents (m), mass (kg). The first three are the lab's own.
KINDS = {
    "brick": ((0.032, 0.016, 0.0096), 0.0025),
    "block": ((0.04, 0.04, 0.04), 0.02),
    "sock": ((0.06, 0.035, 0.025), 0.02),
    "tiny cube": ((0.02, 0.02, 0.02), 0.005),
    "flat tile": ((0.06, 0.06, 0.008), 0.01),
    "stick": ((0.10, 0.015, 0.015), 0.01),
    "tall post": ((0.03, 0.03, 0.06), 0.02),
    "big cube": ((0.055, 0.055, 0.055), 0.03),
    "heavy block": ((0.04, 0.04, 0.04), 0.15),
    "very heavy block": ((0.04, 0.04, 0.04), 0.5),
}


def _one(a: tuple) -> dict:
    kind, seed, seconds = a
    import functools

    from microduck_local import world
    from microduck_local.world.scenario import PICKABLE_KINDS

    size, mass = KINDS[kind]
    PICKABLE_KINDS.setdefault(kind, {"size": size, "mass": mass, "rgba": (0.3, 0.7, 0.4, 1.0)})
    world.make_playroom = functools.partial(world.make_playroom, kinds=(kind,))

    from birdbrain.run import run_one
    r = run_one(seed, seconds=seconds)
    return {"kind": kind, **{k: r[k] for k in ("inBasket", "falls", "attempts", "grasps", "toyIds")}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--seed0", type=int, default=90001)
    ap.add_argument("--seconds", type=float, default=300.0)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--kinds", nargs="*", default=list(KINDS))
    args = ap.parse_args()
    jobs = [(k, args.seed0 + s, args.seconds) for k in args.kinds for s in range(args.seeds)]
    with mp.get_context("spawn").Pool(args.jobs) as pool:
        rows = pool.map(_one, jobs)
    print(f"{'kind':18} {'size (cm)':16} {'g':>5} {'in basket':>10} {'grasped':>9} {'falls':>6} {'toys found':>11}")
    for k in args.kinds:
        size, mass = KINDS[k]
        rs = [r for r in rows if r["kind"] == k]
        att, gr = sum(r["attempts"] for r in rs), sum(r["grasps"] for r in rs)
        dims = "×".join(f"{v * 100:g}" for v in size)
        print(f"{k:18} {dims:16} {mass * 1000:5g} {st.mean(r['inBasket'] for r in rs):6.2f} of 6"
              f" {gr:4}/{att:<4} {st.mean(r['falls'] for r in rs):6.2f} {st.mean(r['toyIds'] for r in rs):8.2f}")


if __name__ == "__main__":
    main()
