"""MuJoCo implementation of the environment adapter contract."""

from __future__ import annotations

from importlib.resources import files
from typing import Any

import mujoco
import numpy as np

from birdbrain.adapters import Action, Observation


class MujocoMicroduckAdapter:
    """Run the first articulated Microduck in its small research arena."""

    ACTUATORS = (
        "neck_motor",
        "left_hip_motor",
        "left_ankle_motor",
        "right_hip_motor",
        "right_ankle_motor",
    )

    def __init__(self, *, frame_skip: int = 5) -> None:
        if frame_skip < 1:
            raise ValueError("frame_skip must be positive")
        model_path = files("birdbrain").joinpath("assets/microduck_arena.xml")
        self.model = mujoco.MjModel.from_xml_path(str(model_path))
        self.data = mujoco.MjData(self.model)
        self.frame_skip = frame_skip
        self._closed = False
        self._actuator_ids = {
            name: mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
            for name in self.ACTUATORS
        }
        self.reset()

    def reset(self, *, seed: int | None = None) -> Observation:
        self._ensure_open()
        mujoco.mj_resetData(self.model, self.data)
        if seed is not None:
            rng = np.random.default_rng(seed)
            for body_name in ("blue_block", "red_ball"):
                joint_id = mujoco.mj_name2id(
                    self.model, mujoco.mjtObj.mjOBJ_JOINT, f"{body_name}_free"
                )
                qpos_address = self.model.jnt_qposadr[joint_id]
                self.data.qpos[qpos_address : qpos_address + 2] += rng.uniform(
                    -0.08, 0.08, size=2
                )
        self.data.ctrl[:] = 0.0
        mujoco.mj_forward(self.model, self.data)
        return self.observe()

    def observe(self) -> Observation:
        self._ensure_open()
        return Observation(
            timestamp=float(self.data.time),
            values={
                "duck": self._body_snapshot("microduck"),
                "head": self._body_snapshot("head"),
                "blue_block": self._body_snapshot("blue_block"),
                "red_ball": self._body_snapshot("red_ball"),
                "actuator_targets": {
                    name: float(self.data.ctrl[actuator_id])
                    for name, actuator_id in self._actuator_ids.items()
                },
                "joint_positions": {
                    name: float(
                        self.data.qpos[
                            self.model.jnt_qposadr[
                                mujoco.mj_name2id(
                                    self.model, mujoco.mjtObj.mjOBJ_JOINT, name
                                )
                            ]
                        ]
                    )
                    for name in (
                        "neck_yaw",
                        "left_hip",
                        "left_ankle",
                        "right_hip",
                        "right_ankle",
                    )
                },
                "root_velocity": self.data.qvel[:6].astype(float).tolist(),
                "contacts": self._contacts(),
            },
        )

    def act(self, action: Action) -> Observation:
        self._ensure_open()
        if action.name == "hold":
            pass
        elif action.name == "set_joint_targets":
            self._set_joint_targets(action.parameters)
        else:
            raise ValueError(f"unsupported action: {action.name}")

        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)
        return self.observe()

    def close(self) -> None:
        self._closed = True

    def _body_snapshot(self, name: str) -> dict[str, list[float]]:
        body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, name)
        return {
            "position": self.data.xpos[body_id].astype(float).tolist(),
            "orientation": self.data.xquat[body_id].astype(float).tolist(),
        }

    def _set_joint_targets(self, targets: dict[str, Any]) -> None:
        unknown = set(targets) - set(self._actuator_ids)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"unknown actuator targets: {names}")
        for name, value in targets.items():
            self.data.ctrl[self._actuator_ids[name]] = float(value)

    def _contacts(self) -> list[dict[str, str]]:
        contacts = []
        for contact in self.data.contact[: self.data.ncon]:
            first = mujoco.mj_id2name(
                self.model, mujoco.mjtObj.mjOBJ_GEOM, contact.geom1
            )
            second = mujoco.mj_id2name(
                self.model, mujoco.mjtObj.mjOBJ_GEOM, contact.geom2
            )
            contacts.append({"first": first or "unnamed", "second": second or "unnamed"})
        return contacts

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("adapter is closed")
