"""Paired comparison of two experiment arms on matched seeds.

    birdbrain-compare A.jsonl B.jsonl --metric inBasket --metric falls

Both files hold one JSON row per seed (Microduck Lab's `eval-tidy --out`
rows and `birdbrain-run` rows share `seed`, `inBasket`, and `falls`). For
each metric the report gives both means, the mean paired difference B - A
with a 95% confidence interval (t distribution), wins, ties, and losses,
and an exact two-sided sign-flip permutation p-value (Monte Carlo above 20
pairs). Seeds present in only one file are reported and excluded.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from pathlib import Path
from statistics import fmean
from typing import Any

# Two-sided 97.5% quantiles of Student's t, by degrees of freedom.
_T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262,
         10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110,
         18: 2.101, 19: 2.093, 20: 2.086, 25: 2.060, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980}


def t975(df: int) -> float:
    """The tabulated quantile at or below `df` degrees of freedom (conservative between entries)."""
    if df < 1:
        return math.nan
    return _T975[max(k for k in _T975 if k <= df)]


def load(path: Path) -> dict[int, dict[str, Any]]:
    """Rows by seed. A seed recorded twice is an error: comparisons must not pick silently."""
    rows: dict[int, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            seed = int(row["seed"])
            if seed in rows:
                raise ValueError(f"{path}: seed {seed} appears more than once; use one file per arm")
            rows[seed] = row
    return rows


def sign_flip_p(diffs: list[float], samples: int = 200_000, seed: int = 0) -> float:
    """Two-sided p-value of the mean difference under random sign flips."""
    observed = abs(sum(diffs))
    nonzero = [d for d in diffs if d != 0]
    if not nonzero:
        return 1.0
    if len(nonzero) <= 20:
        hits = sum(abs(sum(s * d for s, d in zip(signs, nonzero, strict=True))) >= observed - 1e-12
                   for signs in itertools.product((1, -1), repeat=len(nonzero)))
        return hits / 2 ** len(nonzero)
    rng = random.Random(seed)
    hits = sum(abs(sum(d if rng.random() < 0.5 else -d for d in nonzero)) >= observed - 1e-12
               for _ in range(samples))
    return (hits + 1) / (samples + 1)


def paired(a: dict[int, dict[str, Any]], b: dict[int, dict[str, Any]], metric: str) -> dict[str, Any]:
    seeds = sorted(set(a) & set(b))
    xa = [float(a[s][metric]) for s in seeds]
    xb = [float(b[s][metric]) for s in seeds]
    diffs = [y - x for x, y in zip(xa, xb, strict=True)]
    n = len(diffs)
    mean = fmean(diffs) if diffs else math.nan
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (n - 1)) if n > 1 else math.nan
    half = t975(n - 1) * sd / math.sqrt(n) if n > 1 else math.nan
    return {
        "metric": metric, "n": n, "mean_a": fmean(xa) if xa else math.nan,
        "mean_b": fmean(xb) if xb else math.nan, "diff": mean, "ci95": (mean - half, mean + half),
        "wins": sum(d > 0 for d in diffs), "ties": sum(d == 0 for d in diffs),
        "losses": sum(d < 0 for d in diffs), "p": sign_flip_p(diffs),
        "only_a": sorted(set(a) - set(b)), "only_b": sorted(set(b) - set(a)),
    }


def report(result: dict[str, Any]) -> str:
    lo, hi = result["ci95"]
    return (f"{result['metric']}: A {result['mean_a']:.3f} · B {result['mean_b']:.3f} · "
            f"B-A {result['diff']:+.3f} [95% CI {lo:+.3f}, {hi:+.3f}] · "
            f"B higher {result['wins']}, equal {result['ties']}, lower {result['losses']} · "
            f"sign-flip p = {result['p']:.3f} · n = {result['n']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    ap.add_argument("--metric", action="append", default=None)
    args = ap.parse_args()
    a, b = load(args.a), load(args.b)
    for metric in args.metric or ["inBasket", "falls"]:
        result = paired(a, b, metric)
        print(report(result))
        if result["only_a"] or result["only_b"]:
            print(f"  unmatched seeds: only A {result['only_a']}, only B {result['only_b']}")


if __name__ == "__main__":
    main()
