import math

import numpy as np
import pytest

from birdbrain.occupancy import CELL, OccupancyMap, cell_of


def _wall(m, x, y0, y1):
    for k in range(int((y1 - y0) / CELL) + 1):
        m._add(cell_of(x, y0 + k * CELL), 4.0)


def test_a_clear_line_needs_no_route_and_a_wall_is_walked_round():
    m = OccupancyMap()
    assert m.route((0.0, 0.0), (2.0, 0.0)) is None
    _wall(m, 1.0, -1.0, 0.6)                      # a wall with a gap above y = 0.6
    via = m.route((0.0, 0.0), (2.0, 0.0))
    assert via is not None and via[1] > 0.6        # head for the gap
    assert m.clear((0.0, 0.0), via)


def test_a_wall_seen_by_the_range_sensor_is_mapped():
    m = OccupancyMap()
    depth = np.full((8, 8), 1000, dtype=np.uint16)   # everything 1 m away, the head level
    m.update(depth, np.ones((8, 8), dtype=bool), (0.0, 0.0, 0.0), 0.24, 0.0, 0.0, 0.064)
    hit = [c for c, v in m.odds.items() if v > 0]
    assert hit and all(abs((c[0] + 0.5) * CELL - 1.0) < 0.2 for c in hit)
    assert m.odds[cell_of(0.5, 0.0)] < 0                # the way to it is free


def test_the_floor_is_not_in_the_way():
    m = OccupancyMap()
    pitch, cam_z, half = 0.3, 0.24, math.tan(math.radians(22.5))
    depth = np.zeros((8, 8), dtype=np.uint16)
    for row in range(8):
        for col in range(8):
            zy, zz = half - (2 * col + 1) * half / 8, half - (2 * row + 1) * half / 8
            down = math.sin(pitch) - zz * math.cos(pitch)
            if down > 0:
                depth[row, col] = min(4000, int(1000 * cam_z / down * math.sqrt(1 + zy * zy + zz * zz)))
    m.update(depth, depth > 0, (0.0, 0.0, 0.0), cam_z, pitch, 0.0, 0.064)
    assert not any(v > 1.0 for v in m.odds.values())


def test_the_frontier_is_the_nearest_edge_of_what_has_been_seen():
    m = OccupancyMap()
    for i in range(-5, 15):                       # a free strip along x from -0.5 to 1.5 m
        for j in range(-2, 3):
            m._add((i, j), -2.0)
    f = m.frontier((0.0, 0.0), min_dist=0.8)
    assert f is not None and math.dist(f, (0.0, 0.0)) >= 0.8
    assert abs(f[1]) >= 0.2 or f[0] > 1.3 or f[0] < -0.4   # on the strip's edge


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="known: growth by 2 cells closes a 0.6 m doorway; the fix did not help as a whole "
                          "and was reverted (ledger E-034, E-035)")
def test_a_doorway_between_two_walls_stays_open_at_any_offset():
    for offset in (0.0, 0.03, 0.05, 0.07):
        m = OccupancyMap()
        _wall(m, 1.0, -4.0, -0.3 + offset)
        _wall(m, 1.0, 0.3 + offset, 4.0)            # a 0.6 m doorway in a long wall
        assert m.clear((0.0, offset), (2.0, offset)), offset           # straight through the door
        assert not m.clear((0.0, 1.0), (2.0, 1.0))                     # the wall
        via = m.route((0.0, 1.0), (2.0, 1.0))
        assert via is not None and abs(via[1] - offset) < 0.35, (offset, via)   # head for the door
