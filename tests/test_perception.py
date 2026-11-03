import math

import pytest

from birdbrain.body import MICRODUCK, Frame, Observation, Sighting
from birdbrain.kr import KnowledgeBase
from birdbrain.perception import Perception


def sighting_of(px, py, height, pose, cam_z=0.23, cam_pitch=0.2, cls="toy"):
    """The bearing and elevation a camera at `pose` would report for a floor point."""
    x, y, yaw = pose
    cx, cy = x + MICRODUCK.cam_ahead * math.cos(yaw), y + MICRODUCK.cam_ahead * math.sin(yaw)
    dx, dy, dz = px - cx, py - cy, height - cam_z
    bx = dx * math.cos(yaw) + dy * math.sin(yaw)                  # body frame
    by = -dx * math.sin(yaw) + dy * math.cos(yaw)
    cp, sp = math.cos(cam_pitch), math.sin(cam_pitch)
    fx, fz = bx * cp - dz * sp, bx * sp + dz * cp                 # into the pitched camera frame
    return Sighting(cls, math.atan2(by, fx), math.atan2(fz, math.hypot(fx, by)), 0.03, 1.0), \
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
