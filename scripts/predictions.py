"""Score the duck's predictions over lifetimes (ledger E-017): prequential Brier scores.

    .venv/bin/python scripts/predictions.py rows.jsonl [rows.jsonl ...] [--late 6]

Every action is predicted before it runs and scored when it ends, so every score is
on an outcome the predictor had not seen. For each outcome (the expected effect held;
a fall), and each predictor (causal rules; one count per skill; one count per kind of
action), prints the mean Brier score per episode over lifetimes, then compares rules
with skill counts per lifetime, paired, early and late in life.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import fmean

from birdbrain.evaluation import paired, report

PREDICTORS = ("rules", "skill", "kind")


def load(paths: list[str]) -> list[dict]:
    rows = []
    for path in paths:
        rows += [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows


def brier(r: dict, outcome: str, predictor: str) -> float | None:
    n = r.get(f"brier_{outcome}_n", 0)
    return r[f"brier_{outcome}_{predictor}"] / n if n else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--late", type=int, default=6)
    args = ap.parse_args()
    rows = load(args.files)
    # A lifetime is (file's owner arm, seed).
    life = lambda r: f"{r.get('owner')}:{r['seed']}"
    for outcome in ("effect", "fell"):
        print(f"== {outcome}: mean Brier per episode ({len({life(r) for r in rows})} lifetimes)")
        print("  ep  " + "  ".join(f"{p:>7}" for p in PREDICTORS) + "  actions/ep")
        by_ep = defaultdict(list)
        for r in rows:
            by_ep[r["episode"]].append(r)
        for ep in sorted(by_ep):
            rs = by_ep[ep]
            cells = [fmean(b for r in rs if (b := brier(r, outcome, p)) is not None) for p in PREDICTORS]
            print(f"  {ep:>2}  " + "  ".join(f"{c:7.4f}" for c in cells)
                  + f"  {fmean(r.get(f'brier_{outcome}_n', 0) for r in rs):10.1f}")
        per_life: dict[str, dict] = {}
        for key in sorted({life(r) for r in rows}):
            rs = [r for r in rows if life(r) == key]

            def pooled(predictor: str, episodes: set[int], rs: list = rs, outcome: str = outcome) -> float:
                sel = [r for r in rs if r["episode"] in episodes]
                n = sum(r.get(f"brier_{outcome}_n", 0) for r in sel)
                return sum(r.get(f"brier_{outcome}_{predictor}", 0.0) for r in sel) / n if n else float("nan")

            last = max(r["episode"] for r in rs)
            late, early, final = set(range(args.late, last + 1)), {1, 2}, {last - 1, last}
            per_life[key] = {"seed": key, **{f"late_{p}": pooled(p, late) for p in PREDICTORS},
                             "early_rules": pooled("rules", early), "final_rules": pooled("rules", final)}
        # Lives with nothing scored in a window cannot be compared there.
        def usable(*keys: str, per_life: dict = per_life) -> dict[str, dict]:
            return {k: v for k, v in per_life.items() if all(v[x] == v[x] for x in keys)}

        for other in ("skill", "kind"):
            lives = usable(f"late_{other}", "late_rules")
            result = paired({k: {**v, "x": v[f"late_{other}"]} for k, v in lives.items()},
                            {k: {**v, "x": v["late_rules"]} for k, v in lives.items()}, "x")
            print(f"  late episodes, rules vs {other}: " + report(result)
                  + f" · diff {result['diff']:+.6f} [{result['ci95'][0]:+.6f}, {result['ci95'][1]:+.6f}]")
        lives = usable("early_rules", "final_rules")
        print("  rules, episodes 1-2 vs last two: "
              + report(paired({k: {**v, "x": v["early_rules"]} for k, v in lives.items()},
                              {k: {**v, "x": v["final_rules"]} for k, v in lives.items()}, "x")))


if __name__ == "__main__":
    main()
