"""Why actions fail in World 2 runs, from the event logs (ledger E-021).

    .venv/bin/python scripts/world2_failures.py TAG [TAG ...] [--from 11]

Per tag: outcomes of top-level picks and deliveries (and skills written in their place)
by status and reason, with the reason's object id removed, and the share of deliveries
that failed because the basket was lost: no longer believed where it was, or not found
by deliver's search (E-022), or, before that search existed, not known at all.
"""

import argparse
import glob
import json
import re
from collections import Counter
from pathlib import Path

#: Delivery failures that mean the basket was lost (reasons with ids replaced by X).
BASKET_LOST = {"failed: X is no longer where it was believed", "failed: not known(basket) after 4 iterations",
               "failed: not known(basket) or not holding(self) after 4 iterations", "failed: X position unknown"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--from", dest="first", type=int, default=1, help="first room of a life to count")
    args = ap.parse_args()
    for tag in args.tags:
        out: dict[str, Counter] = {"pick": Counter(), "deliver": Counter()}
        rooms = 0
        for path in glob.glob(f"data/runs/{tag}-L*/events.jsonl"):
            if int(re.search(r"-L\d+e(\d+)-", path).group(1)) < args.first:
                continue
            rooms += 1
            for line in Path(path).read_text(encoding="utf-8").splitlines():
                if '"OUTCOME"' not in line:
                    continue
                p = json.loads(line)["payload"]
                parent = next((k for k in out if p["skill"] == k or p["skill"].startswith(f"w_{k}")), None)
                if parent is None:
                    continue
                reason = re.sub(r"\w+#\d+", "X", p["reason"] or "")
                out[parent][p["status"] + (f": {reason}" if reason else "")] += 1
        print(f"== {tag}: {rooms} rooms from room {args.first}")
        for skill, c in out.items():
            n = sum(c.values())
            print(f"  {skill}: {n} ({n / max(rooms, 1):.1f} a room)")
            for k, v in c.most_common(8):
                print(f"    {v / n:6.1%}  {k}")
            if skill == "deliver" and n:
                print(f"    basket lost: {sum(v for k, v in c.items() if k in BASKET_LOST) / n:.1%}")


if __name__ == "__main__":
    main()
