"""Microduck Lab adapter: run the BirdBrain mind as a lab brain.

The lab hands a brain a `Senses` snapshot each 50 Hz tick and expects an
`Intent`. This module is the only place BirdBrain touches lab types.
`observation()` copies exactly what the physical robot can sense and drops
the rest; in particular a lab `Detection.name` (the true identity of the
object) never crosses into the mind.

`BirdBrainBrain` deliberately has no `world` or `robot_id` attribute, so the
lab's `attach_world` hands it nothing.
"""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Any

from birdbrain.body import Command, Frame, Observation, RangeFrame, Sighting
from birdbrain.mind import Log, Mind, Provider

KIND = "birdbrain"


def observation(senses: Any) -> Observation:
    """Translate lab `Senses` into a BirdBrain `Observation`."""
    frame = None
    det = senses.det
    if det is not None:
        frame = Frame(
            t=float(det.t),
            sightings=tuple(
                Sighting(cls=d.cls, bearing=float(d.bearing), elevation=float(d.elevation),
                         width=float(d.width), conf=float(d.conf), color=d.color)
                for d in det.detections
            ),
            cam_z=float(det.cam_z), cam_pitch=float(det.cam_pitch), cam_yaw=float(det.cam_yaw),
        )
    tof = senses.tof
    range_frame = None if tof is None else RangeFrame(float(tof.t), tof.depth_mm, tof.valid)
    return Observation(
        t=float(senses.t), odom=tuple(float(v) for v in (senses.odom or (0.0, 0.0, 0.0))),
        speed=float(senses.speed or 0.0), holding=bool(senses.holding), reflex=senses.skill,
        bumped=bool(senses.bumped), frame=frame, range_frame=range_frame,
    )


def intent(command: Command) -> Any:
    from microduck_local.brain.runtime import Intent
    return Intent(twist=command.twist, head=command.head, note=command.note,
                  beak=command.beak, skill=command.reflex)


class BirdBrainBrain:
    """A lab `Brain` whose decisions come from the BirdBrain mind."""

    kind = KIND
    wants_head = True                         # the lab applies this brain's head commands

    def __init__(self, provider: Provider | None = None, log: Log | None = None, **mind_options: Any) -> None:
        self._provider, self._log, self._options = provider, log, mind_options
        self.reset()

    def reset(self) -> None:
        provider = self._provider if self._provider is not None else provider_from_env()
        self.mind = Mind(provider=provider, log=self._log, **self._options)

    @property
    def state(self) -> str:
        return self.mind.state

    def step(self, senses: Any, heard: tuple[str, ...] = (), petted: bool = False) -> Any:
        """`heard` and `petted` come from the owner; the lab's senses have no microphone."""
        obs = observation(senses)
        if heard or petted:
            obs = replace(obs, heard=tuple(heard), petted=petted)
        return intent(self.mind.step(obs))

    def inputs(self) -> dict[str, Any]:
        action = self.mind._action
        return {"birdbrain": {"action": None if action is None else
                              {"skill": action["skill"], "args": action["args"], "reason": action["reason"]},
                              "stats": dict(self.mind.stats)}}


def provider_from_env() -> Provider | None:
    """`BIRDBRAIN_PROVIDER=bedrock` selects the cloud brain; anything else is local."""
    if os.environ.get("BIRDBRAIN_PROVIDER", "local") == "bedrock":
        from birdbrain.providers.bedrock import BedrockProvider
        return BedrockProvider.from_env()
    return None


def register() -> None:
    """Make `birdbrain` a brain kind in Microduck Lab's registry."""
    from microduck_local.brain.runtime import REGISTRY
    REGISTRY.register(KIND, BirdBrainBrain)
