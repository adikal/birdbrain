"""Milestone 4 report (ledger E-017): what the rules learned, and deciding with them.

    .venv/bin/python scripts/rules_report.py --lives data/lifetimes/<tag>-* \
        [--counts counts_{none,basket,wall,leave}.jsonl --rules rules_{none,basket,wall,leave}.jsonl]

`--lives`: memory directories of finished lives; prints, per skill and condition, the
median effect on the log-odds (against the other values of the feature) across lives,
how many lives agree on its sign, and the credible rules found in each life.
`--counts`/`--rules`: rows of the same lives deciding with counts and with rules;
prints each owner arm's own measure, falls, failed picks, and toys lost to picks per
room (rooms 6 on), rules minus counts, paired by life.
"""

import argparse
import collections
import json
from pathlib import Path
from statistics import fmean, median

from birdbrain.evaluation import paired, report
from birdbrain.mind import RULE_OUTCOMES
from birdbrain.rules import RuleLearner

OWN = {"none": lambda r: r["sat_basket"] - r["sat_basket_start"], "basket": lambda r: r["sat_basket"] - r["sat_basket_start"],
       "wall": lambda r: r["sat_wall"], "leave": lambda r: r["sat_leave"]}


def learned(lives: list[Path]) -> None:
    for name, outcome, prior, sd in RULE_OUTCOMES:
        effects, credible = collections.defaultdict(list), collections.Counter()
        for d in lives:
            learner = RuleLearner.from_json((d / f"rules_{name}.json").read_text(encoding="utf-8"), prior=prior, sd_base=sd)
            for skill in learner.examples:
                m = learner.model(skill)
                for key in m.keys:
                    effects[(skill, key)].append(m.contrast(key)[0])
            for r in learner.rules():
                credible[(r["skill"], r["when"], "raises" if r["odds"] > 1 else "lowers")] += 1
        print(f"== {name} ({outcome}): conditions seen in at least half of {len(lives)} lives, by median effect")
        rows = [(abs(median(v)), s, k, median(v), sum(x < 0 for x in v), len(v))
                for (s, k), v in effects.items() if len(v) >= len(lives) / 2]
        for _, skill, key, med, neg, n in sorted(rows, reverse=True)[:12]:
            print(f"  {skill:<12} {key:<34} median {med:+.2f}  lowers the odds in {neg} of {n} lives")
        print(f"  credible rules (3 sd), lives in which each appears: {dict(credible.most_common(10)) or 'none'}")


def deciding(counts: list[str], rules: list[str]) -> None:
    print("== deciding with rules minus deciding with counts, rooms 6 on, paired by life")
    for c_path, r_path in zip(counts, rules, strict=True):
        arms = {}
        for label, path in (("counts", c_path), ("rules", r_path)):
            rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
            arm = rows[0]["owner"]
            arms[label] = {s: {"seed": s, **{m: fmean(f(r) for r in rows if r["seed"] == s and r["episode"] >= 6)
                                             for m, f in (("own", OWN[arm]), ("falls", lambda r: r["falls"]),
                                                          ("failed picks", lambda r: r["pickDecisionsFailed"]),
                                                          ("lost by pick", lambda r: r["lostByPick"]))}}
                           for s in sorted({r["seed"] for r in rows})}
        for measure in ("own", "falls", "failed picks", "lost by pick"):
            print(f"  {arm:<7} " + report(paired(arms["counts"], arms["rules"], measure)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lives", nargs="*", default=[])
    ap.add_argument("--counts", nargs="*", default=[])
    ap.add_argument("--rules", nargs="*", default=[])
    args = ap.parse_args()
    lives = sorted(d for pattern in args.lives for d in Path().glob(f"{pattern}/life-*"))
    if lives:
        learned(lives)
    if args.counts:
        deciding(args.counts, args.rules)


if __name__ == "__main__":
    main()
