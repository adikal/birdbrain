"""The cloud brain on AWS Bedrock, through the Converse API.

Skills are offered as tools whose arguments are enumerated entity ids, so
the model's whole output vocabulary is "call one of these, on one of these".
Each tool also asks for `p`, the model's probability that the skill's stated
effect will hold when it ends, and a one-line `reason`. Local code still
validates every call (`Mind.validate`).

Credentials come from the standard AWS chain (AWS_PROFILE, SSO, environment,
instance roles). Nothing about them is logged; errors are reduced to a
category before they leave this module.
"""

from __future__ import annotations

import os
import time
from typing import Any

from birdbrain.mind import Choice, DecisionRequest, ProviderError, ToolSpec

DEFAULT_MODEL = "us.anthropic.claude-sonnet-5-5"
DEFAULT_REGION = "us-west-2"

SYSTEM = """You are the mind of BirdBrain, a small duck robot (25 cm tall) living in a room.
Read the goal statement at the top of each briefing: it says whether you have a task.
You act only by calling exactly one of the tools you are given; each tool is a skill the duck
already knows. Arguments must be ids from the tool's list; never invent objects.
Your senses are a forward camera that reports object classes and a short-range depth sensor.
Object positions come from that camera and can be wrong, especially far away.
For the call, give p: your probability that the tool's stated effect will hold when it ends,
and a brief reason (one sentence). Think about what you know, what you are unsure of, and what
has and has not worked so far."""


class BedrockProvider:
    name = "bedrock"

    def __init__(self, *, model: str = DEFAULT_MODEL, region: str = DEFAULT_REGION,
                 client: Any = None, max_tokens: int = 1024, read_timeout: float = 30.0) -> None:
        # Sonnet 5.5 on Bedrock accepts neither a forced tool choice nor `temperature`
        # (ledger E-009), so the tool call is requested with toolChoice "auto" and
        # a reply without one is a provider error that falls back.
        self.model, self.region, self.max_tokens = model, region, max_tokens
        if client is None:
            import boto3
            from botocore.config import Config
            client = boto3.client("bedrock-runtime", region_name=region, config=Config(
                connect_timeout=5, read_timeout=read_timeout, retries={"max_attempts": 2, "mode": "standard"}))
        self.client = client

    @classmethod
    def from_env(cls, model: str | None = None) -> BedrockProvider:
        return cls(model=model or os.environ.get("BIRDBRAIN_BEDROCK_MODEL", DEFAULT_MODEL),
                   region=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or DEFAULT_REGION)

    def choose(self, request: DecisionRequest) -> Choice:
        started = time.monotonic()
        try:
            response = self.client.converse(
                modelId=self.model,
                system=[{"text": SYSTEM}],
                messages=[{"role": "user", "content": [{"text": request.briefing + "\n\nChoose the next action."}]}],
                toolConfig={"tools": [tool_spec(t, request.goals) for t in request.tools], "toolChoice": {"auto": {}}},
                inferenceConfig={"maxTokens": self.max_tokens},
            )
        except Exception as error:  # noqa: BLE001 - reduced to a category below
            raise ProviderError(_category(error), time.monotonic() - started) from None
        latency = time.monotonic() - started
        usage = response.get("usage", {})
        tokens = {"input": int(usage.get("inputTokens", 0)), "output": int(usage.get("outputTokens", 0))}
        call = next((block["toolUse"] for block in response.get("output", {}).get("message", {}).get("content", [])
                     if "toolUse" in block), None)
        if call is None:
            raise ProviderError(f"no_tool_call ({response.get('stopReason', 'unknown')})", latency, tokens)
        given = dict(call.get("input") or {})
        p, reason = given.pop("p", None), str(given.pop("reason", ""))[:300]
        goal = given.pop("goal", None)
        try:
            p = None if p is None else float(p)
        except (TypeError, ValueError):
            raise ProviderError("malformed_p", latency, tokens) from None
        return Choice(skill=str(call.get("name", "")), args=given, reason=reason, p=p,
                      provider=self.name, model=self.model, latency_s=latency, usage=tokens,
                      goal=None if goal is None else str(goal))


def tool_spec(tool: ToolSpec, goals: tuple = ()) -> dict[str, Any]:
    properties: dict[str, Any] = {
        param: {"type": "string", "enum": ids, "description": f"which object ({len(ids)} known)"}
        for param, ids in tool.params.items()
    }
    properties["p"] = {"type": "number", "minimum": 0, "maximum": 1,
                       "description": f"probability that `{tool.expect}` holds when this ends"}
    properties["reason"] = {"type": "string", "description": "one sentence"}
    served = [g.id for g in goals if any(name == tool.name for name, _ in g.tools)]
    if served:
        properties["goal"] = {"type": "string", "enum": served, "description": "the goal this action serves"}
    record = (f" So far: {tool.trials} tries, effect held with estimated probability {tool.p_rule:.2f}."
              if tool.trials else " Not tried yet.")
    return {"toolSpec": {
        "name": tool.name,
        "description": f"{tool.doc} Expected effect: {tool.expect}.{record}",
        "inputSchema": {"json": {"type": "object", "properties": properties,
                                 "required": [*tool.params, "p", "reason", *(["goal"] if served else [])]}},
    }}


def _category(error: Exception) -> str:
    code = getattr(error, "response", {}).get("Error", {}).get("Code") if hasattr(error, "response") else None
    if code:
        return {"ThrottlingException": "throttled", "AccessDeniedException": "access_denied",
                "ValidationException": "validation", "ModelTimeoutException": "timeout",
                "ResourceNotFoundException": "model_unavailable",
                "ServiceUnavailableException": "unavailable"}.get(code, f"client_error:{code}")
    name = type(error).__name__
    if "Timeout" in name:
        return "timeout"
    if "Credential" in name or "NoRegion" in name:
        return "credentials"
    return name


class BedrockAuthor:
    """Writes skills (Milestone 5, `authoring.py`) with the same model and credentials."""

    def __init__(self, provider: BedrockProvider | None = None, max_tokens: int = 4096) -> None:
        self.provider = provider or BedrockProvider.from_env()
        self.max_tokens = max_tokens

    @property
    def model(self) -> str:
        return self.provider.model

    def write(self, prompt: str) -> tuple[dict[str, Any], dict[str, int]]:
        from birdbrain.authoring import SYSTEM as AUTHOR_SYSTEM
        from birdbrain.authoring import write_skill_tool
        try:
            response = self.provider.client.converse(
                modelId=self.provider.model, system=[{"text": AUTHOR_SYSTEM}],
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                toolConfig={"tools": [write_skill_tool()], "toolChoice": {"auto": {}}},
                inferenceConfig={"maxTokens": self.max_tokens})
        except Exception as error:  # noqa: BLE001 - reduced to a category
            raise ProviderError(_category(error)) from None
        usage = response.get("usage", {})
        tokens = {"input": int(usage.get("inputTokens", 0)), "output": int(usage.get("outputTokens", 0))}
        call = next((block["toolUse"] for block in response.get("output", {}).get("message", {}).get("content", [])
                     if "toolUse" in block), None)
        if call is None:
            raise ProviderError(f"no_tool_call ({response.get('stopReason', 'unknown')})", 0.0, tokens)
        return dict(call.get("input") or {}), tokens


JUDGE_SYSTEM = """You advise a small two-legged duck robot about objects it has just seen, before it has
tried to handle them. Answer with what you would expect from the object's appearance and the
robot's body, as a careful engineer would. Say how many trials of the robot's own experience your
judgement is worth: little if appearance says little, more if the answer follows from the body."""


def judge_tool() -> dict[str, Any]:
    p = {"type": "number", "minimum": 0, "maximum": 1}
    return {"toolSpec": {
        "name": "judge_object",
        "description": "Your expectation about the robot handling this object.",
        "inputSchema": {"json": {"type": "object", "properties": {
            "p_hold": {**p, "description": "probability that a pick leaves the object held in the beak"},
            "p_delivered": {**p, "description": "probability that, once held, carrying it to the basket and "
                                                "dropping it in works"},
            "p_fall": {**p, "description": "probability that the robot falls while carrying it to the basket"},
            "worth_trials": {"type": "number", "minimum": 0, "maximum": 10,
                             "description": "how many of the robot's own trials this judgement is worth"},
            "reason": {"type": "string", "description": "one sentence"}},
            "required": ["p_hold", "p_delivered", "p_fall", "worth_trials", "reason"]}}}}


class BedrockJudge:
    """The cloud brain's prior about an object, from how it looks (ledger E-036, H-009)."""

    def __init__(self, provider: BedrockProvider | None = None, max_tokens: int = 512) -> None:
        self.provider = provider or BedrockProvider.from_env()
        self.max_tokens = max_tokens

    def judge(self, prompt: str) -> tuple[dict[str, Any], dict[str, int]]:
        try:
            response = self.provider.client.converse(
                modelId=self.provider.model, system=[{"text": JUDGE_SYSTEM}],
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                toolConfig={"tools": [judge_tool()], "toolChoice": {"auto": {}}},
                inferenceConfig={"maxTokens": self.max_tokens})
        except Exception as error:  # noqa: BLE001 - reduced to a category
            raise ProviderError(_category(error)) from None
        usage = response.get("usage", {})
        tokens = {"input": int(usage.get("inputTokens", 0)), "output": int(usage.get("outputTokens", 0))}
        call = next((block["toolUse"] for block in response.get("output", {}).get("message", {}).get("content", [])
                     if "toolUse" in block), None)
        if call is None:
            raise ProviderError(f"no_tool_call ({response.get('stopReason', 'unknown')})", 0.0, tokens)
        return dict(call.get("input") or {}), tokens
