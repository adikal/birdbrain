"""Milestone 6: what experience buys each agent, and which agent it buys more.

    .venv/bin/python scripts/m6_report.py C.jsonl C_twin.jsonl D.jsonl D_twin.jsonl [--late 11]

Each agent's gain from experience is its measure over rooms --late on minus the same
measure for its twin that keeps no memory between rooms (`--no-memory`), on the same
rooms, per life. The report gives each agent's gain and the second agent's gain minus the
first's, paired by life. Measures are those of `world2_report.py`.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from world2_report import MEASURES, load, per_life

from birdbrain.evaluation import paired, report

SHOWN = ("tidied, possible", "tidied, known kinds", "tidied, new kinds", "falls", "falls holding heavy",
         "failed pick decisions", "owner's measure gained", "her things moved")


def gains(kept: str, twin: str, late: int) -> dict[int, dict[str, float]]:
    a, b = per_life(load(twin), late), per_life(load(kept), late)
    return {s: {m: b[s][m] - a[s][m] for m in MEASURES if a[s][m] is not None and b[s][m] is not None}
            for s in a if s in b}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("first", nargs=2, metavar=("FIRST", "FIRST_TWIN"))
    ap.add_argument("second", nargs=2, metavar=("SECOND", "SECOND_TWIN"))
    ap.add_argument("--late", type=int, default=11)
    args = ap.parse_args()
    first, second = gains(*args.first, args.late), gains(*args.second, args.late)
    zero = {s: dict.fromkeys(MEASURES, 0.0) for s in set(first) | set(second)}
    for name, g in ((args.first[0], first), (args.second[0], second)):
        print(f"gain from experience, rooms {args.late} on, {name} minus its twin:")
        for m in SHOWN:
            seeds = [s for s in g if m in g[s]]
            print("  " + report(paired({s: zero[s] for s in seeds}, {s: g[s] for s in seeds}, m)))
    print(f"\n{args.second[0]}'s gain minus {args.first[0]}'s, paired by life:")
    for m in SHOWN:
        seeds = [s for s in first if s in second and m in first[s] and m in second[s]]
        print("  " + report(paired({s: first[s] for s in seeds}, {s: second[s] for s in seeds}, m)))


if __name__ == "__main__":
    main()
