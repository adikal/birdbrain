"""The cloud brain's prior about objects, from how they look (ledger E-036, H-009).

When the duck first sees an object of a new appearance (a colour and a size, as its own
senses estimate them), it asks the cloud brain what to expect before it has tried: will a
pick leave it held, will carrying it to the basket work, will the duck fall carrying it.
The answer enters the causal rules as pseudo-outcomes of those conditions, weighted by how
many of the duck's own trials the cloud brain says its judgement is worth (at most
`MAX_WORTH`). The duck's own outcomes then add to them and, as they accumulate, outweigh
them: a prior, not a rule.

The question carries only what the duck could know: the object's appearance, and facts
about its own body. Answers are kept for life (`advice.json`), so each appearance is asked
about once.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

#: The most a single judgement may count for, in trials of the duck's own experience.
MAX_WORTH = 5.0

BODY = ("The robot is a two-legged duck, 25 cm tall and weighing 0.74 kg, that walks slowly and "
        "can tip over. It picks objects up from the floor in its beak: the beak opens to about "
        "3.6 cm and closes on what is between its tips, and an object much wider than that cannot "
        "be held. It carries what it holds in its beak to a basket with a 6 cm rim and drops it in. "
        "Its camera sees colours within about 1 m and estimates an object's size from how wide it "
        "looks (to about 10%).")


class Judge(Protocol):
    def judge(self, prompt: str) -> tuple[dict[str, Any], dict[str, int]]: ...


def appearance(features: dict[str, str], role: str) -> tuple[str, str] | None:
    """(colour, size) of the target or held object, if both are known."""
    colour, size = features.get(f"{role} colour"), features.get(f"{role} size")
    if colour in (None, "unknown") or size in (None, "unknown"):
        return None
    return colour, size


def prompt(colour: str, size: str) -> str:
    return (f"{BODY}\n\nThe robot has just seen an object it has never handled. It looks {colour}, and "
            f"its largest extent is {size}. Nothing else is known about it. What do you expect?")


class Advice:
    def __init__(self, judge: Judge | None = None, answers: dict[str, Any] | None = None) -> None:
        self.judge = judge
        self.answers: dict[str, Any] = answers or {}       # "colour|size" -> the answer, or an error
        self.tokens = 0

    def asked(self, colour: str, size: str) -> bool:
        return f"{colour}|{size}" in self.answers

    def ask(self, colour: str, size: str) -> dict[str, Any] | None:
        """The cloud brain's judgement of an appearance, asked once; None if unavailable."""
        key = f"{colour}|{size}"
        if key not in self.answers and self.judge is not None:
            try:
                answer, usage = self.judge.judge(prompt(colour, size))
                self.tokens += usage.get("input", 0) + usage.get("output", 0)
                self.answers[key] = _checked(answer)
            except Exception as error:  # noqa: BLE001 - a failed question is simply not asked again
                self.answers[key] = {"error": type(error).__name__}
        answer = self.answers.get(key)
        return answer if answer and "error" not in answer else None

    def pseudo_outcomes(self, colour: str, size: str) -> list[tuple[str, str, dict[str, str], float, float]]:
        """(rule outcome, skill, conditions, outcome, weight) for the judgement of an
        appearance: what the rules add as if the duck had tried it."""
        a = self.ask(colour, size)
        if a is None:
            return []
        w = min(MAX_WORTH, a["worth_trials"])
        if w <= 0:
            return []
        target = {"target colour": colour, "target size": size}
        held = {"holding": "yes", "held colour": colour, "held size": size}
        return [("effect", "pick", target, a["p_hold"], w),
                ("effect", "deliver", held, a["p_delivered"], w),
                ("fell", "deliver", held, a["p_fall"], w)]

    def to_json(self) -> str:
        return json.dumps({"answers": self.answers}, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, text: str, judge: Judge | None = None) -> Advice:
        return cls(judge, json.loads(text).get("answers", {}))


def _checked(answer: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k in ("p_hold", "p_delivered", "p_fall"):
        out[k] = min(1.0, max(0.0, float(answer[k])))
    out["worth_trials"] = min(10.0, max(0.0, float(answer["worth_trials"])))
    out["reason"] = str(answer.get("reason", ""))[:300]
    return out

