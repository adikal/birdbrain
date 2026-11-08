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
from birdbrain.owner import PREFERENCES as OWNERS


class PlayroomSession:
    """One duck in one seeded playroom, stepped at the 50 Hz control rate.

    The loop mirrors `eval_tidy.run_one` (scenario builder, walker, senses,
    intent routing, score). `step()` advances one tick; `result()` scores the
    run from simulator truth.
    """

    def __init__(self, seed: int, *, toys: int = 6, provider: str = "local", latency: str = "frozen",
                 journal: EventJournal | None = None, token_budget: int | None = None,
                 model: str | None = None, speculate: bool = False,
                 memory_dir: Path | None = None, needs: bool | str = False, room: str = "messy",
                 owner: str | None = None, episode: int | None = None, lifetime: int | None = None,
                 credit: str = "moments", rules: str | None = None, owner_model: str = "kinds",
                 author: bool = False, title: str | None = None, world: str = "playroom",
                 kinds: str = "dev", advice: bool = False, develop: bool = False) -> None:
        from microduck_local.brain.brain_env import POLICIES_DIR, onnx_infer
        from microduck_local.world import World, make_playroom

        from birdbrain.lab import BirdBrainBrain

        self.seed, self.toys, self.latency = seed, toys, latency
        self.owner = None
        self._kinds: list[tuple[float, str | None]] = []     # (decision time, kind of action)
        self._heard_changes: list[float] = []
        self.credit_given: list[float] = []
        self.world_name, self.kinds_split = world, kinds if world == "world2" else None
        if world == "world2":
            from birdbrain import world2
            if room != "messy":
                raise ValueError("World 2 has no tidy room")
            world2.register()
            self.scenario = world2.make_world(seed, world2.kinds_for(kinds, episode))
            self.toys = len(self.scenario.pickables)
        elif world == "playroom":
            self.scenario = make_playroom(seed=seed, n=toys, brain=None)
        else:
            raise ValueError(f"unknown world {world!r}")
        if room == "tidy":
            # Every toy starts in the basket: the test of doing nothing when nothing is worth doing.
            from dataclasses import replace
            bx, by = self.scenario.basket.pos
            spots = [(dx, dy) for dy in (-0.05, 0.05) for dx in (-0.07, 0.0, 0.07)]
            if len(self.scenario.pickables) > len(spots):
                raise ValueError(f"the tidy room holds at most {len(spots)} toys")
            self.scenario.pickables = [replace(p, pos=(bx + dx, by + dy))
                                       for p, (dx, dy) in zip(self.scenario.pickables, spots[:len(self.scenario.pickables)], strict=True)]
        elif room != "messy":
            raise ValueError(f"unknown room {room!r}")
        self.room = room
        self.world = World(self.scenario, infer_for={"d0": onnx_infer(POLICIES_DIR / "alpha_walking.onnx")},
                           seed=seed)
        self.duck = self.world.ducks["d0"]
        self.rules2 = None
        if world == "world2":
            import random

            from birdbrain.world2 import WorldRules
            self.rules2 = WorldRules(self.world, self.duck, seed)
            self._colour_rng, self._coloured = random.Random(seed * 17 + 3), (None, None)
        self.journal = journal or EventJournal()
        chooser = None
        if provider == "bedrock":
            from birdbrain.providers.bedrock import BedrockProvider
            chooser = BedrockProvider.from_env(model=model)
        corners = [p for w in self.scenario.walls for p in (w.start, w.end)] if self.scenario.walls else []
        half_thick = 0.01
        self.bounds = ((min(x for x, _ in corners) + half_thick, min(y for _, y in corners) + half_thick,
                        max(x for x, _ in corners) - half_thick, max(y for _, y in corners) - half_thick)
                       if corners else None)
        # Milestone 3b: an owner arm means the social need is approval. "none" is the
        # control: approval is a need, but nobody is there to give it.
        self.owner_arm, self.episode, self.lifetime = owner, episode, lifetime
        if owner is not None:
            needs = "approval"
        self.owner = None
        if owner not in (None, "none"):
            from birdbrain.owner import Owner
            self.owner = Owner(owner, seed=seed * 7919 + 13,
                               position=(self.bounds[0] + 0.3, self.bounds[3] - 0.3))
        self.brain = BirdBrainBrain(provider=chooser, log=self._log, latency=latency, token_budget=token_budget,
                                    speculate=speculate, memory_dir=memory_dir, needs=needs,
                                    room=self.bounds if needs == "approval" else None, seed=seed,
                                    credit=credit, rules=rules, owner_model=owner_model,
                                    author=self._author(model) if author else None,
                                    judge=self._judge(model) if advice else None, develop=develop)
        self.mind = self.brain.mind
        self.mind.episode = episode
        self._falls = self._attempts = 0
        self.grasp_errors: list[float | None] = []
        self.basket_errors: list[tuple[float, float]] = []      # (distance to basket, belief error)
        self._next_check = 0.0
        self._in_basket = {n: self.world.in_basket(n) for n in self.world.pickables}
        self.untidied = 0                                   # toys taken out of the basket
        self._toys_start: dict[str, Any] | None = None
        self._sat_start: dict[str, int] = {}
        self.time_in: dict[str, float] = {}                 # seconds per skill
        self.journal.publish("RUN_STARTED", sim_time=0.0, payload={
            "title": title, "seed": seed, "toys": toys, "provider": self.mind.provider.name,
            "model": getattr(self.mind.provider, "model", None), "latency": latency,
            "scenario": self.scenario.name, "room": list(self.scenario.floor),
            "basket_size": list(self.scenario.basket.size) if self.scenario.basket else None,
            # The room's layout, for viewers: walls beyond the four outer ones, and furniture.
            "walls": [[*w.start, *w.end] for w in self.scenario.walls[4:]],
            "boxes": [[round(b.pos[0], 3), round(b.pos[1], 3), round(b.size[0], 3), round(b.size[1], 3),
                       round(b.yaw, 3)] for b in self.scenario.boxes],
            "world": world})

    def _log(self, kind: str, payload: dict[str, Any]) -> None:
        if kind == "DECISION":
            self._kinds.append((self.world.t, payload.get("kind")))
        elif kind == "HEARD" and self.owner is not None and self._heard_changes:
            # Evaluation only: the share of credit the duck gave to the kind of action it was
            # doing when the change she answered happened (ledger E-016).
            changed = self._heard_changes.pop(0)
            if payload.get("valence"):
                cause = next((k for t0, k in reversed(self._kinds) if t0 <= changed), None)
                self.credit_given.append(float(payload["causes"].get(cause, 0.0)))
        self.journal.publish(kind, sim_time=self.world.t, payload=payload)

    @property
    def t(self) -> float:
        return self.world.t

    def step(self) -> None:
        from microduck_local.brain.runtime import Senses

        world, duck = self.world, self.duck
        tof, tof_age = world.senses_tof(duck)
        det = duck.detector.last if duck.detector is not None else None
        if det is not None and self.rules2 is not None:
            # World 2's colour classifier, read once per detector frame.
            if self._coloured[0] is not det:
                from birdbrain.world2 import colour_sensor
                self._coloured = (det, colour_sensor(det, self.rules2.kind, self._colour_rng))
            det = self._coloured[1]
        senses = Senses(t=world.t, tof=tof, tof_age=tof_age, det=det,
                        det_age=None if det is None else world.t - det.t,
                        speed=duck.heading_speed(world.data), odom=world.odom(duck),
                        holding=duck.holding is not None, skill=duck.skill, bumped=world.bumped(duck))
        heard, petted = (), False
        if self.owner_arm is not None and self._toys_start is None:
            from birdbrain.owner import OWNER_WALL_M, PREFERENCES
            room = self.owner_room()
            self._toys_start = dict(room.toys)
            self._sat_start = {name: sum(f(room, toy, self._toys_start, OWNER_WALL_M) for toy in room.toys)
                               for name, f in PREFERENCES.items()}
        if self.owner is not None:
            heard, petted = self.owner.step(world.t, self.owner_room(), tuple(duck.trunk_pos(world.data)[:2]))
            self._heard_changes = list(self.owner.heard_changes)
        command = self.brain.step(senses, heard=heard, petted=petted)
        state = self.mind.state
        self.time_in[state] = self.time_in.get(state, 0.0) + 0.02
        world.apply_intent(duck, command)
        if duck.skill is None:
            duck.set_cmd(world.data, command.twist, command.head)
        world.step()
        if self.rules2 is not None:
            self.rules2.step(0.02)
        self._evaluate()

    def _evaluate(self) -> None:
        """Truth, for evaluation only: grasp miss distances and falls."""
        duck = self.duck
        if duck.holding is not None and self._in_basket.get(duck.holding):
            self.untidied += 1
            self._in_basket[duck.holding] = False
        if self.world.t >= self._next_check:
            for n in self.world.pickables:
                if n != duck.holding:
                    self._in_basket[n] = self.world.in_basket(n)
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
        kinds = {} if self.rules2 is None else self.rules2.kind
        toys = [{"id": n, "x": round(float(w.data.xpos[b][0]), 3), "y": round(float(w.data.xpos[b][1]), 3),
                 "in_basket": bool(w.in_basket(n)),
                 **({"kind": kinds[n].name, "colour": kinds[n].colour, "what": kinds[n].category}
                    if n in kinds else {})} for n, b in w.pickables.items()]
        pos = self.duck.trunk_pos(w.data)
        return {"duck": [round(float(pos[0]), 3), round(float(pos[1]), 3)], "toys": toys,
                "basket": list(w.basket.pos) if w.basket else None}

    def perception_metrics(self) -> dict[str, Any]:
        """Evaluation only: belief quality against simulator truth."""
        kb = self.mind.kb
        far = sorted(err for dist, err in self.basket_errors if dist > 1.0)
        near = sorted(err for dist, err in self.basket_errors if dist <= 1.0)
        confident = [e for e in kb.of_class("basket") if kb.get("at", e) is not None and kb.get("at", e).conf >= 0.5]
        # Pick decisions, including those run as a skill written in place of pick (E-019 review).
        picks = [e for e in kb.find_events("action") if e.data.get("depth") == 0
                 and "pick" in {e.data.get("skill"), e.data.get("variant_of")}]
        return {
            "basketErrFarMedian": round(_quantile(far, 0.5), 3), "basketErrFarP90": round(_quantile(far, 0.9), 3),
            "basketErrNearMedian": round(_quantile(near, 0.5), 3),
            "confidentBaskets": len(confident),
            "merges": sum(1 for a in kb.history if a.rel == "same_as"),
            "toyIds": len(kb.of_class("toy")),
            # Picks stopped on the way (E-023) are counted apart (E-025 review).
            "pickDecisions": len(picks) - self.mind.stats.get("reconsidered", 0),
            "pickDecisionsFailed": sum(1 for e in picks if e.data.get("outcome") != "done")
            - self.mind.stats.get("reconsidered", 0),
            "pickStops": self.mind.stats.get("reconsidered", 0),
        }

    @staticmethod
    def _judge(model: str | None) -> Any:
        from birdbrain.providers.bedrock import BedrockJudge, BedrockProvider
        return BedrockJudge(BedrockProvider.from_env(model=model))

    @staticmethod
    def _author(model: str | None) -> Any:
        from birdbrain.providers.bedrock import BedrockAuthor, BedrockProvider
        return BedrockAuthor(BedrockProvider.from_env(model=model))

    def owner_room(self) -> Any:
        """Truth for the owner (and for evaluation): never passed to the mind."""
        from birdbrain.owner import Room
        w = self.world
        toys = {n: (float(w.data.xpos[b][0]), float(w.data.xpos[b][1])) for n, b in w.pickables.items()}
        colours = {} if self.rules2 is None else {n: k.colour for n, k in self.rules2.kind.items()}
        return Room(toys=toys, in_basket={n: bool(w.in_basket(n)) for n in toys},
                    held=self.duck.holding, bounds=self.bounds, colours=colours)

    def owner_metrics(self) -> dict[str, Any]:
        """Evaluation only: how the room stands against each preference, from truth."""
        if self.owner_arm is None:
            return {}
        from birdbrain.owner import OWNER_WALL_M, PREFERENCES
        room = self.owner_room()
        sat = {name: sum(f(room, toy, self._toys_start, OWNER_WALL_M) for toy in room.toys)
               for name, f in PREFERENCES.items()}
        log = self.owner.log if self.owner is not None else []
        return {"owner": self.owner_arm, "episode": self.episode, "lifetime": self.lifetime,
                **{f"sat_{k}": v for k, v in sat.items()},
                **{f"sat_{k}_start": v for k, v in self._sat_start.items()},
                "ownerApprovals": sum(1 for _, v, _ in log if v > 0),
                "ownerDisapprovals": sum(1 for _, v, _ in log if v < 0),
                "ownerPets": sum(1 for *_, said in log if said == "pet"),
                # Changes she disliked, by how they happened: the duck picked the toy up, or the
                # toy moved while nobody held it (knocked, pushed, or put down where she dislikes).
                "creditToCause": round(sum(self.credit_given), 3), "creditN": len(self.credit_given),
                "lostByPick": sum(1 for _, _, now, held in self.owner.changes if not now and held)
                if self.owner is not None else 0,
                "lostOtherwise": sum(1 for _, _, now, held in self.owner.changes if not now and not held)
                if self.owner is not None else 0,
                "ownerModel": None if self.mind.reactions is None else self.mind.reactions.summary(),
                "credit": None if self.mind.reactions is None else self.mind.reactions.credit,
                "mood": None if self.mind.needs is None else round(self.mind.needs.mood, 3)}

    def close(self) -> None:
        self.mind.close()

    def result(self, wall_seconds: float) -> dict[str, Any]:
        mind, duck = self.mind, self.duck
        return {
            "seed": self.seed, "toys": self.toys, "seconds": round(self.world.t, 1),
            "provider": mind.provider.name, "model": getattr(mind.provider, "model", None),
            "latency": self.latency, "run_id": self.journal.run_id,
            "inBasket": self.world.tidy_score()["inBasket"], "falls": duck.falls,
            "room": self.room, "needs": self.mind.needs is not None, "untidied": self.untidied,
            "timeIn": {k: round(v, 1) for k, v in sorted(self.time_in.items())},
            "battery": None if self.mind.needs is None else round(self.mind.needs.battery, 3),
            "attempts": int(duck.grasp_attempts), "grasps": int(duck.grasp_successes),
            "graspErrors": self.grasp_errors,
            "records": {name: r.to_dict() for name, r in mind.records.items()},
            **mind.stats, "tokens": mind.tokens_used, **self.perception_metrics(),
            "simSeconds": round(self.world.t, 1), "wallSeconds": round(wall_seconds, 1),
            "writtenSkills": mind.authoring.summary(), "authoringTokens": mind.authoring.tokens,
            "adviceTokens": 0 if mind.advice is None else mind.advice.tokens,
            "rules": mind.use_rules, "ownerModelKind": mind.owner_model if mind.reactions is not None else None,
            **self.owner_metrics(), **self.world_metrics(),
        }

    def world_metrics(self) -> dict[str, Any]:
        """Evaluation only: World 2's truth measures."""
        if self.rules2 is None:
            return {}
        from birdbrain.world2 import measures
        return {"world": self.world_name, "kinds": self.kinds_split,
                **measures(self.world, self.mind.kb, self.rules2,
                            {p.id: p.pos for p in self.scenario.pickables})}


def run_one(seed: int, *, toys: int = 6, seconds: float = 300.0, provider: str = "local",
            latency: str = "frozen", runs_dir: Path | None = None, tag: str = "",
            token_budget: int | None = None, model: str | None = None,
            camera: bool = False, speculate: bool = False,
            memory_dir: Path | None = None, needs: bool = False, room: str = "messy",
            owner: str | None = None, episode: int | None = None, lifetime: int | None = None,
            credit: str = "moments", rules: str | None = None, owner_model: str = "kinds",
            author: bool = False, title: str | None = None, world: str = "playroom",
            kinds: str = "dev", advice: bool = False, develop: bool = False) -> dict[str, Any]:
    life = "" if episode is None else f"-L{lifetime}e{episode}"
    run_id = f"{tag or 'run'}{life}-s{seed}-{provider}-{int(time.time() * 1000) % 10**9}"
    store = JsonlRunStore(runs_dir) if runs_dir else None
    journal = EventJournal(run_id=run_id, store=store)
    session = PlayroomSession(seed, toys=toys, provider=provider, latency=latency, journal=journal,
                              token_budget=token_budget, model=model, speculate=speculate,
                              memory_dir=memory_dir, needs=needs, room=room,
                              owner=owner, episode=episode, lifetime=lifetime, credit=credit,
                              rules=rules, owner_model=owner_model, author=author, title=title,
                              world=world, kinds=kinds, advice=advice, develop=develop)
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


def _run_args(a: tuple) -> list[dict[str, Any]]:
    seed, kwargs, episodes, memory_root = a
    if episodes is None:
        return [run_one(seed, **kwargs)]
    return run_lifetime(seed, episodes, memory_root, **kwargs)


def room_seed(lifetime: int, episode: int) -> int:
    """Each episode of a lifetime is a different room; rooms of different lifetimes never coincide."""
    return 100 * lifetime + episode


def run_lifetime(lifetime: int, episodes: int, memory_root: Path | None,
                 owner_change: tuple[int, str] | None = None, **kwargs: Any) -> list[dict[str, Any]]:
    """One life: `episodes` rooms in a row, with the duck's memory kept between them
    (design section 5), or none (`memory_root` None: agent A, Milestone 6). With
    `owner_change` (room, preference), the owner wants something else from that room on
    (Milestone 6); the duck is not told. Rows carry the lifetime as `seed` and the episode."""
    memory = None if memory_root is None else memory_root / f"life-{lifetime}"
    if memory is not None and memory.exists() and any(memory.iterdir()):
        raise ValueError(f"{memory} already holds a life; choose a fresh --memory directory")
    rows = []
    for e in range(1, episodes + 1):
        owner = owner_change[1] if owner_change is not None and e >= owner_change[0] else kwargs.get("owner")
        row = run_one(room_seed(lifetime, e), **{**kwargs, "owner": owner, "memory_dir": memory, "episode": e,
                                                "lifetime": lifetime})
        rows.append({**row, "room_seed": row["seed"], "seed": lifetime, "episode": e, "memoryKept": memory is not None,
                     **({"ownerChangedAt": owner_change[0]} if owner_change is not None else {})})
    return rows


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
    ap.add_argument("--needs", action="store_true",
                    help="no task: the duck acts on its needs and self-generated goals (Milestone 3)")
    ap.add_argument("--room", choices=["messy", "tidy"], default="messy",
                    help="messy: toys scattered; tidy: every toy starts in the basket")
    ap.add_argument("--memory", type=Path, default=None,
                    help="lifetime memory directory: seeds run in order as episodes of one life (forces --jobs 1)")
    ap.add_argument("--owner", choices=["none", *OWNERS], default=None,
                    help="Milestone 3b: the social need is approval; a scripted owner with this hidden "
                         "preference reacts with phrases (none: the control, nobody there)")
    ap.add_argument("--owner-change", default=None, metavar="ROOM:PREFERENCE",
                    help="Milestone 6, with --owner and --episodes: from this room of each life the owner "
                         "has this preference instead, e.g. 11:hers")
    ap.add_argument("--credit", choices=["moments", "underway"], default="moments",
                    help="Milestone 3b: credit the owner's reactions to the duck's own changes to the room "
                         "(grasp, release, bump; E-016) or to any action under way (E-015)")
    ap.add_argument("--rules", choices=["mean", "draw", "cautious"], default=None,
                    help="decide with causal rules (Milestone 4) instead of counts per skill: their posterior "
                         "mean, one posterior draw per decision (E-018), or a draw for the expected effect with an upper "
                         "bound on falls (H-020); the rules are learned and scored "
                         "either way")
    ap.add_argument("--owner-model", choices=["kinds", "conditions"], default="kinds",
                    help="Milestone 3b: learn the owner's reactions per hand-chosen kind of action, or over the "
                         "conditions of each action (E-018)")
    ap.add_argument("--author", action="store_true",
                    help="Milestone 5: between episodes, the cloud brain (Bedrock) writes skills for situations "
                         "where a skill clearly fails; written skills are tried and kept or retired on merit")
    ap.add_argument("--episodes", type=int, default=None,
                    help="each seed is a lifetime of this many episodes (rooms), memory kept between them; "
                         "memory goes under --memory (default data/lifetimes/<tag>)")
    ap.add_argument("--speculate", action="store_true",
                    help="think while acting: ask for the next decision when each skill starts")
    ap.add_argument("--camera", action="store_true",
                    help="record viewer data for the dashboard at 2 Hz: head-camera images and the truth overlay")
    ap.add_argument("--title", default=None, help="what the run shows, for the dashboard's run list")
    ap.add_argument("--world", choices=["playroom", "world2"], default="playroom",
                    help="world2: many kinds of object with hidden properties, furniture, inner walls (E-021)")
    ap.add_argument("--kinds", choices=["dev", "all", "late"], default="dev",
                    help="World 2's object kinds: development only, all, or new kinds from room 11 of a life")
    ap.add_argument("--advice", action="store_true",
                    help="the cloud brain (Bedrock) judges each newly seen appearance of object once; its "
                         "judgement enters the rules as a prior (E-036)")
    ap.add_argument("--agent", choices=["A", "B", "C", "D"], default=None,
                    help="Milestone 6: A reactive (task, no memory between rooms); B task with memory; "
                         "C proactive (needs, memory); D developmental (C deciding with its rules, --rules mean: "
                         "each toy judged by its own pick and delivery, deferring what a credible rule speaks against)")
    ap.add_argument("--no-memory", action="store_true",
                    help="with --episodes: nothing is kept between rooms (agent A is B with this), so each "
                         "agent has a twin that measures what its experience bought (Milestone 6)")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--out", required=True, help="rows are appended here as JSON lines")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    runs_dir = Path(os.environ.get("BIRDBRAIN_RUNS_DIR", "data/runs"))
    kwargs = {"toys": args.toys, "seconds": args.seconds, "provider": args.provider,
              "latency": args.latency, "runs_dir": runs_dir, "tag": args.tag,
              "token_budget": args.token_budget, "model": args.model, "camera": args.camera,
              "speculate": args.speculate, "memory_dir": args.memory, "needs": args.needs, "room": args.room,
              "owner": args.owner, "credit": args.credit, "rules": args.rules, "owner_model": args.owner_model,
              "author": args.author, "title": args.title, "world": args.world, "kinds": args.kinds,
              "advice": args.advice, "develop": False}
    if args.agent is not None:
        if args.episodes is None:
            ap.error("--agent compares lives: give --episodes")
        kwargs["needs"] = args.agent in {"C", "D"}
        kwargs["develop"] = args.agent == "D"
        if args.agent == "D" and args.rules is None:
            kwargs["rules"] = "mean"        # its scorecard judges each toy by the rules (Milestone 4)
    if args.owner_change is not None:
        room, _, preference = args.owner_change.partition(":")
        if args.owner in (None, "none") or args.episodes is None or not room.isdigit() or preference not in OWNERS:
            ap.error("--owner-change ROOM:PREFERENCE needs --owner and --episodes, and a preference from "
                     f"{', '.join(OWNERS)}")
        kwargs["owner_change"] = (int(room), preference)
    memory_root = None
    if args.episodes is not None:
        memory_root = (None if args.agent == "A" or args.no_memory
                       else args.memory or Path("data/lifetimes") / (args.tag or "untagged"))
        kwargs.pop("memory_dir")
    elif args.memory is not None:
        args.jobs = 1
    seeds = [args.seed0 + k for k in range(args.seeds)]
    rows: list[dict[str, Any]] = []
    with out.open("a", encoding="utf-8") as stream:
        def keep(row: dict[str, Any]) -> None:
            rows.append(row)
            stream.write(json.dumps({**row, "tag": args.tag, "agent": args.agent}) + "\n")
            stream.flush()
            life = f" episode {row['episode']}" if row.get("episode") else ""
            owner = (f" · owner {row['owner']}: liked {row.get('sat_' + row['owner'], '-')}"
                     f" (start {row.get('sat_' + row['owner'] + '_start', '-')}) · heard +{row.get('approvals', 0)}"
                     f"/-{row.get('disapprovals', 0)}" if row.get("owner") not in (None, "none") else "")
            print(f"seed {row['seed']}{life}: {row['inBasket']}/{row['toys']} in basket{owner} · grasps "
                  f"{row['grasps']}/{row['attempts']} · falls {row['falls']} · decisions {row['decisions']}"
                  f" · fallbacks {row['fallbacks']} · {row['wallSeconds']} s wall", flush=True)

        if args.jobs > 1 and len(seeds) > 1:
            import multiprocessing as mp
            ctx = mp.get_context("spawn")
            with ctx.Pool(min(args.jobs, len(seeds))) as pool:
                for batch in pool.imap(_run_args, [(s, kwargs, args.episodes, memory_root) for s in seeds]):
                    for row in batch:
                        keep(row)
        else:
            for seed in seeds:
                for row in _run_args((seed, kwargs, args.episodes, memory_root)):
                    keep(row)
    rows.sort(key=lambda r: r["seed"])
    for line in summarize(rows):
        print(line)


if __name__ == "__main__":
    main()
