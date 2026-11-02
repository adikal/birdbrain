"""Deterministic run scoring and comparison."""

from __future__ import annotations

from statistics import fmean
from typing import Any


def score_run(events: list[dict[str, Any]]) -> dict[str, Any]:
    snapshots = [
        event["payload"] for event in events if event["type"] == "STATE_SNAPSHOT"
    ]
    anomalies = sum(event["type"] == "ANOMALY" for event in events)
    failed = any(event["type"] == "RUN_FAILED" for event in events)
    completed = any(event["type"] == "RUN_STOPPED" for event in events)
    confidences = [float(frame.get("confidence", 0.0)) for frame in snapshots]
    heights = [float(frame["duck"]["position"][2]) for frame in snapshots]
    cognitive_cycles = sum(event["type"] == "PLAN_CREATED" for event in events)
    metrics = {
        "completed": completed,
        "failed": failed,
        "anomalies": anomalies,
        "frames": len(snapshots),
        "cognitive_cycles": cognitive_cycles,
        "mean_confidence": round(fmean(confidences), 4) if confidences else 0.0,
        "min_body_height_m": round(min(heights), 4) if heights else 0.0,
    }
    score = 50.0
    score += 15.0 if completed else 0.0
    score -= 35.0 if failed else 0.0
    score += min(15.0, cognitive_cycles * 1.5)
    score += min(10.0, metrics["mean_confidence"] * 10.0)
    score += 10.0 if metrics["min_body_height_m"] >= 0.11 else 0.0
    score -= min(20.0, anomalies * 5.0)
    return {"score": round(max(0.0, min(100.0, score)), 1), "metrics": metrics}


def compare_runs(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    metric_deltas = {}
    for name in (
        "anomalies",
        "frames",
        "cognitive_cycles",
        "mean_confidence",
        "min_body_height_m",
    ):
        metric_deltas[name] = round(right["metrics"][name] - left["metrics"][name], 4)
    return {
        "left": left,
        "right": right,
        "score_delta": round(right["score"] - left["score"], 1),
        "metric_deltas": metric_deltas,
        "winner": "right"
        if right["score"] > left["score"]
        else "left"
        if left["score"] > right["score"]
        else "tie",
    }
