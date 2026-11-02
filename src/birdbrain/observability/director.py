"""Small simulator loop that publishes live dashboard events."""

from __future__ import annotations

import math
from collections.abc import Callable
from threading import Event, Thread
from time import monotonic

from birdbrain.adapters import Action
from birdbrain.observability.journal import EventJournal
from birdbrain.sim import MujocoMicroduckAdapter


class SimulationDirector:
    """Advance Microduck and expose its real state as structured events."""

    def __init__(
        self,
        journal: EventJournal,
        *,
        seed: int = 42,
        frequency_hz: float = 10.0,
        adapter_factory: Callable[[], MujocoMicroduckAdapter] | None = None,
    ) -> None:
        if frequency_hz <= 0:
            raise ValueError("frequency_hz must be positive")
        self.journal = journal
        self.seed = seed
        self.frequency_hz = frequency_hz
        self._adapter_factory = adapter_factory or (
            lambda: MujocoMicroduckAdapter(frame_skip=20)
        )
        self._stop = Event()
        self._thread: Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name="birdbrain-sim", daemon=True)
        self._thread.start()

    def stop(self, *, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        adapter = self._adapter_factory()
        period = 1.0 / self.frequency_hz
        anomaly_reported = False
        try:
            observation = adapter.reset(seed=self.seed)
            self.journal.publish(
                "RUN_STARTED",
                sim_time=observation.timestamp,
                payload={
                    "seed": self.seed,
                    "model": "birdbrain_microduck_arena",
                    "producer": "MujocoMicroduckAdapter",
                },
            )
            tick = 0
            while not self._stop.is_set():
                started = monotonic()
                phase = tick * 0.12
                targets = {
                    "neck_motor": 0.22 * math.sin(phase * 0.35),
                    "left_hip_motor": 0.12 * math.sin(phase),
                    "right_hip_motor": -0.12 * math.sin(phase),
                    "left_ankle_motor": -0.06 * math.sin(phase + 0.8),
                    "right_ankle_motor": 0.06 * math.sin(phase + 0.8),
                }
                observation = adapter.act(Action("set_joint_targets", targets))
                self.journal.publish(
                    "ACTION_SELECTED",
                    sim_time=observation.timestamp,
                    payload={
                        "action": "set_joint_targets",
                        "targets": targets,
                        "frame_skip": adapter.frame_skip,
                        "summary": "Applied standing test joint targets",
                    },
                )
                snapshot = self._snapshot(adapter, observation.values, started)
                self.journal.publish(
                    "STATE_SNAPSHOT",
                    sim_time=observation.timestamp,
                    payload=snapshot,
                )
                if snapshot["duck"]["position"][2] < 0.11 and not anomaly_reported:
                    self.journal.publish(
                        "ANOMALY",
                        sim_time=observation.timestamp,
                        payload={
                            "code": "body_height_low",
                            "severity": "warning",
                            "summary": "Duck body height fell below standing threshold",
                            "height_m": snapshot["duck"]["position"][2],
                        },
                    )
                    anomaly_reported = True
                tick += 1
                self._stop.wait(max(0.0, period - (monotonic() - started)))
        except Exception as error:  # noqa: BLE001 - emit failures into the trace
            self.journal.publish(
                "RUN_FAILED",
                sim_time=0.0,
                payload={"error": type(error).__name__, "message": str(error)},
            )
        finally:
            adapter.close()

    @staticmethod
    def _snapshot(
        adapter: MujocoMicroduckAdapter,
        values: dict[str, object],
        started: float,
    ) -> dict[str, object]:
        duck = values["duck"]
        assert isinstance(duck, dict)
        orientation = duck["orientation"]
        assert isinstance(orientation, list)
        heading, pitch = _heading_and_pitch(orientation)
        velocity = values["root_velocity"]
        assert isinstance(velocity, list)
        speed = math.hypot(velocity[0], velocity[1])
        sim_time = float(adapter.data.time)
        return {
            "mode": "EXPLORING",
            "intention": "Stabilize posture and inspect the blue block",
            "rationale": "Running the baseline standing controller while observing arena objects.",
            "skill": "stand_and_scan",
            "attention": "blue_block",
            "confidence": max(0.45, 0.82 - min(abs(pitch) / 60.0, 0.3)),
            "energy": max(0.35, 1.0 - sim_time * 0.0008),
            "speed_mps": speed,
            "pitch_deg": pitch,
            "heading_deg": heading,
            "step_ms": (monotonic() - started) * 1000.0,
            "duck": duck,
            "head": values["head"],
            "blue_block": values["blue_block"],
            "red_ball": values["red_ball"],
            "actuator_targets": values["actuator_targets"],
            "joint_positions": values["joint_positions"],
            "contacts": values["contacts"],
            "goals": [
                {"name": "Stabilize posture", "utility": 0.91},
                {"name": "Inspect blue block", "utility": 0.77},
                {"name": "Map east wall", "utility": 0.42},
            ],
        }


def _heading_and_pitch(quaternion: list[float]) -> tuple[float, float]:
    w, x, y, z = quaternion
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    pitch_term = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.asin(pitch_term)
    return math.degrees(yaw), math.degrees(pitch)
