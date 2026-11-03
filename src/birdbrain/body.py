"""The body boundary: what the mind receives from a body and what it sends back.

`Observation` holds only what the physical Microduck can sense. Adapters
(`birdbrain.lab` for Microduck Lab, later one for Pollen's robotd) build it
from their native types and copy nothing else, which is how simulator truth
is kept out of the mind. `Command` is the mind's only output.

`BodyProfile` collects measured facts about the body that control code needs.
The Microduck values are measured on Pollen's shipped `alpha_walking` policy;
each cites where it was measured.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True, slots=True)
class Sighting:
    """One camera detection. Deliberately has no identity field: the robot's
    detector reports a class and a box, and which object it is must be inferred."""

    cls: str
    bearing: float          # rad, camera frame, +left
    elevation: float        # rad, camera frame, +up
    width: float            # rad, apparent angular width
    conf: float
    color: str | None = None


@dataclass(frozen=True, slots=True)
class Frame:
    """A camera frame: when it was captured, from where, and what it contained."""

    t: float
    sightings: tuple[Sighting, ...]
    cam_z: float            # camera height above the floor (m)
    cam_pitch: float        # optical axis depression below horizontal (rad)
    cam_yaw: float          # camera yaw relative to the body heading (rad)


@dataclass(frozen=True, slots=True)
class RangeFrame:
    """The head's 8x8 time-of-flight depth frame."""

    t: float
    depth_mm: np.ndarray    # (8, 8) uint16, 0 = no return
    valid: np.ndarray       # (8, 8) bool


@dataclass(frozen=True, slots=True)
class Observation:
    t: float
    odom: tuple[float, float, float]        # x, y, yaw in the odometry frame
    speed: float                            # forward speed (m/s)
    holding: bool                           # the beak holds something (servo load on the robot)
    reflex: str | None                      # the reflex skill running, if any
    bumped: bool                            # touching something (IMU and servo loads on the robot)
    frame: Frame | None = None
    range_frame: RangeFrame | None = None


@dataclass(frozen=True, slots=True)
class Command:
    """One control-rate command. `head` is (neck_pitch, head_pitch, head_yaw, head_roll)."""

    twist: tuple[float, float, float] = (0.0, 0.0, 0.0)
    head: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    beak: str | None = None                 # "open" | "close"
    reflex: str | None = None               # request a reflex skill, e.g. "ground_pick"
    note: str = ""


STOP = Command()


@dataclass(frozen=True)
class BodyProfile:
    """Measured facts the control primitives rely on."""

    # Locomotion. microduck-lab `walker_facts.py` and `brain/gait.py`.
    walk_speed: float = 0.30          # command; forward commands below ~0.2 produce no motion
    slow_speed: float = 0.25          # slowest command that still walks
    turn_rate: float = 1.0            # yaw command; from standstill |wz| < 1.0 produces no turn
    turn_kick: float = 0.20           # forward command that starts the gait for a cold turn (does not travel)
    reverse_speed: float = -0.40      # commands from -0.30 to 0 produce no motion
    cold_after_s: float = 0.4         # standing this long, the gait needs a kick to turn
    k_turn: float = 2.5               # steering gain while walking (tidy.py)
    align: float = 0.35               # turn in place first when the target is further off the nose (rad)
    # Picking. microduck-lab `world/arena.py` PICK_REACH_* and `brain/tidy.py`.
    reach_ahead: float = 0.070        # stop with the target this far ahead of the trunk (0.078 tip, -0.008 pad)
    reach_left: float = 0.014         # the beak is slightly left of the centreline
    settle_s: float = 0.6             # stand still this long before a ground pick
    # Head. `brain/tidy.py`: the walker cannot turn in place with the head down.
    head_down: tuple[float, float, float, float] = (0.0, 0.6, 0.0, 0.0)
    head_level: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    head_settle_s: float = 0.4
    # Camera. microduck-lab `sensors/detector.py` DetectorSpec and `brain/tidy.py`.
    cam_ahead: float = 0.064          # camera ahead of the trunk origin (m)
    fov_h: float = np.deg2rad(116.0)
    fov_v: float = np.deg2rad(60.0)
    # Range sensor. `brain/tidy.py`: a held toy fills the bottom-centre zones.
    hold_blind_m: float = 0.12
    blocked_m: float = 0.25
    # Object classes the detector reports: centre height above the floor (m).
    class_height: dict[str, float] = field(
        default_factory=lambda: {"toy": 0.015, "basket": 0.08, "ball": 0.035, "duck": 0.12, "person": 0.9}
    )
    # Class sizes the duck is told about (footprint half-width, m).
    class_half_width: dict[str, float] = field(default_factory=lambda: {"basket": 0.15})


MICRODUCK = BodyProfile()

#: Object classes the mind can name: what the detector reports, plus derived places.
CLASSES = frozenset(MICRODUCK.class_height) | {"place"}
