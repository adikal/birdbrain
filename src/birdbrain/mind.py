"""The mind: perceive, decide, act, measure (docs/design.md section 8).

Each control tick the mind folds the observation into the knowledge base and
advances the running skill. When a skill ends, the outcome is measured
against its prediction, and a provider chooses the next action as a tool
call. Local code validates every choice; anything invalid, late, or failed
falls back to the local policy, and the event log records why.

A prediction is structured: the skill's expected effect (an expression),
its deadline (the skill's budget), and probabilities from two sources, the
counted outcomes of earlier runs of the same skill and, when a model
chooses, the model's own estimate (ledger H-007).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from birdbrain.body import CLASSES, MICRODUCK, STOP, BodyProfile, Command, Observation
from birdbrain.expr import Evaluator, ExprError
from birdbrain.kr import SELF, KnowledgeBase, Position
from birdbrain.perception import Perception
from birdbrain.relations import attempts, failures, inside, known
from birdbrain.skills import Context, Library, Outcome, SkillRun, resolve_args, start

TIDY_GOAL = "Tidy the room: put every toy in the basket."
DEFAULT_TOOLS = ("pick", "deliver", "look_around", "explore", "rest")

Log = Callable[[str, dict[str, Any]], None]


# ---------------------------------------------------------------------------
# The decision boundary
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ToolSpec:
    name: str
    doc: str
    expect: str
    params: dict[str, list[str]]          # entity parameter -> the entity ids it may take
    p_rule: float
    trials: int


@dataclass(frozen=True)
class DecisionRequest:
    t: float
    goal: str
    briefing: str
    tools: tuple[ToolSpec, ...]


@dataclass(frozen=True)
class Choice:
    skill: str
    args: dict[str, Any]
    reason: str
    p: float | None = None                # the chooser's probability that the expected effect holds
    provider: str = "local"
    model: str | None = None
    latency_s: float = 0.0
    usage: dict[str, int] = field(default_factory=dict)


class Provider(Protocol):
    name: str

    def choose(self, request: DecisionRequest) -> Choice: ...


class ProviderError(RuntimeError):
    """A provider could not produce a choice; `category` is safe to log."""

    def __init__(self, category: str, latency_s: float = 0.0, usage: dict[str, int] | None = None):
        super().__init__(category)
        self.category, self.latency_s, self.usage = category, latency_s, usage or {}


# ---------------------------------------------------------------------------
# Skill statistics: counted outcomes per skill
# ---------------------------------------------------------------------------

@dataclass
class SkillRecord:
    trials: int = 0
    effect_held: int = 0
    done: int = 0
    seconds: float = 0.0

    @property
    def p(self) -> float:
        """Laplace estimate that the expected effect holds."""
        return (self.effect_held + 1) / (self.trials + 2)

    def to_dict(self) -> dict[str, Any]:
        return {"trials": self.trials, "effect_held": self.effect_held, "done": self.done,
                "mean_s": round(self.seconds / self.trials, 2) if self.trials else None,
                "p": round(self.p, 3)}


# ---------------------------------------------------------------------------
# The local policy: the fallback, and agent A of the evaluation
# ---------------------------------------------------------------------------

class LocalPolicy:
    """Deterministic rules for an explicit tidy goal."""

    name = "local"

    def __init__(self, ctx: Context, give_up_after: int = 3, rest_after: int = 6) -> None:
        self.ctx, self.give_up_after, self.rest_after = ctx, give_up_after, rest_after
        self._idle = 0

    def candidates(self) -> list[str]:
        kb, t = self.ctx.kb, self.ctx.t
        return [e for e in kb.of_class("toy")
                if known(kb, t, e) and not self._in_basket(e)
                and failures(kb, t, "pick", e) < self.give_up_after]

    def _in_basket(self, e: str) -> bool:
        return any(inside(self.ctx.kb, self.ctx.t, e, b) for b in self.ctx.kb.of_class("basket"))

    def choose(self, request: DecisionRequest) -> Choice:
        kb = self.ctx.kb
        tools = {tool.name: tool for tool in request.tools}
        p = {name: tool.p_rule for name, tool in tools.items()}
        if kb.value("holding", SELF) is not None and "deliver" in tools:
            self._idle = 0
            return Choice("deliver", {}, "holding a toy", p["deliver"])
        pickable = set(tools["pick"].params["x"]) if "pick" in tools else set()
        toys = [e for e in self.candidates() if e in pickable]
        if toys:
            self._idle = 0
            here = kb.position(SELF)
            nearest = min(toys, key=lambda e: kb.position(e).distance(here))
            return Choice("pick", {"x": nearest}, "nearest toy outside the basket", p["pick"])
        self._idle += 1
        if self._idle > self.rest_after:
            preferences = ("rest", "look_around", "explore")
            reason = "nothing left to tidy"
        elif self._idle % 2 == 1:
            preferences = ("look_around", "explore", "rest")
            reason = "no toy known; look"
        else:
            preferences = ("explore", "look_around", "rest")
            reason = "no toy in view; explore"
        for name in (*preferences, *tools):
            if name in tools and not tools[name].params:
                return Choice(name, {}, reason, p[name])
        raise ProviderError("no applicable tool")


# ---------------------------------------------------------------------------
# The mind
# ---------------------------------------------------------------------------

class Mind:
    def __init__(self, *, provider: Provider | None = None, library: Library | None = None,
                 body: BodyProfile = MICRODUCK, goal: str = TIDY_GOAL,
                 tools: tuple[str, ...] = DEFAULT_TOOLS, log: Log | None = None,
                 latency: str = "frozen", token_budget: int | None = None,
                 snapshot_hz: float = 2.0) -> None:
        if latency not in {"frozen", "real"}:
            raise ValueError("latency must be 'frozen' or 'real'")
        self.log: Log = log or (lambda kind, payload: None)
        self.kb = KnowledgeBase(self._kb_event)
        self.perception = Perception(self.kb, body)
        self.ctx = Context(self.kb, Evaluator(self.kb, CLASSES), body, log=self.log)
        self.library = library or Library()
        self.local = LocalPolicy(self.ctx)
        self.provider: Provider = provider or self.local
        self.goal, self.tools, self.latency_mode = goal, tools, latency
        self.token_budget, self.tokens_used = token_budget, 0
        self.records: dict[str, SkillRecord] = {}
        self.stats = {"decisions": 0, "fallbacks": 0, "invalid": 0, "provider_errors": 0}
        self._run: SkillRun | None = None
        self._action: dict[str, Any] | None = None
        self._snapshot_every = 1.0 / snapshot_hz if snapshot_hz > 0 else math.inf
        self._next_snapshot = 0.0
        self.recent: list[dict[str, Any]] = []

    # -- per tick ---------------------------------------------------------------
    def step(self, obs: Observation) -> Command:
        self.perception.update(obs)
        self.ctx.observe(obs)
        command = STOP
        for _ in range(3):                    # a skill that ends at once yields nothing
            if self._run is None:
                self._decide()
            try:
                command = next(self._run)
                break
            except StopIteration as stop:
                self._finish(stop.value)
        self.ctx.last = command
        if obs.t >= self._next_snapshot:
            self._next_snapshot = obs.t + self._snapshot_every
            self.log("STATE_SNAPSHOT", self.snapshot(obs, command))
        return command

    def close(self) -> None:
        """End the running skill (recorded as interrupted) so nothing is logged after the run."""
        if self._run is not None:
            self._run.close()
            self._finish(Outcome("interrupted", "run ended"))

    @property
    def state(self) -> str:
        return "idle" if self._action is None else self._action["skill"]

    # -- deciding ---------------------------------------------------------------
    def request(self) -> DecisionRequest:
        tools = []
        for name in self.tools:
            skill = self.library[name]
            params: dict[str, list[str]] = {}
            for param, cls in skill.params.items():
                params[param] = [e for e in self.kb.of_class(cls) if known(self.kb, self.ctx.t, e)]
            if any(not ids for ids in params.values()):
                continue                       # nothing it could be applied to
            record = self.records.get(name, SkillRecord())
            tools.append(ToolSpec(name, skill.doc, skill.expect, params, record.p, record.trials))
        return DecisionRequest(self.ctx.t, self.goal, self.briefing(), tuple(tools))

    def _decide(self) -> None:
        request = self.request()
        consulted = self.provider is not self.local
        try:
            choice, fallback_reason = self._ask(request)
        except ProviderError as error:              # not even the local policy can act
            self.log("NO_DECISION", {"reason": error.category, "tools": [t.name for t in request.tools]})
            self._run, self._action = _idle(self.ctx), None
            return
        tool = next(t for t in request.tools if t.name == choice.skill)
        args = resolve_args(self.ctx, self.library[choice.skill], choice.args)
        held = self.kb.value("holding", SELF)
        self.stats["decisions"] += 1
        self._action = {
            "skill": choice.skill, "args": args, "t0": self.ctx.t, "held": held,
            "expect": tool.expect, "p_rule": round(tool.p_rule, 4), "trials": tool.trials,
            "p_model": choice.p if choice.provider != "local" else None,
            "provider": choice.provider, "model": choice.model, "reason": choice.reason,
        }
        self.log("DECISION", {
            **self._action, "fallback": fallback_reason, "latency_s": round(choice.latency_s, 3),
            "usage": choice.usage, "briefing_chars": len(request.briefing),
            "tools": [t.name for t in request.tools],
            "summary": f"{choice.skill}({', '.join(map(str, args.values()))}): {choice.reason}",
        })
        run = start(self.ctx, self.library, choice.skill, args)
        if self.latency_mode == "real" and consulted and choice.latency_s > 0:
            run = _after_wait(self.ctx, choice.latency_s, run)    # also after a failed or invalid call
        self._run = run

    def _ask(self, request: DecisionRequest) -> tuple[Choice, str | None]:
        if self.provider is self.local:
            return self.local.choose(request), None
        if self.token_budget is not None and self.tokens_used >= self.token_budget:
            return self._fallback(request, "token budget spent")
        started = time.monotonic()
        try:
            choice = self.provider.choose(request)
        except ProviderError as error:
            self.stats["provider_errors"] += 1
            self.tokens_used += sum(v for k, v in error.usage.items() if k in {"input", "output"})
            return self._waited(self._fallback(request, f"provider: {error.category}"),
                                error.latency_s or time.monotonic() - started)
        except Exception as error:  # noqa: BLE001 - any provider failure falls back
            self.stats["provider_errors"] += 1
            return self._waited(self._fallback(request, f"provider: {type(error).__name__}"),
                                time.monotonic() - started)
        if not choice.latency_s:
            choice = Choice(**{**choice.__dict__, "latency_s": time.monotonic() - started})
        self.tokens_used += sum(v for k, v in choice.usage.items() if k in {"input", "output"})
        problem = self.validate(choice, request)
        if problem is not None:
            self.stats["invalid"] += 1
            self.log("CHOICE_REJECTED", {"skill": choice.skill, "args": choice.args, "problem": problem,
                                          "provider": choice.provider, "reason": choice.reason})
            fallback, why = self._fallback(request, f"invalid: {problem}")
            return Choice(**{**fallback.__dict__, "latency_s": choice.latency_s, "usage": choice.usage}), why
        return choice, None

    @staticmethod
    def _waited(result: tuple[Choice, str], latency_s: float) -> tuple[Choice, str]:
        choice, why = result
        return Choice(**{**choice.__dict__, "latency_s": latency_s}), why

    def _fallback(self, request: DecisionRequest, why: str) -> tuple[Choice, str]:
        self.stats["fallbacks"] += 1
        return self.local.choose(request), why

    def validate(self, choice: Choice, request: DecisionRequest) -> str | None:
        tool = next((t for t in request.tools if t.name == choice.skill), None)
        if tool is None:
            return f"{choice.skill!r} is not an available tool"
        if set(choice.args) != set(tool.params):
            return f"{choice.skill} takes {sorted(tool.params)}, got {sorted(choice.args)}"
        for param, value in choice.args.items():
            if value not in tool.params[param]:
                return f"{value!r} is not a valid {param} for {choice.skill}"
        if choice.p is not None and not (isinstance(choice.p, (int, float)) and 0.0 <= choice.p <= 1.0):
            return "p must be a probability"
        try:
            resolve_args(self.ctx, self.library[choice.skill], choice.args)
        except ExprError as error:
            return str(error)
        return None

    # -- measuring --------------------------------------------------------------
    def _finish(self, outcome: Outcome) -> None:
        action, self._action, self._run = self._action, None, None
        if action is None:
            return
        env = {**action["args"], "held": action["held"]}
        try:
            held = bool(self.ctx.evaluator.eval(action["expect"], env, self.ctx.t))
        except ExprError:
            held = False
        record = self.records.setdefault(action["skill"], SkillRecord())
        record.trials += 1
        record.effect_held += held
        record.done += outcome.ok
        record.seconds += self.ctx.t - action["t0"]
        result = {
            "skill": action["skill"], "args": action["args"], "status": outcome.status,
            "reason": outcome.reason, "path": outcome.path,
            "seconds": round(self.ctx.t - action["t0"], 2),
            "expect": action["expect"], "effect_held": held,
            "p_rule": action["p_rule"], "p_model": action["p_model"], "trials": action["trials"],
            "surprise_rule": _surprise(action["p_rule"], held),
            "surprise_model": _surprise(action["p_model"], held),
            "provider": action["provider"],
        }
        self.recent = (self.recent + [result])[-8:]
        self.log("OUTCOME", {**result, "summary": f"{action['skill']} {outcome.status}"
                             + (f" ({outcome.reason})" if outcome.reason else "")
                             + f"; expected {action['expect']}: {'held' if held else 'did not hold'}"})

    # -- briefing ----------------------------------------------------------------
    def briefing(self) -> str:
        kb, t = self.kb, self.ctx.t
        me = kb.position(SELF)
        yaw = math.degrees(kb.value("heading", SELF, default=0.0))
        held = kb.value("holding", SELF)
        lines = [f"Goal: {self.goal}", f"Time: {t:.1f} s.",
                 f"You are at ({me.x:+.2f}, {me.y:+.2f}) m, heading {yaw:+.0f} degrees, "
                 f"holding {held or 'nothing'}." if me else "Your position is unknown."]
        objects = []
        for e in sorted(kb.entities):
            a = kb.get("at", e)
            if (e == SELF or kb.cls(e) == "place" or a is None or not isinstance(a.value, Position)
                    or not known(kb, t, e)):
                continue
            p = a.value
            where = (f"{e} at ({p.x:+.2f}, {p.y:+.2f}) m, uncertainty {p.sigma:.2f} m, "
                     f"{p.distance(me):.2f} m from you, last seen {t - a.t_obs:.0f} s ago")
            if kb.cls(e) == "toy":
                in_basket = any(inside(kb, t, e, b) for b in kb.of_class("basket"))
                tries = attempts(kb, t, "pick", e)
                fails = failures(kb, t, "pick", e)
                where += "; in the basket" if in_basket else "; not in the basket"
                if tries:
                    where += f"; pick tried {tries} times, failed {fails}"
            objects.append(f"- {where}.")
        lines += ["Objects you know about:", *(objects or ["- none yet."])]
        if self.recent:
            lines.append("Your recent actions, oldest first:")
            for r in self.recent[-6:]:
                args = ", ".join(map(str, r["args"].values()))
                lines.append(f"- {r['skill']}({args}) {r['status']}"
                             + (f" ({r['reason']})" if r["reason"] else "")
                             + f" after {r['seconds']:.0f} s; expected effect "
                             + ("held." if r["effect_held"] else "did not hold."))
        records = [f"- {n}: {r.trials} tries, expected effect held {r.effect_held}"
                   for n, r in sorted(self.records.items())]
        if records:
            lines += ["Your skill record:", *records]
        return "\n".join(lines)

    def snapshot(self, obs: Observation, command: Command) -> dict[str, Any]:
        kb = self.kb
        entities = []
        for e in sorted(kb.entities):
            a = kb.get("at", e)
            if e == SELF or a is None or not isinstance(a.value, Position):
                continue
            entities.append({"id": e, "cls": kb.cls(e), "x": round(a.value.x, 3), "y": round(a.value.y, 3),
                             "sigma": round(a.value.sigma, 3), "conf": round(a.conf, 2),
                             "seen_ago": round(obs.t - a.t_obs, 1)})
        return {
            "pose": [round(v, 3) for v in obs.odom], "speed": round(obs.speed, 3),
            "holding": kb.value("holding", SELF), "reflex": obs.reflex,
            "action": None if self._action is None else {
                k: self._action[k] for k in ("skill", "args", "reason", "expect", "p_rule", "p_model", "provider")},
            "note": command.note, "twist": [round(v, 3) for v in command.twist],
            "entities": entities, "records": {n: r.to_dict() for n, r in self.records.items()},
            "stats": dict(self.stats), "tokens": self.tokens_used,
            "view": self.perception.last_view,
        }

    def _kb_event(self, kind: str, payload: dict[str, Any]) -> None:
        if payload.get("args") == [SELF] and payload.get("rel") in {"at", "heading"}:
            return                              # the pose rides in snapshots
        self.log(kind, payload)


def _idle(ctx: Context, seconds: float = 1.0) -> SkillRun:
    """Stand still briefly when no action can be chosen, then decide again."""
    t0 = ctx.t
    while ctx.t - t0 < seconds:
        yield Command(head=ctx.body.head_level, note="no applicable action")
    return Outcome("done")


def _after_wait(ctx: Context, seconds: float, run: SkillRun) -> SkillRun:
    """Stand for `seconds` of simulated time, as the robot would while the cloud answered."""
    t0 = ctx.t
    while ctx.t - t0 < seconds:
        yield Command(head=ctx.body.head_level, note="waiting for the cloud brain")
    return (yield from run)


def _surprise(p: float | None, held: bool) -> float | None:
    if p is None:
        return None
    q = p if held else 1.0 - p
    return round(-math.log(max(q, 1e-6)), 4)


__all__ = [
    "TIDY_GOAL",
    "Choice",
    "DecisionRequest",
    "LocalPolicy",
    "Mind",
    "Provider",
    "ProviderError",
    "ToolSpec",
]
