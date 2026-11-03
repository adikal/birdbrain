"""The owner's phrases and their valence (docs/design.md section 4.3, Milestone 3b).

The lists live in `phrases.toml`, next to this file, so they can be edited without
touching code; `BIRDBRAIN_PHRASES` points at another file.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

ENV = "BIRDBRAIN_PHRASES"


def normalize(text: str) -> str:
    """Lower case, apostrophes dropped, other punctuation as spaces, single spaces."""
    text = re.sub(r"['\u2019]", "", text.lower())
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


@dataclass(frozen=True)
class Phrases:
    positive: tuple[str, ...]
    negative: tuple[str, ...]

    def __post_init__(self) -> None:
        both = set(self.positive) & set(self.negative)
        if both:
            raise ValueError(f"phrases listed as both positive and negative: {sorted(both)}")

    def valence(self, heard: str) -> int:
        """+1 for approval, -1 for disapproval, 0 for anything not on the lists."""
        said = normalize(heard)
        return 1 if said in self.positive else -1 if said in self.negative else 0


def load(path: Path | str | None = None) -> Phrases:
    """The phrase lists from `path`, else from $BIRDBRAIN_PHRASES, else the built-in file."""
    path = path or os.environ.get(ENV)
    text = (Path(path).read_text(encoding="utf-8") if path
            else files("birdbrain").joinpath("phrases.toml").read_text(encoding="utf-8"))
    data = tomllib.loads(text)
    lists = {}
    for key in ("positive", "negative"):
        raw = data.get(key, {}).get("phrases", [])
        if not raw or not all(isinstance(p, str) and normalize(p) for p in raw):
            raise ValueError(f"[{key}] needs a non-empty list of phrases")
        lists[key] = tuple(dict.fromkeys(normalize(p) for p in raw))
    return Phrases(**lists)
