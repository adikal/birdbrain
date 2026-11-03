"""Summarize Milestone 3b lifetimes (ledger E-015): per arm and episode, from truth.

    .venv/bin/python scripts/lifetimes.py none.jsonl basket.jsonl wall.jsonl leave.jsonl [--late 6]

For each file (one owner arm), prints the mean over lifetimes, per episode, of: toys in
the basket gained, toys against a wall (not in the basket), toys left unmoved, picks,
the owner's approvals and disapprovals per minute (what she meant), and what the duck
believes about its owner's reactions at the end.

Then, over the late episodes (from --late on), each arm's own measure per lifetime,
paired by lifetime seed against the control arm (`owner none`) and against the other
owner arms, and how often the duck's belief singles out the right kind of action.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import fmean

from birdbrain.evaluation import paired, report

#: Each owner's own measure, from truth.
MEASURE = {"basket": lambda r: r["sat_basket"] - r["sat_basket_start"],
           "wall": lambda r: r["sat_wall"], "leave": lambda r: r["sat_leave"]}
NAMES = {"basket": "basket_gain", "wall": "at_wall", "leave": "unmoved"}
#: The kind of action each owner's preference should single out.
RIGHT = {"basket": ("top", "deliver"), "wall": ("top", "put_by_wall"), "leave": ("bottom", "pick from")}


def load(path: str) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def per_episode(path: str, rows: list[dict]) -> None:
    by_ep = defaultdict(list)
    for r in rows:
        by_ep[r["episode"]].append(r)
    print(f"== {path}: owner {rows[0].get('owner')}, {len({r['seed'] for r in rows})} lifetimes")
    print("  ep  basket+  wall  unmoved  picks  approve/min  disapprove/min  falls")
    for ep in sorted(by_ep):
        rs = by_ep[ep]
        per_min = [r["seconds"] / 60.0 for r in rs]
        print(f"  {ep:>2}  {fmean(MEASURE['basket'](r) for r in rs):7.2f}  {fmean(r['sat_wall'] for r in rs):4.2f}"
              f"  {fmean(r['sat_leave'] for r in rs):7.2f}  {fmean(r['pickDecisions'] for r in rs):5.2f}"
              f"  {fmean(r['ownerApprovals'] / m for r, m in zip(rs, per_min, strict=True)):11.2f}"
              f"  {fmean(r['ownerDisapprovals'] / m for r, m in zip(rs, per_min, strict=True)):14.2f}"
              f"  {fmean(r['falls'] for r in rs):5.2f}")


def lifetime_means(rows: list[dict], late: int) -> dict[int, dict]:
    """Per lifetime: each measure averaged over episodes >= late, and early/late approval rates."""
    out: dict[int, dict] = {}
    for seed in sorted({r["seed"] for r in rows}):
        rs = [r for r in rows if r["seed"] == seed]
        lr = [r for r in rs if r["episode"] >= late]
        last_ep = max(r["episode"] for r in rs)
        early = [r for r in rs if r["episode"] <= 2]
        final = [r for r in rs if r["episode"] >= last_ep - 1]
        rate = lambda xs: fmean(r["ownerApprovals"] / (r["seconds"] / 60.0) for r in xs)
        out[seed] = {"seed": seed, **{NAMES[k]: fmean(f(r) for r in lr) for k, f in MEASURE.items()},
                     "picks": fmean(r["pickDecisions"] for r in lr),
                     "approve_early": rate(early), "approve_late": rate(final),
                     "model": next(r for r in rs if r["episode"] == last_ep).get("ownerModel") or {}}
    return out


def singles_out(model: dict, how: str, kind: str) -> bool:
    if not model:
        return False
    ranked = sorted(model.items(), key=lambda kv: kv[1]["expected"])
    name = ranked[-1][0] if how == "top" else ranked[0][0]
    return name.startswith(kind)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--late", type=int, default=6, help="late episodes start here")
    args = ap.parse_args()
    arms = {}
    for path in args.files:
        rows = load(path)
        if rows:
            per_episode(path, rows)
            arms[rows[0]["owner"]] = lifetime_means(rows, args.late)
    print(f"\n== late episodes ({args.late} on), per lifetime, paired by lifetime seed")
    for arm in ("basket", "wall", "leave"):
        if arm not in arms:
            continue
        name = NAMES[arm]
        for other in ("none", "basket", "wall", "leave"):
            if other != arm and other in arms:
                print(f"  {arm} owner vs {other}: " + report(paired(arms[other], arms[arm], name)))
        lt = arms[arm]
        print(f"  {arm} owner: approvals/min, episodes 1-2 {fmean(v['approve_early'] for v in lt.values()):.2f}"
              f" -> last two {fmean(v['approve_late'] for v in lt.values()):.2f};"
              f" belief singles out {RIGHT[arm][1]!r} in {sum(singles_out(v['model'], *RIGHT[arm]) for v in lt.values())}"
              f" of {len(lt)} lifetimes")
    if "none" in arms:
        c = arms["none"]
        print(f"  control: late basket gain {fmean(v['basket_gain'] for v in c.values()):.2f},"
              f" at wall {fmean(v['at_wall'] for v in c.values()):.2f},"
              f" unmoved {fmean(v['unmoved'] for v in c.values()):.2f}, picks {fmean(v['picks'] for v in c.values()):.2f}")


if __name__ == "__main__":
    main()
