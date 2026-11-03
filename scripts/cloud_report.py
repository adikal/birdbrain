"""Summarize cloud decisions in recorded runs: latency, tokens, validity, and calibration (H-007).

    python scripts/cloud_report.py data/runs e010-frozen
"""
import json
import math
import sys
from pathlib import Path


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


root, prefix = Path(sys.argv[1]), sys.argv[2]
decisions, outcomes = [], []
for f in sorted(root.glob(f"{prefix}*/events.jsonl")):
    for line in f.open():
        e = json.loads(line)
        if e["type"] == "DECISION":
            decisions.append(e["payload"])
        elif e["type"] == "OUTCOME":
            outcomes.append(e["payload"])
cloud = [d for d in decisions if d["provider"] != "local"]
lat = [d["latency_s"] for d in cloud]
tin = [d["usage"].get("input", 0) for d in cloud]
tout = [d["usage"].get("output", 0) for d in cloud]
print(f"decisions {len(decisions)} · cloud {len(cloud)} · fallbacks {sum(1 for d in decisions if d['fallback'])}")
print(f"latency s: median {pct(lat, .5):.2f} · p95 {pct(lat, .95):.2f} · max {max(lat):.2f}")
print(f"tokens per decision: input median {pct(tin, .5)} (p95 {pct(tin, .95)}) · output median {pct(tout, .5)}")
print(f"total tokens: input {sum(tin)} · output {sum(tout)}")
skills = {}
for d in cloud:
    skills[d["skill"]] = skills.get(d["skill"], 0) + 1
print("choices:", dict(sorted(skills.items(), key=lambda kv: -kv[1])))
# Calibration: outcomes of cloud decisions with both probabilities.
pairs = [(o["p_model"], o["p_rule"], o["effect_held"], o["trials"]) for o in outcomes
         if o.get("p_model") is not None and o["provider"] != "local" and o["expect"] != "true"]
if pairs:
    def brier(i):
        return sum((p[i] - p[2]) ** 2 for p in pairs) / len(pairs)
    def logloss(i):
        return -sum(math.log(max(p[i] if p[2] else 1 - p[i], 1e-6)) for p in pairs) / len(pairs)
    base = sum(p[2] for p in pairs) / len(pairs)
    print(f"calibration over {len(pairs)} outcomes (effect held {base:.2f}): "
          f"Brier model {brier(0):.3f} · rule {brier(1):.3f} · constant {base * (1 - base):.3f}; "
          f"log loss model {logloss(0):.3f} · rule {logloss(1):.3f}")
    for lo, hi in ((0, 3), (3, 10), (10, 99)):
        sub = [p for p in pairs if lo <= p[3] < hi]
        if sub:
            bm = sum((p[0] - p[2]) ** 2 for p in sub) / len(sub)
            br = sum((p[1] - p[2]) ** 2 for p in sub) / len(sub)
            print(f"  rule trials {lo}-{hi - 1}: n {len(sub)} · Brier model {bm:.3f} · rule {br:.3f}")
    bins = {}
    for p in pairs:
        b = min(int(p[0] * 5), 4)
        bins.setdefault(b, []).append(p[2])
    print("  model reliability:", {f"{b / 5:.1f}-{(b + 1) / 5:.1f}": f"{sum(v) / len(v):.2f} (n {len(v)})" for b, v in sorted(bins.items())})
