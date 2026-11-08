"""World 2: rooms with many kinds of object, hidden properties, and furniture (ledger E-021).

This is WORLD code. It builds lab scenarios, adds world rules the lab does not model,
emulates one sensor, and measures from truth. The mind never imports it: the duck sees
only what `birdbrain.lab.observation` copies, as before.

Objects. A kind is a colour and a shape (24 kinds). What a kind does is hidden, and
follows its appearance:
- black objects are heavy (150 g): carrying one tips the duck over (E-021 probe);
- white objects are slippery: one carried drops out of the beak at random;
- big objects (6 cm across) are too wide for the beak: a grasp does not hold.
Eight kinds are held out of development; every colour and every shape stays in it.

Rooms. Larger than the playroom, with 2 to 5 pieces of furniture, half of them split by
an inner wall with a doorway, 0 to 2 balls, and 4 to 15 objects.

What the lab does not do, done here:
- the grasp rule for wide objects, and slipping (`WorldRules`);
- a colour classifier for objects (`colour_sensor`), modelled on the lab's own colour
  classifier for ducks (`DetectorNoise.datasheet`: within 1 m, right 95% of the time).
  It reads the detection's true identity to know the colour, which the mind never sees;
- registering the kinds in the lab's `PICKABLE_KINDS` table, which is how the lab knows
  an object's size and mass (`register`).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from typing import Any

COLOURS: dict[str, tuple[float, float, float, float]] = {
    "red": (0.85, 0.15, 0.15, 1.0),
    "yellow": (0.95, 0.80, 0.15, 1.0),
    "blue": (0.15, 0.35, 0.90, 1.0),
    "green": (0.20, 0.65, 0.30, 1.0),
    "white": (0.95, 0.95, 0.95, 1.0),
    "black": (0.08, 0.08, 0.08, 1.0),
}
#: Shapes: full extents (m) and mass (kg) when not heavy.
SHAPES: dict[str, tuple[tuple[float, float, float], float]] = {
    "cube": ((0.025, 0.025, 0.025), 0.005),
    "block": ((0.04, 0.04, 0.04), 0.02),
    "stick": ((0.09, 0.015, 0.015), 0.01),
    "big": ((0.06, 0.06, 0.05), 0.03),
}
HEAVY_COLOUR, SLIPPERY_COLOUR = "black", "white"
HEAVY_KG = 0.15
#: The beak holds nothing whose narrower side is wider than this (m). The lab's block
#: (40 mm) is held with the bill around it (arena `_mouth`); a 60 mm box is not.
GAPE_LIMIT_M = 0.05
#: Chance per second that a slippery object drops out of the beak.
SLIP_PER_S = 0.08
#: The colour classifier (lab `DetectorNoise.datasheet`, for ducks).
COLOUR_RANGE_M, COLOUR_P = 1.0, 0.95


@dataclass(frozen=True)
class Kind:
    name: str
    colour: str
    shape: str
    size: tuple[float, float, float]
    mass: float
    held_out: bool

    @property
    def heavy(self) -> bool:
        return self.colour == HEAVY_COLOUR

    @property
    def slippery(self) -> bool:
        return self.colour == SLIPPERY_COLOUR

    @property
    def too_wide(self) -> bool:
        return min(self.size[0], self.size[1]) > GAPE_LIMIT_M

    @property
    def category(self) -> str:
        return "wide" if self.too_wide else "heavy" if self.heavy else "slippery" if self.slippery else "plain"


def _kinds() -> dict[str, Kind]:
    colours, shapes = list(COLOURS), list(SHAPES)
    # Held out: colour i with shape i mod 4, and colours 0 and 1 also with shape i + 2,
    # so each colour keeps at least two shapes and each shape four colours in development.
    held = {(i, i % 4) for i in range(6)} | {(0, 2), (1, 3)}
    out = {}
    for i, c in enumerate(colours):
        for j, s in enumerate(shapes):
            size, mass = SHAPES[s]
            out[f"{c} {s}"] = Kind(f"{c} {s}", c, s, size, HEAVY_KG if c == HEAVY_COLOUR else mass, (i, j) in held)
    return out


KINDS = _kinds()
DEV_KINDS = tuple(k for k, v in KINDS.items() if not v.held_out)
ALL_KINDS = tuple(KINDS)


def register() -> None:
    """Add World 2's kinds to the lab's table of pickable kinds (size, mass, colour)."""
    from microduck_local.world.scenario import PICKABLE_KINDS
    for name, k in KINDS.items():
        entry = {"size": k.size, "mass": k.mass, "rgba": COLOURS[k.colour]}
        if PICKABLE_KINDS.setdefault(name, entry) != entry:
            raise RuntimeError(f"the lab already has a different pickable kind {name!r}")


def kinds_for(split: str, episode: int | None) -> tuple[str, ...]:
    """dev: development kinds only; all: every kind; late: development kinds in rooms 1 to
    10 of a life and every kind from room 11, so new kinds meet a duck with experience."""
    if split == "dev":
        return DEV_KINDS
    if split == "all":
        return ALL_KINDS
    if split == "late":
        return ALL_KINDS if (episode or 0) >= 11 else DEV_KINDS
    raise ValueError(f"unknown kinds split {split!r}")


def make_world(seed: int, kinds: tuple[str, ...], n: tuple[int, int] = (4, 15)) -> Any:
    """A World 2 room, deterministic in `seed`."""
    from microduck_local.world.scenario import (
        Ball,
        Basket,
        Box,
        Duck,
        Pickable,
        Scenario,
        Wall,
        robot_physics_dt,
    )

    rng = random.Random(seed)
    hx, hy = rng.uniform(1.75, 2.25), rng.uniform(1.4, 1.75)
    corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    walls = [Wall(corners[i], corners[(i + 1) % 4], 0.3, 0.02) for i in range(4)]
    clear: list[tuple[float, float, float]] = []        # (x, y, radius) kept free

    def free(x: float, y: float, r: float) -> bool:
        return all(math.dist((x, y), (cx, cy)) > r + cr for cx, cy, cr in clear)

    sx, sy = rng.choice((-1, 1)), rng.choice((-1, 1))
    basket = Basket((sx * (hx - 0.35), sy * (hy - 0.35)), (0.3, 0.3), 0.06)
    clear.append((*basket.pos, 0.4))
    if rng.random() < 0.5:
        # An inner wall across the room with a doorway, so the room is two spaces.
        wx = rng.uniform(-0.4, 0.4)
        door, half = rng.uniform(-hy + 0.6, hy - 0.6), 0.3
        walls += [Wall((wx, -hy), (wx, door - half), 0.3, 0.02), Wall((wx, door + half), (wx, hy), 0.3, 0.02)]
        clear += [(wx, door, 0.45)] + [(wx, y, 0.12) for y in _steps(-hy, door - half)] \
            + [(wx, y, 0.12) for y in _steps(door + half, hy)]
    spawn = None
    for _ in range(200):
        x, y = rng.uniform(-hx + 0.4, hx - 0.4), rng.uniform(-hy + 0.4, hy - 0.4)
        if free(x, y, 0.35):
            spawn = (x, y, rng.uniform(-math.pi, math.pi))
            clear.append((x, y, 0.35))
            break
    if spawn is None:
        raise RuntimeError(f"no room for the duck in world2 room {seed}")
    boxes = []
    for _ in range(rng.randint(2, 5)):
        for _try in range(50):
            w, d, h = rng.uniform(0.15, 0.5), rng.uniform(0.15, 0.5), rng.uniform(0.06, 0.3)
            x, y = rng.uniform(-hx + 0.35, hx - 0.35), rng.uniform(-hy + 0.35, hy - 0.35)
            r = math.hypot(w, d) / 2
            if free(x, y, r + 0.3):
                boxes.append(Box((x, y, h / 2), (w, d, h), 0.0))
                clear.append((x, y, r + 0.05))
                break
    balls = []
    for _ in range(rng.randint(0, 2)):
        for _try in range(50):
            x, y = rng.uniform(-hx + 0.3, hx - 0.3), rng.uniform(-hy + 0.3, hy - 0.3)
            if free(x, y, 0.15):
                balls.append(Ball((x, y)))
                clear.append((x, y, 0.1))
                break
    toys = []
    for i in range(rng.randint(*n)):
        for _try in range(100):
            x, y = rng.uniform(-hx + 0.12, hx - 0.12), rng.uniform(-hy + 0.12, hy - 0.12)
            if free(x, y, 0.1):
                toys.append(Pickable(f"t{i}", rng.choice(kinds), (x, y), rng.uniform(0, math.pi)))
                clear.append((x, y, 0.06))
                break
    return Scenario(name=f"world2-{seed}", seed=seed, floor=(2 * hx + 0.5, 2 * hy + 0.5), walls=walls,
                    boxes=boxes, balls=balls,
                    ducks=[Duck("d0", spawn, None, "datasheet", "datasheet", None, robot="microduck")],
                    pickables=toys, basket=basket, physics_dt=robot_physics_dt("microduck"))


def _steps(a: float, b: float, step: float = 0.15) -> list[float]:
    n = max(1, int(abs(b - a) / step))
    return [a + (b - a) * k / n for k in range(n + 1)]


class WorldRules:
    """The rules of World 2 the lab does not model, applied after each world step."""

    def __init__(self, world: Any, duck: Any, seed: int) -> None:
        self.world, self.duck = world, duck
        self.kind = {n: KINDS[k] for n, k in world.pickable_kind.items()}
        self.rng = random.Random(seed * 31 + 7)
        self.refused = self.slipped = 0
        self._refused_at = -math.inf
        self.falls_holding: dict[str, int] = {}
        self.grasped: dict[str, int] = {}            # grasps that closed on an object, by category
        self._falls = 0
        self.held: str | None = None                 # what was held at the end of the last tick

    def step(self, dt: float) -> None:
        duck = self.duck
        if duck.falls > self._falls:
            self._falls = duck.falls
            if self.held is not None:
                c = self.kind[self.held].category
                self.falls_holding[c] = self.falls_holding.get(c, 0) + 1
        held = duck.holding
        if held is not None:
            kind = self.kind[held]
            # The lab's pick reflex retries the grasp every tick of its closing window, so a
            # wide object is counted once per try.
            new_try = not kind.too_wide and held != self.held or kind.too_wide and self.world.t - self._refused_at > 1.0
            if new_try:
                for c in (kind.category, f"{kind.category}_{'new' if kind.held_out else 'known'}"):
                    self.grasped[c] = self.grasped.get(c, 0) + 1
            if kind.too_wide:
                self.world.release(duck)
                self.refused += new_try
                self._refused_at = self.world.t
            elif kind.slippery and self.rng.random() < SLIP_PER_S * dt:
                self.world.release(duck)
                self.slipped += 1
        self.held = duck.holding


def colour_sensor(frame: Any, kinds: dict[str, Kind], rng: random.Random) -> Any:
    """The detector frame with each object's colour, as a colour classifier would read it."""
    out = []
    for d in frame.detections:
        k = kinds.get(d.name)
        if d.cls == "toy" and d.range_est <= COLOUR_RANGE_M:
            if k is None:                        # a ghost: the classifier still names a colour
                colour = rng.choice(list(COLOURS))
            else:
                colour = k.colour if rng.random() < COLOUR_P else rng.choice([c for c in COLOURS if c != k.colour])
            d = replace(d, color=colour)
        out.append(d)
    return replace(frame, detections=out)


def measures(world: Any, kb: Any, rules: WorldRules, start: dict[str, tuple[float, float]]) -> dict[str, Any]:
    """Truth, for evaluation only. `start`: where each object was at the start of the room."""
    from birdbrain.kr import Position
    from birdbrain.owner import HER_COLOUR

    beliefs = [kb.position(e) for e in kb.of_class("toy")]
    beliefs = [p for p in beliefs if isinstance(p, Position)]
    by: dict[str, list[int]] = {}
    unfound = hers_moved = hers = 0
    for name, body in world.pickables.items():
        k = rules.kind[name]
        inb = bool(world.in_basket(name))
        keys = [k.category, "new" if k.held_out else "known", "possible" if not k.too_wide else "impossible",
                f"{k.category}_{'new' if k.held_out else 'known'}"]
        if not k.too_wide:
            keys.append("new_possible" if k.held_out else "known_possible")
        for key in keys:
            by.setdefault(key, [0, 0])
            by[key][0] += inb
            by[key][1] += 1
        x, y = float(world.data.xpos[body][0]), float(world.data.xpos[body][1])
        if k.colour == HER_COLOUR:
            hers += 1
            hers_moved += math.dist((x, y), start[name]) > 0.1
        held = name in {d.holding for d in world.ducks.values()}
        if not inb and not held and not any(math.hypot(p.x - x, p.y - y) <= 0.25 for p in beliefs):
            unfound += 1
    out = {f"w2_{k}_in": v[0] for k, v in by.items()} | {f"w2_{k}_n": v[1] for k, v in by.items()}
    return {**out, "w2_objects": len(world.pickables), "w2_unfound": unfound,
            "hers_n": hers, "hers_moved": hers_moved, "w2_refused": rules.refused,
            "w2_slipped": rules.slipped, **{f"w2_falls_holding_{k}": v for k, v in rules.falls_holding.items()},
            **{f"w2_grasped_{k}": v for k, v in rules.grasped.items()}}
