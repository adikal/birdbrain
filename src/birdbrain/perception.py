"""Perception: turn observations into assertions about entities.

The detector reports a class, a bearing, and an elevation for each object it
sees, with no identity. Perception locates each sighting on the floor from
the camera pose, associates it with a known entity of the same class (or
creates one), and fuses the position with a scalar Kalman update. An entity
that should have been seen and was not loses confidence; below a floor its
position is no longer asserted.
"""

from __future__ import annotations

import itertools
import math
from collections import deque
from dataclasses import dataclass

from birdbrain.body import MICRODUCK, BodyProfile, Frame, Observation, Sighting
from birdbrain.kr import SELF, KnowledgeBase, Position, same_place

CONFIRMED = 0.5          # an entity is acted on once its position confidence reaches this


@dataclass(frozen=True)
class PerceptionParams:
    gate_chi2: float = 9.21          # association gate: 99% of a 2-D Gaussian
    gate_floor: float = 0.04         # extra standard deviation in the gate for unmodelled error (m)
    bearing_sigma: float = math.radians(1.5)
    # Elevation error of a sighting (rad), measured against simulator truth (ledger E-011):
    # median 0.020 standing and 0.018 moving, but heavy-tailed while moving (p99 0.097).
    elevation_sigma_still: float = 0.025
    elevation_sigma_moving: float = 0.035
    robust_chi2: float = 4.0         # beyond this innovation, a measurement is down-weighted (Huber)
    # Sightings taken while moving are heavy-tailed (ledger E-011, H-013): about 2% are
    # several standard deviations off. They are modelled as a second, wide component.
    outlier_p: float = 0.03
    outlier_scale: float = 16.0      # covariance multiplier of the outlier component (4x sigma)
    # How fast an unobserved estimate loses precision (m/s), by class. Baskets do
    # not move by themselves; toys move only when something acts on them.
    drift_per_s: tuple[tuple[str, float], ...] = (("basket", 0.0), ("toy", 0.005))
    default_drift_per_s: float = 0.01
    hold_radius: float = 0.15        # a toy believed this close to the beak tip is the one grasped
    min_sigma: float = 0.02          # successive sightings share errors; never trust a fix beyond this
    # Confidence is the probability that the object exists where believed, updated
    # in log-odds from each frame (ledger E-013). A detection consistent with the
    # entity counts log(p_d / p_false); a frame that should have shown it and did
    # not counts log((1 - p_d) / (1 - p_false)), with p_d the measured detection
    # rate at that range. The prior for a new entity needs two hits to confirm.
    prior_logit: float = -3.0
    p_false: float = 0.1             # a consistent detection without the object (ghosts, mis-association)
    logit_limit: float = 5.0
    # Measured detection rate by range (m), inside the field of view (ledger E-013).
    # The last toy bin holds everything beyond 1.75 m; beyond the table the last value holds.
    detection_rate: tuple[tuple[str, tuple[tuple[float, float], ...]], ...] = (
        ("toy", ((0.25, 0.97), (0.5, 0.95), (0.625, 0.84), (0.875, 0.61), (1.125, 0.41),
                 (1.375, 0.33), (1.625, 0.21), (1.875, 0.11))),
        ("basket", ((0.5, 0.97), (2.0, 0.96))),
    )
    default_detection_rate: float = 0.5
    fov_margin: float = math.radians(8.0)
    min_width: float = math.radians(2.0)   # objects that would look smaller than this may go unseen


class Perception:
    def __init__(self, kb: KnowledgeBase, body: BodyProfile = MICRODUCK,
                 params: PerceptionParams | None = None) -> None:
        self.kb, self.body, self.p = kb, body, params or PerceptionParams()
        self._odom: deque[tuple[float, tuple[float, float, float]]] = deque(maxlen=100)
        self._last_frame_t = -math.inf
        self._held: str | None = None
        self._moving_until = -math.inf
        #: The latest camera frame and what each sighting was taken to be (entity id, or a reason).
        self.last_view: dict | None = None
        #: Pairs of entities once seen in the same frame: provably distinct objects.
        self._distinct: set[frozenset[str]] = set()
        self._gated: set[str] = set()

    # -- per tick ---------------------------------------------------------------
    def update(self, obs: Observation) -> None:
        if self._odom:
            dt = max(obs.t - self._odom[-1][0], 1e-3)
            yaw_rate = abs(_wrap(obs.odom[2] - self._odom[-1][1][2])) / dt
            if abs(obs.speed) > 0.05 or yaw_rate > 0.2:
                self._moving_until = obs.t + 0.3
        self._odom.append((obs.t, obs.odom))
        x, y, yaw = obs.odom
        kb = self.kb
        kb.tell("at", (SELF,), Position.round(x, y, 0.01), t=obs.t, source="odometry",
                same=same_place(0.05))
        kb.tell("heading", (SELF,), yaw, t=obs.t, source="odometry",
                same=lambda a, b: abs(_wrap(a - b)) < 0.1)
        self._update_holding(obs)
        if obs.frame is not None and obs.frame.t > self._last_frame_t:
            self._last_frame_t = obs.frame.t
            self._integrate(obs.frame, obs.t)

    # -- holding ----------------------------------------------------------------
    def _update_holding(self, obs: Observation) -> None:
        kb, t = self.kb, obs.t
        if obs.holding and self._held is None:
            tip = self.beak_tip(obs.odom)
            toys = [e for e in kb.of_class("toy")
                    if kb.position(e) is not None and kb.position(e).distance(tip) <= self.p.hold_radius]
            held = min(toys, key=lambda e: kb.position(e).distance(tip), default=None)
            if held is None:
                held = kb.new_entity("toy", t)      # grasped something it had not placed
            self._held = held
            kb.untell("at", (held,), t=t, reason="picked up")
            kb.tell("holding", (SELF,), held, t=t, source="beak")
        elif not obs.holding and self._held is not None:
            held, self._held = self._held, None
            kb.untell("holding", (SELF,), t=t, reason="released")
            tip = self.beak_tip(obs.odom)
            kb.tell("at", (held,), Position.round(tip.x, tip.y, 0.04), t=t, conf=0.6,
                    source="released", same=same_place())

    def still(self, t: float) -> bool:
        """The body was neither walking nor turning at time `t`."""
        return t >= self._moving_until

    def beak_tip(self, odom: tuple[float, float, float]) -> Position:
        x, y, yaw = odom
        a, l = self.body.reach_ahead + 0.01, self.body.reach_left
        return Position.round(x + a * math.cos(yaw) - l * math.sin(yaw),
                              y + a * math.sin(yaw) + l * math.cos(yaw), 0.03)

    # -- frames -----------------------------------------------------------------
    def _integrate(self, frame: Frame, now: float) -> None:
        pose = self._pose_at(frame.t)
        still = self.still(frame.t)
        view, placed = [], []
        for sighting in frame.sightings:
            seen = {"cls": sighting.cls, "bearing": round(sighting.bearing, 4),
                    "elevation": round(sighting.elevation, 4), "width": round(sighting.width, 4),
                    "conf": round(sighting.conf, 2)}
            view.append(seen)
            if sighting.cls == "toy" and self._held is not None and self._looks_held(sighting, frame):
                seen["as"] = f"held ({self._held})"
                continue
            located = self.locate(sighting, frame, pose, still)
            if located is None:
                seen["as"] = "not placed"
                continue
            placed.append((sighting, located, seen))
        matched: set[str] = set()
        assignment, self._gated = self._assign(placed, frame.t)
        for (sighting, located, seen), entity in zip(placed, assignment, strict=True):
            entity = entity or self.kb.new_entity(sighting.cls, frame.t)
            self._fuse(entity, located, frame.t, sighting)
            entity = self._merge_duplicates(entity, frame.t, matched)
            matched.add(entity)
            seen["as"] = entity
        same_frame = sorted(matched)
        self._distinct.update(frozenset((a, b)) for i, a in enumerate(same_frame) for b in same_frame[i + 1:])
        self._register_misses(frame, pose, matched | self._gated)
        self.last_view = {"t": round(frame.t, 3), "cam_yaw": round(frame.cam_yaw, 4),
                          "cam_pitch": round(frame.cam_pitch, 4), "sightings": view}

    def locate(self, s: Sighting, frame: Frame, pose: tuple[float, float, float],
               still: bool) -> Position | None:
        """Place a sighting on the floor in the odometry frame, with an error ellipse.

        The sighting's direction is a ray in the pitched camera frame; it is
        rotated into the body frame and intersected with the horizontal plane
        at the class's height. Range comes from that intersection, so its
        error grows as drop / sin^2(depression); bearing error is direct.
        """
        height = self.body.class_height.get(s.cls)
        if height is None:
            return None
        ce, se = math.cos(s.elevation), math.sin(s.elevation)
        fx, fy, fz = ce * math.cos(s.bearing), ce * math.sin(s.bearing), se     # camera frame
        cp, sp = math.cos(frame.cam_pitch), math.sin(frame.cam_pitch)
        bx, by, bz = fx * cp + fz * sp, fy, -fx * sp + fz * cp                  # body frame, pitched down
        drop = frame.cam_z - height
        if bz >= -0.02 or drop <= 0:
            return None                          # at or above the horizon of that plane
        travel = drop / -bz
        hx, hy = travel * bx, travel * by        # floor offset from the camera, body frame
        horizontal = math.hypot(hx, hy)
        if horizontal > 4.0:
            return None
        depression = math.asin(min(1.0, -bz))
        elevation_error = self.p.elevation_sigma_still if still else self.p.elevation_sigma_moving
        s_range = math.hypot(drop / max(math.sin(depression), 0.05) ** 2 * elevation_error,
                             0.02 * horizontal) + 0.01
        s_cross = horizontal * self.p.bearing_sigma + 0.01
        x, y, yaw = pose
        heading = yaw + frame.cam_yaw
        ch, sh = math.cos(heading), math.sin(heading)
        cx, cy = x + self.body.cam_ahead * math.cos(yaw), y + self.body.cam_ahead * math.sin(yaw)
        px, py = cx + hx * ch - hy * sh, cy + hx * sh + hy * ch
        a = math.atan2(py - cy, px - cx)
        c, n = math.cos(a), math.sin(a)
        vr, vc = s_range * s_range, s_cross * s_cross
        return Position(px, py, vr * c * c + vc * n * n, (vr - vc) * c * n, vr * n * n + vc * c * c)

    def _assign(self, placed: list, t: float) -> tuple[list[str | None], set[str]]:
        """One-to-one association of a frame's sightings with known entities.

        Every sighting-entity pair of the same class inside the gate is a
        candidate; pairs are taken best first (highest likelihood: Mahalanobis
        distance plus the log-determinant of the combined covariance), so no
        sighting can take an entity that another sighting fits better.
        A sighting left without an entity is a new object. Also returns every
        entity that some sighting fell inside the gate of: those were not missed,
        even if another entity took the sighting.
        """
        pairs = []
        still = self.still(t)
        penalty = 2.0 * math.log((1.0 - self.p.outlier_p) / self.p.outlier_p)
        for k, (sighting, located, _) in enumerate(placed):
            wide = located.scaled(self.p.outlier_scale)
            for entity in self.kb.of_class(sighting.cls):
                if entity == self._held:
                    continue
                known = self._predicted(entity, t)
                if known is None:
                    continue
                # Ranked by likelihood under a two-component error model: a vague phantom
                # cannot outbid a precise estimate that also fits, and a moving sighting
                # may be an outlier of a confident entity rather than a new object.
                costs = []
                if known.mahalanobis2(located, self.p.gate_floor) <= self.p.gate_chi2:
                    costs.append(known.association_cost(located, self.p.gate_floor))
                if not still and known.mahalanobis2(wide, self.p.gate_floor) <= self.p.gate_chi2:
                    costs.append(known.association_cost(wide, self.p.gate_floor) + penalty)
                if costs:
                    pairs.append((min(costs), k, entity))
        out: list[str | None] = [None] * len(placed)
        taken: set[str] = set()
        for _, k, entity in sorted(pairs):
            if out[k] is None and entity not in taken:
                out[k] = entity
                taken.add(entity)
        return out, {entity for _, _, entity in pairs}

    def _fuse(self, entity: str, m: Position, t: float, s: Sighting) -> None:
        kb = self.kb
        old = self._predicted(entity, t)
        current = kb.get("at", entity)
        if old is None:
            fused, conf = m, _prob(self.p.prior_logit + self._hit_logit(s.cls, m, t))
        else:
            # Robust update: a measurement far from a confident estimate is more likely
            # an outlier of the heavy-tailed sensor than a move, so it counts for less.
            # The less precise of the two is the likelier outlier: a noisy far sighting
            # should not drag a precise estimate, and a precise close sighting that
            # disagrees means the estimate was wrong.
            d2 = old.mahalanobis2(m, self.p.gate_floor)
            if d2 > self.p.robust_chi2:
                if m.sigma >= old.sigma:
                    m = m.scaled(d2 / self.p.robust_chi2)
                else:
                    old = old.scaled(d2 / self.p.robust_chi2)
            fused = old.fuse(m).floored(self.p.min_sigma)
            prior = _logit(current.conf) if current else self.p.prior_logit
            conf = self._clip(prior + self._hit_logit(s.cls, m, t))
        kb.tell("at", (entity,), fused, t=t, conf=conf, source="camera", same=same_place())
        if s.color:
            kb.tell("color", (entity,), s.color, t=t, source="camera")

    def _merge_duplicates(self, entity: str, t: float, seen_now: set[str]) -> str:
        """Two entities of one class whose estimates agree are one object seen twice.

        The survivor is the older entity (it carries the history); the newer
        one's position assertion closes with the reason recorded. Entities ever
        seen in the same frame are distinct objects and are never merged.
        """
        kb = self.kb
        mine = self._predicted(entity, t)
        cls = kb.cls(entity)
        if mine is None or cls is None:
            return entity
        for other in kb.of_class(cls):
            if other in (entity, self._held) or other in seen_now or frozenset((entity, other)) in self._distinct:
                continue
            theirs = self._predicted(other, t)
            if theirs is None or mine.mahalanobis2(theirs, self.p.gate_floor) > self.p.gate_chi2:
                continue
            keep, drop = sorted((entity, other), key=_entity_number)
            kept, dropped = kb.get("at", keep), kb.get("at", drop)
            fused = self._predicted(keep, t).fuse(self._predicted(drop, t))
            kb.untell("at", (drop,), t=t, reason=f"same object as {keep}")
            kb.tell("at", (keep,), fused, t=t, conf=max(kept.conf, dropped.conf),
                    source=f"merged {drop}", same=same_place())
            kb.tell("same_as", (drop,), keep, t=t, source="perception")
            # The survivor inherits what was known to be distinct from the merged entity.
            self._distinct.update(frozenset((keep, x)) for pair in list(self._distinct) if drop in pair
                                  for x in pair if x != drop)
            return keep
        return entity

    def _register_misses(self, frame: Frame, pose: tuple[float, float, float], matched: set[str]) -> None:
        kb = self.kb
        for assertion in list(kb.current("at")):
            entity = assertion.args[0]
            if entity == SELF or entity in matched or not self._should_see(entity, frame, pose):
                continue
            p_d = self.detection_rate(kb.cls(entity), self._range_to(entity, pose))
            miss = math.log(max(1.0 - p_d, 1e-3) / (1.0 - self.p.p_false))
            assertion.conf = self._clip(_logit(assertion.conf) + miss)

    def _should_see(self, entity: str, frame: Frame, pose: tuple[float, float, float]) -> bool:
        """Would the camera have seen this entity, if it were where we believe?"""
        kb = self.kb
        cls, where = kb.cls(entity), kb.position(entity)
        if cls not in self.body.class_height or where is None or where.sigma > 0.15:
            return False                         # not something the camera can see (e.g. a place)
        if cls == "toy" and self._inside_basket(where):
            return False                       # the rim hides toys in the basket
        x, y, yaw = pose
        cx, cy = x + self.body.cam_ahead * math.cos(yaw), y + self.body.cam_ahead * math.sin(yaw)
        horizontal = math.hypot(where.x - cx, where.y - cy)
        radius = 0.02 if cls == "toy" else self.body.class_half_width.get(cls, 0.1)
        if horizontal < 0.08 or 2 * math.atan2(radius, horizontal) < self.p.min_width:
            return False
        bearing = _wrap(math.atan2(where.y - cy, where.x - cx) - yaw - frame.cam_yaw)
        if abs(bearing) > self.body.fov_h / 2 - self.p.fov_margin:
            return False
        depression = math.atan2(frame.cam_z - self.body.class_height.get(cls, 0.0), horizontal)
        return abs(depression - frame.cam_pitch) < self.body.fov_v / 2 - self.p.fov_margin

    def detection_rate(self, cls: str | None, rng: float) -> float:
        """Measured probability that the detector reports an object of `cls` at `rng` m."""
        table = dict(self.p.detection_rate).get(cls or "")
        if table is None:
            return self.p.default_detection_rate
        if rng <= table[0][0]:
            return table[0][1]
        for (r0, p0), (r1, p1) in itertools.pairwise(table):
            if rng <= r1:
                return p0 + (p1 - p0) * (rng - r0) / (r1 - r0)
        return table[-1][1]

    def _hit_logit(self, cls: str, m: Position, t: float) -> float:
        p_d = self.detection_rate(cls, self._range_to_point(m, self._pose_at(t)))
        return math.log(max(p_d, self.p.p_false) / self.p.p_false)    # a sighting never counts against

    def _range_to(self, entity: str, pose: tuple[float, float, float]) -> float:
        where = self.kb.position(entity)
        return math.inf if where is None else self._range_to_point(where, pose)

    @staticmethod
    def _range_to_point(p: Position, pose: tuple[float, float, float]) -> float:
        return math.hypot(p.x - pose[0], p.y - pose[1])

    def _clip(self, logit: float) -> float:
        return _prob(max(-self.p.logit_limit, min(self.p.logit_limit, logit)))

    def _inside_basket(self, where: Position) -> bool:
        half = self.body.class_half_width["basket"]
        for basket in self.kb.of_class("basket"):
            b = self.kb.position(basket)
            if b is not None and abs(where.x - b.x) < half and abs(where.y - b.y) < half:
                return True
        return False

    def _looks_held(self, s: Sighting, frame: Frame) -> bool:
        depression = frame.cam_pitch - s.elevation
        return depression > 0.5 and abs(s.bearing) < 0.6     # a toy right under the camera is in the beak

    def _predicted(self, entity: str, t: float) -> Position | None:
        assertion = self.kb.get("at", entity)
        if assertion is None or not isinstance(assertion.value, Position):
            return None
        drift = dict(self.p.drift_per_s).get(self.kb.cls(entity) or "", self.p.default_drift_per_s)
        return assertion.value.grown(drift * max(0.0, t - assertion.t_obs))

    def _pose_at(self, t: float) -> tuple[float, float, float]:
        """Odometry when a frame was captured, so motion since then does not misplace it."""
        best, best_dt = None, math.inf
        for ts, pose in self._odom:
            if abs(ts - t) < best_dt:
                best, best_dt = pose, abs(ts - t)
        return best if best is not None and best_dt <= 0.5 else self._odom[-1][1]


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _prob(logit: float) -> float:
    return 1.0 / (1.0 + math.exp(-logit))


def _entity_number(entity: str) -> int:
    return int(entity.rsplit("#", 1)[-1]) if "#" in entity else 0


def _wrap(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))
