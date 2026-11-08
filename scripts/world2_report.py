"""Summarize World 2 lifetimes (ledger E-021), from truth.

    .venv/bin/python scripts/world2_report.py A.jsonl [B.jsonl] [--late 11]

For each file: the measures below by band of rooms (1-5, 6-10, 11-15, 16-20), pooled over
lifetimes, so learning within a life shows as a trend. With two files, each measure over
rooms --late on, per lifetime, paired by lifetime (B minus A).

Ratios pool counts over the rooms of a band or window (sum of numerators over sum of
denominators); a room without objects of a category adds nothing to that category.
"""

import argparse
import json
from pathlib import Path

from birdbrain.evaluation import paired, report

#: name: (numerator, denominator); a denominator of None means per room.
MEASURES = {
    "tidied, possible": ("w2_possible_in", "w2_possible_n"),
    "tidied, plain": ("w2_plain_in", "w2_plain_n"),
    "tidied, heavy": ("w2_heavy_in", "w2_heavy_n"),
    "tidied, slippery": ("w2_slippery_in", "w2_slippery_n"),
    "tidied, known kinds": ("w2_known_possible_in", "w2_known_possible_n"),
    "tidied, new kinds": ("w2_new_possible_in", "w2_new_possible_n"),
    "falls": ("falls", None),
    "falls holding heavy": ("w2_falls_holding_heavy", None),
    "heavy grasped per heavy object": ("w2_grasped_heavy", "w2_heavy_n"),
    "  of new kinds": ("w2_grasped_heavy_new", "w2_heavy_new_n"),
    "wide grasped per wide object": ("w2_refused", "w2_wide_n"),
    "  of new kinds ": ("w2_grasped_wide_new", "w2_wide_new_n"),
    "slipped": ("w2_slipped", None),
    "never found, share of objects": ("w2_unfound", "w2_objects"),
    "pick decisions": ("pickDecisions", None),
    "failed pick decisions": ("pickDecisionsFailed", None),
    "her things moved": ("hers_moved", "hers_n"),
    "owner's measure gained": ("owner_gain", None),
}
BANDS = ((1, 5), (6, 10), (11, 15), (16, 20))


def load(path: str) -> list[dict]:
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in rows:
        _derive(r)
    return rows


def _derive(r: dict) -> None:
    """Measures computed from other fields of a row."""
    if r.get("owner") == "hers":
        r["owner_gain"] = r["sat_hers"] - r["sat_hers_start"]
    r.setdefault("hers_n", 0)


def value(rows: list[dict], measure: str) -> float | None:
    num, den = MEASURES[measure]
    top = sum(r.get(num, 0) for r in rows)
    if den is None:
        return top / len(rows) if rows else None
    bottom = sum(r.get(den, 0) for r in rows)
    return top / bottom if bottom else None


def bands(path: str, rows: list[dict]) -> None:
    lives = len({r["seed"] for r in rows})
    print(f"== {path}: {lives} lifetimes, {len(rows)} rooms, owner {rows[0].get('owner')}, "
          f"kinds {rows[0].get('kinds')}")
    print(f"  {'measure':34}" + "".join(f"{f'rooms {a}-{b}':>13}" for a, b in BANDS))
    for m in MEASURES:
        vals = [value([r for r in rows if a <= r["episode"] <= b], m) for a, b in BANDS]
        if all(v is None for v in vals):
            continue
        print(f"  {m:34}" + "".join(f"{'-':>13}" if v is None else f"{v:13.3f}" for v in vals))


def per_life(rows: list[dict], late: int) -> dict[int, dict]:
    out = {}
    for seed in sorted({r["seed"] for r in rows}):
        rs = [r for r in rows if r["seed"] == seed and r["episode"] >= late]
        out[seed] = {m: value(rs, m) for m in MEASURES}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--late", type=int, default=11)
    args = ap.parse_args()
    loaded = [load(f) for f in args.files]
    for path, rows in zip(args.files, loaded, strict=True):
        bands(path, rows)
    if len(loaded) == 2:
        a, b = (per_life(rows, args.late) for rows in loaded)
        print(f"\nrooms {args.late} on, per lifetime, {args.files[1]} minus {args.files[0]}:")
        for m in MEASURES:
            seeds = [s for s in a if s in b and a[s][m] is not None and b[s][m] is not None]
            if len(seeds) < 2:
                continue
            print("  " + report(paired({s: a[s] for s in seeds}, {s: b[s] for s in seeds}, m)))


if __name__ == "__main__":
    main()
