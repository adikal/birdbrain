"""What the duck's head camera saw, rendered for the dashboard (viewer only).

Each image is rendered from the camera pose recorded with the detector's
latest frame, with the detector's own field of view (116 x 60 degrees on the
Microduck), so the boxes the mind received line up with the picture. The
scene is the world at render time, at most one detector period (0.1 s) after
the frame, so a moving object can sit slightly off its box. Images
are written as JPEG files beside the run's events and announced with a
`CAMERA_FRAME` event. The mind never receives them.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

NEAR_PLANE_M = 0.01
SKY_RGB = (196, 212, 224)          # the lab's rooms have no sky; empty pixels get this colour


class HeadCamera:
    def __init__(self, world: Any, duck: Any, out_dir: Path, width: int = 640) -> None:
        self.world, self.duck, self.out_dir = world, duck, out_dir
        spec = duck.detector.spec
        self.hfov, self.vfov = math.radians(spec.fov_h_deg), math.radians(spec.fov_v_deg)
        self.width = width
        self.height = round(width * math.tan(self.vfov / 2) / math.tan(self.hfov / 2))
        self._renderer = None                 # created on first use, in the rendering thread
        self._last_t = -math.inf
        self._option = mujoco.MjvOption()
        for group, on in enumerate((1, 1, 0, 0, 1, 0)):   # scenery, other robots, toys
            self._option.geomgroup[group] = on

    def capture(self, frame_t: float | None = None) -> dict[str, Any] | None:
        """Render the detector's newest frame once, if it is the frame captured at
        `frame_t` (when given); return the event payload, or None."""
        frame = self.duck.detector.last if self.duck.detector is not None else None
        if frame is None or frame.t <= self._last_t or len(frame.cam_pose) != 7:
            return None
        if frame_t is not None and abs(frame.t - frame_t) > 1e-6:
            return None
        self._last_t = frame.t
        model, data = self.world.model, self.world.data
        if self._renderer is None:
            vis = model.vis.global_
            vis.offwidth, vis.offheight = max(vis.offwidth, self.width), max(vis.offheight, self.height)
            self._renderer = mujoco.Renderer(model, height=self.height, width=self.width)
        x, y, z, qw, qx, qy, qz = frame.cam_pose
        rot = np.zeros(9)
        mujoco.mju_quat2Mat(rot, np.array([qw, qx, qy, qz]))
        forward = rot.reshape(3, 3)[:, 0]
        cam = mujoco.MjvCamera()
        cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        cam.distance = 0.5
        cam.lookat[:] = np.array([x, y, z]) + forward * cam.distance
        cam.azimuth = math.degrees(math.atan2(forward[1], forward[0]))
        cam.elevation = math.degrees(math.asin(float(np.clip(forward[2], -1.0, 1.0))))
        # The head camera's optics, set only for this render: its field of view, and a
        # near plane of 1 cm. The model's default (about 5 cm here) clips everything
        # during a ground pick, when the camera is 2.5 cm above the floor.
        fovy, znear = model.vis.global_.fovy, model.vis.map.znear
        model.vis.global_.fovy = math.degrees(self.vfov)
        model.vis.map.znear = NEAR_PLANE_M / max(model.stat.extent, 1e-6)
        try:
            self._renderer.update_scene(data, camera=cam, scene_option=self._option)
            self._renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW] = False   # shadow maps alias this close
            pixels = self._renderer.render().copy()
            # Lit surfaces are never exactly black, so pure black is where nothing was drawn.
            pixels[(pixels == 0).all(axis=-1)] = SKY_RGB
        finally:
            model.vis.global_.fovy, model.vis.map.znear = fovy, znear
        from PIL import Image

        self.out_dir.mkdir(parents=True, exist_ok=True)
        name = f"{round(frame.t * 1000):08d}.jpg"
        buffer = io.BytesIO()
        Image.fromarray(pixels).save(buffer, format="JPEG", quality=80)
        (self.out_dir / name).write_bytes(buffer.getvalue())
        return {"file": name, "t": round(frame.t, 3), "width": self.width, "height": self.height,
                "hfov": round(self.hfov, 4), "vfov": round(self.vfov, 4)}

    def close(self) -> None:
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
