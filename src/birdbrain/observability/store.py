"""Durable JSONL storage for BirdBrain runs: one events file and one summary per run.

Events are appended and flushed as they arrive; the file is fsynced and the
summary written when a run starts, every `summary_every` events, and when it
ends. Readers do not take the writer's lock: appends are whole lines, and a
partially written last line is skipped.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from threading import Lock
from typing import IO, Any

from birdbrain.observability.events import EventEnvelope

_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_TERMINAL_STATUS = {"RUN_STOPPED": "completed", "RUN_FAILED": "failed"}


class JsonlRunStore:
    def __init__(self, root: Path, summary_every: int = 500) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.summary_every = summary_every
        self._lock = Lock()
        self._open: dict[str, IO[str]] = {}
        self._summaries: dict[str, dict[str, Any]] = {}

    def append(self, event: EventEnvelope) -> None:
        run_dir = self.run_dir(event.run_id)
        terminal = event.type in _TERMINAL_STATUS
        with self._lock:
            stream = self._open.get(event.run_id)
            if stream is None:
                run_dir.mkdir(parents=True, exist_ok=True)
                stream = self._open[event.run_id] = (run_dir / "events.jsonl").open("a", encoding="utf-8")
            stream.write(json.dumps(event.to_dict(), separators=(",", ":")) + "\n")
            stream.flush()
            summary = self._summaries.setdefault(event.run_id, self._read_summary(run_dir) or {
                "run_id": event.run_id, "schema_version": event.schema_version,
                "started_at": event.wall_time, "event_count": 0})
            summary.update(updated_at=event.wall_time, event_count=summary["event_count"] + 1,
                           last_sequence=event.sequence, last_sim_time=event.sim_time,
                           status=_TERMINAL_STATUS.get(event.type, "running"))
            if event.type == "RUN_STARTED":
                summary["config"] = event.payload
            if "result" in event.payload:
                summary["result"] = event.payload["result"]
            if terminal or event.type == "RUN_STARTED" or summary["event_count"] % self.summary_every == 0:
                if terminal:
                    os.fsync(stream.fileno())
                self._write_summary(run_dir, summary)
            if terminal:
                stream.close()
                del self._open[event.run_id]
                del self._summaries[event.run_id]

    def list_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            live = {run_id: dict(s) for run_id, s in self._summaries.items()}
        summaries = [live.get(path.name) or self._read_summary(path)
                     for path in self.root.iterdir() if path.is_dir()]
        return sorted((s for s in summaries if s), key=lambda s: s.get("updated_at", ""), reverse=True)

    def get_summary(self, run_id: str) -> dict[str, Any] | None:
        run_dir = self.run_dir(run_id)
        with self._lock:
            live = self._summaries.get(run_id)
            if live is not None:
                return dict(live)
        return self._read_summary(run_dir)

    def read_events(self, run_id: str, *, after_sequence: int = 0, limit: int = 5_000) -> list[dict[str, Any]]:
        if limit < 1 or limit > 10_000:
            raise ValueError("limit must be between 1 and 10000")
        path = self.run_dir(run_id) / "events.jsonl"
        if not path.is_file():
            return []
        events: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.endswith("\n"):
                    break                            # a line still being written
                event = json.loads(line)
                if int(event["sequence"]) > after_sequence:
                    events.append(event)
                    if len(events) >= limit:
                        break
        return events

    def run_dir(self, run_id: str) -> Path:
        if not _RUN_ID.fullmatch(run_id):
            raise ValueError("invalid run id")
        return self.root / run_id

    @staticmethod
    def _read_summary(run_dir: Path) -> dict[str, Any] | None:
        path = run_dir / "summary.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _write_summary(run_dir: Path, summary: dict[str, Any]) -> None:
        temporary = run_dir / ".summary.json.tmp"
        temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, run_dir / "summary.json")
