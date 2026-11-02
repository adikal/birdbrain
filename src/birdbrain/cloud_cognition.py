"""Optional OpenAI Responses API cognition with a safe local fallback."""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from birdbrain.adapters import Observation
from birdbrain.cognition import BaselineCognition, CognitiveDecision

Transport = Callable[[dict[str, Any]], dict[str, Any]]


class OpenAIResponsesCognition:
    """Let a model select bounded goals and skills; local code retains control."""

    provider = "openai_responses"

    def __init__(
        self,
        baseline: BaselineCognition,
        *,
        api_key: str,
        model: str = "gpt-6-astra",
        timeout: float = 8.0,
        transport: Transport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.baseline = baseline
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._transport = transport or self._request

    def decide(self, observation: Observation, *, tick: int) -> CognitiveDecision:
        local = self.baseline.decide(observation, tick=tick)
        if tick % 10 != 0:
            return local
        request = self._payload(observation, local)
        started = time.monotonic()
        requested = {
            "provider": self.provider,
            "model": self.model,
            "summary": "Requesting bounded goal and skill selection",
        }
        try:
            response = self._transport(request)
            output = self._parse_output(response)
            goal_names = {str(goal["name"]) for goal in local.goals}
            if output["goal"] not in goal_names:
                raise ValueError("model selected an unknown goal")
            if output["skill"] not in {"orient_to_object", "recover_posture"}:
                raise ValueError("model selected an unknown skill")
            if not 0.0 <= float(output["confidence"]) <= 1.0:
                raise ValueError("model confidence was outside the safe range")
            latency_ms = round((time.monotonic() - started) * 1000, 1)
            usage = response.get("usage", {})
            trace = [
                *local.trace,
                ("MODEL_REQUESTED", requested),
                (
                    "MODEL_RESPONDED",
                    {
                        "provider": self.provider,
                        "model": self.model,
                        "latency_ms": latency_ms,
                        "usage": usage,
                        "goal": output["goal"],
                        "skill": output["skill"],
                        "confidence": output["confidence"],
                        "summary": "Cloud deliberation completed",
                    },
                ),
            ]
            return CognitiveDecision(
                action=self.baseline.action_for_skill(output["skill"], tick=tick),
                intention=output["goal"],
                rationale=output["rationale"],
                skill=output["skill"],
                attention="blue_block",
                goals=local.goals,
                trace=trace,
                metadata={"provider": self.provider, "model": self.model},
            )
        except Exception as error:  # noqa: BLE001 - fallback is the safety boundary
            local.trace.extend(
                [
                    ("MODEL_REQUESTED", requested),
                    (
                        "MODEL_FALLBACK",
                        {
                            "provider": self.provider,
                            "model": self.model,
                            "error": type(error).__name__,
                            "summary": "Cloud cognition unavailable; used local baseline",
                        },
                    ),
                ]
            )
            return local

    def _payload(
        self, observation: Observation, local: CognitiveDecision
    ) -> dict[str, Any]:
        duck = observation.values["duck"]["position"]
        block = observation.values["blue_block"]["position"]
        context = {
            "sim_time": observation.timestamp,
            "body_height_m": duck[2],
            "blue_block_position": block,
            "candidate_goals": local.goals,
            "memory_facts": self.baseline.memory.facts(),
        }
        goal_names = [str(goal["name"]) for goal in local.goals]
        return {
            "model": self.model,
            "store": False,
            "max_output_tokens": 300,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Select one supplied goal and one allowed skill. Keep the rationale brief. Never invent actions or actuator values.",
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(context)}],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "birdbrain_decision",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "goal": {"type": "string", "enum": goal_names},
                            "skill": {
                                "type": "string",
                                "enum": ["orient_to_object", "recover_posture"],
                            },
                            "rationale": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                        "required": ["goal", "skill", "rationale", "confidence"],
                        "additionalProperties": False,
                    },
                }
            },
        }

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        import certifi

        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(
                request, timeout=self.timeout, context=context
            ) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Responses API returned HTTP {error.code}") from error

    @staticmethod
    def _parse_output(response: dict[str, Any]) -> dict[str, Any]:
        if isinstance(response.get("output_text"), str):
            return json.loads(response["output_text"])
        for item in response.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return json.loads(content["text"])
        raise ValueError("response did not contain structured output")
