"""Durable JSONL storage for BirdBrain observability runs."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from threading import Lock
from typing import Any

from birdbrain.observability.events import EventEnvelope

_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_TERMINAL_STATUS = {"RUN_STOPPED": "completed", "RUN_FAILED": "failed"}


class JsonlRunStore:
    """Append-only event records with a small summary index per run."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def append(self, event: EventEnvelope) -> None:
        run_dir = self._run_dir(event.run_id)
        with self._lock:
            run_dir.mkdir(parents=True, exist_ok=True)
            events_path = run_dir / "events.jsonl"
            line = json.dumps(event.to_dict(), separators=(",", ":")) + "\n"
            with events_path.open("a", encoding="utf-8") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())

            existing = self._read_summary(run_dir) or {}
            summary = {
                "run_id": event.run_id,
                "schema_version": event.schema_version,
                "started_at": existing.get("started_at", event.wall_time),
                "updated_at": event.wall_time,
                "event_count": int(existing.get("event_count", 0)) + 1,
                "last_sequence": event.sequence,
                "last_sim_time": event.sim_time,
                "status": _TERMINAL_STATUS.get(event.type, "running"),
            }
            self._write_summary(run_dir, summary)

    def list_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            summaries = [
                summary
                for path in self.root.iterdir()
                if path.is_dir() and (summary := self._read_summary(path)) is not None
            ]
        return sorted(summaries, key=lambda item: item["updated_at"], reverse=True)

    def get_summary(self, run_id: str) -> dict[str, Any] | None:
        run_dir = self._run_dir(run_id)
        with self._lock:
            return self._read_summary(run_dir)

    def read_events(
        self, run_id: str, *, after_sequence: int = 0, limit: int = 5_000
    ) -> list[dict[str, Any]]:
        if limit < 1 or limit > 10_000:
            raise ValueError("limit must be between 1 and 10000")
        events_path = self._run_dir(run_id) / "events.jsonl"
        if not events_path.is_file():
            return []
        events: list[dict[str, Any]] = []
        with self._lock, events_path.open(encoding="utf-8") as stream:
            for line in stream:
                event = json.loads(line)
                if int(event["sequence"]) > after_sequence:
                    events.append(event)
                    if len(events) >= limit:
                        break
        return events

    def _run_dir(self, run_id: str) -> Path:
        if not _RUN_ID.fullmatch(run_id):
            raise ValueError("invalid run id")
        return self.root / run_id

    @staticmethod
    def _read_summary(run_dir: Path) -> dict[str, Any] | None:
        path = run_dir / "summary.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_summary(run_dir: Path, summary: dict[str, Any]) -> None:
        path = run_dir / "summary.json"
        temporary = run_dir / ".summary.json.tmp"
        temporary.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
