"""Small durable episodic and semantic memory for the first cognition loop."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any


class LocalMemory:
    """Append episodes and maintain a provenance-aware semantic wiki."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def remember(self, episode: dict[str, Any]) -> None:
        with (
            self._lock,
            (self.root / "episodes.jsonl").open("a", encoding="utf-8") as stream,
        ):
            stream.write(json.dumps(episode, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def recall(self, entity: str, *, limit: int = 3) -> list[dict[str, Any]]:
        path = self.root / "episodes.jsonl"
        if not path.is_file():
            return []
        with self._lock, path.open(encoding="utf-8") as stream:
            matches = []
            for line in stream:
                episode = json.loads(line)
                if entity in episode.get("entities", []):
                    matches.append(episode)
        return matches[-limit:]

    def update_fact(
        self, key: str, value: Any, *, source_run_id: str, sequence_hint: int
    ) -> dict[str, Any]:
        with self._lock:
            wiki = self._read_wiki()
            fact = {
                "value": value,
                "source_run_id": source_run_id,
                "sequence_hint": sequence_hint,
            }
            wiki[key] = fact
            temporary = self.root / ".wiki.json.tmp"
            temporary.write_text(
                json.dumps(wiki, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            os.replace(temporary, self.root / "wiki.json")
            return fact

    def facts(self) -> dict[str, Any]:
        with self._lock:
            return self._read_wiki()

    def _read_wiki(self) -> dict[str, Any]:
        path = self.root / "wiki.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
