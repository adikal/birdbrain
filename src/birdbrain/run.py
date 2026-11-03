"""Run BirdBrain in Microduck Lab's playroom and score it from simulator truth.

    birdbrain-run --seeds 16 --seconds 300 --out experiments/E-008/rows.jsonl
    birdbrain-run --provider bedrock --seeds 5 --out experiments/E-010/rows.jsonl

The loop mirrors Microduck Lab's `eval_tidy.run_one` step for step (same
scenario builder, walker, senses, intent routing, and score), so a row here
is comparable with an `eval-tidy` row for the same seed. The world's true
state is read only by this module, to score the run; the mind sees only
what `birdbrain.lab.observation` copies.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from statistics import fmean
from typing import Any

from birdbrain.observability import EventJournal, JsonlRunStore


class PlayroomSession:
    """One duck in one seeded playroom, stepped at the 50 Hz control rate.

    The loop mirrors `eval_tidy.run_one` (scenario builder, walker, senses,
    intent routing, score). `step()` advances one tick; `result()` scores the
    run from simulator truth.
    """

    def __init__(self, seed: int, *, toys: int = 6, provider: str = "local", latency: str = "frozen",
                 journal: EventJournal | None = None, token_budget: int | None = None,
                 model: str | None = None) -> None:
        from microduck_local.brain.brain_env import POLICIES_DIR, onnx_infer
        from microduck_local.world import World, make_playroom

        from birdbrain.lab import BirdBrainBrain

        self.seed, self.toys, self.latency = seed, toys, latency
        self.scenario = make_playroom(seed=seed, n=toys, brain=None)
        self.world = World(self.scenario, infer_for={"d0": onnx_infer(POLICIES_DIR / "alpha_walking.onnx")},
                           seed=seed)
        self.duck = self.world.ducks["d0"]
        self.journal = journal or EventJournal()
        chooser = None
        if provider == "bedrock":
            from birdbrain.providers.bedrock import BedrockProvider
            chooser = BedrockProvider.from_env(model=model)
        self.brain = BirdBrainBrain(provider=chooser, log=self._log, latency=latency, token_budget=token_budget)
        self.mind = self.brain.mind
        self._falls = self._attempts = 0
        self.grasp_errors: list[float | None] = []
        self.basket_errors: list[tuple[float, float]] = []      # (distance to basket, belief error)
        self._next_check = 0.0
        self.journal.publish("RUN_STARTED", sim_time=0.0, payload={
            "seed": seed, "toys": toys, "provider": self.mind.provider.name,
            "model": getattr(self.mind.provider, "model", None), "latency": latency,
            "scenario": self.scenario.name, "room": list(self.scenario.floor),
            "basket_size": list(self.scenario.basket.size) if self.scenario.basket else None})

    def _log(self, kind: str, payload: dict[str, Any]) -> None:
        self.journal.publish(kind, sim_time=self.world.t, payload=payload)

    @property
    def t(self) -> float:
        return self.world.t

    def step(self) -> None:
        from microduck_local.brain.runtime import Senses

        world, duck = self.world, self.duck
        tof, tof_age = world.senses_tof(duck)
        det = duck.detector.last if duck.detector is not None else None
        senses = Senses(t=world.t, tof=tof, tof_age=tof_age, det=det,
                        det_age=None if det is None else world.t - det.t,
                        speed=duck.heading_speed(world.data), odom=world.odom(duck),
                        holding=duck.holding is not None, skill=duck.skill, bumped=world.bumped(duck))
        command = self.brain.step(senses)
        world.apply_intent(duck, command)
        if duck.skill is None:
            duck.set_cmd(world.data, command.twist, command.head)
        world.step()
        self._evaluate()

    def _evaluate(self) -> None:
        """Truth, for evaluation only: grasp miss distances and falls."""
        duck = self.duck
        if duck.grasp_attempts > self._attempts:
            self._attempts = duck.grasp_attempts
            err = duck.last_grasp_err
            self.grasp_errors.append(None if err is None else round(float(err), 4))
            self._log("GRASP_TRUTH", {"error_m": self.grasp_errors[-1], "held": duck.holding is not None})
        if self.world.t >= self._next_check and self.world.basket is not None:
            self._next_check = self.world.t + 0.5
            kb = self.mind.kb
            best = max((e for e in kb.of_class("basket") if kb.get("at", e) is not None),
                       key=lambda e: kb.get("at", e).conf, default=None)
            if best is not None:
                belief, (bx, by) = kb.position(best), self.world.basket.pos
                trunk = duck.trunk_pos(self.world.data)
                self.basket_errors.append((float(math.hypot(trunk[0] - bx, trunk[1] - by)),
                                           float(math.hypot(belief.x - bx, belief.y - by))))
        if duck.falls > self._falls:
            self._falls = duck.falls
            last = self.mind.ctx.last
            self._log("FALL", {"falls": duck.falls, "skill": self.mind.state,
                               "note": "" if last is None else last.note})

    def camera_event(self, camera: Any) -> bool:
        """Render the camera frame the mind has just interpreted, with what it made of it.
        Returns False until such a frame is available (the mind reads a frame one tick
        after the detector produces it)."""
        view = self.mind.perception.last_view
        if view is None:
            return False
        shot = camera.capture(frame_t=view["t"])
        if shot is None:
            return False
        shot["view"] = view
        self.journal.publish("CAMERA_FRAME", sim_time=self.world.t, payload=shot)
        return True

    def truth(self) -> dict[str, Any]:
        """Simulator truth for viewers: never passed to the mind."""
        w = self.world
        toys = [{"id": n, "x": round(float(w.data.xpos[b][0]), 3), "y": round(float(w.data.xpos[b][1]), 3),
                 "in_basket": bool(w.in_basket(n))} for n, b in w.pickables.items()]
        pos = self.duck.trunk_pos(w.data)
        return {"duck": [round(float(pos[0]), 3), round(float(pos[1]), 3)], "toys": toys,
                "basket": list(w.basket.pos) if w.basket else None}

    def perception_metrics(self) -> dict[str, Any]:
        """Evaluation only: belief quality against simulator truth."""
        kb = self.mind.kb
        far = sorted(err for dist, err in self.basket_errors if dist > 1.0)
        near = sorted(err for dist, err in self.basket_errors if dist <= 1.0)
        confident = [e for e in kb.of_class("basket") if kb.get("at", e) is not None and kb.get("at", e).conf >= 0.5]
        picks = [e for e in kb.find_events("action") if e.data.get("skill") == "pick" and e.data.get("depth") == 0]
        return {
            "basketErrFarMedian": round(_quantile(far, 0.5), 3), "basketErrFarP90": round(_quantile(far, 0.9), 3),
            "basketErrNearMedian": round(_quantile(near, 0.5), 3),
            "confidentBaskets": len(confident),
            "merges": sum(1 for a in kb.history if a.rel == "same_as"),
            "toyIds": len(kb.of_class("toy")),
            "pickDecisions": len(picks),
            "pickDecisionsFailed": sum(1 for e in picks if e.data.get("outcome") != "done"),
        }

    def close(self) -> None:
        self.mind.close()

    def result(self, wall_seconds: float) -> dict[str, Any]:
        mind, duck = self.mind, self.duck
        return {
            "seed": self.seed, "toys": self.toys, "seconds": round(self.world.t, 1),
            "provider": mind.provider.name, "model": getattr(mind.provider, "model", None),
            "latency": self.latency, "run_id": self.journal.run_id,
            "inBasket": self.world.tidy_score()["inBasket"], "falls": duck.falls,
            "attempts": int(duck.grasp_attempts), "grasps": int(duck.grasp_successes),
            "graspErrors": self.grasp_errors,
            "records": {name: r.to_dict() for name, r in mind.records.items()},
            **mind.stats, "tokens": mind.tokens_used, **self.perception_metrics(),
            "simSeconds": round(self.world.t, 1), "wallSeconds": round(wall_seconds, 1),
        }


def run_one(seed: int, *, toys: int = 6, seconds: float = 300.0, provider: str = "local",
            latency: str = "frozen", runs_dir: Path | None = None, tag: str = "",
            token_budget: int | None = None, model: str | None = None,
            camera: bool = False) -> dict[str, Any]:
    run_id = f"{tag or 'run'}-s{seed}-{provider}-{int(time.time() * 1000) % 10**9}"
    store = JsonlRunStore(runs_dir) if runs_dir else None
    journal = EventJournal(run_id=run_id, store=store)
    session = PlayroomSession(seed, toys=toys, provider=provider, latency=latency, journal=journal,
                              token_budget=token_budget, model=model)
    head = None
    if camera and store is not None:
        from birdbrain.observability.camera import HeadCamera
        head = HeadCamera(session.world, session.duck, store.run_dir(run_id) / "camera")
    t0, next_shot = time.time(), 0.0
    while session.t < seconds:
        session.step()
        if head is not None and session.t >= next_shot and session.camera_event(head):
            next_shot = session.t + 0.5
            journal.publish("TRUTH", sim_time=session.t, payload=session.truth())
    if head is not None:
        head.close()
    session.close()
    row = session.result(time.time() - t0)
    journal.publish("RUN_STOPPED", sim_time=session.t, payload={"result": row, "truth": session.truth()})
    return row


def _quantile(xs: list[float], q: float) -> float:
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else math.nan


def _run_args(a: tuple) -> dict[str, Any]:
    seed, kwargs = a
    return run_one(seed, **kwargs)


def summarize(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["no rows"]
    n = len(rows)
    inb = [r["inBasket"] for r in rows]
    falls = fmean(r["falls"] for r in rows)
    first = (f"seeds {n} · in basket {fmean(inb):.2f} of {rows[0]['toys']} "
             f"(sd {_sd(inb):.2f}, min {min(inb)}, max {max(inb)}) · falls {falls:.2f}/run")
    total = {k: sum(r[k] for r in rows) for k in
             ("grasps", "attempts", "decisions", "fallbacks", "invalid", "provider_errors")}
    second = (f"grasps {total['grasps']}/{total['attempts']} · decisions {total['decisions']} · "
              f"fallbacks {total['fallbacks']} · invalid {total['invalid']} · "
              f"provider errors {total['provider_errors']}")
    return [first, second]


def _sd(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = fmean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=16)
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--toys", type=int, default=6)
    ap.add_argument("--seconds", type=float, default=300.0)
    ap.add_argument("--provider", choices=["local", "bedrock"], default="local")
    ap.add_argument("--model", default=None, help="Bedrock model id (default: BIRDBRAIN_BEDROCK_MODEL)")
    ap.add_argument("--latency", choices=["frozen", "real"], default="frozen",
                    help="frozen: the world waits for the cloud brain; real: the duck stands while it thinks")
    ap.add_argument("--token-budget", type=int, default=None, help="per run; beyond it the local policy decides")
    ap.add_argument("--camera", action="store_true",
                    help="record viewer data for the dashboard at 2 Hz: head-camera images and the truth overlay")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--out", required=True, help="rows are appended here as JSON lines")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    runs_dir = Path(os.environ.get("BIRDBRAIN_RUNS_DIR", "data/runs"))
    kwargs = {"toys": args.toys, "seconds": args.seconds, "provider": args.provider,
              "latency": args.latency, "runs_dir": runs_dir, "tag": args.tag,
              "token_budget": args.token_budget, "model": args.model, "camera": args.camera}
    seeds = [args.seed0 + k for k in range(args.seeds)]
    rows: list[dict[str, Any]] = []
    with out.open("a", encoding="utf-8") as stream:
        def keep(row: dict[str, Any]) -> None:
            rows.append(row)
            stream.write(json.dumps({**row, "tag": args.tag}) + "\n")
            stream.flush()
            print(f"seed {row['seed']}: {row['inBasket']}/{row['toys']} in basket · grasps "
                  f"{row['grasps']}/{row['attempts']} · falls {row['falls']} · decisions {row['decisions']}"
                  f" · fallbacks {row['fallbacks']} · {row['wallSeconds']} s wall", flush=True)

        if args.jobs > 1 and len(seeds) > 1:
            import multiprocessing as mp
            ctx = mp.get_context("spawn")
            with ctx.Pool(min(args.jobs, len(seeds))) as pool:
                for row in pool.imap(_run_args, [(s, kwargs) for s in seeds]):
                    keep(row)
        else:
            for seed in seeds:
                keep(run_one(seed, **kwargs))
    rows.sort(key=lambda r: r["seed"])
    for line in summarize(rows):
        print(line)


if __name__ == "__main__":
    main()
