"""Summarize outcome reasons and falls across recorded runs (data/runs or a given directory)."""
import collections
import json
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "data/runs")
prefix = sys.argv[2] if len(sys.argv) > 2 else ""
reasons, falls, grasps = collections.Counter(), collections.Counter(), collections.Counter()
for f in sorted(root.glob(f"{prefix}*/events.jsonl")):
    for line in f.open():
        e = json.loads(line)
        p = e["payload"]
        if e["type"] == "OUTCOME":
            reasons[(p["skill"], p["status"], p["reason"].split(" is ")[-1][:45])] += 1
        elif e["type"] == "FALL":
            falls[(p["skill"], p["note"].split(" (")[0])] += 1
        elif e["type"] == "GRASP_TRUTH":
            err = p["error_m"]
            grasps["held" if p["held"] else ("miss <5cm" if err is not None and err < 0.05 else "no toy near beak")] += 1
print("outcomes:"); [print(f"  {v:3d} {k}") for k, v in reasons.most_common()]
print("falls:"); [print(f"  {v:3d} {k}") for k, v in falls.most_common()]
print("grasps (truth):", dict(grasps))
