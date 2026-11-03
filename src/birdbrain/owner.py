"""The scripted owner of Milestone 3b (docs/design.md section 4.3).

She lives in the simulator, reads the true room, and has a hidden preference
over where toys are. When a toy's state changes in a way she cares about, she
reacts after a delay, not every time, with a random phrase of the matching
valence from the editable phrase lists; some of what she says is misheard as
the opposite. Near her, approval may come as petting instead.

Nothing here is visible to the mind except what she says and does, delivered
through the same observation fields the robot's microphone would fill.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from birdbrain.phrases import Phrases
from birdbrain.phrases import load as load_phrases

Point = tuple[float, float]

#: What "against a wall" means to the owner (m from the wall face). The duck has its own
#: notion (`relations.WALL_NEAR`) and does not know hers.
OWNER_WALL_M = 0.2


@dataclass(frozen=True)
class Room:
    """Truth the owner looks at: each toy's position and whether it is in the basket or held."""

    toys: Mapping[str, Point]
    in_basket: Mapping[str, bool]
    held: str | None
    bounds: tuple[float, float, float, float]       # wall faces: xmin, ymin, xmax, ymax


def wall_distance(p: Point, bounds: tuple[float, float, float, float]) -> float:
    xmin, ymin, xmax, ymax = bounds
    return min(p[0] - xmin, xmax - p[0], p[1] - ymin, ymax - p[1])


def _basket(room: Room, toy: str, start: Mapping[str, Point], wall_m: float) -> bool:
    return toy != room.held and room.in_basket[toy]


def _wall(room: Room, toy: str, start: Mapping[str, Point], wall_m: float) -> bool:
    return (toy != room.held and not room.in_basket[toy]
            and wall_distance(room.toys[toy], room.bounds) <= wall_m)


def _leave(room: Room, toy: str, start: Mapping[str, Point], wall_m: float) -> bool:
    return toy != room.held and math.dist(room.toys[toy], start[toy]) <= 0.1


#: Hidden preferences: is this toy the way she likes it?
PREFERENCES: dict[str, Callable[[Room, str, Mapping[str, Point], float], bool]] = {
    "basket": _basket,            # toys in the basket
    "wall": _wall,                # toys against a wall (not in the basket)
    "leave": _leave,              # toys left where they were at the start of the episode
}


@dataclass
class Owner:
    preference: str
    seed: int = 0
    react_p: float = 0.6                 # she reacts to this share of the changes she cares about
    delay_s: tuple[float, float] = (1.0, 5.0)
    mishear_p: float = 0.1               # heard as the opposite valence
    pet_radius: float = 0.5              # she can pet the duck within this distance of her
    pet_p: float = 0.5                   # ...and then pets instead of speaking with this probability
    wall_m: float = OWNER_WALL_M
    position: Point | None = None          # where she sits; None: she never pets the duck
    phrases: Phrases = field(default_factory=load_phrases)
    check_every_s: float = 0.25

    def __post_init__(self) -> None:
        if self.preference not in PREFERENCES:
            raise ValueError(f"unknown owner preference {self.preference!r}; one of {sorted(PREFERENCES)}")
        self._likes = PREFERENCES[self.preference]
        self._rng = random.Random(self.seed)
        self._start: dict[str, Point] | None = None
        self._state: dict[str, bool] = {}
        self._pending: list[tuple[float, int]] = []          # (time to react, valence)
        self._next_check = 0.0
        #: Truth for evaluation: every reaction she made (t, valence meant, what she said or "pet").
        self.log: list[tuple[float, int, str]] = []

    def satisfied(self, room: Room) -> int:
        return sum(self._likes(room, toy, self._start or room.toys, self.wall_m) for toy in room.toys)

    def step(self, t: float, room: Room, duck: Point) -> tuple[tuple[str, ...], bool]:
        """What the duck hears and feels at time `t`."""
        if self._start is None:
            self._start = dict(room.toys)
        if t >= self._next_check:
            self._next_check = t + self.check_every_s
            for toy in room.toys:
                now = self._likes(room, toy, self._start, self.wall_m)
                before = self._state.get(toy)
                self._state[toy] = now
                if before is not None and now != before and self._rng.random() < self.react_p:
                    self._pending.append((t + self._rng.uniform(*self.delay_s), 1 if now else -1))
        heard: list[str] = []
        petted = False
        due = sorted(p for p in self._pending if p[0] <= t)
        self._pending = [p for p in self._pending if p[0] > t]
        for when, valence in due:
            if petted and valence > 0 and self.position is not None:
                self._pending.append((when, valence))          # one pet at a time: the rest wait
                continue
            if (valence > 0 and self.position is not None and math.dist(duck, self.position) <= self.pet_radius
                    and self._rng.random() < self.pet_p):
                petted = True
                self.log.append((t, valence, "pet"))
                continue
            said = valence if self._rng.random() >= self.mishear_p else -valence
            phrase = self._rng.choice(self.phrases.positive if said > 0 else self.phrases.negative)
            heard.append(phrase)
            self.log.append((t, valence, phrase))
        return tuple(heard), petted
