"""The mind: perceive, decide, act, measure (docs/design.md section 3.6).

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

import json
import math
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from birdbrain.authoring import Author, Authoring, failure_reasons
from birdbrain.body import CLASSES, MICRODUCK, STOP, BodyProfile, Command, Observation
from birdbrain.expr import Evaluator, ExprError
from birdbrain.goals import Goal, approval_candidates, candidates, kinds_owner
from birdbrain.kr import SELF, KnowledgeBase, Position
from birdbrain.needs import Needs
from birdbrain.occupancy import CELL
from birdbrain.perception import Perception
from birdbrain.phrases import load as load_phrases
from birdbrain.reactions import ConditionReactionModel, ReactionModel
from birdbrain.records import SkillRecord
from birdbrain.relations import attempts, failures, inside, known
from birdbrain.relations import where as where_is
from birdbrain.rules import RuleLearner, features
from birdbrain.skills import (
    Abort,
    Context,
    Library,
    Outcome,
    SkillRun,
    resolve_args,
    start,
)

TIDY_GOAL = "Tidy the room: put every toy in the basket."
NEEDS_GOAL = ("Nobody gives you tasks. You live in this room and act on your own needs: energy "
              "(rest to recharge), curiosity (look around and explore), safety (avoid falling), and "
              "tidiness, because your owner likes the toys to be in the basket. Doing nothing useful "
              "is fine when nothing is worth doing.")
APPROVAL_GOAL = ("Nobody gives you tasks. You live in this room with your owner and act on your "
                 "own needs: energy (rest to recharge), curiosity (look around and explore), safety "
                 "(avoid falling), and approval: you want your owner to be pleased with you. She "
                 "tells you when she likes or dislikes something, but never what she wants; you "
                 "have to work that out from when she reacts. Doing nothing is fine when nothing "
                 "is worth doing.")
DEFAULT_TOOLS = ("pick", "deliver", "look_around", "explore", "rest")
#: Milestone 3b: the ways of putting a toy down are offered side by side (design section 4.3).
APPROVAL_TOOLS = ("pick", "deliver", "put_by_wall", "drop", "look_around", "explore", "rest")
#: Outcomes the causal rules predict: (name, how a rule states it, prior base rate as Beta
#: pseudo-counts, prior sd of the base log-odds). The fall prior is the base rate of E-014
#: (0.025 per trial), held more firmly because falls are rare.
RULE_OUTCOMES = (("effect", "its expected effect holds", (1.0, 1.0), 2.0),
                 ("fell", "the duck falls", (0.25, 9.75), 1.0))

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
    goals: tuple[Goal, ...] = ()          # self-generated goals with their scorecard (needs mode)


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
    goal: str | None = None               # the goal this action serves (needs mode)


class Provider(Protocol):
    name: str

    def choose(self, request: DecisionRequest) -> Choice: ...


class ProviderError(RuntimeError):
    """A provider could not produce a choice; `category` is safe to log."""

    def __init__(self, category: str, latency_s: float = 0.0, usage: dict[str, int] | None = None):
        super().__init__(category)
        self.category, self.latency_s, self.usage = category, latency_s, usage or {}


# ---------------------------------------------------------------------------
# The local policy: the fallback, and agent A of the evaluation
# ---------------------------------------------------------------------------


#: (p the action works without a fall, whether a credible rule bears on it), for a skill
#: on its arguments, optionally as if holding an object.
Judge = Callable[..., tuple[float, bool]]


class LocalPolicy:
    """Deterministic rules for an explicit tidy goal.

    With a `judge` (the causal rules), a toy a credible rule speaks against (a condition
    of it that lowers the chance a pick or its delivery works, or raises the chance of a
    fall) is a poor prospect: it waits until nothing better is known (ledger E-023,
    E-023b, E-029)."""

    name = "local"

    def __init__(self, ctx: Context, give_up_after: int = 3, rest_after: int = 6,
                 judge: Judge | None = None) -> None:
        self.ctx, self.give_up_after, self.rest_after = ctx, give_up_after, rest_after
        self.judge = judge
        self._idle = 0

    def better_than(self, toy: str) -> bool:
        """Some other known toy is not a poor prospect."""
        return any(e != toy and not self.worth(e)[1] for e in self.candidates())

    def worth(self, toy: str) -> tuple[float, bool]:
        """Chance that picking and delivering `toy` works without a fall, and whether a
        credible rule speaks against it."""
        pick, why_pick = self.judge("pick", {"x": toy})
        carry, why_carry = self.judge("deliver", {}, held=toy)
        return pick * carry, why_pick or why_carry

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
        here = kb.position(SELF)
        if toys and self.judge is not None:
            worth = {e: self.worth(e) for e in toys}
            good = [e for e in toys if not worth[e][1]]   # no credible rule against it (E-029)
            # A poor prospect is deferred, not dropped: it is tried when nothing better is
            # known and the duck has looked and explored for something better (E-023).
            choices = good or (toys if self._idle >= 2 else [])
            if choices:
                # Nearest first: ranking by the rules' uncertain means picks what looks best
                # by error (L-020; E-023, where it cost the playroom 0.2 toys a room).
                self._idle = 0
                best = min(choices, key=lambda e: kb.position(e).distance(here))
                why = "nearest toy outside the basket" if good else "nothing better known"
                return Choice("pick", {"x": best}, f"{why} (works {worth[best][0]:.2f})", p["pick"])
            toys = []
        if toys:
            self._idle = 0
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


class NeedsPolicy:
    """The local policy when no task is given: pursue the top-scoring goal (agent C)."""

    name = "local"

    def choose(self, request: DecisionRequest) -> Choice:
        tools = {t.name: t for t in request.tools}
        for goal in request.goals:
            for tool, params in goal.tools:
                if tool in tools:
                    return Choice(tool, dict(params), f"top of the scorecard: {goal.kind} for {goal.source} "
                                  f"(U = {goal.utility:.2f})", tools[tool].p_rule, goal=goal.id)
        raise ProviderError("no applicable goal")


# ---------------------------------------------------------------------------
# The mind
# ---------------------------------------------------------------------------

class Mind:
    def __init__(self, *, provider: Provider | None = None, library: Library | None = None,
                 body: BodyProfile = MICRODUCK, goal: str = TIDY_GOAL,
                 tools: tuple[str, ...] = DEFAULT_TOOLS, log: Log | None = None,
                 latency: str = "frozen", token_budget: int | None = None,
                 snapshot_hz: float = 2.0, speculate: bool = False,
                 memory_dir: Path | None = None, needs: bool | str = False,
                 room: tuple[float, float, float, float] | None = None, seed: int = 0,
                 credit: str = "moments", rules: str | None = None, owner_model: str = "kinds",
                 author: Author | None = None) -> None:
        if latency not in {"frozen", "real"}:
            raise ValueError("latency must be 'frozen' or 'real'")
        self.log: Log = log or (lambda kind, payload: None)
        self.kb = KnowledgeBase(self._kb_event)
        self.perception = Perception(self.kb, body)
        self.ctx = Context(self.kb, Evaluator(self.kb, CLASSES), body, log=self.log, map=self.perception.map)
        self.library = library or Library()
        # Needs mode (Milestone 3): no task; goals come from needs and are scored. The
        # social need is tidiness (needs=True) or approval (needs="approval", Milestone 3b).
        social = "tidiness" if needs is True else needs
        self.needs = Needs(social=social) if needs else None
        self.approval = bool(needs) and social == "approval"
        self.local = NeedsPolicy() if needs else LocalPolicy(self.ctx, judge=self.judge)
        self.provider: Provider = provider or self.local
        if needs and goal == TIDY_GOAL:
            goal = APPROVAL_GOAL if self.approval else NEEDS_GOAL
        if self.approval and tools == DEFAULT_TOOLS:
            tools = APPROVAL_TOOLS
        if room is not None:
            # The room's walls in the odometry frame: a map the robot would build with its
            # range sensor; given here (design section 4.3).
            self.kb.tell("bounds", (SELF,), tuple(float(v) for v in room), t=0.0, source="map")
        self.goal, self.tools, self.latency_mode = goal, tools, latency
        self._goal: Goal | None = None
        # Think while acting (ledger H-010): when a skill starts, ask for the decision that
        # should follow it, assuming its expected effect holds; use that answer if it does.
        if speculate and needs:
            # The speculative request would offer only the goals of the state before the
            # action, so after a pick it could never propose delivering (review, E-014).
            raise ValueError("speculation is not supported in needs mode")
        self.speculate = speculate
        self._next: dict[str, Any] | None = None
        self.token_budget, self.tokens_used = token_budget, 0
        # Lifetime memory: what survives between episodes (the room is reset, so
        # beliefs about where things are do not). Skill records for now.
        self.memory_dir = memory_dir
        self.records: dict[str, SkillRecord] = self._load_records()
        #: What the duck believes earns its owner's approval (Milestone 3b), kept for life.
        if owner_model not in {"kinds", "conditions"}:
            raise ValueError("owner_model must be 'kinds' or 'conditions'")
        if rules not in {None, "mean", "draw", "cautious"}:
            raise ValueError("rules must be None, 'mean', 'draw' or 'cautious'")
        self.owner_model = owner_model
        self.reactions = self._load_reactions() if self.approval else None
        if self.reactions is not None:
            self.reactions.credit = credit
        self._held_before, self._bumped_before = False, False
        #: Counted outcomes per kind of action (a pick by a wall is not a pick in the open).
        self.kind_records: dict[str, SkillRecord] = self._load_records("kind_records.json") if self.approval else {}
        self.rng = random.Random(seed)              # Thompson draws (reactions.py)
        self.np_rng = np.random.default_rng(seed)   # posterior draws of logistic models
        #: Causal rules (Milestone 4): how likely each skill's expected effect, and a fall, are
        #: under the conditions the duck believes hold. Always learned and scored; used for
        #: decisions when `rules` is set.
        self.use_rules = rules                      # None: counts; "mean" or "draw" (E-018)
        self._rule_draws: dict[tuple[str, str], Any] = {}
        self.rules = {name: self._load_rules(name, outcome, prior, sd) for name, outcome, prior, sd in RULE_OUTCOMES}
        #: Every scored outcome of the life (skill, features, status, reason, held, fell).
        self.outcomes: list[dict[str, Any]] = self._load_json("outcomes.json", [])
        #: Skills written by the cloud brain and their trials (Milestone 5, `authoring.py`).
        #: Written skills are tried whenever their situation recurs; new ones are requested
        #: only with an `author`.
        self.authoring = Authoring(author=author)
        self.episode: int | None = None             # set by the runner for lifetimes
        text = self._load_json("authored.json", None, raw=True)
        if text is not None:
            self.authoring.load(text, self.library)
        self.phrases = load_phrases() if self.approval else None
        self.stats = {"decisions": 0, "fallbacks": 0, "invalid": 0, "provider_errors": 0, "falls_sensed": 0}
        self._run: SkillRun | None = None
        self._action: dict[str, Any] | None = None
        self._snapshot_every = 1.0 / snapshot_hz if snapshot_hz > 0 else math.inf
        self._next_map = self._next_look = 0.0     # MAP events (E-030); reconsidering (E-023)
        self._next_snapshot = 0.0
        self.recent: list[dict[str, Any]] = []

    # -- per tick ---------------------------------------------------------------
    def step(self, obs: Observation) -> Command:
        fell = self._fell(obs)
        self.perception.update(obs)
        self.ctx.observe(obs)
        if fell and self._run is not None:
            # A fall ends the plan as failed: the body is somewhere else now (ledger E-013).
            try:
                self._run.throw(Abort("fell"))
            except (Abort, StopIteration):
                pass
            self._run.close()
            self._finish(Outcome("failed", "fell"))
        self._reconsider(obs.t)
        if self.reactions is not None:
            # The duck's own changes to the room, as its body senses them (E-016).
            if obs.holding != self._held_before or (obs.bumped and not self._bumped_before):
                self.reactions.moment(obs.t)
            self._held_before, self._bumped_before = obs.holding, obs.bumped
        if self.approval and (obs.heard or obs.petted):
            self._hear(obs)
        if self.needs is not None:
            state = self.state
            self.needs.update(self.kb, obs.t, moving=not self.ctx.cold, resting=state == "rest",
                              exploring=state in {"look_around", "explore"}, fell=fell)
            if self.needs.exhausted and state != "rest":
                # Homeostatic reflex: an empty battery forces rest without consulting the mind.
                if self._run is not None:
                    self._run.close()
                    self._finish(Outcome("interrupted", "battery empty"))
                self.log("REFLEX", {"reflex": "rest", "battery": round(self.needs.battery, 3)})
                self._start("rest", {}, Choice("rest", {}, "battery empty", provider="reflex", goal="rest"),
                            None, request=self.request())
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
        if command.reflex is not None and self._action is not None:
            self._action["reflexed"] = True       # the body is acting now; no reconsidering (E-025 review)
        if obs.t >= self._next_snapshot:
            self._next_snapshot = obs.t + self._snapshot_every
            self.log("STATE_SNAPSHOT", self.snapshot(obs, command))
        if obs.t >= self._next_map:
            # What the duck believes is in the way (E-030), for viewers: every 5 s.
            self._next_map = obs.t + 5.0
            cells = sorted(self.perception.map.occupied_cells)
            self.log("MAP", {"cell": CELL, "occupied": [list(c) for c in cells]})
        return command

    def _reconsider(self, t: float) -> None:
        """On the way to a toy the duck sees it better (its colour within 1 m). If the
        rules now credibly judge it a poor prospect (E-023), or, with an owner, the pick
        turns out to be another kind of action (E-024), stop and choose again. A stopped
        action is not an outcome of the skill and teaches nothing."""
        action = self._action
        if (action is None or self._run is None or self.provider is not self.local
                or "pick" not in {action["skill"], action["variant_of"]} or t < self._next_look):
            return
        self._next_look = t + 0.5
        toy = action["args"].get("x")
        if toy is None or self.kb.value("holding", SELF) is not None or action.get("reflexed"):
            return                  # a pick reflex once asked for runs to its end
        why = None
        if self.approval:
            # With an owner (E-024): the pick was chosen as a kind of action; if the duck now
            # sees what kind it is (the toy's colour), choose again with that knowledge.
            colour = self.kb.value("color", toy)
            if colour is not None and colour not in action["kind"].split():
                why = f"it is {colour}"
        elif isinstance(self.local, LocalPolicy) and self.local.judge is not None:
            worth, credible = self.local.worth(toy)
            if credible and self.local.better_than(toy):
                why = f"now judged a poor prospect ({worth:.2f})"
        if why is None:
            return
        self._run.close()
        self.log("RECONSIDERED", {"skill": action["skill"], "x": toy, "why": why,
                                  "summary": f"{action['skill']}({toy}) stopped: {why}"})
        self.stats["reconsidered"] = self.stats.get("reconsidered", 0) + 1
        self._finish(Outcome("interrupted", "reconsidered"))

    def _fell(self, obs: Observation) -> bool:
        """The body fell and got up elsewhere: odometry jumps further than one tick allows.
        On the robot the IMU reports the fall directly; the event is the same."""
        last, self._last_pose = getattr(self, "_last_pose", None), obs.odom
        if last is None or math.hypot(obs.odom[0] - last[0], obs.odom[1] - last[1]) < 0.15:
            return False
        where = Position.round(last[0], last[1], 0.05)
        event = self.kb.begin("fall", obs.t, [SELF], x=round(where.x, 3), y=round(where.y, 3),
                              during=self.state)
        self.kb.end(event, obs.t)
        self.stats["falls_sensed"] += 1
        return True

    def close(self) -> None:
        """End the running skill (recorded as interrupted) and save lifetime memory."""
        if self._run is not None:
            self._run.close()
            self._finish(Outcome("interrupted", "run ended"))
        self.reflect()
        self._save_records()
        if self.memory_dir is not None:
            for name, learner in self.rules.items():
                self._write_memory(f"rules_{name}.json", learner.to_json())
            self._write_memory("outcomes.json", json.dumps(self.outcomes) + "\n")
            self._write_memory("authored.json", self.authoring.to_json())
        if self.reactions is not None and self.memory_dir is not None:
            self._write_memory("owner_model.json", self.reactions.to_json())
            self._write_memory("kind_records.json", _records_json(self.kind_records))

    # -- reflection (Milestone 5) ---------------------------------------------------
    def reflect(self) -> None:
        """Between episodes: keep or retire written skills with enough trials, then, if the
        rules show a compound skill clearly failing under some condition, ask the author
        for a skill for that situation (`authoring.py`)."""
        for review in self.authoring.review(self.rng, self.episode):
            self.log("SKILL_REVIEWED", {**review, "summary": f"{review['child']}: {review['status']} "
                                                              f"(p better {review['p_better']:.2f})"})
        if self.authoring.author is None:
            return
        weak = self.authoring.weakness(self.rules["effect"], self.library)
        if weak is None:
            return
        skill, feature, value, evidence = weak
        entry = self.authoring.propose(skill, feature, value, evidence,
                                       failure_reasons(self.outcomes, skill, feature, value), self.library,
                                       episode=self.episode)
        self.stats["skills_requested"] = self.stats.get("skills_requested", 0) + 1
        self.stats["skills_written"] = self.stats.get("skills_written", 0) + (entry["status"] == "trial")
        self.log("SKILL_WRITTEN", {**{k: v for k, v in entry.items() if not k.startswith("answer")},
                                   "program": self.authoring.skills.get(entry.get("child", "")),
                                   "summary": f"asked for a skill for {skill} when {feature} {value}: {entry['status']}"
                                              + (f" ({entry['child']})" if entry.get("child") else "")})

    def _load_json(self, name: str, default: Any, raw: bool = False) -> Any:
        path = None if self.memory_dir is None else self.memory_dir / name
        if path is None or not path.is_file():
            return default
        text = path.read_text(encoding="utf-8")
        try:
            return text if raw else json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError(f"memory file {path} is unreadable ({error}); move it aside to start fresh") from None

    # -- the owner (Milestone 3b) -------------------------------------------------
    def _hear(self, obs: Observation) -> None:
        """Each phrase or pet is a reaction of the owner's: it moves the duck's estimate of
        her mood and is credited to the actions that could have caused it."""
        heard = [(text, self.phrases.valence(text)) for text in obs.heard]
        if obs.petted:
            heard.append(("(petted)", 1))
        for text, valence in heard:
            shares = {}
            if valence:
                self.needs.hear(valence)
                shares = self.reactions.react(valence, obs.t)
                self.stats["approvals" if valence > 0 else "disapprovals"] = (
                    self.stats.get("approvals" if valence > 0 else "disapprovals", 0) + 1)
            event = self.kb.begin("reaction", obs.t, [SELF], said=text, valence=valence,
                                  during=self.state, causes=shares)
            self.kb.end(event, obs.t)
            self.log("HEARD", {"said": text, "valence": valence, "during": self.state, "causes": shares,
                               "mood": round(self.needs.mood, 3),
                               "summary": f"owner: \"{text}\" ({'+' if valence > 0 else '-' if valence < 0 else '?'})"
                               + (f"; credited to {', '.join(f'{k} {v:.2f}' for k, v in shares.items())}" if shares else "")})

    def _owner_briefing(self) -> list[str]:
        out = []
        heard = [e for e in self.kb.find_events("reaction") if self.ctx.t - e.t0 <= 120.0][-5:]
        if heard:
            out.append("What your owner said recently, oldest first:")
            out += [f"- {self.ctx.t - e.t0:.0f} s ago, while you were doing {e.data['during']}: "
                    f"\"{e.data['said']}\" ("
                    + ("approval" if e.data["valence"] > 0 else "disapproval" if e.data["valence"] < 0
                       else "not a phrase you know") + ")" for e in heard]
        if isinstance(self.reactions, ConditionReactionModel):
            learned = self.reactions.rules()[:6]
            if learned:
                out.append("Conditions that change how she reacts (credible: at least three standard "
                           "deviations from no effect):")
                out += [f"- {r}." for r in learned]
        kinds = self.reactions.summary()
        if kinds:
            out.append("What you have learned about her reactions (each reaction is credited to the "
                       "actions that could have caused it; probabilities include a cautious prior):")
            out += [f"- after {k}: approval {v['p_approve']:.2f}, disapproval {v['p_disapprove']:.2f} "
                    f"({v['trials']:.0f} times)" for k, v in kinds.items()]
        return out

    def _thompson_draws(self) -> dict[str, float]:
        """Posterior draws of the owner's reactions, redrawn whenever the duck holds
        nothing: one set of beliefs per pick-and-put, so a put is not chosen against the
        beliefs that made the pick worth doing."""
        if self.kb.value("holding", SELF) is None or not hasattr(self, "_draws"):
            self._draws: dict[str, float] = {}
        return self._draws

    # -- causal rules (Milestone 4) -------------------------------------------------
    def predict(self, skill: str, args: dict[str, Any]) -> tuple[float, float]:
        """(p expected effect holds, p fall) for `skill` on `args` now, from the rules: their
        posterior mean, or with `rules="draw"` one model drawn from the posterior per skill
        and decision, shared by every candidate (Thompson sampling, ledger E-018)."""
        f = features(self.kb, self.ctx.t, args)
        if self.use_rules == "mean":
            return self.rules["effect"].predict(skill, f)[0], self.rules["fell"].predict(skill, f)[0]
        out = []
        for name in ("effect", "fell"):
            if name == "fell" and self.use_rules == "cautious":
                # Explore what is wanted, fear what is feared: falls are judged by an upper
                # credible bound (mean + 2 sd on the log-odds), so a little-known risky
                # pick is not tried on a lucky draw (ledger H-020).
                m = self.rules[name].model(skill)
                out.append(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, m.logit(f) + 2.0 * m.logit_sd(f))))))
                continue
            key = (name, skill)
            if key not in self._rule_draws:
                self._rule_draws[key] = self.rules[name].model(skill).draw(self.np_rng)
            out.append(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, self._rule_draws[key].logit(f))))))
        return out[0], out[1]

    def judge(self, skill: str, args: dict[str, Any], held: str | None = None) -> tuple[float, bool]:
        """The rules' chance that `skill` on `args` works (its expected effect holds) without
        a fall, optionally as if holding `held`, and whether a credible rule speaks against it."""
        f = features(self.kb, self.ctx.t, args, held=held)
        effect, _, why_effect = self.rules["effect"].predict(skill, f)
        fell, _, why_fell = self.rules["fell"].predict(skill, f)
        # Credible against it: a credible condition that lowers the chance of the effect or
        # raises the chance of a fall (E-025 review: any credible condition was taken).
        against = (self.rules["effect"].against(skill, why_effect, -1)
                   or self.rules["fell"].against(skill, why_fell, +1))
        return effect * (1.0 - fell), against

    def _owner_p(self):
        """The owner's reaction to an action, one posterior draw, held while the duck
        holds a toy so a pick and its put are chosen with the same beliefs."""
        draws = self._thompson_draws()
        if self.owner_model == "kinds":
            return kinds_owner(self.reactions, self.rng, draws, self.action_kind)

        def owner(skill: str, args: dict[str, Any]) -> tuple[float, float, float]:
            f = features(self.kb, self.ctx.t, args)
            ps = []
            for valence in (+1, -1):
                if (valence, skill) not in draws:
                    draws[(valence, skill)] = self.reactions.learner(valence).model(skill).draw(self.np_rng)
                z = draws[(valence, skill)].logit(f)
                ps.append(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z)))))
            return ps[0], ps[1], 0.0
        return owner

    def _predictions(self, skill: str, f: dict[str, str], record: SkillRecord) -> dict[str, Any]:
        """Every predictor's forecast for this action, recorded before it runs, so each can
        be scored on outcomes it has not seen (prequential evaluation, ledger E-017)."""
        kind = self.kind_records.get(self.action_kind(skill, self._action["args"])) if self.kind_records else None
        out: dict[str, Any] = {}
        for name, *_ in RULE_OUTCOMES:
            p_rules, n, when = self.rules[name].predict(skill, f)
            skill_p = record.p if name == "effect" else record.fall_rate
            kind_p = None if kind is None or not kind.trials else (kind.p if name == "effect" else kind.fall_rate)
            out[name] = {"rules": round(p_rules, 4), "skill": round(skill_p, 4),
                         "kind": None if kind_p is None else round(kind_p, 4),
                         "when": [f"{k} {v}" for k, v in when], "n": round(n, 1)}
        return out

    def _score_predictions(self, predicted: dict[str, Any], outcome: dict[str, bool]) -> dict[str, Any]:
        """Brier score of each predictor on this outcome; summed per run in `stats`."""
        scores: dict[str, Any] = {}
        for name, y in outcome.items():
            p = predicted[name]
            kind = p["kind"] if p["kind"] is not None else p["skill"]
            scores[name] = {k: round((v - float(y)) ** 2, 4) for k, v in
                            (("rules", p["rules"]), ("skill", p["skill"]), ("kind", kind))}
            for k, v in scores[name].items():
                key = f"brier_{name}_{k}"
                self.stats[key] = round(self.stats.get(key, 0.0) + v, 4)
            self.stats[f"brier_{name}_n"] = self.stats.get(f"brier_{name}_n", 0) + 1
        return scores

    def _load_rules(self, name: str, outcome: str, prior: tuple[float, float], sd_base: float) -> RuleLearner:
        path = None if self.memory_dir is None else self.memory_dir / f"rules_{name}.json"
        if path is None or not path.is_file():
            return RuleLearner(outcome, prior=prior, sd_base=sd_base)
        try:
            return RuleLearner.from_json(path.read_text(encoding="utf-8"), prior=prior, sd_base=sd_base)
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise ValueError(f"memory file {path} is unreadable ({error}); move it aside to start fresh") from None

    def action_kind(self, skill: str, args: dict[str, Any]) -> str:
        """The duck's own description of an action, for learning what its owner reacts to:
        a pick says where the toy was and, once the duck has seen it, its colour (E-024)."""
        if skill == "pick" and "x" in args:
            colour = self.kb.value("color", args["x"])
            return f"pick {colour + ' ' if colour else ''}from {where_is(self.kb, self.ctx.t, args['x'])}"
        return skill

    def _load_reactions(self) -> ReactionModel:
        cls = ConditionReactionModel if self.owner_model == "conditions" else ReactionModel
        path = None if self.memory_dir is None else self.memory_dir / "owner_model.json"
        if path is None or not path.is_file():
            return cls()
        try:
            return cls.from_json(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, TypeError, KeyError) as error:
            raise ValueError(f"memory file {path} is unreadable ({error}); move it aside to start fresh") from None

    def _write_memory(self, name: str, text: str) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.memory_dir / f".{name}.{os.getpid()}.tmp"       # one writer per memory dir
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.memory_dir / name)

    def _load_records(self, name: str = "skill_records.json") -> dict[str, SkillRecord]:
        path = None if self.memory_dir is None else self.memory_dir / name
        if path is None or not path.is_file():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            # Fail loudly: starting fresh would silently discard a lifetime of records.
            raise ValueError(f"memory file {path} is unreadable ({error}); move it aside to start fresh") from None
        return {name: SkillRecord(**{k: r[k] for k in ("trials", "effect_held", "done", "seconds", "falls", "recent")
                                     if k in r}) for name, r in raw.items()}

    def _save_records(self) -> None:
        if self.memory_dir is None:
            return
        self._write_memory("skill_records.json", _records_json(self.records))

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
        goals = ()
        if self.needs is not None:
            names = {t.name for t in tools}
            predict = self.predict if self.use_rules else None
            self._rule_draws = {}                   # one posterior draw per skill per decision
            goals = tuple(approval_candidates(self.kb, self.ctx.t, self.needs, self.records, names,
                                              self._owner_p(), self.kind_records, predict=predict,
                                              kind_of=self.action_kind)
                          if self.approval else
                          candidates(self.kb, self.ctx.t, self.needs, self.records, names, predict=predict))
            tools = _serving(tools, goals)
        return DecisionRequest(self.ctx.t, self.goal, self.briefing(goals), tuple(tools), goals)

    def _decide(self) -> None:
        request = self.request()
        consulted = self.provider is not self.local
        wait = None
        speculated = self._take_speculation(request)
        if speculated is not None:
            choice, fallback_reason, wait = speculated
        else:
            try:
                choice, fallback_reason = self._ask(request)
            except ProviderError as error:              # not even the local policy can act
                self.log("NO_DECISION", {"reason": error.category, "tools": [t.name for t in request.tools]})
                self._run, self._action = _idle(self.ctx), None
                return
        if wait is None:
            wait = choice.latency_s if consulted else 0.0      # also after a failed or invalid call
        self._start(choice.skill, choice.args, choice, fallback_reason, request, wait,
                    speculative=speculated is not None)
        if self.speculate and consulted:
            self._speculate(self._action["expect"], wait)

    def _start(self, skill: str, raw_args: dict[str, Any], choice: Choice, fallback_reason: str | None,
               request: DecisionRequest, wait: float = 0.0, speculative: bool = False) -> None:
        tool = next((t for t in request.tools if t.name == skill), None)
        record = self.records.get(skill, SkillRecord())
        expect = tool.expect if tool is not None else self.library[skill].expect
        args = resolve_args(self.ctx, self.library[skill], raw_args)
        held = self.kb.value("holding", SELF)
        goal = self._goal_for(request, choice.goal, skill, args)
        self._goal = goal
        if choice.provider != "reflex":
            self.stats["decisions"] += 1
        situation = features(self.kb, self.ctx.t, args)
        kind = self.action_kind(skill, args)
        ran, trials = self.authoring.choose(skill, situation, self.rng)
        parent, skill = skill, ran
        if skill != parent:
            expect = self.library[skill].expect
            record = self.records.get(skill, SkillRecord())
        self._action = {
            "skill": skill, "variant_of": parent if skill != parent else None, "written_trials": trials, "args": args, "t0": self.ctx.t, "held": held,
            "confirmed_before": None if self.needs is None else self.needs.confirmed(self.kb),
            "expect": expect, "p_rule": round(record.p, 4), "trials": record.trials,
            "p_model": choice.p if choice.provider not in {"local", "reflex"} else None,
            "provider": choice.provider, "model": choice.model, "reason": choice.reason,
            "goal": None if goal is None else goal.id, "goal_source": None if goal is None else goal.source,
            "kind": kind,
            "features": situation,
        }
        self._action["predicted"] = self._predictions(skill, self._action["features"], record)
        if self.reactions is not None:
            self.reactions.started(self._action["kind"], self.ctx.t, skill=skill,
                                   features=self._action["features"])
        payload = {
            **{k: v for k, v in self._action.items() if k not in {"confirmed_before", "written_trials"}}, "fallback": fallback_reason, "latency_s": round(choice.latency_s, 3),
            "usage": choice.usage, "briefing_chars": len(request.briefing),
            "tools": [t.name for t in request.tools], "speculative": speculative,
            "summary": f"{skill}({', '.join(map(str, args.values()))}): {choice.reason}",
        }
        if self.needs is not None:
            payload["needs"] = dict(self.needs.pressure)
            agrees = bool(request.goals) and goal is not None and goal.id == request.goals[0].id
            payload["agrees_with_scorecard"] = agrees
            payload["goal_named"] = choice.goal
            if choice.provider not in {"local", "reflex"}:
                # The cloud brain's own choices only: the local policy agrees by construction.
                named = choice.goal is not None and goal is not None and choice.goal == goal.id
                for key, value in (("cloud_decisions", 1), ("cloud_agrees_with_scorecard", agrees),
                                   ("cloud_goal_corrected", not named)):
                    self.stats[key] = self.stats.get(key, 0) + value
            payload["battery"] = round(self.needs.battery, 3)
            payload["scorecard"] = [g.to_dict() for g in request.goals[:6]]
            payload["scorecard_top"] = request.goals[0].id if request.goals else None
        self.log("DECISION", payload)
        run = start(self.ctx, self.library, skill, args)
        if self.latency_mode == "real" and wait > 0:
            run = _after_wait(self.ctx, wait, run)
        self._run = run

    @staticmethod
    def _goal_for(request: DecisionRequest, goal_id: str | None, skill: str, args: dict[str, Any]) -> Goal | None:
        """The goal an action serves: the one named, else the best-scoring goal that it serves."""
        if goal_id is not None:
            named = next((g for g in request.goals if g.id == goal_id), None)
            if named is not None and named.serves(skill, args):
                return named
        return next((g for g in request.goals if g.serves(skill, args)), None)

    # -- thinking while acting ------------------------------------------------------
    def _speculate(self, expect: str, wait: float) -> None:
        """Ask now for the decision that should follow the action just started.

        The call is made immediately (the simulation freezes for it, as for any call).
        On the robot it could only be sent once the current decision's answer arrived,
        `wait` seconds from now, so its answer counts as available `wait + latency_s`
        of simulated time later.
        """
        if self.token_budget is not None and self.tokens_used >= self.token_budget:
            self._next = None
            return
        action = self._action
        args = ", ".join(map(str, action["args"].values()))
        request = self.request()
        briefing = (request.briefing + f"\nYou have just started {action['skill']}({args}). "
                    f"Assume it succeeds, so that {expect} holds when it ends (held = "
                    f"{action['held'] or 'what you will be holding'}). "
                    "Choose the action to take right after it.")
        speculative = DecisionRequest(request.t, request.goal, briefing, request.tools, request.goals)
        started = time.monotonic()
        try:
            choice = self.provider.choose(speculative)
        except Exception as error:  # noqa: BLE001 - a failed speculation is simply not used
            self._next = None
            self.log("SPECULATION", {"status": "error", "error": type(error).__name__})
            return
        latency = choice.latency_s or time.monotonic() - started
        self.tokens_used += sum(v for k, v in choice.usage.items() if k in {"input", "output"})
        self._next = {"choice": choice, "ready_at": self.ctx.t + wait + latency, "for": action["skill"],
                      "t0": action["t0"]}
        self.stats["speculations"] = self.stats.get("speculations", 0) + 1

    def _take_speculation(self, request: DecisionRequest) -> tuple[Choice, None, float] | None:
        """The speculative answer, if the last action's expected effect held and the
        answer is still valid now; with the time still to wait for it."""
        pending, self._next = self._next, None
        last = self.recent[-1] if self.recent else None
        if pending is None or last is None or last["skill"] != pending["for"] or last["t0"] != pending["t0"]:
            return None
        if last["status"] != "done" or not last["effect_held"] or self.validate(pending["choice"], request) is not None:
            self.stats["speculation_misses"] = self.stats.get("speculation_misses", 0) + 1
            self.log("SPECULATION", {"status": "discarded", "skill": pending["choice"].skill,
                                     "status_was": last["status"], "effect_held": last["effect_held"]})
            return None
        self.stats["speculation_hits"] = self.stats.get("speculation_hits", 0) + 1
        wait = max(0.0, pending["ready_at"] - self.ctx.t)
        self.log("SPECULATION", {"status": "used", "skill": pending["choice"].skill, "wait_s": round(wait, 3)})
        return pending["choice"], None, wait

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
        if request.goals:
            if choice.goal is not None and choice.goal not in {g.id for g in request.goals}:
                return f"{choice.goal!r} is not one of the candidate goals"
            if not any(g.serves(choice.skill, choice.args) for g in request.goals):
                return f"{choice.skill} on {choice.args} serves none of the candidate goals"
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
        if self.needs is not None and action["skill"] in {"look_around", "explore"}:
            self.needs.observe_exploration(action["skill"], len(self.needs.confirmed(self.kb) - action["confirmed_before"]))
        fell = outcome.reason == "fell"
        # An action stopped from outside (the episode ended, the battery reflex) says nothing
        # about the skill, and an effect of "true" cannot fail: neither is scored or learned
        # as an outcome of the skill (review of E-017).
        scores: dict[str, Any] = {}
        if outcome.status != "interrupted":
            scored = {"fell": fell} if action["expect"] == "true" else {"effect": held, "fell": fell}
            scores = self._score_predictions(action["predicted"], scored)
            for name, y in scored.items():
                self.rules[name].add(action["skill"], action["features"], float(y))
            self.outcomes.append({"skill": action["skill"], "variant_of": action["variant_of"],
                                  "features": action["features"], "status": outcome.status,
                                  "reason": outcome.reason, "held": held, "fell": fell, "episode": self.episode,
                                  "trials": [t.child for t in action["written_trials"]]})
            self.authoring.record(action["written_trials"], action["skill"], held and not fell, fell)
        if self.reactions is not None:
            stopped = outcome.reason == "reconsidered"
            self.reactions.ended(action["kind"], self.ctx.t, counted=not stopped)
            if not stopped:
                self.kind_records.setdefault(action["kind"], SkillRecord()).record(
                    held, outcome.ok, self.ctx.t - action["t0"], outcome.reason == "fell")
        if outcome.reason != "reconsidered":            # a stopped pick is no trial of the skill
            record = self.records.setdefault(action["skill"], SkillRecord())
            record.record(held, outcome.ok, self.ctx.t - action["t0"], outcome.reason == "fell")
        result = {
            "skill": action["skill"], "args": action["args"], "status": outcome.status, "t0": action["t0"],
            "reason": outcome.reason, "path": outcome.path,
            "seconds": round(self.ctx.t - action["t0"], 2),
            "expect": action["expect"], "effect_held": held,
            "p_rule": action["p_rule"], "p_model": action["p_model"], "trials": action["trials"],
            "surprise_rule": _surprise(action["p_rule"], held),
            "surprise_model": _surprise(action["p_model"], held),
            "provider": action["provider"], "predicted": action["predicted"], "brier": scores,
        }
        self.recent = (self.recent + [result])[-8:]
        self.log("OUTCOME", {**result, "summary": f"{action['skill']} {outcome.status}"
                             + (f" ({outcome.reason})" if outcome.reason else "")
                             + f"; expected {action['expect']}: {'held' if held else 'did not hold'}"})

    # -- briefing ----------------------------------------------------------------
    def briefing(self, goals: tuple[Goal, ...] = ()) -> str:
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
                tries = attempts(kb, t, "pick", e)
                fails = failures(kb, t, "pick", e)
                if self.approval:
                    where += {"basket": "; in the basket", "wall": "; against a wall",
                              "open": "; in the open"}[where_is(kb, t, e)]
                else:
                    in_basket = any(inside(kb, t, e, b) for b in kb.of_class("basket"))
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
                   + (f", fell {r.falls} times" if r.falls else "")
                   for n, r in sorted(self.records.items())]
        if records:
            lines += ["Your skill record:", *records]
        learned = [learner.text(r) for learner in self.rules.values() for r in learner.rules()][:8]
        if learned:
            lines += [("What you have learned about when your skills work (each rule is credible: at "
                      "least three standard deviations from no effect):"), *(f"- {r}." for r in learned)]
        if self.needs is not None:
            p = self.needs.pressure
            scale = ("0 = satisfied, 1 = urgent; tidiness is weighted double, so it runs to 2"
                     if not self.approval else "0 = satisfied, 1 = urgent; approval is 0.5 when you "
                     "believe your owner is neither pleased nor displeased")
            lines.append(f"Your needs ({scale}): "
                         + ", ".join(f"{name} {p[name]:.2f}" for name in self.needs.NAMES)
                         + f". Battery {self.needs.battery:.0%}.")
            if self.reactions is not None:
                lines += self._owner_briefing()
            if goals:
                lines.append("Goals you could pursue, with a scorecard computed from your measured "
                             "outcomes (U = value + learning + information - cost - risk); it is "
                             "evidence, and the choice is yours:")
                for g in goals[:8]:
                    tools = ", ".join(f"{name}({', '.join(v for _, v in params)})" for name, params in g.tools)
                    lines.append(f"- {g.id} [{g.source}] U {g.utility:+.2f} (value {g.terms['dV']:.2f}, "
                                 f"learning {g.terms['LP']:.2f}, information {g.terms['IG']:.2f}, "
                                 f"cost {g.terms['C']:.2f}, risk {g.terms['R']:.2f}); act with {tools}")
                lines.append("Name the goal your action serves.")
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
                             "seen_ago": round(obs.t - a.t_obs, 1),
                             **({"color": kb.value("color", e)} if kb.value("color", e) else {}),
                             **({"size": kb.value("size", e)} if kb.value("size", e) else {})})
        return {
            "pose": [round(v, 3) for v in obs.odom], "speed": round(obs.speed, 3),
            "holding": kb.value("holding", SELF), "reflex": obs.reflex,
            "action": None if self._action is None else {
                k: self._action[k] for k in ("skill", "args", "reason", "expect", "p_rule", "p_model", "provider")},
            "note": command.note, "twist": [round(v, 3) for v in command.twist],
            "entities": entities, "records": {n: r.to_dict() for n, r in self.records.items()},
            "stats": dict(self.stats), "tokens": self.tokens_used,
            "view": self.perception.last_view,
            "needs": None if self.needs is None else self.needs.snapshot(),
            "owner_model": None if self.reactions is None else self.reactions.summary(),
            "written_skills": self.authoring.summary(),
            "rules": [learner.text(r) for learner in self.rules.values() for r in learner.rules()][:12],
            "goal": None if self._goal is None else self._goal.to_dict(),
        }

    def _kb_event(self, kind: str, payload: dict[str, Any]) -> None:
        if payload.get("args") == [SELF] and payload.get("rel") in {"at", "heading"}:
            return                              # the pose rides in snapshots
        self.log(kind, payload)


def _records_json(records: dict[str, SkillRecord]) -> str:
    data = {n: {"trials": r.trials, "effect_held": r.effect_held, "done": r.done, "seconds": r.seconds,
                "falls": r.falls, "recent": r.recent} for n, r in records.items()}
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _serving(tools: list[ToolSpec], goals: tuple[Goal, ...]) -> list[ToolSpec]:
    """Only the tools, and the arguments, that serve some candidate goal: with no task,
    an action that serves no goal has no reason to be offered (ledger E-014)."""
    out = []
    for tool in tools:
        uses = [dict(params) for g in goals for name, params in g.tools if name == tool.name]
        if not uses:
            continue
        params = {p: [v for v in values if any(u.get(p) == v for u in uses)] for p, values in tool.params.items()}
        if all(params.values()):
            out.append(replace(tool, params=params))
    return out


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
