"""Skills composed by the cloud brain (Milestone 5, ledger E-019).

At the end of each episode the duck reflects. Its causal rules (`rules.py`) say
under which condition a skill most often fails to achieve its expected effect. If
the evidence is strong enough, the cloud brain is shown that skill's program, the
condition, the outcomes and their reasons, and the language skills are written in,
and is asked for a new program for that situation. Local code checks the program
against the library; anything outside the bounded language is refused.

A written skill does not replace its parent. Whenever the parent is about to run
and the condition holds, the duck chooses between the parent and the written skill
on their success under that condition (the expected effect held and the duck did not
fall). Both start from zero: the situation was chosen because the parent looked bad
there, so the parent's past counts are biased low (ledger L-023). The two take turns
until each has `min_trials` outcomes, then Thompson sampling decides, each a
Beta(1, 1) posterior. The written skill is kept when it is better with probability at
least `keep_p` and retired when it is worse with that probability; kept skills stay
under review. A retired skill is no longer chosen, and a kept one can be the parent
of a newer written skill. All of
it is kept for life in the memory directory (`authored.json`).

Nothing a written skill does can reach the body except through the primitives, so
the safety of the body does not depend on what the cloud brain writes.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

AUTHORED_PREFIX = "w_"          # written skills are named w_<name>, so they never shadow built-in ones


class Author(Protocol):
    """Anything that can answer a request for a skill: the cloud brain, or a test double."""

    def write(self, prompt: str) -> tuple[dict[str, Any], dict[str, int]]:  # (tool input, token usage)
        ...


@dataclass
class Trial:
    parent: str
    feature: str
    value: str
    child: str
    status: str = "trial"                                      # trial | kept | retired
    #: Outcomes since the trial opened, both skills from zero: skill -> [successes, trials, falls].
    counts: dict[str, list[float]] = field(default_factory=dict)
    reason: str = ""
    opened: int | None = None                                  # the episode after which it was written
    decided: int | None = None                                 # the episode after which it was last kept or retired

    def holds(self, skill: str, f: dict[str, str]) -> bool:
        return skill == self.parent and f.get(self.feature) == self.value

    def p_better(self, rng: random.Random, samples: int = 4000) -> float:
        """Posterior probability that the written skill succeeds more often than its parent."""
        (sc, nc, _), (sp, np_, _) = self.counts[self.child], self.counts[self.parent]
        wins = sum(rng.betavariate(1 + sc, 1 + nc - sc) > rng.betavariate(1 + sp, 1 + np_ - sp)
                   for _ in range(samples))
        return wins / samples


@dataclass
class Authoring:
    author: Author | None = None
    min_evidence: int = 8            # outcomes under the condition before asking
    min_z: float = 2.0               # the condition's effect, in posterior sds
    max_rate: float = 0.6            # ... and the skill's success under it at most this
    max_attempts: int = 2            # per condition, per life
    min_trials: int = 8              # per skill, run in turn before Thompson sampling decides
    keep_p: float = 0.9
    max_depth: int = 3               # a written skill can stand in for one that stands in for another
    skills: dict[str, dict[str, Any]] = field(default_factory=dict)        # name -> program
    trials: list[Trial] = field(default_factory=list)
    attempts: dict[str, int] = field(default_factory=dict)                 # "skill|feature=value" -> n
    log: list[dict[str, Any]] = field(default_factory=list)                # every request and answer
    tokens: int = 0

    # -- during an episode -------------------------------------------------------------
    def choose(self, skill: str, f: dict[str, str], rng: random.Random) -> tuple[str, list[Trial]]:
        """The skill to run in place of `skill` here, and the trials whose situation holds.

        A trial is a fair comparison (ledger E-020): until both its skills have `min_trials`
        outcomes, the one with fewer runs; after that, one Thompson draw each. The parent
        runs unless some written skill wins; if several do (overlapping situations), the
        highest draw runs. A kept written skill can itself be the parent of a newer one, so
        the choice repeats from whatever won, up to `max_depth`."""
        trials: list[Trial] = []
        for _ in range(self.max_depth):
            open_ = [t for t in self.trials if t.status != "retired" and t.holds(skill, f)]
            trials += open_
            best, best_draw = skill, None
            for trial in open_:
                (_, nc, _), (_, np_, _) = trial.counts[trial.child], trial.counts[trial.parent]
                if min(nc, np_) < self.min_trials:              # still taking turns
                    draw_child, draw_parent = (1.0, 0.0) if nc <= np_ else (0.0, 1.0)
                else:
                    (sc, _, _), (sp, _, _) = trial.counts[trial.child], trial.counts[trial.parent]
                    draw_child = rng.betavariate(1 + sc, 1 + nc - sc)
                    draw_parent = rng.betavariate(1 + sp, 1 + np_ - sp)
                if draw_child > draw_parent and (best_draw is None or draw_child > best_draw):
                    best, best_draw = trial.child, draw_child
            if best == skill:
                return skill, trials
            skill = best
        return skill, trials

    def record(self, trials: list[Trial], ran: str, success: bool, fell: bool) -> None:
        """A run of the parent counts in every trial whose situation held; a run of a
        written skill counts in its own."""
        for trial in trials:
            if ran not in {trial.parent, trial.child}:
                continue
            s, n, falls = trial.counts.setdefault(ran, [0.0, 0.0, 0.0])
            trial.counts[ran] = [s + success, n + 1, falls + fell]

    # -- between episodes ----------------------------------------------------------------
    def review(self, rng: random.Random, episode: int | None = None) -> list[dict[str, Any]]:
        """Keep a written skill that is better with probability `keep_p`, and retire one that
        is worse with that probability, once both it and its parent have `min_trials`
        outcomes in the trial. Kept skills stay under review and can still be retired."""
        out = []
        for trial in self.trials:
            if trial.status == "retired" or min(trial.counts[trial.child][1], trial.counts[trial.parent][1]) < self.min_trials:
                continue
            p, before = trial.p_better(rng), trial.status
            if p >= self.keep_p:
                trial.status = "kept"
            elif p <= 1.0 - self.keep_p:
                trial.status = "retired"
            if trial.status != before:
                trial.decided = episode
            if trial.status != before or before == "trial":
                out.append({"child": trial.child, "p_better": round(p, 3), "status": trial.status})
        return out

    def weakness(self, rules: Any, library: Any) -> tuple[str, str, str, dict[str, Any]] | None:
        """The (skill, feature, value) under which a compound skill most clearly fails,
        with its evidence, or None if nothing is clear enough."""
        best = None
        for skill, ex in rules.examples.items():
            if skill not in library or library[skill].level != "compound":
                continue
            if skill.startswith(AUTHORED_PREFIX) and not any(t.child == skill and t.status == "kept" for t in self.trials):
                continue                                   # a written skill is improved on only once kept
            if any(t.parent == skill and t.status == "trial" for t in self.trials):
                continue                                   # one open question per skill
            m = rules.model(skill)
            for key in m.keys:
                feature, value = key.split("=", 1)
                under = [y for f, y, _ in ex if f.get(feature) == value]
                other = [y for f, y, _ in ex if feature in f and f.get(feature) != value]
                if len(under) < self.min_evidence or not other:
                    continue
                effect, sd = m.contrast(key)
                rate = sum(under) / len(under)
                if sd <= 0 or effect / sd > -self.min_z or rate > self.max_rate:
                    continue
                if self.attempts.get(f"{skill}|{key}", 0) >= self.max_attempts:
                    continue
                if any(t.parent == skill and t.feature == feature and t.value == value and t.status == "kept"
                       for t in self.trials):
                    continue                               # already answered
                if best is None or effect / sd < best[0]:
                    best = (effect / sd, skill, feature, value,
                            {"rate": rate, "n": len(under), "rate_otherwise": sum(other) / len(other),
                             "n_otherwise": len(other), "z": effect / sd})
        return None if best is None else best[1:]

    def propose(self, skill: str, feature: str, value: str, evidence: dict[str, Any], reasons: dict[str, int],
                library: Any, episode: int | None = None) -> dict[str, Any]:
        """Ask the author for a skill for this situation; check it; open a trial."""
        key = f"{skill}|{feature}={value}"
        self.attempts[key] = self.attempts.get(key, 0) + 1
        prompt = request_text(skill, feature, value, evidence, reasons, library)
        entry: dict[str, Any] = {"skill": skill, "condition": f"{feature} {value}", "evidence": evidence,
                                 "episode": episode}
        problem = None
        for attempt in range(2):                           # one retry, told what was wrong
            text = prompt if problem is None else prompt + f"\n\nYour previous program was refused: {problem}\nFix it."
            try:
                answer, usage = self.author.write(text)
            except Exception as error:  # noqa: BLE001 - a failed request is recorded, not raised
                entry.update(status="error", error=type(error).__name__)
                self.log.append(entry)
                return entry
            self.tokens += sum(v for k, v in usage.items() if k in {"input", "output"})
            name, spec, problem = self._check(answer, skill, library)
            entry[f"answer_{attempt}"] = answer
            if problem is None:
                library.add(name, spec)
                self.skills[name] = spec
                trial = Trial(skill, feature, value, name, reason=str(answer.get("reason", ""))[:400], opened=episode)
                trial.counts = {skill: [0.0, 0.0, 0.0], name: [0.0, 0.0, 0.0]}
                self.trials.append(trial)
                entry.update(status="trial", child=name)
                self.log.append(entry)
                return entry
        entry.update(status="refused", problem=problem)
        self.log.append(entry)
        return entry

    def _check(self, answer: dict[str, Any], parent: str, library: Any) -> tuple[str, dict[str, Any], str | None]:
        """A written skill takes its parent's parameters and expected effect, so the two
        can be compared on the same outcome; it may not call itself; the library checks
        the rest (constructs, known skills and arguments, bound names)."""
        raw = re.sub(r"[^a-z0-9_]", "_", str(answer.get("name", "")).lower()).strip("_")[:32] or "skill"
        name = AUTHORED_PREFIX + raw
        while name in library or name in self.skills:
            name += "_2"
        body = answer.get("body")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError as error:
                return name, {}, f"body is not valid JSON ({error})"
        p = library[parent]
        spec = {"doc": str(answer.get("doc", ""))[:300] or f"A variant of {parent}.", "params": dict(p.params),
                "defaults": dict(p.defaults), "budget": min(p.budget + 30.0, 150.0), "expect": p.expect,
                "body": body, "variant_of": parent}
        if not isinstance(body, list) or not body:
            return name, spec, "body must be a non-empty list of steps"
        written = sorted({c for c in _calls(body) if isinstance(c, str) and c.startswith(AUTHORED_PREFIX)})
        if name in written:
            return name, spec, "a skill may not call itself"
        try:
            library.add(name, spec)
        except Exception as error:  # noqa: BLE001 - anything the checks reject is a refusal
            return name, spec, f"{type(error).__name__}: {error}" if not isinstance(error, ValueError) else str(error)
        del library.skills[name]                           # added for real by the caller
        return name, spec, None

    # -- memory ------------------------------------------------------------------------
    def to_json(self) -> str:
        return json.dumps({"skills": self.skills, "trials": [t.__dict__ for t in self.trials],
                           "attempts": self.attempts, "log": self.log, "tokens": self.tokens},
                          indent=2, sort_keys=True) + "\n"

    def load(self, text: str, library: Any) -> None:
        raw = json.loads(text)
        self.attempts, self.log, self.tokens = raw["attempts"], raw["log"], raw["tokens"]
        fields = set(Trial.__dataclass_fields__)
        self.trials = [Trial(**{k: v for k, v in t.items() if k in fields}) for t in raw["trials"]]
        parent_of = {t.child: t.parent for t in self.trials}
        pending = {name: {**spec, "variant_of": spec.get("variant_of", parent_of.get(name))}
                   for name, spec in raw["skills"].items()}
        self.skills.update(pending)                        # kept on record even if one no longer loads
        while pending:                                     # a written skill may call an earlier one
            loaded = []
            for name, spec in pending.items():
                try:
                    library.add(name, spec)
                except Exception:  # noqa: BLE001, S112 - retried after the others load; see below
                    continue
                loaded.append(name)
            for name in loaded:
                del pending[name]
            if not loaded:
                break
        for t in self.trials:                              # the library changed under these
            if t.child in pending:
                t.status = "retired"

    def summary(self) -> list[dict[str, Any]]:
        out = []
        for t in self.trials:
            (sc, nc, fc), (sp, np_, fp) = t.counts[t.child], t.counts[t.parent]
            out.append({"skill": t.child, "for": f"{t.parent} when {t.feature} {t.value}", "status": t.status,
                        "written": f"{sc:g} of {nc:g} succeeded, {fc:g} falls",
                        "parent": f"{sp:g} of {np_:g} succeeded, {fp:g} falls", "doc": self.skills.get(t.child, {}).get("doc", "")})
        return out


SYSTEM = """You write skills for BirdBrain, a small duck robot (25 cm tall, a beak that grasps
toys from the floor, a forward camera that reports object classes, a short-range depth sensor).
A skill is a small program in a bounded language that local code runs at 50 Hz. You answer by
calling the tool write_skill once. Programs that do not check are refused."""


def request_text(skill: str, feature: str, value: str, evidence: dict[str, Any], reasons: dict[str, int],
                 library: Any) -> str:
    """Everything the author needs, and nothing about what the outcome should be."""
    from birdbrain.relations import FUNCTIONS

    parent = library[skill]
    primitives = [f"- {s.name}({', '.join(f'{k}: {v}' for k, v in s.params.items())}): {s.doc}"
                  for s in library.skills.values() if s.level == "primitive"]
    compounds = [f"- {s.name}({', '.join(s.params)}): {s.doc}" for s in library.skills.values()
                 if s.level == "compound" and not s.name.startswith(AUTHORED_PREFIX)]
    why = "\n".join(f"- {k}: {v} times" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:8]) or "- none recorded"
    return f"""The skill `{skill}` often fails when {feature} is {value}.
Its expected effect is `{parent.expect}`. Under that condition the effect held in
{evidence['rate']:.0%} of {evidence['n']} tries, against {evidence['rate_otherwise']:.0%} of {evidence['n_otherwise']} tries otherwise.
How those tries ended (status: reason):
{why}

The skill now ({skill}, parameters {json.dumps(parent.params)}):
{json.dumps(parent.body, indent=1)}

Write a new skill for this situation. It takes the same parameters and should achieve
the same expected effect. It will be tried in place of `{skill}` only when {feature} is
{value}, and kept only if it succeeds more often there (a fall counts as a failure). It
may call `{skill}` itself, the compound skills listed below, and primitives.

The language. A program is a JSON list of steps; each step has exactly one of:
- {{"call": skill, "args": {{...}}}}, optionally with "until": condition, "timeout": seconds,
  "on_fail": [steps];
- {{"if": condition, "then": [steps], "else": [steps]}};
- {{"repeat": [steps], "max": positive integer, "until": condition}};
- {{"bind": name, "to": expression}}, after which `name` can be used.
Arguments and conditions are expressions over beliefs, for example
`near(self, x, 0.12) and facing(x, 0.1)`, `beyond(x, basket, 0.45)`, `known(basket)`,
`distance(self, basket) > 0.8`, `nearest(toy, known(it))`. String arguments are quoted: "'level'".
Names: parameters, bound names, `self`, `held` (what the duck holds), object classes
(`toy`, `basket`: the best-known one).
Relations: {', '.join(sorted(FUNCTIONS))}, and nearest/exists/count(class, condition with `it`).
Primitives:
{chr(10).join(primitives)}
Compound skills:
{chr(10).join(compounds)}

Call write_skill with: name (a short snake_case name), doc (one sentence saying what it does),
body (the program, as a JSON list), and reason (why it should work better here)."""


def write_skill_tool() -> dict[str, Any]:
    return {"toolSpec": {"name": "write_skill", "description": "Submit a new skill program.",
                         "inputSchema": {"json": {"type": "object", "required": ["name", "doc", "body", "reason"],
                                                  "properties": {"name": {"type": "string"}, "doc": {"type": "string"},
                                                                 "body": {"type": "array", "items": {"type": "object"}},
                                                                 "reason": {"type": "string"}}}}}}


def failure_reasons(outcomes: list[dict[str, Any]], skill: str, feature: str, value: str) -> dict[str, int]:
    """How the skill's tries under the condition ended, counted by status and reason."""
    out: dict[str, int] = {}
    for o in outcomes:
        if o["skill"] == skill and o["features"].get(feature) == value:
            reason = o["reason"] or ("effect held" if o["held"] else "effect did not hold")
            key = f"{o['status']}: {reason}"
            out[key] = out.get(key, 0) + 1
    return out


def _calls(body: Any) -> list[Any]:
    """Every skill a program calls, at any depth."""
    out: list[Any] = []
    if isinstance(body, list):
        for step in body:
            out += _calls(step)
    elif isinstance(body, dict):
        if "call" in body:
            out.append(body["call"])
        for key in ("then", "else", "repeat", "on_fail"):
            out += _calls(body.get(key))
    return out
