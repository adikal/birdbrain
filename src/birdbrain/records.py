"""Skill statistics: counted outcomes per skill, kept across episodes in memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillRecord:
    trials: int = 0
    effect_held: int = 0
    done: int = 0
    seconds: float = 0.0
    falls: int = 0
    recent: list[bool] = field(default_factory=list)     # the last 10 outcomes, oldest first

    @property
    def p(self) -> float:
        """Laplace estimate that the expected effect holds."""
        return (self.effect_held + 1) / (self.trials + 2)

    @property
    def progress(self) -> float:
        """Learning progress: change in success rate between the last five tries and the five before."""
        if len(self.recent) < 10:
            return 0.0
        new, old = self.recent[-5:], self.recent[:-5][-5:]
        return abs(sum(new) / len(new) - sum(old) / len(old))

    #: Prior on falls per trial, from the base rate over all skills (about 0.5 falls in
    #: 21 skill runs per episode, E-013), worth this many trials. Without it one fall in
    #: one trial read as a 33% risk and the duck never tidied again (ledger E-014).
    FALL_PRIOR, FALL_PRIOR_TRIALS = 0.025, 10

    @property
    def fall_rate(self) -> float:
        return (self.falls + self.FALL_PRIOR * self.FALL_PRIOR_TRIALS) / (self.trials + self.FALL_PRIOR_TRIALS)

    def record(self, held: bool, done: bool, seconds: float, fell: bool) -> None:
        self.trials += 1
        self.effect_held += held
        self.done += done
        self.seconds += seconds
        self.falls += fell
        self.recent = (self.recent + [held])[-10:]

    def to_dict(self) -> dict[str, Any]:
        return {"trials": self.trials, "effect_held": self.effect_held, "done": self.done,
                "mean_s": round(self.seconds / self.trials, 2) if self.trials else None,
                "p": round(self.p, 3), "falls": self.falls, "progress": round(self.progress, 3)}
