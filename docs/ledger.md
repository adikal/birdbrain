# Research ledger

This is BirdBrain's lab notebook. Every experiment that informs the design is
written here, including the ones that fail. The design doc cites entries from
this file; code that exists because of an entry should cite it too.

## How to use it

Each experiment follows the same loop:

1. **Question.** What we do not know.
2. **Hypothesis and prediction.** What we expect, stated so a number can refute it.
3. **Method.** Command, seed or seeds, commit, and anything else needed to rerun it.
4. **Result.** The numbers, and what the event log and contact sheet show.
5. **Analysis.** What the result means, and how far it generalizes.
6. **Decision.** What changes in the design, the code, or the next experiment.

Write the hypothesis and prediction before running. Single runs are labeled
as such; claims that compare agents need several seeds and a reported spread.
Distill anything durable into **Lessons**, and keep **Open hypotheses**
ordered by what to test next.

Entry ids: `E-###` experiments, `H-###` hypotheses, `L-###` lessons.

## Lessons

- **L-001. Score outcomes from true state.** The prototype scored 78.8/100 on
  a run where the duck had fallen on its face, because the score counted
  cognitive cycles and confidence. Evaluation measures what happened in the
  world. (E-001)
- **L-002. Validate the body before the mind.** Every decision in the
  prototype was a reaction to a body that could not stand. Check that the
  body does what a skill assumes before interpreting any cognitive result.
  (E-001)
- **L-003. Reuse the body; build the mind.** A hand-built duck took hours to
  stand and could not turn. Pollen's model and policies, run in Microduck
  Lab, walk, turn, and pick up toys today. BirdBrain does not do locomotion
  research. (E-002, E-003)
- **L-004. Commands have dead bands.** The shipped walker ignores forward
  commands below about 0.2 m/s and, from standstill, turn commands below
  about 1.0 rad/s. Read `walker-facts` before choosing a skill's command
  values. (E-005)
- **L-005. Probe against truth before tuning.** Logging the true beak-to-toy
  distance of every grasp showed the failures were bimodal: good picks land
  within 1 cm, failed ones 0.2 to 1.4 m from any toy. The failures were
  stale or duplicate beliefs, not control error, which no amount of tuning
  the approach would have fixed. (E-008)
- **L-006. Successive sightings share their errors.** Fusing every camera
  frame as an independent measurement made estimates overconfident and
  split one object into several entities. A floor on the fused uncertainty,
  an anisotropic error model (range error far larger than bearing error),
  and merging entities whose estimates agree fixed most of it. (E-008)
- **L-007. An action can refute a belief.** When a pick closes on nothing,
  the toy is not where the duck believed. Lowering that belief's confidence
  (`doubt`) stopped the duck from walking back to the same empty spot. (E-008)
- **L-008. Waiting for the cloud costs real time.** With the world running
  during each 2 s cloud call, the duck stood still for about 15% of a run and
  tidied one toy fewer in both seeds tried. Thinking has to overlap acting
  before hardware. (E-010)
- **L-009. Check the provider's API surface for each model.** Sonnet 5.5 on
  Bedrock rejects a forced tool choice and the `temperature` parameter;
  both failed only at call time. (E-009)
- **L-010. Fix identity before tuning behavior.** A one-to-one assignment
  per frame, never merging objects seen together, and a reach gate on
  grasps cut entity churn fifteenfold (E-011). Each rule replaced a greedy
  shortcut that was locally reasonable and globally wrong.
- **L-011. A fix that does not move the target metric is reverted.** The
  precision rule of E-012 sounded right and was rejected on the numbers.
- **L-012. Each scorecard term must be the difference the goal makes.**
  Rest was credited with relieving the safety need, but that need fades
  whatever the duck does, so after one fall the duck rested for most of a
  run. Uncertainty was credited to tidy goals, but tidying does not set out
  to test beliefs, so it sent the duck to its least certain toys first.
  (E-014)
- **L-013. Small counts need a prior.** One fall in one trial read as a
  33% fall rate and stopped all tidying. A prior from the base rate, worth
  10 trials, fixed it. (E-014)
- **L-014. Held-out seeds that informed a fix are spent.** E-014 round 1
  failed on held-out seeds; the fixes it prompted were judged on fresh
  seeds. (E-014)
- **L-015. A need can smuggle in the answer.** Entering the owner's
  preference as a tidiness need made "tidies with no task" true by
  construction. A need should name what the creature wants (approval),
  not the state of the world that satisfies it. (E-014, E-015)
- **L-016. Exploration must be able to fade.** An uncertainty bonus kept
  the duck experimenting with nobody there, and it fell picking toys it had
  put by walls. Thompson sampling explores in proportion to how thin the
  evidence is. It does not stop altogether: with nobody there the control
  still makes about 5 picks an episode after 10 rooms, because the best of
  several thinly known ways of putting a toy down always looks a little
  good. The draws must last the whole pick and put, or the
  plan contradicts itself. (E-015)
- **L-017. Credit needs hindsight.** Splitting each reaction once, by what
  the duck believed then, left coincident actions with lasting credit.
  Re-explaining the whole history (EM) on each new reaction explains them
  away. (E-015)
- **L-018. Measure the mechanism before fixing it.** The churn by the wall
  was attributed to credit timing; a truth measure of credit showed the
  timing was already right, and a probe of individual picks found the real
  causes. (E-016)
- **L-019. Few data favour shared effects over splits.** A rule tree must
  divide a short life's outcomes to find a condition; an additive model
  uses all of them for every condition. (E-017)
- **L-020. Better predictions are not better choices.** Rules that
  predicted better made worse choices when the duck chose by their means.
  The optimizer's curse is the likely reason (H-018). (E-017)
- **L-021. Exploration has a price, and the body pays it.** Thompson
  sampling over a wide posterior sent the duck to the riskiest picks. Where
  failure is costly, explore the outcome you want and be pessimistic about
  the one you fear. (E-018)
- **L-022. Ask the author about a measured failure.** Shown the program, the
  condition, the rates, and how the tries ended, the cloud brain wrote
  targeted fixes. The rules of Milestone 4 earned their keep here, by
  pointing at what to fix. (E-019)
- **L-023. A choice made because something looked bad is biased.** The
  situations chosen for authoring were the parent's worst, so the parent's
  own counts there understate it. Compare against fresh outcomes. (E-019)
- **L-024. A measure keyed by a name must follow what runs in its place.**
  Written variants of `pick` ran under their own names, so the failed-pick
  measure, the give-up rule and a rule feature all missed them, and an
  artifact read as a third of a pick saved per room. (E-019 review)
- **L-025. Judge a skill by what the room rewards.** A written delivery
  succeeded more often and took longer, won its trials, and cost the
  room a tenth of a toy where time was short. A trial's score should be
  the same currency as the goal. (E-020)
- **L-026. A measured parameter holds where it was measured.** The basket's
  detection rate (0.96) was measured in a room where it was never more
  than 2 m away. In a larger room the same number made the duck stop
  believing in a basket it was walking toward. Re-measure the body's
  parameters when the world changes, before blaming the mind. (E-022)
- **L-027. Let a strong effect be strong.** A normal prior on each
  condition's effect, right for the many weak ones, held a fall rate of 70%
  to a prediction of 22%, and the duck kept doing what it knew made it
  fall. A heavy-tailed prior shrinks weak effects as much and strong ones
  far less. (E-026)

- **L-028. Gains shrink on the way out.** A change is kept because its
  development lives looked good, so its development gain is biased up;
  then the held-out lives it is checked on are used again and again. E-033
  went from +3.3 points in development to +1.0 held out; the second round
  from +5.6 on lives 400 to 415 to +3.0 on fresh ones (E-032). Quote the
  fresh number. (E-032, E-033)

- **L-029. A correction is a hypothesis too.** A reviewer found real
  defects in the map (a doorway the planner could close, low boxes that hid
  what the camera saw over). Fixed together, the duck did worse, held out
  and in development, and the fixes were reverted. A defect's cost is
  measured, not assumed; fix one, test it, keep it if it helps. (E-034,
  E-035)

## Known defects

Found by review, in the code, each pinned by a strict expected-failure test
(`tests/test_world2_mind.py`, `tests/test_occupancy.py`) unless noted. Fixing
them together did worse (E-034, E-035); each needs its own experiment.

- *The planner can close a 0.6 m doorway*: obstacles are grown by 2 cells
  (0.2 m) for a 0.15 m half-width.
- *The frontier has no exemption round the duck*: beside a wall, exploring
  falls back to wandering.
- *A rule about the situation defers every toy*: a credible condition such
  as "basket unknown", the same for every toy, makes them all poor
  prospects at once; the ledger (E-029) means conditions of the toy.
- *Routing drops the basket's detour*, whose low rim is not on the map.
- *Map occlusion ignores height*: a low box hides what the camera sees
  over it.
- *The Cauchy fit stops at a saddle point* (H-024).
- Not pinned by a test: cells within 0.25 m of the camera are skipped when
  judging what it can see; a range return is placed on the zone's centre
  ray, a quarter of a zone above the sub-rays that report it, so low edges
  read about 2 cm high; the map uses the last camera frame's head pose
  and keeps mapping during reflexes; the imagined delivery in judging a
  pick bins the basket distance from where the duck stands, not from the
  toy; apparent width is computed with three range conventions
  (`_appearance`, `detection_rate`, the probe).
- Tuned to this world: the map's 7 cm floor sits above the 6 cm basket rim;
  the rules' size bins fall between World 2's shapes; the frontier search
  stops after about 40 m².

## Open hypotheses

Ordered by what to test next. Resolved ones keep their verdict.

- **H-001** (Milestone 1) **Supported.** BirdBrain's primitives and
  hand-written compound skills, reading only the robot's senses, tidy as
  well as the lab's `tidy` brain on held-out seeds (E-008).
- **H-002 Supported for the lab brain.** Delivery misses limit its rate: 15
  of its 179 deliveries over 32 seeds left the toy outside the basket
  (E-007, E-008). BirdBrain's deliveries landed in nearly every case.
- **H-006** (Milestone 5) **Supported.** The cloud brain wrote 27 skills
  in the bounded language for situations the duck had measured as failing.
  All of them checked. In those situations they raised success by 8 to 10
  points against the same rooms with the original skills, with no more
  falls. The duck kept 15 and retired 1 on its own evidence (E-019).
  With fair trials and on fresh lives, success there rose 7.5 points per
  life with a task and 10 with the basket owner, with no more falls; the
  duck kept 6 of 44 and retired 3 (E-020).
- **H-023** (World 2) **Supported in part, for another reason** (E-027).
  The duck was idle because the scorecard counted failure twice: her
  reaction to a kind of action is learned per attempt, and was multiplied
  by the chance of success again. Counted once, approvals rose 4-fold and
  her measure +0.26. As first stated: with an owner in a large room the duck mostly looks,
  explores and rests, because the curiosity term of the scorecard outbids
  the small, uncertain value of pleasing her. Exploration valued by what it
  finds (objects confirmed per second, measured), in place of a fixed
  bonus for uncertainty, raises her measure. *Test:* her measure, World 2
  held-out lives.
- **H-025** (perception). Misses of one object from one viewpoint are not
  independent, so a calibrated per-frame detection rate overcounts the
  evidence of absence; counting misses once per change of viewpoint (or
  per second) with the calibrated rate does better than E-028's
  accidentally low rate. *Test:* the playroom and World 2, toys forgotten
  and tidying.
- **H-024** (rules). The Cauchy prior's fit stops at the symmetric split of
  an effect between a feature's collinear indicators, a saddle point
  (E-034 review). Reference coding, with the Laplace covariance from the
  exact Hessian at the mode, gives strong effects their full size and an
  honest sd. *Test:* offline replay Brier scores (`rules_replay.py`), then
  deferral and falls in World 2.
- **H-022** (World 2) **Supported in part.** With a heavy-tailed prior on
  each condition's effect the duck believed the strong ones: falls holding
  heavy objects −0.16 a room, heavy grasps −0.19 per object (E-026). As
  first stated: the duck avoids heavy objects only weakly, because
  its rules add one effect per condition and a heavy kind shares its colour
  or size with kinds that are fine. A condition for colour and size
  together, or memory per object, makes heavy objects poor prospects.
  *Test:* falls while holding a heavy object, World 2 held-out lives.
- **H-021** (authoring). Scoring a written skill's trial by successes per
  second, where the room is short of time, removes E-020's whole-room cost
  without losing the gain in its situation. *Test:* the task setting of
  E-020, toys in the basket, rooms 11 to 20, paired by life.
- **H-007** (Milestone 4) **Early data.** The language model's stated
  probabilities beat counted outcomes for actions with little history
  (Brier 0.167 against 0.206 with fewer than 3 prior trials) and the two
  converge by 10 trials (0.224 against 0.233, n = 27). Whether counts win
  later needs runs whose memory persists across episodes (E-010).
- **H-010 Refuted for the playroom task.** Speculative decisions were used
  78% of the time but added one decision per run and no toys, at 1.35
  times the tokens (E-013). Revisit on hardware.
- **H-012 Partly supported.** Range-aware existence confidence cut failed
  pick decisions from 48% to 36% (E-013); the rest are unexplained.
- **H-013 Supported.** Likelihood association with a second wide error
  component left one confident basket in 14 of 16 runs, up from 11 (E-013).
- **H-011** (open). BirdBrain falls more often than the lab brain (0.50
  against 0.38 per run on held-out seeds after E-013, p = 0.81) because of the
  sidestep in `back_off` and standing near the rim. *Test:* attribute every
  fall to its skill step over 32 seeds, then change only that step.
- **H-003** (Milestone 3) **Supported, narrowly.** Given tidiness as a
  need, the needs scorecard arbitrates well: with no task the duck tidied
  5.25 toys, the same as the task-driven policy on fresh seeds; in a tidy
  room it rested, looked around or explored for 98% of the run and took no
  toy out of the basket; the cloud brain tidied 5.12 to 5.38 toys (E-014).
  It does not show that tidying arises from anything more general, because
  the preference was entered as the need (L-015). H-015 tests that.
- **H-015** (Milestone 3b) **Supported, with the basket effect smaller
  than predicted.** From phrases that carry only approval or disapproval,
  the duck learned each of three hidden owner preferences (its beliefs
  single out the right kind of action in 43 of 48 lives in round 2). Each
  owner arm's own measure beat both other owner arms, and without an owner
  it did not tidy. With the approval need acting as a need (round 2), the
  results over the control were: wall +2.9, leave-it +1.35, basket +1.8.
  The basket result missed its pre-registered thresholds in both rounds
  (E-015).
- **H-016 Refuted.** Crediting actions under way already gave 79% of the
  credit to the true cause in the wall arm; crediting the duck's own changes
  gave 80%. The duck loses toys she likes because its category "by a wall"
  is coarser than hers, and because some positions are wrong (E-016).
- **H-019** (Milestone 4) **Supported for expected effects.** Rules over
  conditions predict whether a skill's expected effect holds better than
  counts per skill or per kind, on outcomes they had not seen. For falls
  they are worse than counts per kind (E-017).
- **H-018 Refuted in development.** Posterior draws from the rules made
  the duck explore rim picks, which fall; falls rose in every arm (E-018).
- **H-020 Refuted in development.** Judging falls by an upper credible
  bound paralysed the duck early in life (E-018).
- **H-017 Refuted in development** (E-018): over conditions, the owner
  model learned the leave-it owner's dislike of picks more slowly.
- **H-017, as first stated.** Learning the conditions of the owner's reactions with
  the rules of E-017, in place of hand-chosen kinds of action, reduces toys
  lost to picks. *Test:* lost-by-pick and own measure, paired by life.
- **H-004** (Milestone 4). Beliefs with evidence predict the outcome of actions
  on unfamiliar objects better than retrieval of similar past episodes.
- **H-008** (Milestone 4). Without a confirmation step, missed or stale
  detections produce a large share of measured surprises and pull curiosity
  toward sensor noise.
- **H-009** (Milestone 4). The language model's priors reduce the number of
  trials needed to reach a reliable rule for an unfamiliar object.
- **H-005** (Milestone 6). Choosing experiments by expected learning progress
  gains more competence per episode than choosing by novelty.

## Experiments

### E-035 · 2026-11-07 · The review fixes, reconsidered (development, reverted)

**Question.** E-034's bundle did worse with the task. Which part?

**Development** (lives 0 to 7, against E-033's development lives):
- (a) Mapping while the head is steady (its last two camera poses agree)
  instead of within 50 ms of a camera frame: the map holds 119 to 164
  occupied cells in three rooms (99% to 100% precise). Task tidying +0.002
  [−0.041, +0.045]; owner −0.35 [−1.01, +0.31]; falls +0.21.
- (b) Mapping with the latest camera pose, as in E-033, keeping every other
  fix: 132 to 213 cells (98% to 100% precise). Task −0.044 [−0.113,
  +0.024]; owner −0.34 [−0.83, +0.16].

**Analysis.** No version of the review's fixes did better than E-033's
code on the measures that matter, in development or held out (E-034). Some
were corrections of real defects (the doorway can close in the planner;
low boxes hide what the camera sees over; the basket's rim is not avoided
while routing), and correcting them still did not help: the defects may
cost less than the changes that removed them, or interact (opening the
doorway sends the duck through it more, where it falls and loses the
basket; height-aware occlusion lets more misses count, as in H-025).

**Decision.** Revert the mind to E-033's code, and keep the defects as
strict expected-failure tests, each failing on its own assertion. The
defects stay open (listed under *Known defects*): each fix needs its own
experiment, one at a time.

**Cleanup after the final review** (`semantic-review/2026-11-07-230647-pr-local.md`;
no change to behaviour: six fingerprint rooms, World 2 with and without the
owner and the playroom, reproduce exactly). The probe, which still called
a reverted method, now applies the mind's actual visibility test (range
sensor, then the map) to objects and to the basket. The superseded
`detection_by_range.py` is gone. The playroom's toy table by range, never
read since E-028, is gone. The range sensor's geometry and the duck's
half-width live once, in `BodyProfile`; the two bare 0.15 m spares are
named; classes of varied size are those with a width table, not "toy" by
name. Mind modules may not import the owner. Tests now cover reconsidering
(the credible stop, no stop after the reflex, the owner's colour stop),
stopped actions in both owner models, E-027's value, appearance, the
Cauchy prior's direction, and World 2's measures.

### E-034 · 2026-11-07 · Review of the second round (pre-registered)

**Review** (`semantic-review/2026-11-07-201521-pr-local.md`, a clean-context
reading of `4e28859..HEAD`). No truth reaches the mind. Findings, checked:
- *The doorway was closed for planning* (confirmed). Obstacles were grown by
  2 cells (0.2 m) for a 0.15 m half-width, leaving a 0.6 m doorway one free
  cell or none, so routes and the frontier could not pass it. Now grown by
  1.5 cells; a test puts a doorway between two walls at four grid offsets.
- *Routing dropped the basket detour* (confirmed). The basket's 6 cm rim is
  not mapped, and `walk_toward` used the waypoint instead of the detour.
  The detour now applies on the way to the waypoint.
- *Phantom obstacles* (likely). A return was placed on the zone's centre
  ray, a quarter of a zone above the sub-rays that report it, so a 6 cm rim
  read as 7.4 to 8.3 cm; and the head pose came from the last camera frame,
  up to 130 ms old. Returns are now placed on the lower sub-row, mapping
  uses a camera frame within 50 ms, and nothing is mapped during a reflex.
  Precision against true obstacles in three rooms: 100% (was 97% to 99%).
- *Map occlusion ignored height* (likely). Any mapped cell hid what lay
  behind it, low boxes and the basket's own rim included. Each cell now
  keeps the top of what was hit, and hides an object only if it stands
  above the line of sight there; the object's own footprint plus a cell is
  not in its way.
- *Waypoints could be overshot* between re-plans; re-planning now also
  happens when one is reached or falls behind.
- *The object detection table was measured with hidden objects counted as
  misses* (likely), and with a different range than the mind uses.
  Re-measured with a true ray cast and the mind's range: 0.12 at 1 to 1.5
  degrees, 0.47 at 2 to 2.5, 0.83 at 3 to 3.5, 0.96 from 3.5.
- *The Cauchy fit stops at a saddle point* (confirmed). A feature's centred
  indicator columns are collinear; under the Cauchy prior the symmetric
  split of an effect between them is a saddle, not the mode, so strong
  effects are shrunk more than intended and their sd understated (in the
  reviewer's example, contrast −2.80 with sd 0.94 against −3.87 with sd 1.76
  at the mode). E-026 measured the learner as it is. Fixing it (reference
  coding, exact Hessian) changes which rules are credible, so it is left as
  its own experiment (H-024).

**Development** (lives 0 to 7, against E-033's development lives; the
playroom against E-031's, since E-033 left it unchanged).
- With every fix: possible objects −0.044 [−0.081, −0.006] (6 of 8 lives
  lower), the playroom −0.23 [−0.42, −0.03].
- With every fix but the re-measured detection table (E-028's kept):
  possible objects +0.007 [−0.053, +0.066], the playroom −0.05 [−0.15,
  +0.05]. The drop came from the table.
- The table measured with true line of sight, and again under the mind's
  own visibility test (0.11 at 1 to 1.5 degrees, 0.44 at 2 to 2.5, 0.79 at
  3 to 3.5, 0.93 from 3.5), is higher at small widths than E-028's, which
  counted hidden objects as misses. The more accurate rate did worse. A
  likely reason: the miss model treats frames as independent, and misses
  of one object from one viewpoint are not, so a calibrated per-frame rate
  counts the same evidence many times; E-028's lower rate discounted it by
  accident (H-025). E-028's table is kept until that is tested.

**Predictions** (lives 400 to 415, rooms 11 to 20, against E-033's arms; the
fixes with E-028's table, commit `b4e234b`):
1. Task: possible objects in the basket, CI lower bound above −0.03.
2. Task: deliveries across the inner wall end `done` at least 42% of the
   time, pooled (E-033: 42%).
3. Owner: her measure gained a room, CI lower bound above −0.3.
4. Playroom toys in the basket: CI lower bound above −0.15.

**Result** (tags `e034-task`, `e034-hers`, `e034-playroom`; `report_task.txt`,
`report_hers.txt`).

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | task: possible objects in the basket | −0.019 [−0.050, +0.013], 8 of 16 lives lower | missed |
| 2 | task: deliveries across the inner wall `done` | 36% (E-033: 42%) | missed |
| 3 | owner: her measure gained a room | +0.19 [−0.08, +0.47], 13 of 16 higher | met |
| 4 | playroom toys in the basket | +0.006 [−0.039, +0.052] | met |

**Diagnosis.** Requiring a camera frame within 50 ms of each range frame
left about half the range frames unmapped: in three rooms the map held 78,
183 and 100 occupied cells against E-033's 162, 232 and 168 (all within
0.2 m of a true obstacle, against 98%). A sparser map routes less well.

**Decision.** Keep the fixes that are corrections (the doorway, the basket
detour, height-aware occlusion, re-planning at waypoints); replace the
freshness rule by one that keeps more of the map (E-035).

### E-033 · 2026-11-07 · Searching for the basket where it has not looked (pre-registered)

**Question.** On E-032's fresh lives, deliveries with the inner wall
between the duck and the basket ended `done` 34% of the time, and 40% lost
the basket: 21 of 119 failed deliver's own search ("not known(basket)
after 4 iterations"). The search walked for 6 s in whatever direction the
duck faced, then looked around.

**Change** (`library/deliver.json`). The search walks to the frontier, as
exploring does (E-031).

**Development** (lives 0 to 7, against E-031's development lives).
Possible objects tidied +0.033 [+0.002, +0.065], 6 of 8 lives higher.
Deliveries across the inner wall `done` 22% against 15%, basket lost 31%
against 37%. With the owner: her measure +0.13 [−0.13, +0.38], falls
−0.13.

**Predictions** (lives 400 to 415, rooms 11 to 20, against E-031's arms):
1. Task: possible objects in the basket, CI lower bound above −0.01.
2. Owner: her measure gained a room, CI lower bound above −0.2.
3. Playroom toys in the basket: CI lower bound above −0.1.

**Result** (tags `e033-task`, `e033-hers`, `e033-playroom`; `report_task.txt`,
`report_hers.txt`).

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | task: possible objects in the basket | +0.010 [−0.006, +0.027] | met |
| 2 | owner: her measure gained a room | −0.02 [−0.17, +0.13] | met |
| 3 | playroom toys in the basket | identical | met |

Deliveries across the inner wall: `done` 42% against 36%, basket lost 23%
against 36% (95 and 107 deliveries). Falls unchanged.

**Analysis.** The search now finds the basket behind the inner wall more
often, as intended; the room's total moved by a point, within noise,
because such deliveries are a tenth of all. The development gain (+3.3)
did not hold at that size.

**Decision.** Keep it: the same frontier walk now serves exploring and
searching, so there is one way of looking for something, and nothing
measured got worse.

### E-032 · 2026-11-07 · The second round on fresh lives (pre-registered)

**Question.** E-026 to E-031 were each checked on lives 400 to 415. Do the
six kept changes, together, hold on lives that informed nothing?

**Arms.** E-025's mind (commit `4e28859`, from a worktree; the world code
is the same) against the current mind, on lives 500 to 515 (rooms 50001 to
51520): World 2 with the task, World 2 with the owner, and the playroom.
On lives 400 to 415 the cumulative differences, against the baseline of
`../E-026-baseline/`, were: possible objects +0.056, wide objects grasped
−0.34 per object (new wide kinds −0.56), falls −0.18; her measure +0.36,
falls with her +0.25; playroom toys +0.31.

**Predictions** (rooms 11 to 20, paired by life):
1. Task: possible objects in the basket, CI lower bound above 0.
2. Task: wide objects of new kinds grasped per object, CI upper bound below
   −0.2.
3. Task: falls, CI upper bound below +0.15.
4. Owner: her measure gained a room, CI lower bound above −0.1.
5. Owner: falls, reported with no prediction.
6. Playroom: toys in the basket, CI lower bound above 0.

**Method.** The new mind at the pre-registration commit (later commits
changed only documentation), `4e28859` from a worktree for the
old. Six arms of 16 lives × 20 rooms. Reports: `report_task.txt`,
`report_hers.txt`.

**Result.**

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | task: possible objects in the basket | 0.41 against 0.38: +0.030 [−0.018, +0.078], 12 of 16 lives higher | missed |
| 2 | task: new wide kinds grasped per object | −0.20 [−0.40, −0.01] | missed (bound −0.2) |
| 3 | task: falls a room | 0.83 against 1.11: −0.28 [−0.55, −0.00] | met |
| 4 | owner: her measure gained a room | +0.27 against −0.13: +0.40 [+0.22, +0.59], 13 of 16 higher | met |
| 5 | owner: falls a room | 0.51 against 0.31: +0.20 [+0.01, +0.40] | reported |
| 6 | playroom toys in the basket | 5.56 against 5.26: +0.29 [+0.21, +0.38], 16 of 16 higher | met |

- *Task, in detail.* Plain objects +0.072 [+0.003, +0.140]; objects of
  kinds never met +0.099 [+0.044, +0.154]; heavy objects grasped −0.27 per
  object (new heavy kind −0.22), falls holding one −0.27; wide −0.16;
  objects never found −0.039.
- *Owner.* Possible objects put away 0.085 against 0.011; objects never
  found 33% against 46%; her blue things moved +0.045 [−0.016, +0.106].

**Analysis.** On lives that informed nothing, the second round made the
duck fall a quarter less with the task, avoid what it has learned it
cannot carry, carry that to kinds it never met, and work for its owner,
whose measure went from slightly negative to clearly positive. The
playroom gained more than at any time since Milestone 1, in every life.
The gain in tidying with the task (+3 points) is smaller than on lives 400
to 415 (+5.6) and its interval includes zero: the size of that gain was
overstated by the lives the changes were tuned on. With the owner the duck
falls more, because it now does things.

**Decision.** The second round stands as a whole. Next: deliveries across
the inner wall (33% `done`), falls at the basket rim, and falls with the
owner.

### E-031 · 2026-11-07 · Exploring where it has not looked (pre-registered)

**Question.** After E-030, 28% of objects in a task room and 40% with the
owner are never found, most of them in parts of the room the duck never
came within a metre of (E-028: 297 of 531 unfound objects). Exploring was
a walk in a straight line, turning away from obstacles, then a look
around: it goes wherever the duck happens to face.

**Change** (`occupancy.py`, `skills.py`, `library/explore.json`).
Exploring walks to the nearest *frontier*: a cell of floor the map has seen
free, at least 0.8 m away by a free path, next to a cell never seen
(breadth-first through free cells round grown obstacles), using the same
routed walk as everything else (E-030). It wanders as before when there is
no frontier.

**Development** (lives 0 to 7, against E-030's development lives). With
the owner, who leaves the duck time to explore: objects never found −0.09
[−0.19, +0.00], possible objects put away +0.057 [−0.019, +0.133], her
measure +0.30 [−0.15, +0.75] (6 of 8 higher), falls +0.24 [−0.15,
+0.62]. With the task: never found −0.03, tidying −0.003 [−0.021,
+0.015]. The playroom: −0.012 [−0.04, +0.02].

**Predictions** (lives 400 to 415, rooms 11 to 20, against E-030's arms):
1. With the owner, objects never found: CI upper bound below 0.
2. With the owner, her measure gained a room: CI lower bound above −0.2.
3. With the task, possible objects in the basket: CI lower bound above −0.03.
4. Playroom toys in the basket: CI lower bound above −0.1.

**Method.** Commit `e6148a7` (`e031-hers`, `e031-task`,
`e031-playroom`, lives 400 to 415) against E-030's arms (`report_hers.txt`,
`report_task.txt`).

**Result.**

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | owner: objects never found | 33% against 40%: −0.069 [−0.112, −0.025], 12 of 16 lower | met |
| 2 | owner: her measure gained a room | +0.000 [−0.35, +0.35] | missed |
| 3 | task: possible objects in the basket | +0.003 [−0.022, +0.029] | met |
| 4 | playroom toys in the basket | identical | met |

With the task, objects never found −0.018 [−0.047, +0.011]. The playroom
was identical: there the frontier is reached in the first room's first
minutes, and exploring after that is as before.

**Analysis.** The duck now finds more of what is there, and with the owner
markedly so. Finding is not putting away: her measure did not move, so
what limits it is what the duck does with what it finds.

**Decision.** Keep it: it is a more general way to explore, it costs
nothing measured, and it is what the next owner experiment builds on.

### E-030 · 2026-11-07 · A map of what is in the way (pre-registered)

**Question.** Deliveries fail when something stands between the duck and
the basket. In E-028's held-out lives, with a clear line 76% of
deliveries ended `done`; with furniture between, 29%; with the inner wall
between, 8%, most with the basket lost. And 31% of objects were never
found, most behind the inner wall. The duck walks straight at its target,
turns away when the range sensor shows something close, and keeps no
memory of what it has seen in the way.

**Change** (`occupancy.py`, `perception.py`, `skills.py`).
- *The map.* Each range-sensor frame is folded into a grid of 10 cm cells
  in the odometry frame: the cells a zone's ray crosses are free, and where
  it ends, if it ends 7 to 50 cm above the floor, something stands
  (log-odds, bounded). The floor, toys and the basket's 6 cm rim stay
  below. Measured against the true walls and furniture in three rooms,
  97% to 99% of the cells it calls occupied lie within 0.2 m of one.
- *Walking.* `walk_toward` re-plans twice a second: if the straight line to
  its target crosses mapped obstacles (grown by the duck's half-width), it
  heads for the furthest point of a shortest way round (A* over the grid,
  unseen cells taken as free) that it can walk to in a straight line.
- *Seeing.* A frame without an object that the map shows behind a wall or
  furniture is no evidence against it, as for the range sensor's own view
  (E-022), now beyond its narrow field.

**Development** (lives 0 to 7, against E-029's development lives).
Possible objects tidied +0.030 [+0.005, +0.054], 7 of 8 higher; plain
objects +0.050. Deliveries with furniture between ended `done` 59% of the
time (E-029: 19%), with the inner wall between 19% (13%); falls −0.09
[−0.55, +0.37]. Routing alone (without the change to seeing) gave
+0.035 [−0.002, +0.073]. The playroom: +0.075 [−0.012, +0.162]. With the
owner, against E-027's development lives (which lack E-028 and E-029):
her measure −0.08 [−0.47, +0.32], falls −0.16.

**Predictions** (lives 400 to 415, rooms 11 to 20, paired by life, against
E-029's mind on the same lives; for the owner, E-029's mind run from a
worktree, `owner_ctl.jsonl`):
1. Possible objects in the basket: CI lower bound above 0.
2. Deliveries with furniture between the duck and the basket end `done` at
   least 40% of the time, pooled (E-028: 29%).
3. Playroom toys in the basket: CI lower bound above −0.1.
4. With the owner, her measure gained a room: CI lower bound above −0.3.

**Method.** Commit `31b691e`. Tags `e030-task`, `e030-playroom`,
`e030-hers`, and `e030-owner-ctl` (E-029's mind from a worktree), lives
400 to 415. Reports: `report_task.txt`, `report_hers.txt`.

**Result.**

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | possible objects in the basket | 0.45 against 0.40: +0.054 [+0.023, +0.085], 14 of 16 lives higher | met |
| 2 | deliveries with furniture between, ending `done` | 54% (E-029 on the same lives: 30%) | met |
| 3 | playroom toys in the basket | −0.006 [−0.056, +0.043] | met |
| 4 | her measure gained a room | +0.000 [−0.20, +0.20] | met |

With the inner wall between, deliveries ended `done` 33% of the time
(E-029: 9%). Objects never found fell from 32% to 28% (−0.041 [−0.080,
−0.002]). Falls +0.14 [−0.09, +0.37].

**Analysis.** A memory of what is in the way, from a sensor the robot
already has, let the duck walk round furniture and through the doorway.
Tidying in World 2 rose by 5 points, the largest single gain since E-022.
The owner's measure did not change: with her, the duck carries less.

**Decision.** Keep it.

### E-029 · 2026-11-07 · Credible evidence, no bar (pre-registered)

**Question.** A toy is deferred when a credible rule speaks against it *and*
its predicted chance of working is below 0.1 (E-023). Wide objects
predicted at 0.2 (observed 0.07) sat just above the bar, and in E-026's
lives 26% of picks were still of wide objects. Is the bar needed?

**Change** (`mind.py`). A toy is a poor prospect when a credible condition
of it lowers the chance a pick or its delivery works, or raises the chance
of a fall. The bar (`NOT_WORTH = 0.1`) is removed. Deferral is unchanged:
nearest first among the rest, a poor prospect once nothing better is known.

**Development** (lives 0 to 7, against E-028's development lives).
Possible objects tidied +0.016 [−0.003, +0.034] (3 lives higher, 5 equal,
0 lower), falls holding heavy objects −0.075 [−0.134, −0.016], heavy
grasped −0.07, wide unchanged; the playroom's toys identical.

**Predictions** (lives 400 to 415, rooms 11 to 20, against E-028's arms):
1. Possible objects in the basket: CI lower bound above −0.02.
2. Falls while holding a heavy object: CI upper bound below +0.05.
3. Playroom toys in the basket: CI lower bound above −0.1.

**Method.** Commit `7583ba6`. Tags `e029-task`, `e029-playroom` on lives
400 to 415, against E-028's arms (`report.txt`).

**Result.**

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | possible objects in the basket | +0.001 [−0.009, +0.011] | met |
| 2 | falls while holding a heavy object | −0.05 [−0.13, +0.03] | met |
| 3 | playroom toys in the basket | +0.000 [−0.02, +0.02] (14 of 16 identical) | met |

Falls a room fell: 0.76 against 0.91, −0.15 [−0.29, −0.01], 8 of 16 lower.

**Decision.** Keep it: the rule is simpler (one constant fewer), the
duck falls less, and nothing else moved.

### E-028 · 2026-11-07 · Small things are hard to see (pre-registered)

**Question.** In E-026's held-out lives, 39% of picks of plain 2.5 cm cubes
failed with the toy "no longer where it was believed" (blocks 9%, sticks
5%). Why?

**Diagnosis.** The perception model's detection rate for toys was a table
by range, measured in the playroom on its three toys (E-013): 0.97 within
0.25 m, 0.41 at 1.1 m, 0.11 at 1.9 m. The detector's limits are in pixels,
so what matters is how wide an object looks. Measured in 32 World 2 rooms
against the detector's own frames (`scripts/detection_probe.py`, true
identities read only by the probe), on frames the model calls visible:
0.08 at 1 to 1.5 degrees, 0.33 at 2 to 2.5, 0.68 at 3 to 3.5, 0.91 at 4
to 4.5, 0.94 beyond. A cube 1 m away looks 1.4 degrees wide and is seen 8%
of the time; the table said 41%, so each frame without it erased belief
in a cube that was there (L-026 again).

**Change** (`perception.py`). Objects (class toy) are detected by apparent
width, from the object's believed size (4 cm until it has been seen) and
its range, with the measured table. The basket stays by range (one size).

**Development** (lives 0 to 7 against E-026's development lives).
- Picks of plain cubes: `done` 69% against 43%, "no longer believed" 9%
  against 36%.
- Possible objects tidied +0.010 [−0.030, +0.050]; heavy objects grasped
  +0.13 [−0.02, +0.28] (heavy cubes are now found too), falls +0.16
  [−0.10, +0.42].
- Playroom: toys in the basket +0.26 [+0.06, +0.46], 6 of 8 lives higher
  (its 3.2 cm bricks were over-expected too).

**Predictions** (lives 400 to 415, rooms 11 to 20, against E-026's arms on
the same lives, paired by life):
1. Picks of plain cubes ending with the toy no longer believed: below 20%
   (E-026: 39%).
2. Possible objects in the basket: CI lower bound above −0.03.
3. Playroom toys in the basket: CI lower bound above −0.1.
4. Falls a room: CI upper bound below +0.3.

**Method.** Commit `ee6f7d4`. Tags `e028-task`, `e028-playroom` on lives
400 to 415, against `../E-026-heavy-tails/{task,playroom}.jsonl`
(`report.txt`).

**Result.**

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | picks of plain cubes ending with the toy no longer believed | 6% (E-026: 39%); `done` 72% | met |
| 2 | possible objects in the basket | +0.006 [−0.020, +0.033] | met |
| 3 | playroom toys in the basket | 5.61 against 5.30: +0.31 [+0.17, +0.45], 14 of 16 lives higher | met |
| 4 | falls a room | +0.02 [−0.17, +0.21] | met |

Wide objects were grasped less (−0.19 [−0.32, −0.07] per object):
believed longer, their sizes are known better. Heavy objects tidied fell
(−0.045), plain ones rose (+0.017).

**Analysis.** The same lesson as E-022, for objects: the detection model
held a number measured on three toys of one size. Detection by apparent
width is the general form, and it is what the camera does. In the playroom
it was worth a third of a toy a room, the largest gain there since
Milestone 1: its 3.2 cm bricks had been doubted the way World 2's cubes
were. In World 2 the cubes are now picked, but the room's total did not
move: deliveries, falls and the hard objects take the time saved.

**Decision.** Keep it.

### E-027 · 2026-11-07 · Pricing the owner's reactions once (pre-registered)

**Question.** With an owner, the duck mostly looks around, explores and
rests (E-025: 2,149 of 4,047 decisions in rooms 11 to 20 were to explore,
1,178 to rest). Why (H-023)?

**Diagnosis** (E-025's fresh owner lives, from the scorecards logged with
every decision). The best pick goal had a median utility of −0.04, the
best put −0.02, exploring +0.004. A pick's value was
`p_pick × (her reaction to the pick + p_put × her reaction to the put)`.
But her reaction to a kind of action is learned per action of that kind,
whether it worked or not: the duck's belief that a delivery earns approval
0.2 of the time already includes the deliveries that failed. Multiplying
by the chance of success again counted failure twice, and halved the
value of every pick and put in a world where half of them fail.

**Changes tried in development** (lives 0 to 7, development kinds, owner
`hers`, against the same lives with E-026's mind).
- (a) *Count failure once* (`goals.py`). A put is worth her reaction to
  it; a pick is worth her reaction to the pick plus the chance it works
  times her reaction to the best put. Picks 5.3 against 3.5 a room,
  approvals 0.46 against 0.19 (8 of 8 lives higher), time delivering 44 s
  against 17, her measure +0.23 [−0.05, +0.50] a room (4 of 8 higher),
  falls +0.28 [−0.02, +0.57], her things moved +0.08.
- (b) *Partial pooling*, with (a). A kind never tried started from the
  flat prior, which expects a reaction to a third of all actions and so,
  with her displeasure weighing more than her pleasure, values every new
  kind at −0.06. Starting a kind from the other kinds of the same skill
  instead: her measure +0.21 [−0.33, +0.75], picks unchanged against the
  control, disapprovals −0.14. No better than (a) alone, and it blurs the
  colour distinction E-024 introduced (a blue pick's disapproval leaks into
  every colour's prior). Reverted.

**Predictions** (lives 400 to 415, `--kinds late`, owner `hers`, rooms 11
to 20, against the baseline of `../E-026-baseline/`, paired by life):
1. Approvals a room: CI lower bound above 0.
2. Her measure gained a room: mean above 0 and CI lower bound above −0.1.
3. Falls a room: CI upper bound below +0.4.

**Method.** Commit `39dd2de` (with E-026's prior). `birdbrain-run --world
world2 --kinds late --owner hers --seeds 16 --seed0 400 --episodes 20
--tag e027-hers` against `../E-026-baseline/hers.jsonl` (`report.txt`).

**Result.**

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | approvals a room | 0.31 against 0.08: +0.23 [+0.05, +0.41], 11 of 16 higher | met |
| 2 | her measure gained a room | +0.18 against −0.08: +0.26 [−0.08, +0.59], 9 of 16 higher | met |
| 3 | falls a room | 0.55 against 0.24: +0.31 [+0.17, +0.46] | missed |

The duck picked 5.3 times a room against 3.7, spent 30 s delivering
against 6, put away more (possible objects 0.09 against 0.02, +0.065
[+0.019, +0.112]) and found more (never found 40% against 46%). It also
moved more of her blue things (0.19 against 0.12 of them) and was
disapproved of more (+0.08).

**Analysis.** Counting failure once turned an idle duck into one that
works for its owner, roughly as often as it should given how often her
approval follows. Acting has the costs acting has in this world: falls,
and her things moved by picks made before their colour was seen. Her
measure rose, with an interval that does not exclude a small loss.

**Decision.** Keep (a), a correction of how the scorecard combined two
probabilities. H-023 is supported in part: the duck is no longer idle;
the falls that come with acting are World 2's general problem (next).

### E-026 · 2026-11-07 · Strong effects, believed (pre-registered)

**Question.** E-025's duck learned "carrying a black object makes me fall"
and kept carrying black objects (0.91 falls per heavy object grasped). Why,
and does a prior that lets a strong effect be strong fix it (H-022)?

**Diagnosis** (E-025's fresh lives, from the outcomes they kept). The duck
fell in 72% of deliveries holding a black object (234 of them; 9% for the
other colours) and its rules predicted 32%. The colour condition was
credible, so the effect was found, but each condition's effect has a
normal prior with sd 0.5 on the log-odds, which holds a 3-sd effect to a
fraction of its size; a heavy object then looked worth 0.12 (the bar for a
poor prospect is 0.1). Of 174 picks of heavy objects in rooms 11 to 20,
156 were chosen as the nearest toy with the colour already known.

**Change** (`rules.py`). The prior on each condition's effect is a Cauchy
distribution with the same curvature at zero (scale 0.71): weak effects
are shrunk as before, strong ones far less. It is fitted at the posterior
mode by the same damped Newton steps, with the precision of the Gaussian
that bounds the Cauchy at the current point; the Laplace covariance uses
that precision too.

**Development.**
- *Offline* (`scripts/rules_replay.py`, every outcome of the 16
  development lives of E-025 replayed in order, predicted before it is
  learned): Brier score lower for falls in deliveries (−0.012 [−0.017,
  −0.006], 13 of 16 lives), for the effect of deliveries (−0.004) and of
  picks (−0.002); unchanged elsewhere. Falls holding a black object:
  predicted 0.37 against the observed 0.55 (Gaussian: 0.18). A wider
  Cauchy (scale 1.77) was better calibrated on strong conditions and worse
  overall (picks +0.016), and was not kept. In the playroom and owner lives
  the two priors predict alike.
- *Lives* (0 to 7, development kinds, against the same lives with E-025's
  mind): heavy objects grasped per heavy object 0.22 against 0.53, falls
  holding one 0.25 against 0.53, falls a room 0.79 against 1.18 (−0.39
  [−0.60, −0.18], 7 of 8 lower); possible objects tidied −0.015 [−0.046,
  +0.016], heavy objects tidied −0.13. The owner and playroom lives were
  identical: there the rules do not decide, or no rule is credibly against
  anything.

**Held-out set.** Lives 200 to 215 have been used four times and 300 to
315 once; from here on, changes are checked on lives 400 to 415 against
E-025's mind run once on them (commit `4e28859`, from a worktree,
`../E-026-baseline/`), and the kept set on fresh lives at the end.

**Predictions** (lives 400 to 415, `--kinds late`, rooms 11 to 20, paired
by life, against the baseline):
1. Falls while holding a heavy object: CI upper bound below 0.
2. Heavy objects grasped per heavy object: CI upper bound below −0.1.
3. Falls a room: CI upper bound below 0.
4. Possible objects in the basket: CI lower bound above −0.04.
5. Playroom toys in the basket: CI lower bound above −0.1.
6. Offline, on the baseline's own task lives: Brier score for falls in
   deliveries, Cauchy minus Gaussian, CI upper bound below 0.

**Method.** Commit `9207b27`. `birdbrain-run --world world2 --kinds late
--seeds 16 --seed0 400 --episodes 20 --tag e026-task` and the playroom
(`e026-playroom`), against `../E-026-baseline/`. Reports: `report.txt`,
`replay_baseline.txt`.

**Result.**

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | falls while holding a heavy object | 0.33 against 0.49: −0.16 [−0.29, −0.04], 11 of 16 lower | met |
| 2 | heavy objects grasped per heavy object | 0.36 against 0.55: −0.19 [−0.32, −0.06] | missed (bound −0.1) |
| 3 | falls a room | 0.89 against 1.05: −0.16 [−0.32, −0.01] | met |
| 4 | possible objects in the basket | −0.008 [−0.025, +0.009] | met |
| 5 | playroom toys in the basket | identical (+0.000) | met |
| 6 | Brier, falls in deliveries, offline | −0.015 [−0.021, −0.009], 16 of 16 lives | met |

Transfer to kinds never met improved: the new heavy kind was grasped
−0.19 [−0.36, −0.02] less, new wide kinds −0.23 [−0.42, −0.04]. A
delivery holding a black object was predicted to fall 0.39 of the time
(observed 0.68; Gaussian 0.22).

**Analysis.** One line of prior changed what the duck does about heavy
objects: it now believes a strong effect when it sees one, avoids heavy
objects more, falls less, and carries more of that to new kinds. Tidying
did not change: the time not spent falling with heavy objects went to
objects as hard to tidy. The predictions still understate strong effects
(0.39 against 0.68), so the avoidance is partial.

**Decision.** Keep the Cauchy prior. H-022 is supported in part.

### E-025 · 2026-11-07 · The kept changes on fresh lives (pre-registered)

**Question.** E-022 to E-024 were each judged on lives 200 to 215, which
have now been used four times. Do the kept changes, together, hold on
lives that informed nothing?

**Review, before the results** (`semantic-review/2026-11-07-104801-pr-local.md`).
A reviewer read the World 2 code in a clean context while the first E-025
runs were under way (a quarter done). No truth reaches the mind. Its
findings that bear on the experiments, all confirmed against the logs:
- *A stopped pick did not stop the body.* Reconsidering closed the pick
  program, but a pick reflex already begun ran on: in E-023b, 147 of 539
  stops ended with the toy grasped about 0.2 s later, and the next pick,
  of another toy, then failed and counted against that toy. Picks are now
  reconsidered only on the way, before the duck stands to pick.
- *Stopped picks were counted.* As pick decisions and failed picks (E-024
  prediction 3, re-scored above as missed), as failed trials of `pick` in
  the skill record, and, with an owner, as candidates for credit. Now none
  of these.
- *The occlusion test took the floor for an obstacle.* For a low object
  1.5 to 2.5 m away, the range zones below it see the floor nearer than the
  object, so misses of toys there stopped counting. A zone now counts as in
  the way only if it reads nearer than both the object and the floor
  along its ray.
- *The basket's detection rate counted occlusion twice.* It was measured
  with occluded frames included, and occluded frames are now not misses.
  Re-measured live on frames the occlusion test calls visible
  (`scripts/detection_probe.py`, 32 rooms): 0.97 to 1.25 m, 0.88 at
  1.75, 0.68 at 2.5, 0.45 at 3.25, 0.10 at 4. A miss now never counts for
  an object where detection is rarer than a ghost.
- *The lost-basket share left out the search's own failure.* Now counted
  (E-022 corrected above).
- *"Credible" was any credible condition.* A toy was a poor prospect when
  its chance was low and any credible condition applied, even one in its
  favour. Now a credible condition must lower the chance of the effect or
  raise the chance of a fall.
- *With an owner, a pick stopped when its place changed* (open, wall), not
  only its colour. Now only a newly seen colour stops it.
- Smaller: deliver's search went on after a slippery object dropped (it
  now stops); a toy held at the end of a room counted as never found;
  ghost detections never had a colour, so "no colour" within 1 m meant
  "not real" (the classifier now names one).

The partial E-025 runs were stopped and discarded; E-025 runs again with
the fixed code (commit `9fd8268`; in development, reconsidering until the
pick reflex is asked for left 1 of 133 stops followed by a grasp, and
tidying was unchanged). Earlier entries' verdicts stand as measured for the
code they tested, with the corrections noted in them. One contamination:
the reviewer reported, from the discarded quarter, a lost-basket share of
20% to 23% for the new mind, against prediction 4's threshold of 20%. The
threshold is left as written.

**Arms.** The mind of E-021 (commit `089b22e`, run from a worktree with
the current `world2.py`, whose changes since only count refusals once per
try) against the current mind (E-022, E-023b and E-024), on lives 300 to
315 (rooms 30001 to 31520): World 2 with the task, World 2 with the owner
who wants her things left alone, and the playroom with the task.

**Predictions** (rooms 11 to 20, paired by life):
1. World 2, task: possible objects in the basket higher, CI lower bound
   above 0.
2. World 2, task: wide objects grasped per wide object, CI upper bound
   below −0.4.
3. World 2, task: falls, CI upper bound below +0.3.
4. World 2, task: deliveries ending with the basket lost below 20% (the
   E-021 mind: about 60%).
5. World 2, owner: her measure gained a room, CI lower bound above 0.
6. Playroom: toys in the basket, CI lower bound above −0.2.

**Method.** Commit `9fd8268` for the new mind; `089b22e` from a worktree
for the old. Six arms of 16 lives × 20 rooms (1,920 rooms). Reports:
`world2_report.py old_task.jsonl new_task.jsonl` (`report_task.txt`),
`... old_hers.jsonl new_hers.jsonl` (`report_hers.txt`),
`world2_failures.py ... --from 11` (`failures.txt`).

**Result.**

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | World 2, task: possible objects in the basket | 0.40 against 0.31: +0.088 [+0.058, +0.119], 14 of 16 lives higher | met |
| 2 | wide objects grasped per wide object | 0.51 against 1.20: −0.70 [−0.86, −0.54], 16 of 16 lower | met |
| 3 | falls a room | 1.33 against 1.02: +0.31 [−0.01, +0.64] | missed |
| 4 | deliveries ending with the basket lost | 16.9% (old mind 57.8%) | met |
| 5 | World 2, owner: her measure gained a room | −0.10 against −0.24: +0.14 [+0.0001, +0.27], 10 of 16 higher | met, barely |
| 6 | playroom toys in the basket | −0.10 [−0.27, +0.07] | missed |

- *Kinds never met.* New wide kinds were grasped 0.75 times per object
  (known 0.41; the old mind 1.14 and 1.20): the size rule carried over in
  part. The new heavy kind was grasped as often as before (0.74 against
  0.72). New kinds were tidied at 0.37 against 0.30 (+0.078 [+0.033,
  +0.122]).
- *Objects never found* fell from 34% to 27% (−0.071 [−0.103, −0.039]).
- *Falls.* They rose during deliveries (0.91 to 1.09 a room) and picks
  (0.11 to 0.24): the new mind reaches the basket and the far objects more
  often, and falls there. Falls while holding a heavy object did not
  change (+0.02).
- *With the owner* her blue things were moved less (0.11 against 0.20 of
  them a room, [−0.17, +0.00]); possible objects put away did not change.
- *The playroom.* The point estimate is a tenth of a toy lower; E-022's
  and E-023b's checks were −0.06 and 0.00. A loss up to a quarter of a toy
  is not ruled out.

**Analysis.** On lives that informed nothing, the kept changes raised
tidying in World 2 by 9 points, cut grasps of wide objects by 58%, found
more objects, and carried part of what was learned to kinds never met.
With the owner the gain is a seventh of a toy a room and barely clear of
zero. Two costs are real or possible: more falls, from doing more where
falls happen, and perhaps a small loss in the playroom. The heavy objects
are still not learned well (H-022), and with an owner the duck still does
little (H-023).

**Decision.** World 2 is done as a milestone: the harder world exposed
what the playroom hid, and the changes kept are those that survived
held-out and fresh checks. Next: H-022 and H-023 in World 2, and falls at
the basket (H-011, now in a world where they matter more).

### E-024 · 2026-11-07 · The owner who wants her things left alone (pre-registered)

**Question.** In E-021 the duck with this owner did almost nothing: a pick
from the open was sometimes of her blue things (disapproved) and sometimes
of a toy she wanted put away (approved once delivered), and the duck,
which learns her reactions per kind of action, could not tell the two
apart. If its kinds of action name what it picks, does it learn what she
wants?

**Changes** (`mind.py`, `goals.py`, `reactions.py`).
- *Kinds name the object.* A pick is described by where the toy is and,
  once the duck has seen it, its colour ("pick blue from open"). Kinds of
  action are what the owner model learns over, and what the scorecard
  counts success and risk by, so both now distinguish objects by colour.
- *Reconsidering.* Colour is seen within 1 m, so a pick chosen from afar is
  of unknown colour. When the duck sees the colour on the way, the pick
  stops and it chooses again knowing the kind. A stopped pick is not a
  trial of its kind.

**Development** (lives 0 to 7, development kinds; against the same lives
with E-022 and E-023, `../E-023-appearance/dev2_hers.jsonl`). Colour in the
kinds alone: her measure +0.15 [−0.02, +0.32] a room. With reconsidering:
picks 5.0 against 2.9 a room, time delivering 22 s against 6, approvals
0.17 against 0.07 a room, disapprovals 0.17 against 0.28, her things moved
by picks 0.12 against 0.30, her measure +0.29 [−0.21, +0.78] (4 of 8 lives
higher). The duck still spends 220 of 300 s looking, exploring and
resting. With the owner model over conditions (`--owner-model
conditions`, whose conditions now include colour), approvals were 0.33 a
room and her measure +0.15 more again [−0.31, +0.61].

**Predictions** (held-out lives 200 to 215, `--kinds late`, owner `hers`,
rooms 11 to 20, paired by life; the control is the same code without the
colour-named kinds and reconsidering: commit `b009c8c` with `896b956`
reverted, run from a worktree):
1. Her measure gained a room: higher, CI lower bound above −0.2.
2. Her things moved by picks: CI upper bound below +0.05.
3. Pick decisions a room: CI lower bound above 0.
4. Reported, with no prediction: the owner model over conditions, as a
   third arm.

**Method.** Commit `9223866`. Arms: `ctl` (from the worktree), `kinds`
(the default owner model), `conditions` (`--owner-model conditions`), each
`--world world2 --kinds late --owner hers --seeds 16 --seed0 200
--episodes 20`. Reports: `world2_report.py ctl.jsonl kinds.jsonl`
(`report_kinds.txt`) and `... conditions.jsonl` (`report_conditions.txt`).

**Result.**

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | her measure gained a room | −0.02 against −0.22: +0.20 [+0.04, +0.37], 11 of 16 lives higher | met |
| 2 | her things moved by picks (changes she disliked, made while the duck held the toy) | −0.02 [−0.17, +0.14] | missed |
| 3 | pick decisions a room, stopped picks left out | 3.9 against 3.5: +0.45 [−0.27, +1.17] (first reported as +1.87, which counted 1.4 stops a room as picks; E-025 review) | missed |
| 4 | the owner model over conditions | her measure +0.17 [+0.05, +0.29]; against kinds −0.03 [−0.26, +0.20] | reported |

- *How her measure rose.* The duck picked more (1.4 picks a room were
  stopped on the way once it saw the colour) and put more away (possible
  objects in the basket 0.028 against 0.007). She disapproved less (0.14
  a room against 0.24, [−0.21, +0.01]). The share of her blue things moved
  fell from 0.15 to 0.10 ([−0.10, +0.01]).
- *What did not change.* Changes she disliked that the duck made while
  holding a toy stayed at 0.2 a room: those include taking a non-blue toy
  out of the basket, and picks of things whose colour was not seen
  before the grasp.
- *Still passive.* Her measure only reached zero. The duck spends most of
  each room looking around, exploring and resting.

**Analysis.** Naming the object in the kind of action let the duck tell her
things from the rest, and acting on that raised her measure by a fifth of a
toy a room. The owner model over conditions did as well, not better; in
World 2 its conditions include colour too, so the two now see the same
distinction. The remaining limit is how little the duck does with an
owner: in a large room curiosity outbids the small, uncertain value of
pleasing her (E-021: exploring while holding a toy).

**Decision.** Keep both changes. Next: check the whole kept set on fresh
lives (E-025). The passivity with an owner is left open (H-023).

### E-023 · 2026-11-07 · Learning about objects from how they look (pre-registered)

**Question.** In E-021 the duck tried every wide object and carried every
heavy one, because nothing it knew about an object said what it was like.
If it notes how objects look and its rules use that, does it learn which
kinds of object fail, and does that carry to kinds it has never met?

**Changes** (`perception.py`, `rules.py`, `mind.py`).
- *Appearance.* Perception keeps each object's size (apparent width times
  range, the median of the last 15 sightings) and colour (the colour seen
  most often). Rules gain four conditions: the target's colour and size,
  and the held object's colour and size (sizes in bins: under 3 cm, 3 to
  5, 5 to 7.5, over 7.5).
- *Choosing.* With the task, the local policy ranks known toys by the rules'
  chance that picking it and then delivering it both work without a fall,
  per second it would take (30 s plus the walk at 0.2 m/s; L-025). A toy
  whose chance is credibly below 0.1 (some rule at 3 sd bears on it) is a
  poor prospect: it is tried only once the duck has looked and explored
  and found nothing better.
- *Reconsidering.* On the way to a toy the duck sees it better (its colour
  within 1 m). If the toy becomes a poor prospect and a better one is known,
  the pick stops and the duck chooses again. A stopped pick is not an
  outcome and teaches nothing.

**Development** (lives 0 to 7, development kinds, against E-022's
development lives; `experiments/E-023-appearance/`). The rules found what
the world hides, from the duck's own outcomes: "pick when target size 5 to
7.5 cm: 1/4 the odds" (0 of 22 held), "deliver when held colour black: 4
times the odds of a fall" (10 of 16). The first version dropped poor
prospects for good; heavy objects tidied fell from 0.34 to 0.09, more than
the gain elsewhere (possible objects −0.02). Deferring them instead:
- wide objects grasped per wide object, rooms 11 to 20: 0.35 against 1.25;
- heavy objects grasped per heavy object: 0.40 against 0.55; falls while
  holding one: 0.43 against 0.56;
- plain objects tidied +0.075 [−0.008, +0.159]; heavy −0.18; possible
  objects +0.014 [−0.033, +0.062];
- falls overall +0.18 [−0.14, +0.49];
- 14% of picks were stopped on the way.

**Predictions** (held-out lives 200 to 215, task, `--kinds late`, against
E-022's task arm, rooms 11 to 20, paired by life unless stated):
1. Wide objects grasped per wide object: CI upper bound below −0.4.
2. Kinds never met transfer: wide objects of the two new wide kinds (green
   and yellow big boxes), grasped per object, pooled over rooms 11 to 20, are
   below 0.6 (E-022, where the mind could not tell kinds apart: 1.31 for
   all wide objects).
3. Falls while holding a heavy object: CI upper bound below 0.
4. Possible objects in the basket: CI lower bound above −0.03.
5. Falls a room: CI upper bound below +0.3.
6. Playroom (lives 160 to 175 against E-022's playroom arm): toys in the
   basket, CI lower bound above −0.3.

**Method.** Commit `fa57799`. As E-022, tags `e023-task`, `e023-playroom`.
Report: `world2_report.py ../E-022-far-basket/task.jsonl task.jsonl`
(`report.txt`).

**Result.**

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | wide objects grasped per wide object | 0.46 against 1.31: −0.85 [−0.99, −0.71], 16 of 16 lives lower | met |
| 2 | the same, new wide kinds only, pooled | 0.54 (66 of 123); known wide kinds 0.42 | met |
| 3 | falls while holding a heavy object | −0.18 [−0.33, −0.02] | met |
| 4 | possible objects in the basket | +0.022 [−0.006, +0.049] | met |
| 5 | falls a room | −0.08 [−0.34, +0.19] | met |
| 6 | playroom toys in the basket | −0.21 [−0.33, −0.09], 14 of 16 lives lower | missed |

- *Transfer.* New kinds were met only from room 11, by a duck that had
  learned on the others. The new wide kinds were grasped 0.61 times per
  object in rooms 11 to 15 and 0.45 in rooms 16 to 20; the black block,
  the one new heavy kind, 0.46 and 0.69 (known heavy kinds 0.42): the size
  rule carried to new kinds, the colour rule less clearly.
- *What it bought.* Plain objects tidied rose (+0.058 [+0.016, +0.100]),
  heavy ones fell (−0.07), and the total gain was small. New kinds were
  tidied at 0.43 against E-022's 0.37 (+0.06 [−0.00, +0.13]).
- *The playroom got worse.* No rule there was credible in most lives, so
  nothing was deferred and no pick was stopped. What changed was the
  ranking: toys were ranked by the rules' mean chance per second instead
  of by distance, and the means, uncertain, picked worse targets (failed
  picks 2.86 a room against 2.38). This is L-020 again: choosing by
  posterior means picks what looks best by error.

**Analysis.** The duck learned from its own outcomes, through how objects
look, which objects cannot be carried and which make it fall, and carried
the size rule to kinds it had never met. Acting on credible rules worked.
Ranking by uncertain means did not, which E-017 and E-018 had already
shown and this design should have respected.

**Decision.** Keep appearance, the credible deferral, and reconsidering.
Rank toys by distance again (E-023b, below).

### E-023b · 2026-11-07 · Credible rules only (development, then held-out)

**Change.** The task policy picks the nearest toy that is not a poor
prospect, as before E-023; the rules enter only through credible deferral
and reconsidering.

**Development** (lives 0 to 7). Against E-023: possible objects +0.005
[−0.023, +0.032], heavy +0.09, wide grasps per wide object 0.30 against
0.35. The playroom's development lives reproduce E-022's rows exactly: no
rule there is credible enough to defer anything.

**Predictions** (held-out lives 200 to 215 against E-022's task arm, and
playroom lives 160 to 175 against E-022's playroom arm; rooms 11 to 20):
1. Wide objects grasped per wide object: CI upper bound below −0.4.
2. Possible objects in the basket: CI lower bound above −0.03.
3. Falls while holding a heavy object: CI upper bound below +0.05.
4. Playroom toys in the basket: CI lower bound above −0.1.

**Method.** Commit `6cb564c` (with E-024's development code, which acts
only with an owner). Tags `e023b-task`, `e023b-playroom` (`b_report.txt`).

**Result.**

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | wide objects grasped per wide object | −0.86 [−1.04, −0.68], 16 of 16 lower | met |
| 2 | possible objects in the basket | +0.014 [−0.017, +0.045] | met |
| 3 | falls while holding a heavy object | −0.07 [−0.26, +0.12] (a stop often left the duck holding the toy it had judged poor; E-025 review) | missed |
| 4 | playroom toys in the basket | identical rows (+0.000) | met |

Transfer was weaker than in E-023: new wide kinds were grasped 0.69 times
per object (known 0.35), the new heavy kind 0.70 (known 0.50). A rule is
one effect per condition, added: a green big box is "green", which picks
well, and "5 to 7.5 cm", which picks badly, and the sum often stays above
the bar for a poor prospect.

**Analysis.** The two designs trade. Ranking by the rules' means (E-023)
avoided heavy objects more and transferred better, and cost the playroom a
fifth of a toy. Credible deferral alone (E-023b) leaves the playroom
exactly as it was and keeps most of the gain on wide objects, and its
effect on heavy objects is not distinguishable from none.

**Decision.** Keep E-023b: a change that makes the familiar world worse
needs more than this to justify it. Learning that a kind of object is
heavy needs more than additive conditions (a condition for colour and
size together, or per-object memory), which is left open (H-022).

### E-022 · 2026-11-07 · Finding the basket in a larger room (pre-registered)

**Question.** E-021's deliveries failed mostly because the duck stopped
believing in the basket on the way to it. Why, and what fixes it?

**Development** (lives 0 to 7, development kinds, task; rows in
`experiments/E-022-far-basket/`). Three causes, found in turn, with a change
for each:
1. *The perception model expected to see a far basket.* Its detection rate
   for the basket was 0.96 at any range (E-013, playroom). Measured in
   World 2 against truth (`scripts/detection_by_range.py`, since replaced by
   `scripts/detection_probe.py`), it is 0.94 to
   1.75 m, 0.88 to 2 m, 0.55 to 0.65 at 2 to 2.75 m, and 0.2 beyond. The
   table now holds these values. Lost-basket deliveries fell from 59% to
   48%.
2. *Furniture hides the basket, and the model did not know.* A frame that
   should have shown the basket counted as a miss even when something
   stood in the way. The range sensor sits beside the camera and looks the
   same way over 45 degrees; a frame now counts as no evidence when the
   range sensor shows something closer than the object (by 0.3 m) in its
   direction. 48% to 45%.
3. *Deliver gave up after one look.* In the trace that showed it (life 2,
   room 1), the duck turned a full circle twice, saw no basket, and failed
   each time without moving. Deliver now walks for 6 s and looks again, up
   to four times. Deliveries `done` rose from 16% to 37%; lost-basket fell
   to 33%.
4. *A far basket was misplaced.* Range from elevation is poor beyond 2 m (a
   degree of error at 3 m moves the estimate by a metre). The detector's
   apparent width gives range to 11% (the basket reads as radius 0.12 m at
   every range, measured), so far sightings now fuse both, weighted by
   their errors. Deliveries `done` 46%, lost-basket 17%.

With all four, possible objects in the basket rose by +0.049 [−0.012,
+0.111] (7 of 8 lives higher), objects never found fell by 0.09, and heavy
objects tidied rose by 0.19. Falls did not change clearly (+0.08 [−0.31,
+0.46]). In the playroom (lives 0 to 7 against E-019's control), toys in
the basket −0.06 [−0.22, +0.10], falls +0.09 [−0.09, +0.28].

**Predictions** (held-out lives 200 to 215, task, against E-021's task
arm; and the playroom's held-out lives 160 to 175 against E-020's task
control; rooms 11 to 20, paired by life):
1. Deliveries ending with the basket lost: below 30% (E-021: 61%).
2. Possible objects in the basket: higher, CI lower bound above 0.
3. Falls: CI upper bound below +0.5 a room.
4. Playroom toys in the basket: CI lower bound above −0.3.
5. Playroom falls: CI upper bound below +0.3.

**Method.** Commit `4915ecc`.
`birdbrain-run --world world2 --kinds late --seeds 16 --seed0 200 --episodes 20 --seconds 300 --tag e022-task`
and `birdbrain-run --seeds 16 --seed0 160 --episodes 20 --seconds 300 --tag e022-playroom`.
Report: `world2_report.py ../E-021-world2/task.jsonl task.jsonl` (`report.txt`).

**Result.**

| Prediction | Measure, rooms 11 to 20 | Result | Verdict |
|---|---|---|---|
| 1 | deliveries ending with the basket lost | 15.5%, counting the search's own failure (first reported as 12%; E-025 review); E-021: 61%; `done` 52% (16%) | met |
| 2 | possible objects in the basket | 0.37 against 0.30: +0.066 [+0.028, +0.104], 13 of 16 lives higher | met |
| 3 | falls a room | +0.06 [−0.09, +0.22] | met |
| 4 | playroom toys in the basket | −0.06 [−0.20, +0.09] | met |
| 5 | playroom falls | −0.05 [−0.17, +0.07] | met |

Objects never found fell from 38% to 30% (−0.082 [−0.134, −0.031]): a
delivery that looks again also sees toys. Slippery objects tidied rose
(+0.05); heavy ones did not. The duck now tries more wide objects (1.31
grasps per wide object against 1.08), because it finds more of them.

**Analysis.** All four changes were corrections of beliefs about the
duck's own senses, each measured against truth: how often the camera sees
a far basket, when it cannot see it at all, how far away it is, and what
to do when it is not in view. None was about objects. The gain in tidying
(+7 points) is smaller than the gain in deliveries (+36 points `done`)
because the other failures now set the pace: picks of what cannot be
carried, and falls carrying heavy things.

**Decision.** Keep all four. Next: learning about objects (E-023).

### E-021 · 2026-11-04 · World 2: how the current mind does in a harder world (pre-registered)

**Question.** How much of what BirdBrain does in a room of six similar toys
carries over to a world with many kinds of object, hidden properties, and
furniture? What breaks first, and what has to change?

**World 2** (`world2.py`, world code the mind never imports; `--world world2`).
- *Objects.* 24 kinds, each a colour (red, yellow, blue, green, white,
  black) and a shape (2.5 cm cube, 4 cm block, 9 × 1.5 cm stick, 6 cm big
  box). What a kind does is hidden and follows its appearance: black things
  weigh 150 g and tip the duck over when carried (the grasp probe: about 10
  falls a room when every toy was heavy); white things slip out of the beak
  (8% a second); big things are too wide to hold (narrower side over 5 cm).
  Eight kinds are held out of development; every colour and shape stays in.
- *Rooms.* 3.5 to 4.5 m by 2.8 to 3.5 m (the playroom is 3 by 2.5), the
  basket in a random corner, 2 to 5 pieces of furniture up to 30 cm tall,
  an inner wall with a 60 cm doorway in half the rooms, 0 to 2 balls, and 4
  to 15 objects. The duck starts at a random place.
- *What the duck senses.* As before, plus a colour for objects within 1 m,
  right 95% of the time (the lab's colour classifier for ducks, applied to
  objects). Weight, slipperiness and width it can learn only by trying.
- *The owner who wants her things left alone* (`--owner hers`): blue things
  are hers and she wants them where they were; everything else she wants
  in the basket.
- *What changed outside the mind.* The lab is not edited. World 2's kinds are
  added to the lab's table of pickable kinds at start-up (`world2.register`),
  and two rules the lab does not model, wide objects and slipping, are
  applied by `WorldRules` after each world step. The playroom reproduces
  E-020's rows exactly (life 160, room 1).

**Procedure for this milestone.** First the current mind, unchanged, on
held-out lives (this entry). Then changes, one per ledger entry, each
developed on development lives (0 to 15) and checked once on these held-out
lives against this baseline, paired by life. The full set of kept changes
is then checked once on fresh lives (300 to 315), since repeated checks on
one held-out set wear it out.

**Development** (lives 0 to 7, 20 rooms, development kinds only;
`dev_task.jsonl`, `dev_auth.jsonl`, `dev_hers.jsonl`). With the task, the
duck put 30% of the objects it could carry in the basket (the playroom:
90%), fell 0.9 times a room, and 37% of the objects were never found.
- *Deliveries fail because the basket is lost.* Of 2,136 deliveries, 16%
  ended `done` (69% in E-020's development logs); 59% failed with "basket
  no longer where it was believed". This does not depend on the furniture
  or the inner wall (54% to 68% in every group). It depends on range. The
  perception model says a basket is detected 96% of the time at any range
  (measured in the playroom, E-013); in World 2 it was seen 79% of the time
  at 1.5 to 2 m, 53% at 2 to 2.5 m, and 20% to 30% beyond. Each frame that
  should have shown the basket and did not takes away log(0.04/0.9) of its
  confidence, so the belief collapses while the duck walks toward it.
- *Picks fail on what cannot be carried.* 45% of picks ended "requirement
  not met" (the beak held nothing): most on wide objects (402 of 440 picks
  aimed at them), and some on slippery and plain ones. The give-up rule is
  per object (three failures), so every new wide object is tried three
  times. The refusal counter counted every tick of the pick reflex's
  closing window; it now counts one per try (the development rows carry
  the old count).
- *Heavy objects*: carried in about half the attempts, and then the duck
  usually falls (51 of 133 deliveries of a heavy object ended in a fall).
- *With the owner*, the duck did little: 3.5 picks and 0.5 deliveries a
  room; her measure fell by 0.2 a room.
- *Authoring* asked about the same situations as in the playroom and
  changed little (+0.01 possible objects tidied, 8 lives).

**Predictions for the held-out baseline**, written before it runs (lives
200 to 215, rooms 20001 to 21520, 20 rooms; development kinds in rooms 1 to
10 and all kinds from room 11, `--kinds late`; arms: task, task with
authoring, and the owner who wants her things left alone):
1. With the task, the share of possible objects in the basket, rooms 11 to
   20, is below 0.40 (development 0.30; the playroom 0.90).
2. More than 40% of deliveries end with the basket lost.
3. The duck does not learn across objects: in rooms 16 to 20, wide objects
   grasped per wide object and heavy objects grasped per heavy object are
   each at least 80% of their values in rooms 1 to 5.
4. Falls exceed 0.5 a room, rooms 11 to 20.
5. Among possible objects, new kinds and known kinds are tidied at rates
   within 0.10 of each other (the mind has no notion of kinds to transfer).
6. Authoring raises the possible share by less than 0.05, rooms 11 to 20.
7. With the owner, her measure gained is at most 0 a room, rooms 11 to 20.
8. More than 25% of objects are never found in a room (task arm).

**Method.** Commit `089b22e`. Each arm:
`birdbrain-run --world world2 --kinds late --seeds 16 --seed0 200 --episodes 20 --seconds 300 --jobs 4 [--author | --owner hers] --tag e021-<arm>`.
960 rooms. Reports: `scripts/world2_report.py task.jsonl auth.jsonl`
(`report_task_auth.txt`), `world2_report.py hers.jsonl` (`report_hers.txt`),
`scripts/world2_failures.py e021-task e021-hers e021-auth --from 11`
(`failures.txt`). Rooms held 9.5 objects on average, 7.1 of them possible.

**Result.**

| Prediction | Measure, rooms 11 to 20 unless stated | Result | Verdict |
|---|---|---|---|
| 1 | possible objects in the basket (task) | 0.30 | met |
| 2 | deliveries ending with the basket lost (task) | 61% | met |
| 3 | grasps per object, rooms 16 to 20 against 1 to 5 | wide 1.09 against 0.98; heavy 0.67 against 0.44 (rose) | met |
| 4 | falls a room (task) | 1.05 | met |
| 5 | new kinds against known kinds, possible objects | 0.31 against 0.30 | met |
| 6 | authoring minus task, possible share | −0.005 [−0.024, +0.014] | met |
| 7 | her measure gained a room | −0.19 [−0.26, −0.13] | met |
| 8 | objects never found (task) | 38% | met |

- *Where the time goes.* Deliveries fail most: of 14 a room, 16% end
  `done` and 61% fail with the basket lost. Picks: 42% fail with nothing in
  the beak (wide objects, and slippery ones that slip as the beak closes).
  A heavy object that is carried usually ends in a fall (0.6 falls a room
  while holding one).
- *Nothing is learned about objects.* The duck grasps heavy objects more
  often late in life than early, and tries every wide object it finds. New
  kinds fare like known ones because no kind is known: the mind's beliefs
  about an object are its class, its position, and the colour it now sees,
  which nothing uses.
- *With the owner.* 3.4 picks and 0.3 deliveries a room. She approved 0.07
  times a room and disapproved 0.18 times; the duck's beliefs end with
  "pick from the open" slightly disapproved, so it mostly rests and looks.
  Her measure fell because the few picks moved her things (15% of them
  moved a room) or dropped other toys short of the basket.
- *Authoring* asked about far deliveries and picks, as in the playroom,
  and changed nothing here. It used 1.1 million tokens over 16 lives (the
  sum of the rows), nine times E-020's, because more situations failed.

**Analysis.** The current mind does not carry over. Its two hand-written
skills assume an open room where the basket is always in view and every
toy can be carried. When the first assumption fails, deliveries fail
before any learning can matter. When the second fails, the duck has no
way to learn about kinds of object: its rules use conditions about place
and belief quality, and the give-up rule works one object at a time. The
playroom result (5.4 of 6) depended on the room as much as on the mind.

**Decision.** Fix in order of measured cost, one change per entry: first
the lost basket (E-022), then learning about objects from their
appearance, then the owner's preference over kinds of object.

### E-020 · 2026-11-04 · Milestone 5a: fair trials for written skills (pre-registered)

**Question.** E-019 kept written skills against a parent prior biased low
(L-023), and two kept skills did no better than the control. With fair
trials, are the skills the duck keeps really better, and does authoring
still help in the situations it targets? Does it help with an owner, where
behaviour comes from the approval scorecard?

**Changes** (`authoring.py`).
- *No prior.* Both skills start from zero in a trial.
- *Turns.* Parent and written skill take turns until each has 8 outcomes
  in the situation; then Thompson sampling decides.
- *Re-review.* Kept skills stay under review and can be retired.
- *Building on.* A kept written skill can be the parent of a newer one.
- Every action of a written skill counts as a try of its parent (E-019
  review).

**Development** (lives 0 to 7, task arm, against E-019's control lives;
`dev_authoring.jsonl`). 17 skills written, 5 retired, 2 kept, 10 still on
trial at the end of life (E-019's rule: 12 written, 8 kept). In the
written skills' situations after they were written, success against the
control life was +0.03 per life [−0.03, +0.09], 3 of 8 lives higher, with
falls −0.01. Part of E-019's apparent gain came from generous keeping, and
part of this one is spent on the parent's turns.

**Predictions, written before the held-out runs** (lives 160 to 175,
rooms 16001 to 17520, 20 rooms; two settings, task and the basket owner,
each with a control and an authoring arm on the same rooms; per life,
paired):
1. Honest judging: across both settings, at least 3 written skills are
   retired.
2. In the written skills' situations after they were written, success in
   the authoring life is not lower than in the control life: per-life CI
   lower bound above −0.05, in each setting.
3. Falls there are not higher: per-life CI upper bound below +0.03.
4. With the basket owner, her own measure (toys gained in the basket,
   rooms 11 to 20) is not lower: CI lower bound above −0.5.
5. Reported, with no prediction: skills kept, and kept skills' success in
   their situations after they were kept, against the control life.

**Method.** Commit `0be3b0a` (later commits change only the dashboard).
Each setting and arm:
`birdbrain-run --seeds 16 --seed0 160 --episodes 20 --seconds 300 --jobs 3 [--owner basket] [--author] --tag e020-<setting>-<arm> --memory data/lifetimes/e020-<setting>-<arm>`.
1,280 rooms. Report, per setting:
`scripts/skills_report.py <setting>_ctl.jsonl <setting>_auth.jsonl --lives data/lifetimes/e020-<setting>-auth --control-lives data/lifetimes/e020-<setting>-ctl --late 11`
(`task_report.txt`, `basket_report.txt`).

**Result.**

| Prediction | Measure | Task | Basket owner | Verdict |
|---|---|---|---|---|
| 1 | written skills retired | 3 of 28 | 0 of 16 | met, at the threshold (3) |
| 2 | success in the written skills' situations, per life, authoring minus control | +0.075 [+0.038, +0.112], 13 of 14 lives higher | +0.104 [−0.018, +0.225], 8 of 11 higher | met |
| 3 | fall rate there, per life | +0.002 [−0.009, +0.013] | −0.029 [−0.084, +0.025] | met |
| 4 | the owner's measure (toys gained in the basket), rooms 11 to 20 | | +0.09 [−0.16, +0.34], 6 higher, 5 lower | met |
| 5 | kept; kept skills after they were kept, per life | 5 kept in 4 lives; +0.12 [−0.06, +0.31], 3 of 4 higher | 1 kept, no outcomes after | reported |

- *Most trials did not finish.* Of 44 written skills, 6 were kept, 3
  retired, and 35 were still on trial when their life ended (20 of 28 in
  the task setting, 15 of 16 with the owner). Turns until each side has 8
  outcomes take most of a life where the situation comes up a few times a
  room, and with the owner it comes up less often.
- *The retired skills were worse than their parents in their trials* (6 of
  15 against 12 of 19, 7 of 10 against 13 of 14, 7 of 20 against 18 of
  31). One kept skill did worse than the control life after it was kept
  (life 174, picks of toys tried before: 45% of 11 against 75% of 12) and
  was still under review at the end.
- *No written skill was built on another.* The duck never asked again
  about a situation where a skill was kept, so the mechanism was not
  exercised (nor in development).
- *Far deliveries* again gained the most: +0.11 [+0.02, +0.20] in the
  task setting (11 of 13 lives), +0.15 [+0.04, +0.25] with the owner (8 of
  10).
- *Unexpected: in the task setting the whole room did slightly worse.*
  Toys in the basket, rooms 11 to 20, were −0.11 [−0.22, −0.004] (7 lives
  lower, 2 higher, sign-flip p = 0.06; E-019: −0.006). Falls were
  unchanged (+0.00). The event logs point to time. A written far delivery
  ends in `done` more often than the original there (69% of 247 against
  55% of 709 in the control arm), but takes longer: 24.2 s against 17.4 s
  a try, 35.0 s against 31.8 s per `done`. Rooms last 300 s and the task
  policy nearly finishes (5.4 of 6), so seconds spent are toys lost. With
  the owner, where the duck has time to spare, there was no such cost.

**Analysis.** With fair trials the gain holds. In the situations the
skills were written for, success rose by 7 to 10 points per life against
the same rooms with the original skills, with no more falls, in both
settings. Judging is now honest: the skills retired were worse in their
trials, and E-019's generous keeping is gone (6 of 44 kept, against 15 of
27). Judging is also slow: most trials were undecided at the end of a
20-room life, so in practice the duck spent its life alternating between
the two skills. That alternation costs little success here, because the written
skills mostly do better.

The trial scores a skill by success per try, and the room rewards success
per second. A skill that succeeds more often but takes longer can win its
trial and cost the room a toy. This showed in the task setting, where time
is short; it is a small effect (a tenth of a toy a room, CI just below
zero) and was not predicted.

**Decision.** Milestone 5a is met: keep decisions are judged on fresh
outcomes, and authoring helps in its situations with an owner as well as
with a task. Keep the 5a trial rule. Two things are left for authoring:
score trials by what the room rewards, success per unit of time where time
is short (H-021); and shorten the turns phase, or let it end early when
the difference is clear, so trials finish within a life.

### E-019 · 2026-11-04 · Milestone 5: skills written by the cloud brain (pre-registered)

**Question.** Can the cloud brain write skills, in the bounded skill
language, that do better than the hand-written ones where those fail, and
keep only those that do, on measured merit (H-006's real test)?

**Design** (`authoring.py`). After each room the duck reflects.
- *Finding a weakness.* It looks for the compound skill and condition with
  the most negative effect on the expected effect (at least 2 posterior
  sds, at least 8 outcomes, success at most 60% there), using the
  Milestone 4 rules.
- *Asking.* Claude Sonnet 5.5 (Bedrock) is shown the skill's program, the
  condition, the success rate there and elsewhere, how those tries ended
  (status and reason, counted), the language, and the primitives. It
  answers with a tool call holding a program.
- *Checking.* Local code checks it: constructs, known skills and
  arguments, bound names, relation arities, no self-call. The written skill
  takes its parent's parameters and expected effect. A refused program
  gets one retry with the reason.
- *Trial.* Whenever the parent is about to run in that situation, the duck
  chooses between parent and written skill by Thompson sampling on success
  (the effect held, no fall). The parent's past outcomes there count as a
  prior worth at most 10 trials, since the situation was chosen for looking
  bad. After 8 trials the written skill is kept when better with
  probability 0.9 and retired when worse with probability 0.9.
- Behaviour is otherwise the task-driven local policy (explicit tidy goal),
  which gives the most skill runs per room. The cloud brain only writes
  skills.

**Development** (lives 0 to 7; rows, report and the written skills in
`experiments/E-019-authoring/`).
- *Ten rooms were too few.* Skills were written after rooms 6 to 10,
  leaving most with no trials.
- *The parent's prior was biased.* Its full past counts entered the trial,
  biased low because the situation was picked for its failures. They now
  count at most 10 trials.
- *A written program called `seen_since` with the wrong arity* and
  crashed the run. Arity is now checked at load, so the author is told,
  and any run-time error inside a skill fails that skill.
- *Lives of 20 rooms.* 12 skills were written in 8 lives, all accepted,
  and 8 were kept. In each written skill's situation after it was
  written, success in the authoring life against the control life (same
  rooms, original skill) was +0.20 [+0.10, +0.31], higher in 9 of 12
  situations, with falls unchanged (−0.008). In rooms 11 to 20, failed
  picks fell by 0.56 a room [−1.01, −0.11] (first reported as −0.83; see
  *Review* below), and toys in the basket were unchanged (−0.01 [−0.19,
  +0.17]).
- The skills written are sensible and specific. For far deliveries:
  approach in stages and re-sight the basket mid-way ("the belief is fresh
  before the final approach"). For picks of toys not seen recently: walk to
  a middle distance, pause, re-observe, look around if lost, then pick.
  Most targeted the two failures the rules found in E-017: far deliveries
  and stale positions.

**Predictions, written before the held-out runs** (lives 144 to 159,
rooms 14401 to 15920, 20 rooms each, control and authoring arms on the same
rooms, paired by life):
1. At least one written skill is kept in at least 10 of 16 lives.
2. In the situations skills were written for, after they were written,
   success (the expected effect held and the duck did not fall) is higher
   in the authoring life than in the control life: mean difference with CI
   lower bound above 0.
3. The fall rate in those situations is not higher: CI upper bound below
   +0.03.
4. Failed pick decisions per room, rooms 11 to 20, authoring minus
   control: CI upper bound below 0.
5. Toys in the basket, rooms 11 to 20: CI lower bound above −0.3.
6. Reported, with no prediction: requests, refusals, retirements, tokens,
   and the situations chosen.

**Method.** Commit `d527b27`. Both arms:
`birdbrain-run --seeds 16 --seed0 144 --episodes 20 --seconds 300 --jobs 5 --tag e019-<arm> --memory data/lifetimes/e019-<arm>`,
with `--author` for the authoring arm. 640 rooms. Report:
`scripts/skills_report.py ctl.jsonl auth.jsonl --lives data/lifetimes/e019-auth --control-lives data/lifetimes/e019-ctl --late 11`
(`report.txt`).

**Result.**

| Prediction | Measure | Result | Verdict |
|---|---|---|---|
| 1 | lives with a kept written skill | 11 of 16 | met |
| 2 | success in the written skills' situations, authoring minus control | +0.079 [+0.005, +0.152] over 26 situations, 15 higher; per life (outcomes pooled, each once) +0.104 [+0.024, +0.183], 10 of 14 higher | met |
| 3 | fall rate in those situations | +0.002 [−0.010, +0.014] | met |
| 4 | failed pick decisions per room, rooms 11 to 20 | −0.05 [−0.31, +0.21], 6 of 16 lower, p = 0.72 (first reported as −0.36; see *Review*) | missed |
| 5 | toys in the basket, rooms 11 to 20 | −0.006 [−0.15, +0.14] | met |

- *Requests.* 27, all accepted on the first or second try. 15 skills were
  kept, 1 retired, and 11 were still on trial when their life ended. The
  author used 107k tokens over 16 lives.
- *Situations chosen.* Far deliveries (15 of 27 requests), picks of toys
  tried before (4), picks of toys with vague or stale positions (6), and
  picks of toys at mid or far distance (2). These are the failures the
  E-017 rules found.
- *Far deliveries.* Success rose +0.13 [+0.03, +0.23] against the control
  life (first request per life; 8 of 14 lives higher). The gain is large in some lives (82%
  against 49%; 86% against 59%; 87% against 58%) and absent in others.
  The written programs differ from life to life; the best approach the
  basket in stages, re-sighting it mid-way.

**Analysis.** The cloud brain, shown a failure the duck had measured and
nothing more, wrote programs in the bounded language that did better in
that situation than the hand-written skill, in the same rooms. The duck
kept the good ones on its own evidence and retired one bad one. H-006 is
supported, and Milestone 5's exit test is met: a skill the cloud brain
wrote was kept on measured merit and did its job better where the original
failed.

The effect on the whole task is small. Toys in the basket were unchanged,
because the task policy already tidies 5.4 of 6 toys and a failed
delivery is usually retried. Failed picks did not change (−0.05 a room).

Two caveats:
- *Keep decisions are generous.* They compare the written skill's trial
  outcomes with a parent prior drawn from the outcomes that made the
  situation look bad (shrunk to 10 trials). Two kept far-delivery skills
  did no better than the control life (50% against 59%; 41% against 42%).
  The unbiased measure is the comparison with the control life, which the
  predictions used.
- *The comparisons are within this task and room family.*

**Decision.** Keep authoring as an option (`--author`). Next: judge keep
decisions against outcomes after the request, not the biased prior; let a
kept skill become the parent for its situation; and try authoring in the
owner arms, where situations are rarer and a written skill matters more.

**Review** (after the results; `semantic-review/2026-11-04-013551-pr-local.md`).
The success and fall results reproduce from `data/lifetimes/e019-*`. No
truth reaches the authoring prompt, and defaults reproduce the control
arm's rows exactly (life 144, rooms 1 to 3, after the fixes). Findings
and fixes:
- *The failed-pick measure missed written variants.* `pickDecisionsFailed`
  counted depth-0 actions named `pick`, so a pick run as `w_pick_*`
  disappeared. Recounted from the event logs (`skills_report.py --runs`),
  pick decisions are 8.08 and 8.06 a room in the two arms and failed picks
  −0.05 [−0.31, +0.21], not −0.36. Development: −0.56, not −0.83. Fixed:
  a written skill's action events carry `variant_of`, and the measure
  counts them (`report_reviewed.txt`).
- *Give-up and `target tried before` missed them too.* `failures(pick, x)`
  did not count a `w_pick_*` that copies pick's body, so a toy could be
  tried past three failures. Fixed in `relations.tries`: a variant's run
  is a try of its parent, and a pick nested inside it is the same try.
  This changes the authoring arm's behaviour; E-019's rows predate it.
- *Overlapping trials.* The first matching trial took every run where two
  conditions of one parent held, starving the second (life 150: 3 runs in
  10 rooms). Now every matching trial draws, the highest written draw runs
  if it beats the parent, and a parent run counts in all of them.
- *Malformed programs crashed a run.* `"args": []` crashed the check at the
  end of a room, before memory was saved; a non-string `if`, `until` or
  `to` passed the check and crashed the next room. The check now refuses
  them. All 27 held-out programs (and the development ones) still pass.
- *A written skill calling another could fail to load.* Skills were loaded
  in name order, so a caller sorting before its callee was retired on the
  next room. They now load in dependency order.
- The 26 situations overlap within a life (and life 157 asked about far
  deliveries twice), so the per-life figure, with each outcome counted
  once, is now computed by the script and is the one to quote. The
  situation counts above were corrected (15/4/6/2).
- Still open: a kept skill is never re-reviewed, so the two kept
  far-delivery skills that did no better than control stay in use.

### E-018 · 2026-11-03 · Milestone 4a: rules that steer (development, both refuted)

**Question.** Does choosing by a posterior draw from the rules, in place of
their mean, turn better predictions into better choices (H-018)? Does
learning the owner's reactions over conditions, with a finer wall-distance
condition (under 0.1, 0.1 to 0.2, 0.2 to 0.3, 0.3 to 0.5, over 0.5 m), in
place of hand-chosen kinds, reduce toys lost to picks (H-017)?

**Design.** `--rules draw` draws one model per skill and decision from the
Laplace posterior and evaluates every candidate with it.
`--owner-model conditions` logs every action with its features. EM
alternates credit with a refit of two logistic models (approval,
disapproval) on soft outcomes. The default configuration reproduces E-017
round 2 decision for decision (checked on 6 episodes).

**Development** (lives 0 to 7, four owner arms, ten rooms; each variant
minus the baseline, rooms 6 to 10, paired by life, n = 8; rows and tables
in `experiments/E-018-steer/`):

| Owner | Draws: own measure | Draws: falls | Conditions: own measure | Conditions: toys lost to picks |
|---|---|---|---|---|
| None | −0.30 [−0.96, +0.36] | +0.08 | −0.15 | 0 |
| Basket | −0.35 [−2.14, +1.44] | +0.38 [+0.10, +0.65] | −0.43 [−1.13, +0.28] | 0 |
| Wall | −1.43 [−3.01, +0.16] | +0.13 | −1.53 [−3.34, +0.29] | −0.43 [−1.48, +0.63] |
| Leave-it | −0.13 [−0.93, +0.68] | +0.05 | −0.93 [−1.45, −0.40] | +2.65 [+1.42, +3.88] |

Both together were no better than either.

**Analysis.**
- *Draws explore where it is dangerous.* Toys inside the basket by the
  rim are rarely tried, so their posterior is wide, and draws sometimes
  make them look good. In the basket arm's late rooms the duck picked such
  toys 19 times (against 2 under counts); one succeeded and 10 fell.
  Thompson sampling did what it is built to do, but exploration here is
  paid in falls, and a life of ten rooms is too short to recoup it. The
  optimizer's curse (L-020) is real, but trading it for unbounded
  exploration is worse.
- *Conditions dilute a simple preference.* The leave-it owner dislikes
  every pick. The kinds model learns that from three kinds and quickly. The
  condition model spreads the same evidence over a dozen features, its
  shrinkage holds the pick effect back, and the duck kept picking (1.9
  failed picks a room against 0.4). The finer wall condition did not
  measurably reduce lost toys in the wall arm.

*Cautious* (H-020, tested afterwards on the same lives): draws for the
expected effect, falls judged by mean + 2 sd on the log-odds. The duck
nearly stopped picking (0.1 failed picks a room, from 1.2 to 2.1), so the
basket and wall owners' measures fell to 0.0 and 0.35 (−3.15 and −4.30,
8 of 8 lives lower) while the leave-it owner gained (+0.78). Early in a
life every fall estimate is uncertain, so an upper bound makes every pick
look dangerous. H-020 is refuted as specified (`caut_vs_base.txt`).

**Decision.** None of the three changes goes to a held-out round; there is
no supported prediction to pre-register. Both remain as options. Next:
explore safely, by drawing for the expected effect while judging falls
pessimistically (an upper credible bound), and give the condition model a
skill-level prior learned across lives, so a simple preference is learned
as fast as with kinds.

### E-017 · 2026-11-03 · Milestone 4: causal rules predict outcomes (pre-registered)

**Question.** Do rules learned from the duck's own outcomes, under conditions
it believes hold, predict those outcomes better than the counts per skill
that the scorecard has used since Milestone 1 (H-019)?

**Design** (`rules.py`). Before every action the mind describes the
situation with coarse features computed from beliefs: where the target is
(basket, wall, open), its distance, whether its position is precise,
how recently it was seen, whether a pick on it failed before, whether it
is by the basket rim or a wall, whether the duck holds something, how
precise and how far the basket is, and whether the duck is by a wall. For
each skill and outcome (the expected effect holds; the duck falls), a
Bayesian logistic model gives the log-odds as a base rate plus one effect
per condition, each effect a deviation from the average situation with
prior N(0, 0.5²). It is fitted at its posterior mode after each outcome. A
rule is credible when its effect is at least two posterior standard
deviations from zero; credible rules are listed in the briefing as
sentences. Each prediction is recorded before the action runs and scored
when it ends (prequential evaluation), next to the count per skill and,
where it exists, the count per kind of action. Actions whose expected
effect is `true` cannot fail and are not scored for effects.

**Development** (lives 0 to 3, all four owner arms).
- *Trees first.* A Bayesian decision tree that splits a rule on the
  feature with the largest Bayes factor (at least 10) rarely split: a life
  holds a few dozen picks, and splitting the data leaves too little per
  branch. Its Brier score equalled the counts' (0.1703 against 0.1703 on
  replayed outcomes). Pooled over 32 lives, the conditions do matter: picks
  of a toy by the basket rim held 13% of the time against 78% elsewhere,
  and deliveries from far 53% against 87%.
- *Additive effects.* A logistic model estimates every condition's effect
  from all of a skill's outcomes at once. Replayed on the same outcomes,
  it scored 3.4% better than counts (0.1645 against 0.1703), and best with
  an effect prior of 0.5 (0.3: −2.8%; 1.0: −1.2%). Newton's method needed
  damping, and conditions are centred so that effects do not trade off
  against the base rate.
- In live development lives, late in life: rules 0.177 against counts
  0.185 (paired difference −0.008, CI −0.014 to −0.003, 11 of 16 lives
  better) and against counts per kind 0.187. For falls, the three were
  equal to three decimals.
- *Deciding with rules* (`--rules`) changed behaviour unevenly on four
  lives per arm: the basket owner's toys gained +1.0, the wall owner's
  −1.65, and falls in the basket arm rose from 0.2 to 0.6 a room. This is
  not yet a basis for a prediction.

**Predictions, written before the held-out runs** (lives 96 to 111, all
four arms, 10 rooms; prediction scores from the arm that decides with
counts, so the rules being scored do not steer what is predicted;
late = rooms 6 to 10; paired by life, n = 64):
1. The rules' Brier score on expected effects is lower than the counts per
   skill (CI upper bound below 0).
2. It is also lower than the counts per kind of action (CI upper bound
   below 0).
3. For falls, the rules are no worse than counts per skill (CI upper bound
   at most +0.0005).
4. Reported, with no prediction: the credible rules found in at least half
   of the lives; deciding with rules against deciding with counts on the
   same lives (each owner arm's own measure, falls).

**Method.** Commit `8725cdf`. For each arm, two runs on lives 96 to 111:
`birdbrain-run --owner <arm> --episodes 10 --seeds 16 --seed0 96 --tag e017-counts-<arm>`
and the same with `--rules` (`e017-rules-<arm>`). 1,280 episodes. Scores:
`scripts/predictions.py`; behaviour: `scripts/lifetimes.py`; rows and
summaries in `experiments/E-017-rules/`.

**Result** (prediction scores from the arm deciding with counts; late =
rooms 6 to 10, per life, paired, n = 64).

| Prediction | Measure | Rules | Counts | Rules minus counts [95% CI] | Verdict |
|---|---|---|---|---|---|
| 1 | Brier, expected effects, against counts per skill | 0.1523 | 0.1575 | −0.0052 [−0.0083, −0.0022], 42 of 64 lives better | met |
| 2 | ... against counts per kind of action | 0.1523 | 0.1580 | −0.0057 [−0.0093, −0.0020], 44 of 64 better | met |
| 3 | Brier, falls, against counts per skill | 0.0037 | 0.0037 | +0.00006 [+0.00001, +0.00011] | met (within +0.0005), slightly worse |

On falls, the rules were worse than counts per kind of action (+0.00021
[+0.00017, +0.00025], 62 of 64 lives worse). In the counts arm, the counts
per kind also chose the approval arms' picks, which should handicap them,
not the rules. In the arm that decided with rules, so that the rules
steered and were scored, they again beat both counts on expected effects
(against counts per skill −0.0061 [−0.0093, −0.0029]; per kind −0.0050
[−0.0089, −0.0011]; n = 63), beat counts per skill on falls (−0.00024
[−0.00036, −0.00011]), and lost to counts per kind on falls (+0.00021,
50 of 64 lives worse).

*Conditions.* No condition reached two posterior standard deviations in
any single life: a life holds 30 to 70 picks, and the prior holds each
effect near zero until the evidence is strong. The directions, though, were
consistent across lives (`condition_effects.txt`). A pick's expected
effect was less likely when the toy was by the basket rim (negative in 52
of 55 lives), in the basket (58 of 64), or last seen a while ago (51 of
64). A delivery was less likely to land from far away (34 of 53).

*Deciding with rules* (exploratory, same lives, rules minus counts):

| Owner | Own measure | Falls per room | Failed picks per room |
|---|---|---|---|
| None (basket gain) | +0.06 [−0.23, +0.35] | +0.11 [+0.02, +0.21] | +0.33 [+0.11, +0.54] |
| Basket | −0.11 [−1.57, +1.35] | +0.14 [−0.02, +0.29] | +0.46 [−0.17, +1.10] |
| Wall | −0.20 [−1.15, +0.75] | +0.13 [−0.02, +0.27] | +0.10 [−0.57, +0.77] |
| Leave-it | +0.01 [−0.35, +0.37] | +0.06 [−0.05, +0.18] | +0.18 [−0.22, +0.57] |

**Analysis.** The rules predict the duck's own outcomes better than the
counts it has used since Milestone 1, on outcomes they had not seen, in two
thirds of lives. The gain is small (3 to 4% of the Brier score) because a
life is short and most conditions matter modestly, but it is consistent,
and the conditions it finds are the ones the development diagnosis found
by hand. Milestone 4's exit test, as written in the roadmap, is met.

Deciding with the rules made things slightly worse: falls and failed picks
rose in every arm, significantly in the control. A likely mechanism is the
optimizer's curse: when the duck chooses among up to six toys by their
predicted means, the most optimistic prediction is disproportionately the
most wrong. Counts per skill give every toy the same probability (counts
per kind differ only by where the toy is), so they offer less to be fooled
by. This is a hypothesis (H-018), not a finding of this experiment.

**Decision.** Keep the rules for prediction, surprise, and the briefing.
Decisions keep the counts by default (`--rules` remains an option). Next:
decide with posterior draws from the rules (H-018), and use the same rules
for the owner's reactions (H-017).

**Review** (critic pass over `e0c955d..61741e9`; fixes in the next commit).
It reproduced the Brier numbers from the rows and found no leakage. It
found these problems, now fixed:
- *No condition could become credible.* Every value of a feature had its
  own centred weight. Those weights sum to zero across a feature's values,
  so the prior alone fixes one direction and each value's sd stayed at
  least 0.5/√K whatever the data. An odds ratio below about 4 could never
  pass. Credibility now tests a value's contrast against the other values
  of its feature, using the full posterior covariance. The odds reported are
  that contrast. The threshold is 3 sd, because a skill is tested against a
  dozen conditions at once. "No credible rule in any life" above, and the
  explanation given for it, are artifacts of the old test.
- *Episode ends were learned as failures.* The action cut off when an
  episode ended (or by the battery reflex) was scored and learned as a
  failure of its skill. Far deliveries are cut off most often, so the rules
  could partly learn the clock. Interrupted actions are no longer scored or
  learned.
- *Training and prediction encoded a missing feature differently.* Both
  now treat it as average.
- *Credit by moments counted an action once per moment.* It now counts
  each action once.
- *With `--rules`, `p_rule` changed meaning.* It no longer does; the
  rules' forecast is in `predicted`.
- *Claims:* falls against counts per kind, the counts arm's per-kind
  steering, the untested optimizer's-curse explanation, and E-016's "costs
  nothing" are corrected above.
- *Reproducibility:* `scripts/rules_report.py` produces the condition
  effects, credible rules, and deciding-with-rules comparisons; E-016's
  development rows are committed.

**Round 2 predictions.** The fixes change what is learned and scored, so
round 2 uses fresh lives 112 to 127, with predictions 1 to 3 unchanged, and
reports credible rules and deciding with rules as before.

**Round 2 result** (commit `ec94ad4`; rows `r2_*.jsonl`, scores
`r2_predictions_*.txt`, rules and decisions `r2_rules_report.txt`; 1,280
episodes; late = rooms 6 to 10, per life, paired, n = 64).

| Prediction | Measure | Rules | Counts | Rules minus counts [95% CI] | Verdict |
|---|---|---|---|---|---|
| 1 | Brier, expected effects, against counts per skill | 0.1284 | 0.1348 | −0.0064 [−0.0095, −0.0033], 42 of 64 better | met |
| 2 | ... against counts per kind of action | 0.1284 | 0.1335 | −0.0052 [−0.0103, −0.0001], 44 of 64 better | met, narrowly |
| 3 | Brier, falls, against counts per skill | 0.0049 | 0.0051 | −0.00015 [−0.00040, +0.00009] | met |

Against counts per kind, the rules were again worse on falls (0.0049
against 0.0047; +0.00020 [+0.00014, +0.00026], 57 of 64 lives worse). In
the arm that decided with rules, they beat counts per skill on both
outcomes and counts per kind on expected effects (−0.0053 [−0.0105,
−0.0002]), and lost to counts per kind on falls (+0.00025).

*Conditions.* Even with the corrected test, no condition reached 3
posterior sds in any single life. The contrasts agree in direction across
lives and are larger than round 1's, now that truncated actions are not
counted as failures:
- A pick's effect is less likely when the toy is by the rim (median −0.37
  on the log-odds, lower in 52 of 55 lives), in the basket (−0.27, 59 of
  64), or last seen a while ago (−0.23, 48 of 64).
- A delivery from far away fails more often (−0.30, 41 of 49).
- A pick by the rim is more likely to end in a fall (+0.46, higher in 48
  of 55 lives).

*Deciding with rules* (rules minus counts, same lives): own measures
none +0.00, basket −0.50 [−1.44, +0.44], wall −0.28 [−1.69, +1.14],
leave-it −0.28 [−0.67, +0.12]. Falls rose in every arm, significantly
in the wall arm (+0.13 [+0.05, +0.20]). Failed picks rose in every arm.

**Analysis (both rounds).** The prediction result replicates on fresh lives
with the corrected learner: rules over conditions predict whether a skill's
expected effect holds 4 to 5% better than counts, and the conditions they
weigh are the ones the development diagnosis found by hand. Falls are rare
(about one in a hundred actions). The rules match counts per skill on
falls but lose slightly to counts per kind, which split picks by where the
toy is, the one condition that matters most for falls. Effects within a
single life stay below 3 sds: they are real across lives but modest within
one. Choosing by the rules' means is worse in both rounds, consistent with
H-018. Milestone 4's exit test is met for expected effects.

### E-016 · 2026-11-03 · Milestone 3c: credit timing and rim falls (development, refuted)

**Question.** H-016 said the wall-arm duck re-moves toys from walls because
the action that follows a change takes the credit for her reaction. H-011
said falls at the basket rim come from the delivery's sidestep.

**Measuring the mechanism.** Two truth measures were added for evaluation:
the share of credit the duck gives to the kind of action it was doing when
the change she answered happened (`creditToCause`), and the toys she liked
that were lost to a pick (`lostByPick`) or otherwise (`lostOtherwise`).

**Credit timing.** A reaction answers a change, and the duck changes the
room at moments its body senses: a grasp, a release, a bump. The new rule
credits those moments in the window, or an action's end if it changed
nothing (`--credit moments`); the old one credits any action under way
(`--credit underway`). On lives 0 to 3:

| Owner | Credit to the true cause, under way | Credit to the true cause, moments | Own measure, late (under way / moments) |
|---|---|---|---|
| Basket | 0.84 (51 reactions) | 0.86 (49) | 2.95 / 2.85 |
| Wall | 0.79 (153) | 0.80 (147) | 5.20 / 5.20 |
| Leave-it | 0.60 (83) | 0.64 (58) | 4.90 / 4.65 |

The old rule already gave 79% of the credit to the true cause in the wall
arm. On eight more lives (4 to 11) the wall owner's disapprovals fell
from 1.45 to 0.80 a room with moments, but toys against walls fell too (4.13
to 3.28, p = 0.055). Credit timing is not what drives the wall arm's lost
toys.

**What does.** A probe on four learned lives (`scripts/owner_pick_probe.py`) traced 35 picks, 8 of toys she liked. In 5
the duck knew the toy was by a wall and picked it anyway: its category
"pick from wall" (0.25 m) is coarser than hers (0.2 m), so on average the
category is only mildly disliked (about −0.2), and the put that follows is
liked (+0.43). In the other 3 the duck believed the toy 0.19 to 0.36 m
from where it was. Widening the duck's "by a wall" by two standard
deviations of the toy's position, as `inside` does for the basket, did
not reduce toys lost to picks (+0.18, CI −1.16 to +1.51) and was reverted.

**Rim falls.** All 101 falls in E-015 round 2 happened within 0.3 m of the
basket rim (from the last pose snapshot before each): among them 27 in
the delivery's sidestep, 26 standing before a ground pick, 13 in the
ground pick, and 8 opening the beak to drop. Two changes to the
delivery were tried on 32 rooms (1000 to 1031) with the task policy:
- stepping back instead of sideways: 3.7% of deliveries fell against
  4.1%, with 0.4 fewer toys;
- stopping 3 cm further out: 0.8% fell, but toys missed the basket and
  tidying fell by 1.69 toys a run (CI −2.11 to −1.26).
Both were rejected. The lab's measured approach is the best available, and
the rest of the risk is in which toys the duck chooses to pick, which
Milestone 4's rules can see ("pick when target by the rim").

**Decision.** H-016 is refuted. The moment rule is kept as the default
because it is the correct definition of a reaction's possible causes and
gave slightly more credit to the true cause in all three arms. Its effect
on behaviour is unsettled: equal on lives 0 to 3 in the wall arm (5.20
toys against walls either way), lower on lives 4 to 11 (3.28 against 4.13,
p = 0.055). Rows are in `experiments/E-016-credit/`. H-011's
sidestep diagnosis is refuted; rim falls are a property of the body and of
the choice of target. Next: learn the reaction model's conditions instead
of hand-chosen kinds (the same rules as E-017), so "by a wall" can be as
fine as the owner's.

### E-015 · 2026-11-03 · Milestone 3b: learning what the owner wants (pre-registered)

**Question.** If the duck's only social need is its owner's approval, and
the owner says only whether she approves, does the duck learn what she
wants (H-015)?

**Design** (docs/design.md section 4.3).
- Needs: energy, curiosity, safety, and approval (the duck's estimate of
  her mood). Tidiness is removed. The briefing never says what the room
  should look like.
- The owner's phrases come from `src/birdbrain/phrases.toml` (approval or
  disapproval only). A scripted owner with a hidden preference reacts 1 to
  5 s after a change she cares about, with probability 0.6, and 10% of
  phrases are misheard as the opposite list.
- Three ways of putting a toy down are offered side by side: `deliver`
  (into the basket), `put_by_wall`, and `drop` (where the duck stands).
- The duck credits each reaction to the actions under way 0.5 to 8 s
  before it, or to nothing, and re-explains its whole history by EM
  (`reactions.py`). It chooses by Thompson sampling from those beliefs.
- A lifetime is 10 episodes of 300 s, each a different room, with skill
  records and owner beliefs kept between episodes.

**Arms**, 16 lifetimes each, the same rooms in every arm: no owner (the
control); an owner who likes toys in the basket; one who likes toys
against the walls (within 0.2 m, not in the basket); one who likes toys
left where they were.

**Development** (lifetimes 0 to 3, not used for the verdict).
- *An exploration bonus never let go.* A first version scored each kind
  of action by its expected reaction plus a bonus for uncertainty (the
  scorecard's IG term). The duck made 10 to 14 picks an episode in every
  arm, including the control, and fell 1 to 2.75 times an episode picking
  toys it had put by walls. Replaced by Thompson sampling: each decision
  values every kind by one draw from its posterior. The control's picks
  fell to 3 to 6 an episode and its falls to 0 to 0.5.
- *Draws must last a pick and its put.* Redrawing at every decision made
  the duck pick a toy because one way of putting it down looked good, then
  put it down another way. Draws are now kept while the duck holds a toy.
- *Online credit is stuck with its first guesses.* Splitting each reaction
  once, by the probabilities at the time, left an action that merely
  followed deliveries with 0.17 expected approval. Re-explaining the whole
  history by EM on every reaction fixed it in a synthetic test (below 0.1),
  and the basket arm reached 5.5 toys gained by episode 10, against 3.75
  without EM.
- *Falls depend on where.* Picks by a wall fell often, so success and fall
  rates are now counted per kind of action ("pick from wall"), not per
  skill.
- *Scale.* The approval weight is 4: with 2, one certain approval was worth
  less than the time a pick and put take, and the basket arm hardly
  delivered.
- *Five episodes were too few.* The learning curves rise until episodes 6
  to 8, so the lifetime is 10 episodes, and the verdict uses episodes 6 to
  10.
- *The leave-it owner approves putting a toy back.* She reacts to every
  change, so a pick she dislikes followed by a drop on the same spot earns
  "no" then "nice". Pick-and-drop is close to neutral for her, and picks
  do not halve. The planned prediction 4 (picks halve) does not follow
  from her preference as scripted; it is replaced below by her own measure.
- Dev result (episodes 6 to 10, owner arm minus control, 4 lifetimes):
  basket gain +3.7, at wall +3.45, unmoved +1.3. The duck's beliefs single
  out the right kind of action in 12 of 12 owner lifetimes.

**Predictions, final, written before the held-out runs** (lifetimes 48
to 63, rooms 4801 to 6310; per lifetime, the mean over episodes 6 to 10;
arms paired by lifetime):
1. Control: on average at most 1.5 toys gained in the basket and at most
   1.5 against walls per episode. Without an owner, the duck does not
   tidy.
2. Basket owner: at least 3.5 toys gained in the basket, and at least 2.0
   more than the control (CI lower bound above 0).
3. Wall owner: at least 3.0 toys against walls, and at least 2.0 more than
   the control (CI lower bound above 0).
4. Leave-it owner: at least 0.5 more toys unmoved than the control (CI
   lower bound above 0).
5. Specificity: each owner arm's own measure is higher than in both other
   owner arms (CI lower bound above 0). The duck learns *her* preference,
   not a generic busyness.
6. Approvals per minute in the last two episodes exceed those in the first
   two, in the basket and wall arms.
7. At the end of life, the kind of action the duck believes most approved
   is `deliver` in at least 12 of 16 basket lifetimes and `put_by_wall` in
   at least 12 of 16 wall lifetimes. The kind it believes most disapproved
   is a pick in at least 12 of 16 leave-it lifetimes.
8. Reported, with no prediction: picks and falls per episode, the leave-it
   arm's approval rate, and a small cloud-brain arm.

**Method.** Commit `01798e7`. For each arm:
`birdbrain-run --seeds 16 --seed0 48 --episodes 10 --seconds 300 --owner <arm> --jobs 4 --tag e015-<arm> --memory data/lifetimes/e015-<arm> --out experiments/E-015-approval/<arm>.jsonl`.
Summary: `scripts/lifetimes.py experiments/E-015-approval/{none,basket,wall,leave}.jsonl`
(saved as `summary.txt`). 640 episodes.

**Result** (episodes 6 to 10, per lifetime, paired by lifetime; n = 16).

| Prediction | Measure | Result | Verdict |
|---|---|---|---|
| 1 | control: toys gained in the basket; against walls | 0.75; 0.81 | met |
| 2 | basket owner: toys gained in the basket | 3.49 | missed by 0.01 (≥ 3.5) |
| 2 | ... minus control | +2.74 (CI +1.82 to +3.65), 14 of 16 higher | met |
| 3 | wall owner: toys against walls | 3.83 | met |
| 3 | ... minus control | +3.01 (CI +2.19 to +3.84), 14 of 16 higher | met |
| 4 | leave-it owner: toys unmoved, minus control | +1.04 (CI +0.64 to +1.44), 14 of 16 higher, 2 equal | met |
| 5 | own measure above both other owner arms | all six CIs above +1.9 | met |
| 6 | approvals per minute, first two episodes to last two | basket 0.12 to 0.45; wall 0.11 to 0.90 | met |
| 7 | belief singles out the right kind | `deliver` 16 of 16; `put_by_wall` 14 of 16; a pick most disapproved 12 of 16 | met (the last at the limit) |

Learning curves (toys gained in the basket for the basket owner, against
walls for the wall owner) rise from about 1 in episode 1 to 3.6 and 4.1
by episode 8 (4.4 for the wall owner by episode 9), and level off. The
leave-it arm has no such curve: its unmoved toys stay at 3.9 to 4.8, at or
above the control in every episode. The control stays below 1 throughout. Late
episodes: falls per episode 0.20 (control), 0.44 (basket), 0.05 (wall),
0.10 (leave-it); picks per episode 4.95, 6.92, 10.29, 5.30.

**Analysis.** From phrases that say only whether, and three neutral ways
of putting a toy down, the duck learns the basket and wall owners'
preferences within about 6 to 8 rooms (+2.7 and +3.0 toys over the
control), and it does not tidy when nobody is there. Each owner arm's own
measure beats both other owner arms by 2.8 to 3.6 toys, so this is her
preference being learned, not a general urge to move toys. The leave-it
effect is smaller (+1.0) and appears from the first room, which points to
disapproval suppressing picks within a room more than to learning across
rooms. Prediction 2 missed its absolute threshold (3.49 against 3.5);
every comparison held.

The review after these runs (below) found that the approval need did not
yet act as a need: the duck's estimate of her mood was computed and
logged, but the value of a reaction did not depend on it. So round 1
shows learning a preference from approval, not that a need for approval
drives it. H-015 is partly supported by round 1; round 2 tests the
corrected need on fresh lifetimes.

Two findings to follow up:
- *Churn by the wall.* The wall arm makes about 10 picks an episode and
  hears 0.39 disapprovals a minute late in life. It picks toys that are
  already against a wall and puts them by a wall again. The owner
  disapproves of the pick and approves of the put, which is net zero.
  But at the end of life the duck believes `pick from wall` costs −0.24
  and `put_by_wall` earns +0.31. The disapproval after a pick usually lands while the
  following put is under way, so the put takes part of the blame and the
  pick too little. The credit model does not know that her reaction
  answers a change that has already happened. Candidate fix: credit a
  reaction to actions whose *end* precedes it, or learn the reaction delay.
- *The leave-it owner* is the hardest: a pick she dislikes followed by a
  drop on the spot earns "no" then "nice", so the lesson is only half
  there (the most disapproved kind is a pick in 12 of 16 lives).

**Cloud brain** (exploratory, prediction 8; commit `499845d`, lifetimes 48
and 49, 5 episodes, `--provider bedrock`; rows `cloud_*.jsonl`, summary
`cloud_summary.txt`). Over 1,026 decisions there were no invalid choices
and no fallbacks, at 82k to 95k tokens per episode. The cloud brain reads
the same beliefs in its briefing and learns faster:
- Basket owner: 3 toys gained in episode 1, 5 to 6 by episodes 3 and 4.
  Its first delivery was framed as an experiment: "delivering it tests
  whether my owner likes toys in the basket".
- Leave-it owner: by episode 3 it had nearly stopped picking (0 to 1 picks
  an episode), and all 6 toys stayed unmoved in episodes 3 to 5. Its
  reasons: "picking toys from the open has so far drawn disapproval, so
  I'll stay still and not risk annoying her". The local policy never got
  there.
- Wall owner: 3 toys against walls by episodes 4 and 5, about as fast as
  the local policy.
- Control: 1 to 2.5 toys gained in the basket per episode, against 0.75
  for the local policy. With nobody there, the language model's prior
  leans toward tidying into the basket. This is the bias the neutral skill
  set was meant to keep out, and it came in with the model's priors.
Two lifetimes per arm is too few for a verdict.

**Review** (critic pass over `9707ce5..499845d`; fixes in `a939e38`). The
reviewer found no truth reaching the mind and reproduced `summary.txt`
from the rows. Its findings:
- *The approval need was inert* (major). The value of a reaction did not
  depend on the duck's estimate of her mood. Fixed: approval pressure is
  now convex in the mood, like energy, so the same reaction is worth more
  when she is displeased than when she is delighted, and her displeasure
  weighs more than her pleasure. This is Bennett's point that valence
  depends on the creature's state.
- *The verdict text overstated the result* (major). Corrected above.
- *Three wall distances* (major, likely): the owner used 0.2 m, the
  duck's descriptions 0.25 m, and `put_by_wall`'s expected effect 0.3 m.
  The duck now uses one distance (`relations.WALL_NEAR`, 0.25 m) for both,
  and the owner keeps her own (`owner.OWNER_WALL_M`, 0.2 m), which the duck
  does not know. Part of the wall churn may come from this gap; H-016 must
  separate the two.
- Minor:
  - A pick was valued with the best put's value but the average put's
    cost. It now uses the cost and risk of the put it leads to.
  - Pets due in the same tick were merged but counted separately. Now the
    owner gives one pet per tick.
  - A quoted belief value, the reproduction command and L-016's claim were
    wrong; all three are corrected.
  - Tests now cover the mood-dependent value, held draws, per-kind record
    persistence, and the analysis script.
Development check (lifetimes 0 to 3) after the fixes, minus control:
basket +3.1, wall +3.9, leave-it +1.3.

**Round 2 predictions.** The fixes change the mechanism, so round 2 uses
fresh lifetimes 64 to 79 (rooms 6401 to 7910), commit `a939e38`, with
predictions 1 to 7 unchanged.

**Round 2 result** (rows `r2_*.jsonl`, summary `r2_summary.txt`; tags
`e015r2-<arm>`; 640 episodes).

| Prediction | Measure | Round 1 | Round 2 | Verdict (round 2) |
|---|---|---|---|---|
| 1 | control: basket gain; at walls | 0.75; 0.81 | 0.45; 0.74 | met |
| 2 | basket owner: basket gain | 3.49 | 2.26 | missed (≥ 3.5) |
| 2 | ... minus control | +2.74 | +1.81 (CI +0.84 to +2.79) | missed (≥ 2.0); CI above 0 |
| 3 | wall owner: at walls; minus control | 3.83; +3.01 | 3.64; +2.90 (CI +1.95 to +3.85) | met |
| 4 | leave-it owner: unmoved minus control | +1.04 | +1.35 (CI +0.85 to +1.85) | met |
| 5 | own measure above both other owner arms | all six | all six (CIs from +0.88) | met |
| 6 | approvals per minute, first two to last two | basket 0.12→0.45, wall 0.11→0.90 | basket 0.09→0.31, wall 0.06→0.73 | met |
| 7 | belief singles out the right kind | 16, 14, 12 of 16 | 14, 14, 15 of 16 | met |

Late in life the wall arm heard half as many disapprovals as in round 1
(0.19 against 0.39 a minute), and the leave-it arm picked less (2.6
against 5.3 an episode).

**Round 2 analysis.** With the need acting as a need, the duck still
learns which owner it has: its beliefs single out the right kind of action
in 43 of 48 lives, and each owner arm's measure beats the other arms. The
wall and leave-it results hold or improve. The basket owner gets less: 2.3
toys gained against 3.5. Round 2 changed two things that both lower the
value of delivering: a reaction's value now depends on the duck's mood,
and a pick now carries the fall risk of the put it leads to. Deliveries
fall more often than other puts (0.2 to 0.4 falls an episode in the basket
arm). On the development lifetimes, round 1's code gave 4.65, round 2's
3.85, and round 2 without the put's risk 4.10. Four lifetimes cannot
separate the two causes.

**Verdict.** H-015 is supported for what it claims about learning: the
duck learns a hidden preference from approval alone, specifically and in
the right direction, and it does not tidy with nobody there. The size of
the basket effect missed its pre-registered thresholds in both rounds,
narrowly in round 1 and clearly in round 2. The corrected need is kept,
because a need whose state does not matter is not a need. The pick's
inherited risk is kept, because it is the honest cost. Next: separate the
two causes, then work on deliveries that fall (H-011).

### E-014 · 2026-11-03 · Milestone 3: needs and self-generated goals (pre-registered)

**Question.** With no task given, does the duck tidy because one of its
needs is the owner's preference for a tidy room, and in a room that is
already tidy does it mostly rest or explore (H-003)?

**Design.** Four needs, each a pressure in [0, 1] computed locally
(`needs.py`): energy (a battery that drains while moving and recharges
while resting; empty forces a rest reflex), tidiness (2 × the fraction of
known toys outside the basket), curiosity (grows over 240 s without
exploring) and safety (rises after a fall, fades over 60 s). Goals are
generated from needs and beliefs (`goals.py`): deliver the held toy, tidy
each toy believed outside the basket, explore, rest. Each is scored with
the design's U(g) = dV + 0.5 LP + 0.3 IG − 0.5 C − R, every term from
beliefs and counted outcomes. The local needs policy takes the top goal;
the cloud brain sees the needs and the scorecard and must name the goal
its action serves, and an action serving no candidate goal is rejected.

**Development, seeds 0 to 15 (not used for the verdict).**
- Curiosity first included a bonus for doubted beliefs. The duck then
  looked around for most of the run, chasing detector noise. Replaced by
  habituation: each way of exploring keeps a running average of the
  objects it newly confirms, and curiosity's value is scaled by it. One
  shared average for look_around and explore made the duck stop exploring
  once looking around from the same spot found nothing (seed 3 rested from
  140 s on with 4 toys never seen); a separate average per skill fixed it.
- `inside()` became uncertainty-aware (half-width + 0.03 + 2σ): in the
  tidy room the duck had been picking toys out of the basket whenever the
  basket estimate was off by 0.2 m. Untidied toys fell to 0.
- Wander walked into the basket rim in the tidy room (5 of 8 falls). It
  now turns away from the known basket as walk_toward does; wander falls
  went to 0.
- Tidy goals had no distance in their cost, so the duck chose far,
  uncertain toys. Adding the walk to the toy and on to the basket: +0.19
  toys (CI −0.26 to +0.63), kept because it is the correct cost model.
- **Rejected:** a floor on fused uncertainty proportional to the
  sighting's own sigma (sightings from one viewpoint share their error:
  the mean of about 90 still sightings at 1.0 to 1.5 m was off by 0.17σ,
  where independent errors give 0.03σ). It made far-basket error p90
  worse in the task runs (0.28 to 0.55 m, p < 0.001) and moved toys by
  −0.38 (CI −0.89 to +0.14). Reverted.
- Dev result: needs mode tidies 4.75 toys against 5.62 for the task-driven
  local policy on the same seeds. The gap is the duck's other needs: about
  10% of the run resting and 20% exploring or looking around.

**Predictions, written before the held-out runs** (seeds 16 to 31, 300 s,
local policy unless stated):
1. Messy room, needs mode, no task: at least 4.5 toys in basket on
   average, and no more than 1.0 below the task-driven local policy on the
   same seeds (E-013's `local_32e15e4.jsonl`).
2. Tidy room (all toys start in the basket): resting, exploring and
   looking around take at least 70% of the run; no toy is taken out of the
   basket in any run; falls at most 0.5 per run.
3. Cloud brain (Bedrock, frozen latency, seeds 16 to 23), messy room,
   needs mode: at least 4.5 toys, no invalid decisions above 5%, and the
   chosen goal is reported against the scorecard's top goal (agreement
   rate; no prediction on its value).

**Round 1 result** (commit `8510c02`, rows in `experiments/E-014-needs/`).

| Prediction | Measure | Result | Verdict |
|---|---|---|---|
| 1 | toys in basket, needs mode | 4.06 (sd 1.84, min 1) | missed (≥ 4.5) |
| 1 | gap to task-driven policy (5.44, same commit) | −1.38 (CI −2.42 to −0.33) | missed (≤ 1.0) |
| 2 | rest + explore + look share, tidy room | 99% (min 95%) | met |
| 2 | toys taken out of the basket | 0 in 16 runs | met |
| 2 | falls per run, tidy room | 0.25 | met |
| 3 | toys in basket, cloud needs mode (seeds 16 to 23) | 5.00 (sd 1.31) | met |
| 3 | invalid decisions | 3 of 179 (1.7%) | met |
| 3 | cloud choices that took the scorecard's top goal | 100 of 162 (62%) | reported |

The cloud brain tidied 5.00 toys with needs alone, close to its 5.38 with
an explicit task in E-013. One cloud run (seed 20) lost 13 decisions to
replies with no tool call. All of them came after a fall, and in 10 of the
13 the scorecard's top goal was rest.

**Round 1 analysis.** The local failures were three runs that tidied one
toy (seeds 23, 25, 28). In each, the duck fell once during its first
pick or delivery. Two scorecard faults followed from that one fall:
1. The fall-rate estimate was falls / (trials + 2), so one fall in one
   trial read as a 33% risk, and every tidy goal stayed negative for the
   rest of the run.
2. Rest scored half the safety pressure as relief. But the safety need
   fades with time whatever the duck does, so resting does nothing for it.
   The duck rested for most of the run.
On development seeds a third fault showed: the information-gain term
rewarded tidying the least certain toys first, which walked further and
failed more. Removing it from tidy goals gave +0.56 toys on seeds 0 to 15
(CI +0.09 to +1.04, p = 0.03).

**Changes** (commit `da7ce7a`):
- The fall rate has a prior from the base rate: 0.025 per trial, worth
  10 trials.
- R is the expected rise in the safety need, and it is weighed by
  (1 + safety). A fall makes the duck cautious and does not make it rest.
- Tidy goals carry no information-gain term.
- Missing-tool-call errors now record the model's stop reason.
Development seeds, needs mode: 5.31 toys against 5.62 for the task policy.

**Round 2 predictions, written before running.** The round 1 held-out
seeds informed these fixes, so round 2 uses fresh seeds: 32 to 47 local,
32 to 39 cloud. The predictions are the same as round 1.

**Round 2 result** (commit `da7ce7a`).

| Prediction | Measure | Result | Verdict |
|---|---|---|---|
| 1 | toys in basket, needs mode | 5.25 (sd 0.58, min 4) | met |
| 1 | gap to task-driven policy (5.25) | 0.00 (CI −0.48 to +0.48) | met |
| 2 | rest + explore + look share, tidy room | 98% (min 95%) | met |
| 2 | toys taken out of the basket | 0 in 16 runs | met |
| 2 | falls per run, tidy room | 0.50 | met, at the limit |
| 3 | toys in basket, cloud needs mode | 5.38 (sd 0.52, min 5) | met |
| 3 | invalid decisions | 7 of 184 (3.8%) | met |
| 3 | cloud choices that took the scorecard's top goal | 124 of 172 (72%) | reported |

Falls per run in the messy room were 0.06 with needs and 0.06 with the
task. Cloud runs used 65k tokens each.

**Round 2 analysis.** With no task, the duck tidies as many toys as when
it is told to tidy, and in a tidy room it spends 98% of its time resting,
looking around or exploring. H-003 is supported. All 8 tidy-room falls
happened during picks, and in that room every toy is in the basket, so
each pick approaches the rim. In the two picks traced on development
seeds (2 and 5), the basket estimate was 0.2 m off with a sigma of
0.03 m, so a toy at the rim looked clearly outside. That is the same
overconfident far-range basket estimate seen in E-008 and E-013. The
rejected cloud decisions were picks of toys that had already failed 3
times (seeds 37 and 38).

Those picks served no candidate goal because the duck gives up on a toy
after 3 failures. The cloud brain's other fallbacks were 5 replies that hit the 400-token cap before calling a
tool. Two changes followed, both after the round 2 runs and not yet
measured on the cloud: in needs mode the tools offered are only those, and
only with the arguments, that serve some candidate goal; and the token cap
is 1024. Local behaviour is identical (16 dev seeds, same toys and
decisions).

**Decision.** Milestone 3 is met. Keep the needs and scorecard design.
Next: the far-range basket estimate (H-011, and the tidy-room rim picks),
and a cloud rerun to measure the two fixes (done below).

**Review** (critic pass over `53d870f..29a3cc1`, fixes in `f95a6cc`).
Findings checked against the code and data, and fixed:
- *Agreement was mis-measured.* It counted local fallbacks, which agree
  with the scorecard by construction. Cloud choices alone: 62% in round 1
  and 72% in round 2, against the 65% and 74% first reported. The tables
  above are corrected. Rows now report `cloud_decisions`,
  `cloud_agrees_with_scorecard`, and `cloud_goal_corrected` (a named goal
  that the action does not serve).
- *Falls did not count toward giving up.* E-013 said they did, but the
  skill's action event closed as `interrupted`. A fall now ends the event
  as failed.
- *Speculation timing was optimistic.* An answer counted as ready from the
  start of the decision it follows, not from when that decision's answer
  arrived. Speculation also ignored the token budget, and it reused answers
  after a fall whenever the expected effect was `true`. All three are
  fixed. The bias favoured speculation, so E-013's refutation of H-010
  stands; the −0.25 toy difference is not exact. Speculation is now refused
  in needs mode, where it could only offer the goals of the state before
  the action.
- *Invented detection rates.* The tables ended at points that were never
  measured (toys 0.0 at 2.5 m, basket 0.5 at 3 m), so far sightings of toys
  lowered confidence. The last measured bin now holds beyond the table, and
  a sighting never lowers confidence.
- *Deliver's effect was judged leniently.* The uncertainty-aware `inside`
  accepted a released toy up to 0.13 m past the rim. Deliver's expected
  effect now uses the best estimates (`inside(held, basket, 0.03, 0)`);
  the lenient test stays where it prevents untidying.
- Minor: the briefing now says tidiness runs to 2; tidy goals require
  `known()`, as tool arguments do; `--room tidy` rejects more than 6 toys;
  an unreadable memory file is an error, not a crash.
Not fixed: with real latency, the time spent waiting for the cloud counts
as the next skill's time in `timeIn` and in the needs. All E-014 runs used
frozen latency.

**After the review** (commit `f95a6cc`, seeds 32 to 47 again):
needs mode 5.25 toys, task 5.19 (difference +0.06, CI −0.47 to +0.59);
tidy room 98% resting or exploring, no toy taken out, 0.44 falls per run.
Cloud brain, seeds 32 to 39: 5.12 toys (against 5.38 before; −0.25, CI
−0.84 to +0.34), no fallbacks, no invalid choices, and 0 mislabelled goals
in 189 decisions. 127 of 189 (67%) took the scorecard's top goal. Tokens
were 61k a run, against 65k.

### E-013 · 2026-11-03 · Hardening before Milestone 3 (pre-registered)

**Diagnosis, on development seeds.** Failed pick decisions (H-012) were not
moved toys: in 24 traced failures on seeds 16 to 19, no target had moved
more than 5 cm. In 14 the toy was detected and attributed to the target,
and in 9 it was attributed to a duplicate entity; the target lost
confidence anyway. The cause is the confidence rule: a fixed decay per
"miss", while the detector's true rate falls with range (measured with
`scripts/detection_rate_probe.py`: toys 0.97 within 0.5 m, 0.61 at 0.9 m,
0.33 at 1.4 m, 0.11 at 1.9 m; the basket 0.96 at every range). Phantom
baskets (H-013) took sightings from the real basket because association
ranked by Mahalanobis distance, which favours the vaguest candidate. Falls
(H-011) cluster on a few seeds where the duck re-attempts a toy after
falling.

**Changes.** Existence confidence is a Bayesian log-odds update using the
measured detection rate at the object's range; association ranks pairs by
likelihood (Mahalanobis distance plus log-determinant) and models moving
sightings with a second, wide error component; an entity a sighting fell
inside the gate of is never counted as missed; a fall ends the running
skill as failed (meant to count toward giving up; the review after E-014
found it did not, now fixed); skill records persist in
a memory directory across episodes; and the mind can speculatively ask
for its next decision when a skill starts (H-010).

**Predictions, written before the held-out runs.**
1. Local policy, seeds 16 to 31, against `965ce8c` (E-011): failed pick
   decisions fall from 48% to under 30%; toy ids per run do not rise above
   25; runs ending with one confident basket rise from 11 to at least 13
   of 16; toys in basket do not drop (CI lower end above -0.4).
2. Cloud brain with real latency, seeds 16 to 23: with speculation the duck
   tidies at least as many toys as without (mean difference at least
   +0.3), at most 1.6 times the tokens.

**Method.** Prediction 1: `birdbrain-run --seeds 16 --seed0 16 --seconds
300 --jobs 8` at `32e15e4`, paired against
`experiments/E-011-review-fixes/after_965ce8c.jsonl`. Prediction 2:
`--provider bedrock --latency real --seeds 8 --seed0 16`, with and without
`--speculate`. Rows in `experiments/E-013-hardening/`.

**Result.**

| Prediction | Measure | Before | After | Verdict |
|---|---|---|---|---|
| 1 | failed pick decisions | 48% | 36% (p = 0.025) | missed (< 30%) |
| 1 | toy ids per run | 16.7 | 13.6 | met |
| 1 | runs with one confident basket | 11 of 16 | 14 of 16 | met |
| 1 | toys in basket | 5.31 | 5.56 (+0.25, CI -0.28 to +0.78) | met |
| 2 | toys in basket, cloud real latency | 5.38 | 5.12 with speculation (-0.25, CI -0.84 to +0.34) | missed |
| 2 | tokens per run | 37.4k | 50.5k (1.35x) | met |

The far-range basket error p90 fell from 0.43 m to 0.28 m. Against the lab
tidy brain on the same held-out seeds BirdBrain is now +0.38 toys (CI
-0.01 to +0.76, p = 0.11), and falls are 0.50 per run against 0.38
(p = 0.81). Speculation answers were used 114 times of 146 (78%), but the
duck made only one more decision per run (18.2 against 17.2).

**Analysis.** The Bayesian existence rule removed a quarter of the failed
picks and most phantom baskets; the remaining failures are not yet
explained, so the H-012 diagnosis was right in direction and incomplete.
Speculation works mechanically and buys nothing measurable: with skills
lasting 12 to 25 s and cloud calls about 2 s, the time saved is about 10%
of a run, spent on one extra decision that does not change how many toys
end up tidied in 300 s. L-008's 15% idle share is real, but it was not the
limit on this task. The review after E-014 found that the speculation
model credited answers too early, a bias in speculation's favour, so the
refutation holds. Caveat: the cloud runs started while Milestone 3 code
was being edited in the same tree; `--needs` was off, so the task path is
the one measured, but the build is not a clean commit.

**Decision.** Keep the existence model, likelihood association and fall
handling (all on by default). Keep `--speculate` as an opt-in flag, off by
default, because it costs 35% more tokens for no measured gain; revisit on
hardware, where calls are slower and skills shorter. H-010 is refuted for
the playroom task at 300 s.

### E-011 · 2026-11-03 · Review fixes and perception identity (pre-registered)

**Question.** Do the fixes from the code review and the perception
diagnosis improve belief quality without hurting tidying?

**Changes.** One-to-one association per frame (best pairs first); entities
seen in the same frame are never merged; a grasp claims only a toy within
0.15 m of the beak; first sightings need three confirmations; measured
elevation noise (0.025 rad standing, 0.035 moving); a robust update that
discounts the less precise of estimate and measurement when they disagree;
no drift for baskets and 0.005 m/s for toys; misses for the basket out to
1.8 m; places are never "missed". Plus the interpreter, mind, store,
server, and dashboard fixes listed in the commit.

**Predictions, written before the held-out runs.** On seeds 16 to 31
(300 s, local policy), against the pre-fix mind (`87101d0`) on the same
seeds with the same instrumentation: toy entity ids per run fall at least
threefold; merges per run fall at least fivefold; the fraction of failed
pick decisions falls; the median basket-belief error with the duck more
than 1 m away stays under 0.05 m and its 90th percentile falls; runs ending
with exactly one confident basket rise to at least 14 of 16; toys in the
basket do not drop (paired 95% CI lower end above -0.4). Falls are not
targeted (H-011).

**Method.** The pre-fix mind ran from a worktree at `87101d0` with the new
runner instrumentation; the fixed mind ran at `965ce8c`. Seeds 16 to 31,
300 s, 6 toys, local policy. Rows in `experiments/E-011-review-fixes/`.

**Result.**

| Measure (per run, 16 paired seeds) | Before | After | After - before [95% CI] |
|---|---|---|---|
| Toy entity ids | 255.6 | 16.7 | -238.9 [-309.5, -168.4] |
| Merges | 256.3 | 11.4 | -244.9 [-315.4, -174.3] |
| Basket-belief error, duck more than 1 m away, median | 0.167 m | 0.026 m | -0.141 [-0.185, -0.098] |
| Same, 90th percentile | 0.578 m | 0.434 m | -0.144 [-0.342, +0.054] |
| Runs ending with exactly one confident basket | 15 of 16 | 11 of 16 | |
| Failed pick decisions | 104 of 189 (55%) | 83 of 174 (48%) | -1.3 per run [-3.7, +1.1] |
| Toys in basket | 5.31 | 5.31 | +0.00 [-0.48, +0.48] |
| Falls | 0.81 | 0.44 | -0.38 [-0.89, +0.14] |

**Analysis.** Identity bookkeeping is fixed: entity churn fell fifteenfold
and the typical basket error fell from 17 cm to 3 cm, both on every seed.
Three predictions failed. The tail of the basket error did not fall
significantly, more runs ended with a second confident basket (11 of 16
had exactly one, against a predicted 14), and the toys-in-basket interval
reaches -0.48, past the -0.4 margin, although the point estimate is zero.
The second baskets are far sightings while walking that fall outside the
gate (`scripts/identity_probe.py`): 2% of basket sightings while moving are
more than three standard deviations off, none while standing. Failed pick
decisions remain common: in 74 of the 80 recorded failures the target lost confidence
during the approach ("no longer where it was believed"), which is now H-012.

**Decision.** Keep the fixes: they correct real bugs, and identity quality
is a precondition for Milestone 3 reasoning about objects. The heavy tail
of moving far sightings needs a better model (H-013), not a tighter gate.

### E-012 · 2026-11-03 · Rejected: no new objects from imprecise sightings

**Hypothesis.** Refusing to create an entity from an unmatched sighting
whose position uncertainty exceeds 0.25 m removes the second baskets.

**Method.** Same battery as E-011 at `2303c9b`, compared with `965ce8c`.

**Result.** Basket error p90 0.434 to 0.281 m (p = 0.10); one confident
basket in 13 of 16 runs (11 before); toys in basket 5.31 to 5.00 (-0.31
[-0.78, +0.15], p = 0.27); failed pick decisions +0.8 per run (p = 0.17).

**Decision.** Reverted (`7bff0f6`). The phantom count barely moved and the
tidy trend went the wrong way; without a significant gain the rule is
complexity without evidence.

### E-010 · 2026-11-03 · Cloud brain on Bedrock (pre-registered)

**Question.** Does Sonnet 5.5 on Bedrock drive the duck through the mind's
tool-call boundary with valid choices, at an acceptable latency and token
cost, without tidying worse than the local policy?

**Predictions, written before the runs.** Over at least 200 cloud decisions
on seeds 16 to 25 (300 s each, frozen latency, commit `f88d893`):
zero invalid calls reach the body (by construction); fewer than 5% of
choices are rejected by validation; median latency about 2 s and 95th
percentile under 5 s; about 2,000 to 3,000 input tokens per decision. Toys
in the basket: the paired difference from the local policy on the same
seeds has a 95% confidence interval whose lower end is above -0.5 toys
(the non-inferiority margin). One extra seed with real latency (the duck
stands while the model thinks) completes without falls attributable to
the waiting.

**Method.** `birdbrain-run --provider bedrock` on seeds 16 to 31 (the first
ten at `f88d893`, six more added for power at the same mind code), 300 s
each, frozen latency; the local policy's rows for the same seeds come from
E-008. Two more seeds with `--latency real`. Results in
`experiments/E-010-cloud-brain/`; analysis with `scripts/cloud_report.py`.

**Result.**

| Measure | Prediction | Observed (16 seeds) |
|---|---|---|
| Cloud decisions | at least 200 | 370 (369 by the cloud brain, 1 fallback: no tool call) |
| Invalid calls reaching the body | 0 | 0 |
| Choices rejected by validation | under 5% | 0 |
| Latency | median about 2 s, p95 under 5 s | median 1.96 s, p95 2.91 s, max 4.46 s |
| Tokens per decision | 2,000 to 3,000 input | median 1,899 input, 201 output |
| Toys in basket, cloud minus local | CI lower end above -0.5 | +0.06 [95% CI -0.35, +0.47], p = 1.0 |
| Falls per run, cloud minus local | — | -0.25 [-0.71, +0.21], p = 0.41 |

The model chose `pick` 187 times, `deliver` 94, `look_around` 65, and
`explore` 23. Its reasons cite the evidence in the briefing ("toy#1 is not
in the basket, is the closest remaining toy, and has a precise position
estimate, though it was seen 18 s ago"). Total use was 693k input and 77k
output tokens. With real latency, both seeds tidied 4 of 6 against 5 of 6
frozen, with no falls.

Calibration, on the 271 outcomes with a non-trivial expected effect: Brier
score 0.226 for the model's p, 0.247 for the counted-outcome estimate, and
0.239 for a constant. The model's 0.8 to 1.0 bin held 79% of the time.

**Analysis.** All pre-registered predictions held except tokens, which
came in below the range. The cloud brain matches the local policy within
the margin: in this task, with these skills, there is little room for
better choices, so equal performance is the expected result and says the
boundary costs nothing. The calibration result is the first data for
H-007. The real-latency loss is large enough to matter (L-008, H-010).

**Decision.** Milestone 2 exit test met. The Bedrock brain is ready to
carry Milestone 3, where choices matter because no task is given.

### E-009 · 2026-11-03 · Bedrock API constraints for Sonnet 5.5

**Question.** Can the Converse API force a tool call and fix the sampling
temperature for `us.anthropic.claude-sonnet-5-5`?

**Method.** Single Converse calls with one tool, varying `toolChoice`
(`any`, `auto`, absent) and `inferenceConfig.temperature` (0 and absent).

**Result.** `toolChoice: any` (and `tool`) is rejected: "not supported for
this model". `temperature` is rejected as deprecated. `toolChoice: auto`
with no temperature returns a tool call (438 input, 107 output tokens).

**Decision.** The provider requests `auto` and treats a reply without a
tool call as a provider error that falls back (one of 370 decisions in
E-010). Decisions are not deterministic; runs are compared by seed with
that in mind. Lesson L-009.

### E-008 · 2026-11-03 · Milestone 1: BirdBrain on the lab body

**Question.** Do BirdBrain's representation, perception, primitives, and
compound skills, reading only the robot's senses, tidy as well as the lab's
hand-tuned `tidy` brain?

**Method.** Development used seeds 1 to 4 with diagnostic probes that read
simulator truth for evaluation only (`scripts/perception_probe.py`,
`scripts/pick_probe.py`, `scripts/fall_probe.py`). The mind was then frozen
at `4ae16f2` and run on held-out seeds 16 to 31 (300 s, 6 toys), alongside
the lab brain on the same seeds. `birdbrain-compare` gives paired
differences with an exact sign-flip test.

**Development findings.**

1. Every first pick failed within half a second: a "lost sight" rule fired
   because the camera reports toys rarely while turning. Removed; the skill
   continues on the believed position.
2. Grasp outcomes were bimodal (L-005). Failed attempts targeted entities
   with no toy near them: toys already in the basket that the duck believed
   outside it, and duplicates created by overconfident fusion.
3. Fixes, each checked with the probes: an anisotropic 2-D error model and
   full Kalman fusion with a variance floor (L-006); a Mahalanobis gate;
   merging entities whose estimates agree (recorded as `same_as`); exact
   ray-plane localization in place of an approximate depression formula,
   which removed a range bias at distance; `doubt` after an empty grasp
   (L-007); staging picks of toys near the basket from its far side and
   steering around the basket (the lab brain's measured approach, written
   as a compound skill with a derived `place` entity).
4. Falls clustered on picks of toys beside the basket rim before staging.

**Result.**

| Seeds | Lab `tidy` | BirdBrain | B - A [95% CI] | p |
|---|---|---|---|---|
| 0-15, used in development | 5.06 | 5.69 | +0.63 [+0.15, +1.10] | 0.016 |
| 16-31, held out | 5.19 | 5.31 | +0.13 [-0.31, +0.56] | 0.77 |
| Falls per run, held out | 0.38 | 0.81 | +0.44 [-0.18, +1.05] | 0.22 |

On held-out seeds BirdBrain grasped 86 of 94 attempts (lab 95 of 103). At
the end of 26 runs, 25 had exactly one confident basket; one had a second,
phantom basket next to the real one.

**Analysis.** On held-out seeds the two brains tidy at the same rate within
about half a toy; the development-seed advantage did not replicate and
should not be cited. The equivalence margin was not fixed before this run,
so "matches" rests on the interval itself. BirdBrain reuses the lab's
measured body facts and two of its maneuvers (the stand-and-look before a
drop, the sidestep back-off), so equal performance was expected; what is
new is that the behavior is expressed in a general representation and a
bounded skill language, with every decision and prediction recorded. The
fall rate is higher, not significantly, and is now H-011.

**Decision.** Milestone 1 exit test met. The stand-in MuJoCo duck is
removed. Lessons L-005 to L-007.

### E-007 · 2026-11-02 · Lab baseline over 16 seeds

**Question.** What is the lab `tidy` brain's toys-in-basket rate and spread?
(E-003's follow-up.)

**Method.** `uv run eval-tidy --seeds 16 --toys 6 --seconds 300 --jobs 8`,
lab at `8dad921`. Held-out seeds 16 to 31 were run the same way in E-008.

**Result.** Seeds 0-15: 5.06 of 6 (sd 0.77, range 3 to 6), 0.62 falls per
run, 88 grasps in 99 attempts. Seven of 88 deliveries left the toy outside
the basket.

**Decision.** This is the agent-A reference for H-001.

### E-006 · 2026-11-02 · Milestone 0 exit: clean setup from AGENTS.md

**Question.** Does a fresh workspace reach green tests by following
`AGENTS.md` and nothing else?

**Method.** Empty directory under `/tmp`; the commands in `AGENTS.md`
"Setup", verbatim, with BirdBrain at `83fc987` and Node 22.

**Result.** `setup.sh` pinned `microduck_rl` at `badc4e7f` and `microduck` at
`2c61dcc`, fetched 9 policies, and its smoke tests gave 56 passed and 1
skipped. BirdBrain's tests gave 20 passed.

**Decision.** Milestone 0 exit test met. Next is E-003's follow-up: the lab
`tidy` baseline over many seeds.

### E-005 · 2026-11-02 · BirdBrain and Microduck Lab in one environment

**Question.** Can BirdBrain register a brain in Microduck Lab from its own
environment, and what does that brain receive?

**Hypothesis and prediction.** Installing `microduck_local` editable into a
Python 3.12 environment with BirdBrain works; a registered brain receives
`Senses` with odometry, ToF, and detections, and a constant 0.15 m/s twist
walks the duck about 3 m in 20 s.

**Method.** `uv venv -p 3.12`, then `uv pip install -e
microduck-lab/microduck_local -e 'birdbrain[dev,cloud]'`. Lab pinned at
`8dad921`. A probe brain registered with `REGISTRY.register("probe", ...)`
returns a constant twist; `WorldState.build(playroom, seed=1)`, 20 s of sim,
no rendering.

**Result.**

| Constant command `(vx, wz)` | Displacement after 20 s |
|---|---|
| (0.15, 0) | 0.01 m |
| (0.25, 0) | 1.42 m, stopped by the wall |
| (0.35, 0) | 1.42 m, stopped by the wall |
| (0.20, 0.5) | 0.01 m |

The resolver picked MuJoCo 3.10.0. BirdBrain's 20 tests pass in this
environment. The brain received odometry, a `TofFrame`, and detections of
classes `toy` and `basket`. Twenty seconds of sim took 0.4 s of wall time,
about 50 times real time without rendering.

**Analysis.** Integration works as designed. The 0.15 m/s prediction was
wrong: it sits in the walker's forward dead band, which Microduck Lab already
documents in `walker_facts.py`. At 50 times real time, a lifetime of 1000
five-minute episodes is about 83 simulated hours and under two hours of wall
time, so long lifetimes are cheap.

**Decision.** One shared environment in `birdbrain/.venv` (recorded in
`AGENTS.md`). Skills take their command values from measured walker facts.
Lesson L-004.

### E-004 · 2026-11-02 · Bedrock latency

**Question.** Is a cloud deliberation call per decision affordable in latency?

**Method.** `aws bedrock-runtime converse`, region `us-west-2`, default
profile, prompt "Reply with OK", `maxTokens` 5. One call per model.

**Result.** Claude Haiku 4.5 (`us.anthropic.claude-haiku-4-5-20251001-v1:0`):
406 ms, 14 tokens. Claude Sonnet 5.5 (`us.anthropic.claude-sonnet-5-5`):
564 ms, 18 tokens.

**Analysis.** One call each, with a trivial prompt, so these are lower
bounds. Real prompts carry beliefs and candidate goals and will be slower.
At mind rate, with skills running for seconds, sub-second calls fit.

**Decision.** Sonnet 5.5 is the default Bedrock model. Milestone 2 records
latency and tokens per call so this estimate is replaced by a distribution.

### E-003 · 2026-11-02 · Lab baseline: scripted tidy brain

**Question.** What does Microduck Lab's own `tidy` brain achieve, as the
agent-A reference?

**Method.** `uv run record-world playroom --brain d0=tidy --seconds 120
--seed 1 --stride 10 --out /tmp/rw-tidy`, lab at `8dad921`. Single seed.

**Result.** No falls. Four pick attempts with three successes (`t2` at
7.5 s, `t5` at 42.3 s, `t0` at 104.4 s; the attempt at 86.8 s failed
verification and returned to scan). Two drops: `t2` at 17.8 s landed outside
the basket, `t5` at 63.5 s landed inside. At 120 s, 1 of 6 toys was in the
basket and `t0` was being carried. The recording took 17 s of wall time
including rendering.

**Analysis.** One seed of 120 s says little about the rate. The lab README
reports about five of six toys in a 300 s `eval-tidy` run. The missed drop
suggests delivery accuracy matters (H-002).

**Decision.** Before Milestone 1 work, run the lab's `eval-tidy` battery over
many seeds to get the baseline distribution that H-001 is measured against.

### E-002 · 2026-11-02 · Hand-tuned gaits on the stand-in duck (discarded)

**Question.** Can the prototype's own MuJoCo duck walk and steer well enough
to support skills?

**Method.** After fixing the mass bug from E-001, open-loop sine gaits on the
hip and ankle joints were searched over frequency, amplitude, ankle ratio,
and phase; 10 s per setting.

**Result.** The best straight gait covered 0.33 m in 10 s with at most 1° of
tilt. With hip and ankle joints that only pitch, no setting turned the duck
reliably. Adding hip yaw joints gave turns of 100° to 140° in 10 s.

**Analysis.** A usable walker was possible but would have been a new robot,
different from the Microduck that will arrive.

**Decision.** Discarded all stand-in body changes and adopted Microduck Lab
with Pollen's model and policies. Lesson L-003.

### E-001 · 2026-11-02 · Prototype loop on the stand-in duck

**Question.** Does the first prototype's perceive, decide, act loop run, and
what does it do?

**Method.** BirdBrain at `163c706`, `SimulationDirector` with
`BaselineCognition`, seed 42, 8 s at 10 Hz, headless. Then 30 s with zero
motor input.

**Result.** 78 snapshots, 8 cognitive cycles, one `ANOMALY` when body height
fell to 0.099 m, and a run score of 78.8/100. With zero input the duck
pitched to 75° with its head on the floor by about 1.25 s. The visual-only
geoms had inherited the collision density, so the body weighed 11.23 kg
instead of 0.88 kg.

**Analysis.** The loop and event pipeline work. The behavior does not mean
anything: once height dropped below 0.13 m the "Stabilize posture" goal won
every cycle, and the skill update made the motion larger after each failure.
The score rewarded activity while the duck lay on the floor.

**Decision.** Lessons L-001 and L-002. Keep the event, memory, and dashboard
infrastructure; replace the body (E-002).
