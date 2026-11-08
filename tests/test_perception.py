import math

import pytest

from birdbrain.body import MICRODUCK, Frame, Observation, Sighting
from birdbrain.kr import KnowledgeBase
from birdbrain.perception import Perception


def sighting_of(px, py, height, pose, cam_z=0.23, cam_pitch=0.2, cls="toy", size=0.04):
    """The bearing, elevation and width a camera at `pose` would report for an object of
    `size` at a floor point."""
    x, y, yaw = pose
    cx, cy = x + MICRODUCK.cam_ahead * math.cos(yaw), y + MICRODUCK.cam_ahead * math.sin(yaw)
    dx, dy, dz = px - cx, py - cy, height - cam_z
    bx = dx * math.cos(yaw) + dy * math.sin(yaw)                  # body frame
    by = -dx * math.sin(yaw) + dy * math.cos(yaw)
    cp, sp = math.cos(cam_pitch), math.sin(cam_pitch)
    fx, fz = bx * cp - dz * sp, bx * sp + dz * cp                 # into the pitched camera frame
    width = 2 * math.atan2(size / 2, math.hypot(dx, dy, dz))
    return Sighting(cls, math.atan2(by, fx), math.atan2(fz, math.hypot(fx, by)), width, 1.0), \
        Frame(0.0, (), cam_z, cam_pitch, 0.0)


@pytest.mark.parametrize("target,pose", [((0.6, 0.1), (0.0, 0.0, 0.0)), ((1.0, -0.4), (0.2, 0.1, -0.5)),
                                         ((-0.3, 0.8), (0.0, 0.0, 2.0))])
def test_locate_inverts_the_camera_geometry(target, pose):
    perception = Perception(KnowledgeBase())
    s, frame = sighting_of(*target, MICRODUCK.class_height["toy"], pose)
    p = perception.locate(s, frame, pose, still=True)
    assert math.hypot(p.x - target[0], p.y - target[1]) < 1e-6
    assert p.sigma < 0.15          # within a metre, standing (measured noise, ledger E-011)


def test_repeated_sightings_make_one_confident_entity():
    kb = KnowledgeBase()
    perception = Perception(kb)
    s, frame = sighting_of(0.6, 0.0, 0.015, (0.0, 0.0, 0.0))
    for k in range(5):
        f = Frame(k * 0.1, (s,), frame.cam_z, frame.cam_pitch, 0.0)
        perception.update(Observation(k * 0.1, (0.0, 0.0, 0.0), 0.0, False, None, False, frame=f))
    toys = kb.of_class("toy")
    assert len(toys) == 1 and kb.get("at", toys[0]).conf >= 0.9


def test_a_miss_behind_something_the_range_sensor_sees_is_no_evidence():
    import numpy as np

    from birdbrain.body import Frame, RangeFrame
    from birdbrain.kr import KnowledgeBase
    from birdbrain.perception import Perception
    p = Perception(KnowledgeBase())
    frame = Frame(t=1.0, sightings=(), cam_z=0.25, cam_pitch=0.0, cam_yaw=0.0)
    depth = np.full((8, 8), 3000, dtype=np.uint16)
    p._range = RangeFrame(1.0, depth, np.ones((8, 8), dtype=bool))
    assert not p.occluded(frame, 0.0, 0.07, 2.0)          # nothing in the way
    depth[:, :] = 800                                     # a box 0.8 m ahead
    assert p.occluded(frame, 0.0, 0.07, 2.0)
    assert not p.occluded(frame, 0.6, 0.07, 2.0)          # outside the range sensor's view
    assert not p.occluded(frame, 0.0, 0.07, 0.9)          # the object is in front of the box


def test_the_floor_in_front_of_a_far_toy_does_not_hide_it():
    import math

    import numpy as np

    from birdbrain.body import Frame, RangeFrame
    from birdbrain.kr import KnowledgeBase
    from birdbrain.perception import Perception
    p = Perception(KnowledgeBase())
    cam_z, pitch = 0.24, 0.29
    frame = Frame(t=1.0, sightings=(), cam_z=cam_z, cam_pitch=pitch, cam_yaw=0.0)
    # A range frame of bare floor: each zone reads the distance to the floor along its ray.
    half, n = math.tan(math.radians(22.5)), 8
    depth = np.zeros((n, n), dtype=np.uint16)
    for row in range(n):
        for col in range(n):
            zy, zz = half - (2 * col + 1) * half / n, half - (2 * row + 1) * half / n
            down = math.sin(pitch) - zz * math.cos(pitch)
            depth[row, col] = min(4000, int(1000 * cam_z / down * math.sqrt(1 + zy * zy + zz * zz))) if down > 0 else 0
    p._range = RangeFrame(1.0, depth, depth > 0)
    for r in (1.5, 2.0, 2.5):
        drop = cam_z - 0.015
        assert not p.occluded(frame, 0.0, math.atan2(drop, r) - pitch, math.hypot(r, drop))


def test_a_far_basket_is_ranged_by_its_apparent_width():
    import math

    from birdbrain.body import MICRODUCK, Frame, Sighting
    from birdbrain.kr import KnowledgeBase
    from birdbrain.perception import Perception
    p = Perception(KnowledgeBase())
    cam_z, r = 0.25, 3.0
    drop = cam_z - MICRODUCK.class_height["basket"]
    width = 2 * math.atan(MICRODUCK.class_width_radius["basket"] / math.hypot(r, drop))
    frame = Frame(t=0.0, sightings=(), cam_z=cam_z, cam_pitch=0.0, cam_yaw=0.0)
    # An elevation that alone would put it at 1.5 m: the width says 3 m, and is trusted more.
    s = Sighting("basket", 0.0, -math.atan(drop / 1.5), width, 0.9)
    where = p.locate(s, frame, (0.0, 0.0, 0.0), still=False)
    assert 2.4 < where.x - MICRODUCK.cam_ahead < 3.2
    s = Sighting("basket", 0.0, 0.01, width, 0.9)               # above the horizon: width only
    assert abs(p.locate(s, frame, (0.0, 0.0, 0.0), still=False).x - MICRODUCK.cam_ahead - r) < 0.05


def test_a_small_object_missed_far_away_is_not_doubted_as_much():
    # Objects are detected by how wide they look (E-028): a miss of a 2.5 cm cube at 1.5 m
    # is weak evidence, a miss of a 9 cm stick there is not.
    p = Perception(KnowledgeBase())
    assert p.detection_rate("toy", 1.5, 0.025) < 0.1
    assert p.detection_rate("toy", 1.5, 0.09) > 0.6
    assert p.detection_rate("toy", 0.4, 0.025) > 0.7
