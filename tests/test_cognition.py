from pathlib import Path

from birdbrain.adapters import Observation
from birdbrain.cognition import BaselineCognition
from birdbrain.evaluation import compare_runs, score_run
from birdbrain.memory import LocalMemory


def observation(sim_time: float = 0.0) -> Observation:
    return Observation(
        timestamp=sim_time,
        values={
            "duck": {"position": [0.0, 0.0, 0.15]},
            "blue_block": {"position": [0.6, 0.2, 0.05]},
        },
    )


def test_cognition_persists_memory_and_emits_explainable_trace(
    tmp_path: Path,
) -> None:
    memory = LocalMemory(tmp_path / "memory")
    cognition = BaselineCognition(memory, run_id="cognition-test")

    decision = cognition.decide(observation(), tick=0)
    event_types = [event_type for event_type, _ in decision.trace]

    assert decision.action.name == "set_joint_targets"
    assert event_types == [
        "OBSERVATION",
        "MEMORY_RETRIEVED",
        "WIKI_UPDATED",
        "GOAL_PROPOSED",
        "PLAN_CREATED",
        "SKILL_INVOKED",
    ]
    assert memory.recall("blue_block")[0]["run_id"] == "cognition-test"
    assert "blue_block.last_distance_m" in memory.facts()


def test_regression_score_rewards_completed_cognitive_runs() -> None:
    baseline = score_run(
        [
            {
                "type": "STATE_SNAPSHOT",
                "payload": {"confidence": 0.7, "duck": {"position": [0, 0, 0.12]}},
            },
            {"type": "RUN_STOPPED", "payload": {}},
        ]
    )
    candidate = score_run(
        [
            {
                "type": "STATE_SNAPSHOT",
                "payload": {"confidence": 0.8, "duck": {"position": [0, 0, 0.14]}},
            },
            {"type": "PLAN_CREATED", "payload": {}},
            {"type": "RUN_STOPPED", "payload": {}},
        ]
    )
    comparison = compare_runs(baseline, candidate)

    assert candidate["score"] > baseline["score"]
    assert comparison["winner"] == "right"
    assert comparison["metric_deltas"]["cognitive_cycles"] == 1
