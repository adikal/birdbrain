"""Replay a life's outcomes through two rule learners and score their predictions
(ledger E-026). No simulation: each life's `outcomes.json` holds every scored outcome
in order, with the conditions it started under.

    .venv/bin/python scripts/rules_replay.py data/lifetimes/<tag>/life-* [--jobs 8]

For each outcome (expected effect held, fell), each learner predicts before it sees it
(prequential), then learns from it, as in a life. Prints the Brier score of each
learner, per outcome and skill, with the paired difference over lives, and the mean
prediction against the observed rate for a few conditions of interest.
"""

import argparse
import json
import multiprocessing as mp
from collections import defaultdict
from pathlib import Path
from statistics import fmean

from birdbrain.evaluation import paired, report
from birdbrain.mind import RULE_OUTCOMES
from birdbrain.rules import RuleLearner
from birdbrain.skills import Library

#: The learners compared: name -> RuleLearner options.
LEARNERS = {"gaussian": {"effect_prior": "gaussian"}, "cauchy": {"effect_prior": "cauchy"}}
#: Conditions whose calibration is printed: (skill, feature, value).
WATCH = (("deliver", "held colour", "black"), ("pick", "target size", "5 to 7.5 cm"),
         ("deliver", "held colour", "white"), ("pick", "target by the rim", "yes"))


def replay(life: str) -> dict:
    expect = {name: s.expect for name, s in Library().skills.items()}
    outcomes = json.loads((Path(life) / "outcomes.json").read_text(encoding="utf-8"))
    out: dict = {"brier": defaultdict(lambda: [0.0, 0]), "watch": defaultdict(lambda: [0.0, 0.0, 0])}
    for name, outcome, prior, sd in RULE_OUTCOMES:
        learners = {k: RuleLearner(outcome, prior=prior, sd_base=sd, **opts) for k, opts in LEARNERS.items()}
        for o in outcomes:
            skill = o["skill"]
            if skill not in expect or (name == "effect" and expect[skill] == "true"):
                continue
            y = float(o["fell"] if name == "fell" else o["held"])
            for k, learner in learners.items():
                p = learner.predict(skill, o["features"])[0]
                b = out["brier"][(name, skill, k)]
                b[0] += (p - y) ** 2
                b[1] += 1
                for ws, feat, value in WATCH:
                    if ws == skill and o["features"].get(feat) == value:
                        w = out["watch"][(name, ws, feat, value, k)]
                        w[0] += p
                        w[1] += y
                        w[2] += 1
                learner.add(skill, o["features"], y)
    return {"life": life, "brier": {"|".join(k): v for k, v in out["brier"].items()},
            "watch": {"|".join(k): v for k, v in out["watch"].items()}}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lives", nargs="+")
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()
    with mp.get_context("spawn").Pool(args.jobs) as pool:
        results = pool.map(replay, args.lives)
    a, b = list(LEARNERS)
    keys = sorted({k.rsplit("|", 1)[0] for r in results for k in r["brier"]})
    print(f"Brier score per outcome, {b} minus {a}, paired by life (lower is better):")
    for key in keys:
        name, skill = key.split("|")
        per = {i: {k: r["brier"][f"{key}|{k}"][0] / r["brier"][f"{key}|{k}"][1] for k in (a, b)}
               for i, r in enumerate(results) if r["brier"].get(f"{key}|{a}", [0, 0])[1] >= 10}
        if len(per) < 2:
            continue
        n = sum(r["brier"].get(f"{key}|{a}", [0, 0])[1] for r in results)
        print(f"  {name:6} {skill:12} n {n:5d} · " + report(paired({i: {"brier": v[a]} for i, v in per.items()},
                                                                    {i: {"brier": v[b]} for i, v in per.items()}, "brier")))
    print("\nmean prediction against the observed rate, pooled over lives:")
    for name, *_ in RULE_OUTCOMES:
        for ws, feat, value in WATCH:
            parts = []
            for k in (a, b):
                tot = [sum(r["watch"].get(f"{name}|{ws}|{feat}|{value}|{k}", [0, 0, 0])[j] for r in results) for j in range(3)]
                if tot[2]:
                    parts.append(f"{k} predicts {tot[0] / tot[2]:.2f}")
            if parts:
                print(f"  {name:6} {ws} when {feat} {value} (n {tot[2]}): observed {tot[1] / tot[2]:.2f}; " + ", ".join(parts))
    print(f"\n{len(results)} lives; mean outcomes per life {fmean(sum(v[1] for k, v in r['brier'].items() if k.endswith(a)) for r in results):.0f}")


if __name__ == "__main__":
    main()
