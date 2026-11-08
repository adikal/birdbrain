"""A map of what is in the way, built from the head's range sensor (ledger E-030).

The 8x8 time-of-flight sensor sits beside the camera and looks the same way. Each zone's
reading is a ray: the cells it crosses are free, and where it ends, if it ends above the
floor and below the top of furniture, something stands. The map is a sparse grid in the
odometry frame, each cell a log-odds of being occupied, so a cell seen free many times
outweighs a stray reading and the other way round.

Toys and the basket's rim are lower than `MIN_HEIGHT` and are left out: the duck walks to
them, and the basket keeps its own approach (`walk_toward(avoid=...)`). What the map holds
is walls, inner walls and furniture, and `route` plans a way around them (A* over the grid,
obstacles grown by the duck's half-width, unknown cells assumed free). `frontier` finds
the nearest place where seen floor meets floor never seen: where to explore (E-031).
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Iterator

import numpy as np

from birdbrain.body import MICRODUCK

CELL = 0.1                    # m
MIN_HEIGHT, MAX_HEIGHT = 0.07, 0.5   # what counts as in the way (m above the floor)
HIT, MISS, LIMIT = 0.85, -0.4, 4.0  # log-odds per reading, and their bound
OCCUPIED = 1.0                # log-odds above which a cell is in the way
MAX_RANGE = 2.0               # m: further readings are too uncertain in height to classify
MIN_RANGE = 0.12              # m: nearer readings may be the duck's own beak or what it holds
GROW = MICRODUCK.half_width   # obstacles are grown by this to plan (see `blocked`)
HALF_FOV, ZONES = MICRODUCK.range_fov / 2, MICRODUCK.range_zones

Cell = tuple[int, int]


def cell_of(x: float, y: float) -> Cell:
    return (math.floor(x / CELL), math.floor(y / CELL))


def centre(c: Cell) -> tuple[float, float]:
    return ((c[0] + 0.5) * CELL, (c[1] + 0.5) * CELL)


def _line(a: Cell, b: Cell) -> Iterator[Cell]:
    """Cells from a to b (Bresenham), a included, b included."""
    (x0, y0), (x1, y1) = a, b
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
    err = dx + dy
    while True:
        yield (x0, y0)
        if (x0, y0) == (x1, y1):
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


class OccupancyMap:
    def __init__(self) -> None:
        self.odds: dict[Cell, float] = {}
        self.occupied_cells: set[Cell] = set()
        self._grown: set[Cell] | None = None
        half = math.tan(HALF_FOV)
        ticks = [half - (2 * k + 1) * half / ZONES for k in range(ZONES)]
        self._zones = [(row, col, zy, zz) for row, zz in enumerate(ticks) for col, zy in enumerate(ticks)]

    # -- building ---------------------------------------------------------------
    def update(self, depth_mm: np.ndarray, valid: np.ndarray, pose: tuple[float, float, float],
               cam_z: float, cam_pitch: float, cam_yaw: float, cam_ahead: float) -> None:
        """Fold one range frame in, taken from `pose` with the head as the camera's."""
        x, y, yaw = pose
        cx, cy = x + cam_ahead * math.cos(yaw), y + cam_ahead * math.sin(yaw)
        heading = yaw + cam_yaw
        ch, sh = math.cos(heading), math.sin(heading)
        cp, sp = math.cos(cam_pitch), math.sin(cam_pitch)
        here = cell_of(cx, cy)
        for row, col, zy, zz in self._zones:
            if not valid[row, col] or depth_mm[row, col] <= 0:
                continue
            d = depth_mm[row, col] / 1000.0
            norm = math.sqrt(1.0 + zy * zy + zz * zz)
            fx, fy, fz = 1.0 / norm, zy / norm, zz / norm
            bx, by, bz = fx * cp + fz * sp, fy, -fx * sp + fz * cp           # body frame, pitched down
            flat = d * math.hypot(bx, by)
            if d < MIN_RANGE or flat > MAX_RANGE:
                continue
            ex, ey = cx + d * (bx * ch - by * sh), cy + d * (bx * sh + by * ch)
            height = cam_z + d * bz
            end = cell_of(ex, ey)
            blocking = MIN_HEIGHT <= height <= MAX_HEIGHT
            for c in _line(here, end):
                if c == end:
                    break
                self._add(c, MISS)
            if blocking:
                self._add(end, HIT)
            elif height < MIN_HEIGHT:
                self._add(end, MISS)                      # the floor, or something low
        self._add(cell_of(x, y), -LIMIT)                  # where the duck stands is free

    def _add(self, c: Cell, delta: float) -> None:
        v = max(-LIMIT, min(LIMIT, self.odds.get(c, 0.0) + delta))
        if (v > OCCUPIED) != (self.odds.get(c, 0.0) > OCCUPIED):
            self._grown = None
            (self.occupied_cells.add if v > OCCUPIED else self.occupied_cells.discard)(c)
        self.odds[c] = v

    # -- reading ----------------------------------------------------------------
    def occupied(self, c: Cell) -> bool:
        return c in self.occupied_cells

    def blocked(self) -> set[Cell]:
        """Occupied cells grown by the duck's half-width."""
        if self._grown is None:
            r = math.ceil(GROW / CELL)
            grown: set[Cell] = set()
            for i, j in self.occupied_cells:
                grown.update((i + a, j + b) for a in range(-r, r + 1) for b in range(-r, r + 1)
                             if a * a + b * b <= r * r)
            self._grown = grown
        return self._grown

    def clear(self, a: tuple[float, float], b: tuple[float, float], spare: float = 0.0,
              grown: bool = True) -> bool:
        """Nothing in the way on the straight line from a to b (ignoring the last `spare` m):
        for walking, obstacles grown by the duck's half-width; for seeing (`grown=False`),
        as they are."""
        end = cell_of(*b)
        blocked = self.blocked() if grown else self.occupied_cells
        for c in _line(cell_of(*a), end):
            # Cells round the duck itself are skipped: standing by a wall is not being blocked.
            if c in blocked and math.dist(centre(c), b) > spare and math.dist(centre(c), a) > GROW + CELL:
                return False
        return True

    def route(self, a: tuple[float, float], b: tuple[float, float], spare: float = 0.0,
              budget: int = 6000) -> tuple[float, float] | None:
        """The furthest point of a shortest way round the obstacles from a to b that can
        be walked to in a straight line: where to head now. None when the line is clear
        or no way is found. Cells within `spare` m of b count as free (b may be a basket
        against a wall)."""
        if self.clear(a, b, spare):
            return None
        blocked, start, goal = self.blocked(), cell_of(*a), cell_of(*b)

        def free(c: Cell) -> bool:
            return (c not in blocked or math.dist(centre(c), a) <= GROW + CELL
                    or math.dist(centre(c), b) <= spare)

        frontier = [(math.dist(start, goal), 0.0, start)]
        came: dict[Cell, Cell | None] = {start: None}
        cost = {start: 0.0}
        found = None
        while frontier and len(came) < budget:
            _, g, c = heapq.heappop(frontier)
            if c == goal or math.dist(centre(c), b) <= max(spare, CELL):
                found = c
                break
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    n = (c[0] + di, c[1] + dj)
                    if (di or dj) and free(n):
                        ng = g + math.hypot(di, dj)
                        if ng < cost.get(n, math.inf):
                            cost[n], came[n] = ng, c
                            heapq.heappush(frontier, (ng + math.dist(n, goal), ng, n))
        if found is None:
            return None
        path = [found]
        while came[path[-1]] is not None:
            path.append(came[path[-1]])
        path.reverse()
        for c in reversed(path[1:]):                       # furthest point reachable straight
            if self.clear(a, centre(c)):
                return centre(c)
        return centre(path[1]) if len(path) > 1 else None

    def frontier(self, a: tuple[float, float], min_dist: float = 0.8, budget: int = 4000) -> tuple[float, float] | None:
        """The nearest cell of floor seen free, at least `min_dist` m away by a free path,
        next to a cell never seen: the edge of what the duck knows (breadth-first through
        free cells, round grown obstacles). None if there is none within the budget."""
        blocked, start = self.blocked(), cell_of(*a)
        seen, queue = {start}, [start]
        for c in queue:
            if len(seen) > budget:
                break
            if (math.dist(centre(c), a) >= min_dist and c not in blocked
                    and any((c[0] + di, c[1] + dj) not in self.odds for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)))):
                return centre(c)
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (c[0] + di, c[1] + dj)
                if n not in seen and self.odds.get(n, 0.0) < 0.0 and n not in blocked:
                    seen.add(n)
                    queue.append(n)
        return None
