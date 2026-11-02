from pathlib import Path

from birdbrain.adapters import Observation
from birdbrain.cloud_cognition import OpenAIResponsesCognition
from birdbrain.cognition import BaselineCognition
from birdbrain.evaluation import compare_runs, score_run
from birdbrain.memory import LocalMemory
from birdbrain.skills import SkillLibrary


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
        "MEMORY_CONSOLIDATED",
    ]
    assert memory.recall("blue_block")[0]["run_id"] == "cognition-test"
    assert "blue_block.last_distance_m" in memory.facts()


def test_memory_consolidation_tracks_provenance_and_conflicts(tmp_path: Path) -> None:
    memory = LocalMemory(tmp_path / "memory")
    for run_id, distance in (("run-a", 0.2), ("run-b", 0.8)):
        memory.remember(
            {
                "run_id": run_id,
                "entities": ["blue_block"],
                "distance_m": distance,
            }
        )

    profile = memory.consolidate("blue_block")

    assert profile["status"] == "conflicted"
    assert profile["source_run_ids"] == ["run-a", "run-b"]
    assert memory.facts()["blue_block.observation_profile"]["value"] == profile


def test_skill_parameters_learn_from_observed_outcomes(tmp_path: Path) -> None:
    memory = LocalMemory(tmp_path / "memory")
    skills = SkillLibrary(tmp_path / "skills")
    cognition = BaselineCognition(
        memory, run_id="learning-test", skills=skills
    )
    cognition.decide(observation(), tick=0)
    low = observation(1.0)
    low.values["duck"]["position"][2] = 0.09

    decision = cognition.decide(low, tick=10)
    update = next(payload for kind, payload in decision.trace if kind == "SKILL_UPDATED")

    assert update["success"] is False
    assert update["amplitude_after"] > update["amplitude_before"]
    assert skills.parameters("orient_to_object")["attempts"] == 1


def test_openai_cognition_uses_strict_schema_and_bounded_skill(tmp_path: Path) -> None:
    captured = {}

    def transport(payload: dict) -> dict:
        captured.update(payload)
        return {
            "output_text": '{"goal":"Inspect blue block","skill":"orient_to_object","rationale":"Novel object merits inspection.","confidence":0.88}',
            "usage": {"input_tokens": 120, "output_tokens": 24},
        }

    baseline = BaselineCognition(
        LocalMemory(tmp_path / "memory"), run_id="cloud-test"
    )
    cognition = OpenAIResponsesCognition(
        baseline, api_key="test-key", model="test-model", transport=transport
    )

    decision = cognition.decide(observation(), tick=0)

    assert captured["store"] is False
    assert captured["text"]["format"]["strict"] is True
    assert decision.skill == "orient_to_object"
    assert decision.metadata == {
        "provider": "openai_responses",
        "model": "test-model",
    }
    assert any(kind == "MODEL_RESPONDED" for kind, _ in decision.trace)


def test_openai_cognition_falls_back_without_exposing_error_details(
    tmp_path: Path,
) -> None:
    def unavailable(_payload: dict) -> dict:
        raise TimeoutError("secret upstream detail")

    baseline = BaselineCognition(
        LocalMemory(tmp_path / "memory"), run_id="fallback-test"
    )
    cognition = OpenAIResponsesCognition(
        baseline, api_key="test-key", transport=unavailable
    )

    decision = cognition.decide(observation(), tick=0)
    fallback = next(payload for kind, payload in decision.trace if kind == "MODEL_FALLBACK")

    assert decision.metadata["provider"] == "local_baseline"
    assert fallback["error"] == "TimeoutError"
    assert "secret upstream detail" not in str(fallback)


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
