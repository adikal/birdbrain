"""Actions: primitives and compound skills (docs/design.md section 3.5).

Every skill, primitive or compound, runs as a generator: each control tick
it yields one `Command` and it finally returns an `Outcome`. The driver
advances the generator once per tick after updating the context.

Primitives are Python generators that close the loop on the knowledge base
(L0 and L1). Compound skills (L2) are data: JSON programs interpreted by
`run_program` with five constructs (sequence, if, repeat-until, bind, call),
plus `until`, `timeout`, and `on_fail` on any call. Every run ends as done,
failed, or timeout, because loops carry an iteration limit, calls carry
timeouts, skills carry a time budget, and recursion has a depth limit.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any

from birdbrain.body import CLASSES, MICRODUCK, BodyProfile, Command, Observation
from birdbrain.expr import ClassRef, Evaluator, ExprError, check_calls, names
from birdbrain.kr import SELF, KnowledgeBase, Position
from birdbrain.relations import bearing, distance, known

DONE, FAILED, TIMEOUT, INTERRUPTED = "done", "failed", "timeout", "interrupted"
MAX_DEPTH = 8

SkillRun = Generator[Command, None, "Outcome"]


@dataclass(frozen=True, slots=True)
class Outcome:
    status: str
    reason: str = ""
    path: str = ""

    @property
    def ok(self) -> bool:
        return self.status == DONE


@dataclass
class Context:
    """What a running skill can see: the latest observation and the knowledge base."""

    kb: KnowledgeBase
    evaluator: Evaluator
    body: BodyProfile = MICRODUCK
    obs: Observation | None = None
    log: Callable[[str, dict[str, Any]], None] = lambda kind, payload: None
    last: Command | None = None             # the command sent last tick
    map: Any = None                         # what is in the way (occupancy.OccupancyMap, E-030)
    _moving_t: float = -math.inf
    _prev_yaw: float | None = None

    @property
    def t(self) -> float:
        return 0.0 if self.obs is None else self.obs.t

    def observe(self, obs: Observation) -> None:
        yaw = obs.odom[2]
        turning = self._prev_yaw is not None and abs(_wrap(yaw - self._prev_yaw)) > 0.006
        if abs(obs.speed) > 0.05 or turning:
            self._moving_t = obs.t
        self._prev_yaw = yaw
        self.obs = obs

    @property
    def cold(self) -> bool:
        """The gait has stopped; an in-place turn needs a forward kick to start."""
        return self.t - self._moving_t > self.body.cold_after_s

    def turn_command(self, sign: float, note: str = "") -> Command:
        kick = self.body.turn_kick if self.cold else 0.0
        return Command(twist=(kick, 0.0, math.copysign(self.body.turn_rate, sign)),
                       head=self.body.head_level, note=note)

    def clearance(self) -> float:
        """Free distance straight ahead from the range sensor (m)."""
        frame = None if self.obs is None else self.obs.range_frame
        if frame is None or self.t - frame.t > 0.3:
            return math.inf
        depth, valid = frame.depth_mm, frame.valid & (frame.depth_mm > 0)
        if self.obs.holding:
            valid = valid & (depth >= int(self.body.hold_blind_m * 1000))
        head_down = self.last is not None and self.last.head[1] > 0.3
        rows = slice(0, 2) if head_down else slice(2, 7)     # head down, the lower rows see the floor
        ahead = depth[rows, 3:5][valid[rows, 3:5]]
        return float(ahead.min()) / 1000.0 if ahead.size else math.inf


# ---------------------------------------------------------------------------
# Primitives (L0 body, L1 control)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Skill:
    name: str
    params: dict[str, str]                  # parameter -> "number", "string", or an object class
    doc: str
    budget: float
    level: str                               # "primitive" or "compound"
    impl: Callable[..., SkillRun] | None = None
    body: list[Any] = field(default_factory=list)
    defaults: dict[str, Any] = field(default_factory=dict)
    expect: str = "true"                   # default prediction, an expression over args and `held`
    variant_of: str | None = None          # a skill written in place of this one (Milestone 5)


PRIMITIVES: dict[str, Skill] = {}


def primitive(params: dict[str, str], doc: str, budget: float = 60.0, **defaults: Any):
    def register(fn: Callable[..., SkillRun]) -> Callable[..., SkillRun]:
        PRIMITIVES[fn.__name__] = Skill(fn.__name__, params, doc, budget, "primitive", fn,
                                        defaults=defaults)
        return fn
    return register


@primitive({"vx": "number", "vy": "number", "wz": "number", "seconds": "number"},
           "Send one twist for a fixed time.", budget=30.0)
def move(ctx: Context, vx: float, vy: float, wz: float, seconds: float) -> SkillRun:
    t0 = ctx.t
    while ctx.t - t0 < seconds:
        yield Command(twist=(vx, vy, wz), head=ctx.body.head_level, note="move")
    return Outcome(DONE)


@primitive({"seconds": "number"}, "Stand still.", budget=60.0)
def stand(ctx: Context, seconds: float) -> SkillRun:
    t0 = ctx.t
    while ctx.t - t0 < seconds:
        yield Command(head=ctx.body.head_level, note="stand")
    return Outcome(DONE)


@primitive({"state": "string"}, "Open or close the beak.", budget=2.0)
def beak(ctx: Context, state: str) -> SkillRun:
    if state not in {"open", "close"}:
        return Outcome(FAILED, f"unknown beak state {state!r}")
    t0 = ctx.t
    while ctx.t - t0 < 0.6:
        yield Command(beak=state, head=ctx.body.head_level, note=f"beak {state}")
    return Outcome(DONE)


@primitive({"name": "string"}, "Run a reflex skill of the body, e.g. ground_pick.", budget=8.0)
def reflex(ctx: Context, name: str) -> SkillRun:
    t0, started = ctx.t, False
    while True:
        running = ctx.obs is not None and ctx.obs.reflex == name
        started = started or running
        if started and not running:
            return Outcome(DONE)
        if not started and ctx.t - t0 > 1.0:
            return Outcome(FAILED, f"reflex {name} did not start")
        yield Command(reflex=None if started else name, note=f"reflex {name}")


@primitive({"condition": "condition"}, "Succeed if the condition holds now, otherwise fail.",
           budget=1.0)
def require(ctx: Context, condition: bool) -> SkillRun:
    return Outcome(DONE if condition else FAILED, "" if condition else "requirement not met")
    yield  # unreachable; makes this a generator


@primitive({"x": "entity"}, "Doubt where x is: an action found it missing. It is not acted on until seen again.",
           budget=1.0)
def doubt(ctx: Context, x: str) -> SkillRun:
    a = ctx.kb.get("at", x)
    if a is not None:
        ctx.kb.tell("at", (x,), a.value, t=ctx.t, conf=min(a.conf, 0.3), source="action found it missing",
                    provenance="action")
    return Outcome(DONE)
    yield  # unreachable; makes this a generator


@primitive({"angle": "number"}, "Turn in place by a signed angle (rad, +left).", budget=30.0)
def turn(ctx: Context, angle: float) -> SkillRun:
    turned, prev = 0.0, ctx.obs.odom[2]
    while abs(turned) < abs(angle):
        yield ctx.turn_command(angle, "turn")
        yaw = ctx.obs.odom[2]
        turned += _wrap(yaw - prev)
        prev = yaw
    return Outcome(DONE)


@primitive({"x": "entity", "tolerance": "number"},
           "Turn in place until x is straight ahead.", budget=20.0, tolerance=0.08)
def turn_toward(ctx: Context, x: str, tolerance: float = 0.08) -> SkillRun:
    while True:
        if ctx.kb.position(x) is None:
            return Outcome(FAILED, f"{x} position unknown")
        b = bearing(ctx.kb, ctx.t, x)
        if abs(b) <= tolerance:
            return Outcome(DONE)
        yield ctx.turn_command(b, f"turn toward {x}")


#: A route stops planning this far short of where the walk stops: the last stretch is left
#: to the approach, which may end at something mapped (a basket against a wall, E-030).
ROUTE_SPARE_M = 0.15


@primitive({"x": "entity", "stop_at": "number", "speed": "number", "look": "string",
            "aim_left": "number", "steady_last": "number", "avoid": "entity", "avoid_r": "number"},
           "Walk until x is stop_at metres ahead, steering on its believed position.",
           budget=40.0, stop_at=0.1, speed=0.30, look="auto", aim_left=0.0, steady_last=0.0,
           avoid=None, avoid_r=0.4)
def walk_toward(ctx: Context, x: str, stop_at: float = 0.1, speed: float = 0.30,
                look: str = "auto", aim_left: float = 0.0, steady_last: float = 0.0,
                avoid: str | None = None, avoid_r: float = 0.4) -> SkillRun:
    """`look`: "level", "down", or "auto" (down when walking straight in close).
    `steady_last`: within this distance of the stop, walk without steering.
    `avoid`: a known obstacle; while the straight line to x passes within
    `avoid_r` of it, steer for the point beside it instead."""
    body = ctx.body
    speed = max(speed, body.slow_speed)
    blocked_since = ctx.t
    route, routed_t = None, -math.inf
    while True:
        here, there = ctx.kb.position(SELF), ctx.kb.position(x)
        if here is None or there is None:
            return Outcome(FAILED, f"{x} position unknown")
        dist = here.distance(there)
        if dist <= stop_at:
            return Outcome(DONE)
        if not known(ctx.kb, ctx.t, x):
            return Outcome(FAILED, f"{x} is no longer where it was believed")
        if ctx.map is not None and ctx.t - routed_t >= 0.5:
            # A way round what the range sensor has seen in the way (E-030), re-planned twice a
            # second; the last stretch to x is left to the approach below.
            route, routed_t = ctx.map.route((here.x, here.y), (there.x, there.y),
                                            spare=stop_at + ROUTE_SPARE_M), ctx.t
        via = route or _detour_point(here, there, ctx.kb.position(avoid) if avoid else None, avoid_r)
        if via is not None:
            yaw = ctx.kb.value("heading", SELF, default=0.0)
            b = _wrap(math.atan2(via[1] - here.y, via[0] - here.x) - yaw)
        else:
            b = _wrap(bearing(ctx.kb, ctx.t, x) - math.atan2(aim_left, max(dist, 0.05)))
        if abs(b) > body.align:
            yield ctx.turn_command(b, f"align on {x}")
            continue
        if ctx.clearance() < body.blocked_m and dist > body.blocked_m:
            if ctx.t - blocked_since > 8.0:
                return Outcome(FAILED, "blocked")
            # Detour reflex: turn left until the way ahead is clear, then step past.
            while ctx.clearance() < body.blocked_m and ctx.t - blocked_since <= 8.0:
                yield ctx.turn_command(+1.0, "blocked: turn away")
            t_clear = ctx.t
            while ctx.t - t_clear < 1.0 and ctx.clearance() >= body.blocked_m:
                yield Command(twist=(body.walk_speed, 0.0, 0.0), head=body.head_level, note="detour")
            continue
        blocked_since = ctx.t
        down = look == "down" or (look == "auto" and dist < 0.5)
        wz = 0.0 if dist - stop_at < steady_last else max(-1.0, min(1.0, body.k_turn * b))
        yield Command(twist=(speed, 0.0, wz), head=body.head_down if down else body.head_level,
                      note=f"walk to {x} ({dist:.2f} m)")


@primitive({"seconds": "number", "avoid": "entity", "avoid_r": "number"},
           "Walk to the nearest edge of the floor seen so far, round what is in the way; "
           "wander if there is none.", budget=60.0, avoid=None, avoid_r=0.45)
def walk_to_unseen(ctx: Context, seconds: float, avoid: str | None = None, avoid_r: float = 0.45) -> SkillRun:
    """Frontier exploration (E-031): head for the nearest place where floor the range sensor
    has seen free meets floor it has never seen, for at most `seconds`."""
    here = ctx.kb.position(SELF)
    goal = None if ctx.map is None or here is None else ctx.map.frontier((here.x, here.y))
    if goal is None:
        return (yield from wander(ctx, seconds, avoid, avoid_r))
    place = ctx.kb.ensure_entity("place:unseen", "place", ctx.t)
    ctx.kb.tell("at", (place,), Position.round(goal[0], goal[1], 0.05), t=ctx.t, source="derived",
                provenance="derived")
    t0, run = ctx.t, walk_toward(ctx, place, stop_at=0.2, avoid=avoid, avoid_r=avoid_r)
    while True:
        if ctx.t - t0 > seconds:
            run.close()
            return Outcome(DONE)
        try:
            command = next(run)
        except StopIteration as stop:
            outcome = stop.value
            return Outcome(DONE) if outcome.status == FAILED and outcome.reason == "blocked" else outcome
        yield command


@primitive({"seconds": "number", "avoid": "entity", "avoid_r": "number"},
           "Wander, turning away from obstacles sensed ahead and from a known one.",
           budget=60.0, avoid=None, avoid_r=0.45)
def wander(ctx: Context, seconds: float, avoid: str | None = None, avoid_r: float = 0.45) -> SkillRun:
    """`avoid`: a known obstacle the range sensor may see too late (a low basket rim);
    the duck turns away while it is within `avoid_r` and ahead."""
    t0 = ctx.t
    while ctx.t - t0 < seconds:
        if ctx.clearance() < 0.4:
            yield ctx.turn_command(+1.0, "wander: turn away")
            continue
        if avoid is not None and ctx.kb.position(avoid) is not None and ctx.kb.position(SELF) is not None:
            b = bearing(ctx.kb, ctx.t, avoid)
            if abs(b) < math.pi / 2 and ctx.kb.position(SELF).distance(ctx.kb.position(avoid)) < avoid_r:
                yield ctx.turn_command(-b or 1.0, f"wander: turn away from {avoid}")
                continue
        yield Command(twist=(ctx.body.walk_speed, 0.0, 0.0), head=ctx.body.head_level, note="wander")
    return Outcome(DONE)


# ---------------------------------------------------------------------------
# Compound skills (L2): data, interpreted
# ---------------------------------------------------------------------------

class Library:
    """All skills by name: the primitives plus the compound programs on disk."""

    def __init__(self, compound: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        self.skills: dict[str, Skill] = dict(PRIMITIVES)
        specs = compound if compound is not None else load_builtin()
        added = [self._register(name, spec) for name, spec in specs.items()]
        for skill in added:                  # check after registering, so skills may call each other
            self._check(skill)

    def add(self, name: str, spec: Mapping[str, Any]) -> Skill:
        """Add (or replace) one compound skill, checking it against the library."""
        previous = self.skills.get(name)
        skill = self._register(name, spec)
        try:
            self._check(skill)
        except Exception:                    # any failed check leaves the library as it was
            if previous is None:
                del self.skills[name]
            else:
                self.skills[name] = previous
            raise
        return skill

    def _register(self, name: str, spec: Mapping[str, Any]) -> Skill:
        if name in PRIMITIVES:
            raise ValueError(f"{name!r} is a primitive")
        skill = Skill(name=name, params=dict(spec.get("params", {})), doc=spec.get("doc", ""),
                      budget=float(spec.get("budget", 60.0)), level="compound",
                      body=list(spec["body"]), defaults=dict(spec.get("defaults", {})),
                      expect=spec.get("expect", "true"), variant_of=spec.get("variant_of"))
        self.skills[name] = skill
        return skill

    def _check(self, skill: Skill) -> None:
        check_program(skill.body, set(skill.params), self)
        names(skill.expect)

    def __getitem__(self, name: str) -> Skill:
        return self.skills[name]

    def __contains__(self, name: str) -> bool:
        return name in self.skills

    def compound(self) -> list[Skill]:
        return [s for s in self.skills.values() if s.level == "compound"]


def load_builtin() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in sorted(files("birdbrain.library").iterdir(), key=lambda p: p.name):
        if item.name.endswith(".json"):
            out[item.name.removesuffix(".json")] = json.loads(item.read_text(encoding="utf-8"))
    return out


def check_program(body: list[Any], bound: set[str], library: Library | None = None) -> None:
    """Static checks: known constructs and skills, known argument names, and
    expressions that parse and use only bound names, classes, `self`, `it`, and `held`."""
    known_names = set(bound) | set(CLASSES) | {"self", "it", "held"}
    for step in body:
        if not isinstance(step, dict) or len({"call", "if", "repeat", "bind"} & step.keys()) != 1:
            raise ValueError(f"a step needs exactly one of call/if/repeat/bind: {step!r}")
        # The runtime trusts these shapes, so a program that breaks them is refused here.
        for key in ("call", "bind", "until", "if", "to"):
            if key in step and not isinstance(step[key], str):
                raise ValueError(f"{key} must be a string: {step!r}")
        for key in ("then", "else", "repeat", "on_fail"):
            if key in step and not isinstance(step[key], list):
                raise ValueError(f"{key} must be a list of steps: {step!r}")
        if not isinstance(step.get("args", {}), dict):
            raise ValueError(f"args must be an object: {step!r}")  # noqa: TRY004 - checks raise ValueError
        if "timeout" in step and (isinstance(step["timeout"], bool) or not isinstance(step["timeout"], (int, float))):
            raise ValueError(f"timeout must be a number of seconds: {step!r}")
        if "bind" in step and not isinstance(step.get("to"), str):
            raise ValueError(f"bind needs an expression in to: {step!r}")
        exprs = [v for k, v in step.items() if k in {"until", "if", "to"} and isinstance(v, str)]
        if "call" in step:
            callee = None
            if library is not None:
                if step["call"] not in library:
                    raise ValueError(f"unknown skill {step['call']!r}")
                callee = library[step["call"]]
                unknown = set(step.get("args", {})) - set(callee.params)
                if unknown:
                    raise ValueError(f"{step['call']} has no parameter(s) {sorted(unknown)}")
            params = callee.params if callee is not None else {}
            exprs += [v for k, v in step.get("args", {}).items() if isinstance(v, str)
                      and not (params.get(k) == "string" and not v.startswith(("'", '"')))]
            check_program(step.get("on_fail", []), bound, library)
        elif "if" in step:
            check_program(step.get("then", []), bound, library)
            check_program(step.get("else", []), bound, library)
        elif "repeat" in step:
            if not isinstance(step.get("max"), int) or step["max"] < 1:
                raise ValueError(f"repeat needs a positive integer max: {step!r}")
            check_program(step["repeat"], bound, library)
        for source in exprs:
            try:
                check_calls(source)
            except ExprError as error:
                raise ValueError(str(error)) from None
            unbound = names(source) - known_names
            if unbound:
                raise ValueError(f"unbound name(s) {sorted(unbound)} in {source!r}")
        if "bind" in step:
            bound = bound | {step["bind"]}
            known_names.add(step["bind"])


class Abort(Exception):
    """Thrown into a running skill to end it as failed, for example by a fall: the
    action event records the failure, so it counts toward giving up (ledger E-013)."""


def start(ctx: Context, library: Library, name: str, args: Mapping[str, Any],
          depth: int = 0, path: str = "") -> SkillRun:
    """Run skill `name` with resolved `args` within its time budget."""
    skill = library[name]
    if depth > MAX_DEPTH:
        return Outcome(FAILED, "recursion too deep", path)
    values = {**skill.defaults, **args}
    missing = [p for p in skill.params if p not in values]
    if missing:
        return Outcome(FAILED, f"missing arguments {missing}", path)
    here = f"{path}/{name}" if path else name
    if skill.level == "primitive":
        child = skill.impl(ctx, **{k: v for k, v in values.items() if k in skill.params})
        return (yield from limit(ctx, child, skill.budget, here))
    entities = [v for k, v in values.items()
                if skill.params.get(k) not in {"number", "string", "condition"}]
    # A written variant's run is also a try of its parent (`relations.tries`).
    variant = {} if skill.variant_of is None else {"variant_of": skill.variant_of}
    event = ctx.kb.begin("action", ctx.t, entities, skill=name, args=dict(values), depth=depth, **variant)
    child = run_program(ctx, library, skill.body, dict(values), depth, here)
    outcome = Outcome(INTERRUPTED, "stopped by its caller", here)
    try:
        outcome = yield from limit(ctx, child, skill.budget, here)
    except Abort as abort:
        outcome = Outcome(FAILED, str(abort), here)
        raise
    finally:
        ctx.kb.end(event, ctx.t, outcome=outcome.status, reason=outcome.reason)
    return outcome


def run_program(ctx: Context, library: Library, body: list[Any], env: dict[str, Any],
                depth: int, path: str) -> SkillRun:
    for index, step in enumerate(body):
        where = f"{path}[{index}]"
        if "bind" in step:
            env[step["bind"]] = ctx.evaluator.entity(ctx.evaluator.eval(step["to"], env, ctx.t), ctx.t)
            ctx.log("SKILL_BIND", {"path": where, "name": step["bind"], "value": env[step["bind"]]})
            continue
        if "if" in step:
            branch = step.get("then", []) if ctx.evaluator.eval(step["if"], env, ctx.t) else step.get("else", [])
            outcome = yield from run_program(ctx, library, branch, env, depth, where)
        elif "repeat" in step:
            outcome = yield from _repeat(ctx, library, step, env, depth, where)
        else:
            outcome = yield from _call(ctx, library, step, env, depth, where)
        if not outcome.ok:
            return outcome
    return Outcome(DONE, path=path)


def _repeat(ctx: Context, library: Library, step: Mapping[str, Any], env: dict[str, Any],
            depth: int, path: str) -> SkillRun:
    until = step.get("until")
    for _ in range(step["max"]):
        if until and ctx.evaluator.eval(until, env, ctx.t):
            return Outcome(DONE, path=path)
        outcome = yield from run_program(ctx, library, step["repeat"], env, depth, path)
        if not outcome.ok:
            return outcome
    if until and not ctx.evaluator.eval(until, env, ctx.t):
        return Outcome(FAILED, f"not {until} after {step['max']} iterations", path)
    return Outcome(DONE, path=path)


def _call(ctx: Context, library: Library, step: Mapping[str, Any], env: dict[str, Any],
          depth: int, path: str) -> SkillRun:
    name = step["call"]
    skill = library[name]
    args = {key: _argument(ctx, skill.params.get(key, "number"), raw, env)
            for key, raw in step.get("args", {}).items()}
    for key, value in args.items():
        optional = key in skill.defaults and skill.defaults[key] is None
        if skill.params.get(key) not in {"number", "string", "condition"} and value is None and not optional:
            return Outcome(FAILED, f"{name}: no {key}", path)
    ctx.log("SKILL_STEP_STARTED", {"path": path, "skill": name, "args": args})
    child = start(ctx, library, name, args, depth + 1, path)
    until, timeout = step.get("until"), step.get("timeout")
    t0 = ctx.t
    outcome: Outcome
    try:
        while True:
            if until and ctx.evaluator.eval(until, env, ctx.t):
                outcome = Outcome(DONE, f"until {until}", path)
                break
            if timeout is not None and ctx.t - t0 > timeout:
                outcome = Outcome(TIMEOUT, f"{name} took over {timeout} s", path)
                break
            try:
                command = next(child)
            except StopIteration as stop:
                outcome = stop.value
                break
            yield command
    finally:
        child.close()
    ctx.log("SKILL_STEP_ENDED", {"path": path, "skill": name, "status": outcome.status,
                                 "reason": outcome.reason, "seconds": round(ctx.t - t0, 2)})
    if not outcome.ok and "on_fail" in step:
        outcome = yield from run_program(ctx, library, step["on_fail"], env, depth, f"{path}!")
    return outcome


def _argument(ctx: Context, kind: str, raw: Any, env: Mapping[str, Any]) -> Any:
    """A program argument: strings are expressions, except plain words for string parameters."""
    if not isinstance(raw, str):
        return raw
    if kind == "string" and not raw.startswith(("'", '"')):
        return raw
    value = ctx.evaluator.eval(raw, env, ctx.t)
    if kind == "condition":
        return bool(value)
    return value if kind in {"number", "string"} else ctx.evaluator.entity(value, ctx.t)


def limit(ctx: Context, child: SkillRun, budget: float, path: str) -> SkillRun:
    t0 = ctx.t
    try:
        while True:
            if ctx.t - t0 > budget:
                return Outcome(TIMEOUT, f"over budget {budget} s", path)
            try:
                command = next(child)
            except StopIteration as stop:
                return stop.value
            except ExprError as error:        # a bad expression fails the skill, not the mind
                return Outcome(FAILED, f"expression error: {error}", path)
            except (TypeError, ValueError, KeyError) as error:
                # A program that passed its checks can still misuse a value at run time (a
                # written skill passing a number where an entity is expected): it fails.
                return Outcome(FAILED, f"error: {type(error).__name__}: {error}", path)
            yield command
    finally:
        child.close()


def resolve_args(ctx: Context, skill: Skill, raw: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve tool-call arguments: entity ids stay ids, class names become entities."""
    out: dict[str, Any] = {}
    for key, value in raw.items():
        kind = skill.params.get(key)
        if kind is None:
            raise ExprError(f"{skill.name} has no parameter {key!r}")
        if kind in {"number", "string", "condition"}:
            out[key] = value
        else:
            entity = ctx.evaluator.entity(ClassRef(value), ctx.t) if value in ctx.evaluator.classes else value
            if entity not in ctx.kb.entities or not known(ctx.kb, ctx.t, entity):
                raise ExprError(f"{value!r} is not a known entity")
            if kind != "entity" and ctx.kb.cls(entity) != kind:
                raise ExprError(f"{key} must be a {kind}, got {ctx.kb.cls(entity)}")
            out[key] = entity
    return out


def _detour_point(here: Any, there: Any, obstacle: Any, radius: float) -> tuple[float, float] | None:
    """If the segment here->there passes within `radius` of the obstacle, a point to aim at
    instead: the closest point of the segment, pushed out to `radius`."""
    if obstacle is None:
        return None
    dx, dy = there.x - here.x, there.y - here.y
    length2 = dx * dx + dy * dy
    if length2 < 1e-9:
        return None
    u = ((obstacle.x - here.x) * dx + (obstacle.y - here.y) * dy) / length2
    if not 0.0 < u < 1.0:
        return None
    cx, cy = here.x + u * dx, here.y + u * dy
    d = math.hypot(cx - obstacle.x, cy - obstacle.y)
    if d >= radius:
        return None
    if d < 1e-6:
        ox, oy = -dy / math.sqrt(length2), dx / math.sqrt(length2)
    else:
        ox, oy = (cx - obstacle.x) / d, (cy - obstacle.y) / d
    return obstacle.x + radius * ox, obstacle.y + radius * oy


def _wrap(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


__all__ = [
    "DONE",
    "FAILED",
    "PRIMITIVES",
    "TIMEOUT",
    "Context",
    "Library",
    "Outcome",
    "Skill",
    "distance",
    "resolve_args",
    "start",
]
