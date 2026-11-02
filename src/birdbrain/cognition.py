"""Provider-neutral deterministic cognition baseline for embodied experiments."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from birdbrain.adapters import Action, Observation
from birdbrain.memory import LocalMemory


@dataclass(frozen=True, slots=True)
class CognitiveDecision:
    action: Action
    intention: str
    rationale: str
    skill: str
    attention: str
    goals: list[dict[str, Any]]
    trace: list[tuple[str, dict[str, Any]]]


class BaselineCognition:
    """A reproducible policy that exercises the complete cognition boundary."""

    def __init__(self, memory: LocalMemory, *, run_id: str) -> None:
        self.memory = memory
        self.run_id = run_id

    def decide(self, observation: Observation, *, tick: int) -> CognitiveDecision:
        values = observation.values
        duck = values["duck"]["position"]
        block = values["blue_block"]["position"]
        distance = math.hypot(block[0] - duck[0], block[1] - duck[1])
        body_height = float(duck[2])
        recalled = self.memory.recall("blue_block", limit=2)
        novelty = (
            1.0
            if not recalled
            else min(1.0, abs(distance - recalled[-1]["distance_m"]) * 4)
        )
        goals = sorted(
            [
                {
                    "name": "Stabilize posture",
                    "utility": 0.95 if body_height < 0.13 else 0.62,
                },
                {"name": "Inspect blue block", "utility": 0.68 + 0.24 * novelty},
                {"name": "Map arena", "utility": 0.38},
            ],
            key=lambda goal: goal["utility"],
            reverse=True,
        )
        selected = goals[0]["name"]
        skill = (
            "recover_posture" if selected == "Stabilize posture" else "orient_to_object"
        )
        phase = tick * 0.12
        amplitude = 0.07 if skill == "recover_posture" else 0.12
        targets = {
            "neck_motor": 0.22 * math.sin(phase * 0.35),
            "left_hip_motor": amplitude * math.sin(phase),
            "right_hip_motor": -amplitude * math.sin(phase),
            "left_ankle_motor": -0.5 * amplitude * math.sin(phase + 0.8),
            "right_ankle_motor": 0.5 * amplitude * math.sin(phase + 0.8),
        }
        trace: list[tuple[str, dict[str, Any]]] = []
        if tick % 10 == 0:
            episode = {
                "run_id": self.run_id,
                "sim_time": observation.timestamp,
                "entities": ["microduck", "blue_block"],
                "distance_m": distance,
                "body_height_m": body_height,
            }
            self.memory.remember(episode)
            fact = self.memory.update_fact(
                "blue_block.last_distance_m",
                round(distance, 4),
                source_run_id=self.run_id,
                sequence_hint=tick,
            )
            trace = [
                (
                    "OBSERVATION",
                    {"summary": f"Blue block is {distance:.2f} m away", **episode},
                ),
                (
                    "MEMORY_RETRIEVED",
                    {
                        "entity": "blue_block",
                        "matches": len(recalled),
                        "episodes": recalled,
                    },
                ),
                ("WIKI_UPDATED", {"fact": "blue_block.last_distance_m", **fact}),
                (
                    "GOAL_PROPOSED",
                    {
                        "candidates": goals,
                        "selected": selected,
                        "source": "baseline_cognition",
                    },
                ),
                (
                    "PLAN_CREATED",
                    {
                        "goal": selected,
                        "steps": ["orient", skill, "observe_outcome"],
                        "predicted_success": goals[0]["utility"],
                    },
                ),
                (
                    "SKILL_INVOKED",
                    {
                        "skill": skill,
                        "summary": f"Executing {skill}",
                        "targets": targets,
                    },
                ),
            ]
        return CognitiveDecision(
            action=Action("set_joint_targets", targets),
            intention=selected,
            rationale=f"Selected highest utility goal after recalling {len(recalled)} relevant episodes.",
            skill=skill,
            attention="blue_block",
            goals=goals,
            trace=trace,
        )
