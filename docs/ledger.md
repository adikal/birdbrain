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

## Open hypotheses

Ordered by what to test next. Resolved ones keep their verdict.

- **H-001** (Milestone 1) **Supported.** BirdBrain's primitives and
  hand-written compound skills, reading only the robot's senses, tidy as
  well as the lab's `tidy` brain on held-out seeds (E-008).
- **H-002 Supported for the lab brain.** Delivery misses limit its rate: 15
  of its 179 deliveries over 32 seeds left the toy outside the basket
  (E-007, E-008). BirdBrain's deliveries landed in nearly every case.
- **H-006** (Milestone 5) **Partly supported.** Every compound skill the
  playroom has needed so far fits the bounded language (sequence, if,
  repeat until, bind, call). The test that matters is skills written by the
  cloud brain.
- **H-007** (Milestone 4) **Early data.** The language model's stated
  probabilities beat counted outcomes for actions with little history
  (Brier 0.167 against 0.206 with fewer than 3 prior trials) and the two
  converge by 10 trials (0.224 against 0.233, n = 27). Whether counts win
  later needs runs whose memory persists across episodes (E-010).
- **H-010** (new). Asking for the next decision while the current skill is
  still finishing recovers most of the time lost to real latency (L-008).
  *Test:* real-latency runs with and without overlap, same seeds.
- **H-011** (new). BirdBrain falls more often than the lab brain (0.81
  against 0.38 per run on held-out seeds, p = 0.22) because of the
  sidestep in `back_off` and standing near the rim. *Test:* attribute every
  fall to its skill step over 32 seeds, then change only that step.
- **H-012** (new). Most failed pick decisions (74 of 80 in E-011) are
  approaches abandoned because the target's confidence dropped below the
  acting threshold mid-walk. Either the duck's feet move the toy, or
  misses are counted for sightings the detector could not make (toys in
  the lower edge of the frame while the head is down). *Test:* for each
  such failure, compare the toy's true displacement during the approach
  with the predicted visibility.
- **H-013** (new). Sightings taken while walking have a heavy-tailed error
  that a Gaussian gate cannot represent, which produces the remaining
  phantom baskets. *Test:* fit a two-component error model on probe data
  and compare phantom counts.
- **H-003** (Milestone 3). Needs that include tidiness make the duck start
  tidying with no task given, and in a tidy room it mostly rests or explores.
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
