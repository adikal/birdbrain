"""Persistent skill parameters and conservative outcome learning."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

_DEFAULTS = {
    "orient_to_object": {"amplitude": 0.12},
    "recover_posture": {"amplitude": 0.07},
}


class SkillLibrary:
    """Store bounded parameters and update them from observed outcomes."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "skills.json"
        self._lock = Lock()

    def parameters(self, name: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._read().get(name, self._default(name)))

    def record_outcome(
        self, name: str, *, success: bool, body_height_m: float
    ) -> dict[str, Any]:
        with self._lock:
            skills = self._read()
            current = dict(skills.get(name, self._default(name)))
            before = float(current["amplitude"])
            attempts = int(current.get("attempts", 0)) + 1
            successes = int(current.get("successes", 0)) + int(success)
            direction = -1.0 if success else 1.0
            after = max(0.04, min(0.16, before + direction * 0.002))
            updated = {
                "amplitude": round(after, 4),
                "attempts": attempts,
                "successes": successes,
                "success_rate": round(successes / attempts, 4),
                "last_body_height_m": round(body_height_m, 4),
            }
            skills[name] = updated
            self._write(skills)
            return {
                "skill": name,
                "success": success,
                "amplitude_before": before,
                "amplitude_after": updated["amplitude"],
                **updated,
            }

    @staticmethod
    def _default(name: str) -> dict[str, Any]:
        if name not in _DEFAULTS:
            raise ValueError(f"unknown skill: {name}")
        return {**_DEFAULTS[name], "attempts": 0, "successes": 0, "success_rate": 0.0}

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {}

    def _write(self, skills: dict[str, Any]) -> None:
        temporary = self.root / ".skills.json.tmp"
        temporary.write_text(
            json.dumps(skills, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, self.path)
