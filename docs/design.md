# BirdBrain: A Persistent, Need-Driven Mind for a Small Biped Robot

*Technical report. Every number below is reproducible from the research
ledger ([`ledger.md`](ledger.md)), which records the hypothesis, method,
commit, seeds, and raw rows behind it. Entries are cited as E-### for
experiments, H-### for hypotheses, and L-### for lessons.*

## Abstract

A language model can plan, explain, and speak, but on its own it has nothing
it wants, no body whose consequences it must live with, and no memory that
outlasts a conversation. We describe BirdBrain, a mind for Pollen Robotics'
Microduck, a 25 cm biped, that supplies those missing layers around a frozen
foundation model. Local code turns the robot's own senses into beliefs with
uncertainty, runs bounded skill programs at 50 Hz, keeps counted outcomes
for life, and maintains a small set of needs. At each decision point it
scores candidate goals from those needs and that evidence, and the cloud
model (Claude Sonnet 5.5 on AWS Bedrock) chooses an action through a
validated tool call. The simulator's true state is used only for scoring.
In a simulated playroom, the mind tidies toys as well as the lab's
hand-tuned controller on held-out rooms (5.31 against 5.19 of 6 toys). The
cloud brain made 370 decisions without one invalid call reaching the body.
With no task given, needs alone produce the same tidying as an explicit
task, and in a room that is already tidy the duck rests or explores 98% of
the time. We then remove the built-in preference. The duck's only social
need becomes its owner's approval, and the owner says only whether she
likes something ("nice", "dont do that"). The duck credits each reaction to
the actions that could have caused it, re-explains its history by
expectation-maximization, and explores by Thompson sampling. Over a life of
ten rooms it learns which of three hidden preferences its owner holds:
toys in the basket, toys against the walls, or toys left where they were.
Its beliefs single out the right kind of action in 43 of 48 lives, and
with nobody there it does not tidy. All results come from simulation with
a scripted owner. The report states the limits of that setting and the
plan for hardware.

## 1. Introduction

The goal of this project is a fully autonomous, curious artificial creature.
It lives in a room for weeks of simulated time, decides what is worth doing,
tries things, forms beliefs about how its world works, and becomes more
capable over time, with the same frozen foundation model throughout. The
step after that is physical: move the same mind, with its memories, onto a
real Microduck.

Two books shaped the idea. Steve Grand's *Creatures* supplied the spirit: a
small creature with its own needs, living one continuous life and learning
from what its actions cause. Max Bennett's *A Brief History of Intelligence*
supplied a checklist. He describes intelligence as five breakthroughs, each
built on the ones before: steering (valence: approach the good, avoid the
bad), reinforcing (learning from outcomes), simulating, mentalizing, and
speaking. Language models arrived at the fifth first. What they lack are the
earlier layers: a reason to act, prediction error from a body, and a world
model that reality keeps correcting. BirdBrain's job is to supply them.

The central hypothesis is that an embodied agent with persistent memory of
outcomes, self-generated goals, and a principled choice of what to try can
develop increasingly useful capabilities without updating the foundation
model's weights.

This report makes the following contributions:

- **An architecture** in which a frozen cloud model chooses goals and
  actions while local code grounds, scores, validates, and executes them.
  The mind reads only what the physical robot can sense, and the interface
  to the body is the same in simulation and on hardware (section 3).
- **A measured goal scorecard** that values each candidate goal by the
  need pressure it relieves, its counted success and fall rates, and its
  cost in time, with each term defined as the difference the goal makes
  (section 4).
- **Learning a hidden preference from valence alone.** An approval need,
  a scripted owner who says only whether she approves, credit assignment by
  expectation-maximization over the reaction history, and exploration by
  Thompson sampling, with three neutral ways to put a toy down
  (section 4.3).
- **A pre-registered experimental record** of fifteen experiments,
  including failed predictions and rejected changes, with paired
  comparisons on held-out rooms (sections 5 and 6).

## 2. Background and related work

**Skill libraries and code as policy.** Voyager and ASPIRE grow libraries
of skills from experience, and WikiSkill separates raw experience,
knowledge, and executable skills. BirdBrain stores compound skills as data
in a bounded language, so every skill run terminates and is measured, and
reserves generated code for later if the data form proves too limiting.

**Learning without weight updates.** WorldEvolver learns from prediction
errors in memory, and OneLife learns executable precondition and effect
rules by exploration. BirdBrain keeps all learning in inspectable memory:
counted skill outcomes, beliefs about objects, and beliefs about what earns
the owner's approval.

**Curiosity and autotelic agents.** GLANCE derives curiosity from
expectation mismatch, and autotelic agents generate their own goals.
BirdBrain's curiosity habituates by measured yield, and its goals come from
needs.

**Cloud models over robot skills.** HomeBody has a cloud model reason over
a robot's local skills. BirdBrain shares the split and adds a validated
tool boundary, a local fallback for every failure, and a scorecard the
model sees as evidence.

**Bandits and credit assignment.** Thompson sampling is a standard way to
balance exploration and exploitation in multi-armed bandits. Assigning
delayed, ambiguous rewards to candidate causes is a latent-variable
problem, solved here by expectation-maximization over the history of
reactions.

What is open is the combination over one persistent life: goals that arise
from the creature's needs, beliefs tested against a body, and a preference
learned from a person's reactions alone.

## 3. Architecture

### 3.1 Overview

```text
┌─ Cloud brain (Bedrock, Sonnet 5.5) ─────────────── at decision points ─┐
│  chooses a goal and the next action · states its expectation · reasons │
└───────────────▲──────────────────────────────────┬─────────────────────┘
          briefing                          tool call
┌───────────────┴──────── Local mind ──────────────▼─────────────────────┐
│  perceive → beliefs · needs · scorecard · validate · measure outcome   │
│  memory: events · assertions · skill and kind records · owner beliefs  │
└──────────────────────────────────────────────────┬─────────────────────┘
                                            active skill
┌─ Skills (50 Hz) ─────────────────────────────────▼─────────────────────┐
│  bounded programs over control primitives: senses → intent             │
└──────────────────────────────────────────────────┬─────────────────────┘
                                                 intent
┌─ Body ───────────────────────────────────────────▼─────────────────────┐
│  Microduck Lab World (simulation)  or  Pollen robotd (hardware)        │
└────────────────────────────────────────────────────────────────────────┘
```

The design follows a few principles:

- **The cloud brain thinks; local code grounds and guards.** The model
  chooses. Local code supplies measured evidence, enforces the action space,
  runs the body, and takes over when the cloud is unavailable.
- **The mind sees what the robot sees.** Cognition reads the robot's senses
  and its own memory. The simulator's true state scores the agent and never
  reaches it.
- **Few general mechanisms.** One loop, one action form (a tool call), one
  skill language, one representation.
- **Complexity on evidence.** A component is added when an experiment shows
  the simpler design failing. A change that does not move its target metric
  is reverted (L-011).
- **Reuse the body.** Locomotion and grasping come from Pollen's policies,
  run in Microduck Lab, a MuJoCo world with Pollen's robot model.
  BirdBrain does not train motor policies (L-003).

### 3.2 Body interface

Each 50 Hz tick the body provides an observation and receives a command:

```text
Observation = (t, odometry (x, y, yaw), forward speed, holding, running reflex, bumped,
               camera detections, 8×8 depth frame, heard phrases, petted)
Command     = (twist (vx, vy, wz), head (neck_pitch, head_pitch, head_yaw, head_roll),
               beak open | close, reflex skill, note)
```

The same commands exist on the robot as `robotd` JSON-RPC calls
(`robot.move`, `robot.head`, `robot.do`), so moving to hardware replaces one
layer. The detector reports a class, bearing, elevation, and width for each
sighting, never an identity. Skills respect the shipped walker's measured
dead bands: forward commands below about 0.2 m/s, and turn commands below
about 1.0 rad/s from standstill, produce no motion (L-004).

The robot's head microphone already feeds a petting classifier and a sound
watcher that reports `Voice` and `Noise` events (Pollen's `pet-detect`). The
`heard` field carries utterances that a keyword spotter of the same kind
(log-mel features and a small CNN) would recognize on the device, so no
audio leaves the robot.

### 3.3 Perception

Perception turns sightings into beliefs about where objects are and whether
they exist.

- **Localization.** Each sighting's ray is intersected with the horizontal
  plane at its class's height. Range error grows as drop / sin²(depression)
  while bearing error is direct, so each sighting carries an anisotropic 2-D
  covariance, long along the ray. The noise model was measured against
  simulator truth (E-011).
- **Fusion.** Estimates are fused by a Kalman update with a variance floor,
  since successive sightings share their errors (L-006). A robust update
  discounts the less precise of estimate and measurement when they disagree.
- **Association.** Each frame's sightings are assigned one-to-one to known
  entities, most likely pair first. Likelihood combines the Mahalanobis
  distance and the log-determinant of the combined covariance, so a vague
  estimate cannot outbid a precise one. Sightings taken while walking may
  also match through a second, wide error component (outlier probability
  0.03), which models their heavy tail (E-013). Objects seen in the same
  frame are never merged, and a grasp claims only a toy within reach of the
  beak.
- **Existence.** Confidence that an object exists is a log-odds belief. A
  sighting raises it by log(p_d / p_false); a frame that should have shown
  the object and did not lowers it by log((1 − p_d) / (1 − p_false)), where
  p_d is the detector's measured hit rate at that range (toys: 0.97 at
  0.25 m, 0.61 at 0.9 m, 0.11 beyond 1.75 m; basket: 0.96 at every range)
  and p_false = 0.1. A miss far away therefore says little.

### 3.4 Representation

The representation is small, general, and committed to no formalism, so that
event calculus, an RDF graph with a time ontology, or PDDL-style action
schemas could be adopted later without changing what is stored.

| Concept | What it is | Example |
|---|---|---|
| Entity | A thing the duck knows about, including itself and derived places | `toy#2`, `basket#1`, `self`, `place:wall<self` |
| Assertion | A relation or property over a valid-time interval, with confidence and sources | `at(toy#2) = (0.91, 0.40) ± 0.05` from t = 12.0 |
| Event | Something that happened over an interval, with participants and outcome | `pick(toy#2)` from 40.8 to 42.3 s, failed; a fall; an utterance |
| Record | Counted outcomes for a skill or a kind of action | `pick from wall`: 14 tries, 9 held, 2 falls |

Facts are never overwritten. When the world changes, the old assertion's
interval closes and a new one opens. Spatial relations (`near`, `facing`,
`inside`, `near_wall`) are computed from positions when queried, so they
never go stale. `inside` allows for uncertainty: a toy within the basket's
half-width plus a margin plus two standard deviations of the combined
uncertainty counts as inside, so an ambiguous toy is not taken out of the
basket. Judging a delivery's own effect uses the best estimates alone. Every
assertion renders as a plain sentence for the cloud brain's briefing.

### 3.5 Skills

Actions are built in three levels:

| Level | What | Examples |
|---|---|---|
| L0, body | What the body offers, identical in the lab and on the robot | twist, head pose, beak, reflex (`ground_pick`) |
| L1, control primitives | Closed-loop routines aimed at any entity, each ending on a condition | `turn_toward(x)`, `walk_toward(x, stop_at, avoid)`, `wander(t, avoid)`, `stand(t)`, `require(cond)`, `doubt(x)` |
| L2, compound skills | Programs over L1 and L2, stored as JSON data | `pick(x)`, `deliver()`, `put_by_wall()`, `drop()`, `look_around()`, `explore()`, `rest()` |

A compound skill is a program in a bounded language with five constructs:
sequence, if, repeat until (with a required iteration limit), bind (name a
query result), and call (recursion up to a depth limit). Any step may carry
an `until` condition and a timeout, and every skill has a time budget.
Conditions and queries are expressions over the representation, so skills
and knowledge share one vocabulary. Every run ends as done, failed, timed
out, or interrupted, which keeps outcomes and statistics well defined and
the body safe. Each skill states its expected effect as an expression (for
`pick(x)`, `holding(self, x)`), which is checked when the run ends.

### 3.6 The decision loop and the cloud brain

At each decision point the mind:

1. **Perceives**: odometry, sightings, utterances, and pets become
   assertions and events.
2. **Briefs**: assembles the known objects with their uncertainty, recent
   actions and outcomes, skill records, needs, candidate goals with their
   scorecard, and, in approval mode, what the owner said recently and what
   the duck has learned about her reactions.
3. **Asks**: the cloud model receives the briefing and the skills as tools
   whose arguments are enumerations of the entities the duck believes in.
   It returns one tool call naming the action, the goal it serves, its
   probability that the expected effect will hold, and a one-line reason.
4. **Checks**: a call naming an unknown tool, an entity outside the
   enumeration, or an action that serves no candidate goal is rejected. On
   rejection, timeout, or error, the local policy chooses, and the event
   records why.
5. **Acts and measures**: the skill runs to its end; its expected effect
   is evaluated, and records, needs, and owner beliefs are updated.

The provider is AWS Bedrock's Converse API with model
`us.anthropic.claude-sonnet-5-5`. Sonnet 5.5 on Bedrock rejects a forced
tool choice and the `temperature` parameter (E-009), so the provider asks
with automatic tool choice and treats a reply without a tool call as a
failure. The model never sends actuator values. A fall ends the running
skill as failed, so it counts toward giving up on a target.

### 3.7 Memory

Memory that survives between episodes (the room is reset, so beliefs about
where things are do not) holds three stores, written atomically to a
memory directory: skill records, records per kind of action, and the
duck's beliefs about its owner, including the full history of her reactions
and their candidate causes. Every event of every run is also recorded to
append-only JSON lines.

### 3.8 Observability and safety

Every briefing, cloud call, validation, fallback, skill step, outcome,
belief change, utterance, and need change is a versioned event with run id,
sequence, and simulated time. A dashboard bound to the loopback interface
replays or follows a run: the believed map against the true one (the truth
overlay is for the viewer only), the head camera with the detections the
mind received, the current action and its reasons, needs and the scorecard,
and what the duck believes about its owner. Skills bound every command to
the body's ranges, and local code can stop all motion without the cloud.

## 4. Motivation

### 4.1 Needs

Needs give the cloud brain something to care about. Each is a pressure
computed locally from the body and from beliefs:

| Need | Pressure | Dynamics |
|---|---|---|
| Energy | (1 − battery)² | battery drains 1/400 per s moving, 1/2000 standing; resting recharges 1/40 per s; empty forces a rest reflex |
| Curiosity | 1 − exp(−Δt / 240 s), Δt since last exploring | habituates: each way of exploring keeps a running average of objects it newly confirms, which scales its value |
| Safety | 0.6 per fall, fading over 60 s | raises the weight of risk; does not make resting valuable, since it fades whatever the duck does |
| Tidiness (Milestone 3) | 2 × fraction of known toys believed outside the basket | the owner's preference entered directly |
| Approval (Milestone 3b) | ((1 − m) / 2)², m the estimated mood | m moves ±0.3 per reaction and relaxes to 0 over about 2 minutes |

The duck discovers goals in the service of its needs; it does not invent
its ultimate values.

### 4.2 The goal scorecard

Candidate goals come from needs and beliefs. Each is scored as

```text
U(g) = α·ΔV(g) + β·LP(g) + γ·IG(g) − δ·C(g) − ε·R(g),    α = 1, β = 0.5, γ = 0.3, δ = 0.5, ε = 1
```

- **ΔV**, the expected reduction in need pressure if g succeeds, times its
  measured probability of success.
- **LP**, recent learning progress on the skills g uses.
- **IG**, the uncertainty of the beliefs g sets out to test. Only
  exploring does that on purpose.
- **C**, the expected time over a 600 s horizon: the skills' measured mean
  duration plus the walk this goal needs.
- **R**, the expected rise in the safety need: the measured fall rate of
  the skills g uses, with a prior of 0.025 falls per trial worth 10 trials,
  times what one fall adds, weighed by (1 + safety).

The scorecard is evidence for the cloud brain, which chooses. The local
policy takes the top goal. Development taught one rule for every term: it
must be the difference the goal makes (L-012). Crediting rest with relief
of the safety need, which fades anyway, made the duck rest after one fall
for most of a run; crediting uncertainty to tidy goals sent it to its least
certain toys first and cost 0.56 toys a run (E-014).

### 4.3 Learning what the owner wants

A tidiness need builds the answer into the creature (L-015). In Milestone
3b the duck's only social need is approval, a need that names no state of
the room. What earns approval has to be learned.

**The owner.** A scripted owner in the simulator holds a hidden preference
over where toys are. When a toy's state changes in a way she cares about,
she reacts after 1 to 5 s with probability 0.6, using a random phrase from
an editable list (`src/birdbrain/phrases.toml`):

```text
approval:     nice · thanks · thank you · well done · good duck · good job · great · i like that
disapproval:  i dont like that · dont do that · no · stop · not that · bad duck
```

10% of her phrases are misheard as the opposite list, and near her she may
pet the duck instead of speaking. Her preferences: toys in the basket; toys
against a wall (within 0.2 m, not in the basket); or toys left where they
were at the start. A phrase matches only as a whole utterance; anything
else heard carries no valence.

**Kinds of action.** The duck describes its own actions: the skill, and for
a pick, where the toy was (in the basket, against a wall, or in the open).
Three ways of putting a toy down are offered side by side and described
only by what they do: `deliver` (into the basket), `put_by_wall` (at the
nearest wall away from the basket), and `drop` (where the duck stands).

**Beliefs.** For each kind k the duck holds independent posteriors over the
probability that it is followed by approval and by disapproval, each
starting at Beta(1, 2), so no kind is assumed to please her.

**Credit by expectation-maximization.** A reaction of valence v at time t
could have been caused by any action under way between t − 8 s and
t − 0.5 s, or by nothing the duck did. Given the current beliefs, each
candidate c receives the share

```text
r_c = p_v(kind(c)) / (Σ_c' p_v(kind(c')) + b),   b = 0.05
```

and the counts, and so the beliefs, are re-estimated from the shares. The
two depend on each other, so on every new reaction the whole history is
re-explained to convergence. A kind that keeps being followed by approval
comes to explain it, and actions that merely happened to coincide are
explained away, including for reactions heard before the duck knew better
(L-017).

**Choice by Thompson sampling.** Each decision values every kind by one
draw (p⁺, p⁻) from its posteriors. The value of the owner's reaction is the
expected relief of the approval need at the current mood m:

```text
value(k) = w · [ p⁺ · (P(m) − P(m + s)) − p⁻ · (P(m − s) − P(m)) ],   P(m) = ((1 − m) / 2)²,  s = 0.3,  w = 4
```

Because P is convex, the same approval is worth more when she is displeased
than when she is pleased, and her displeasure weighs more than her pleasure:
valence depends on the creature's state, as in Bennett's account of affect.
A pick is valued with the put that looks best after it, including that put's
cost and fall risk. Draws are kept while the duck holds a toy, so a put is
chosen with the beliefs that made the pick worth doing. Success and fall
rates are counted per kind, since a pick beside a wall falls more often than
one in the open. There is no separate exploration bonus: an uncertainty
bonus kept the duck busy with nobody there (L-016).

**What the duck knows of the room.** It knows the walls as a map in its
odometry frame; on the robot this map would come from the range sensor. It
does not know the owner's threshold for "against a wall"; its own is
0.25 m.

## 5. Evaluation methodology

**Platform.** Microduck Lab at commit `8dad921`: Pollen's robot model and
shipped walking policy in MuJoCo at 50 Hz, a 3.0 × 2.5 m walled playroom
with six toys and a 0.3 m basket in one corner, the `datasheet` sensor noise
preset, and simulated versions of the robot's camera detector and depth
sensor. A room is fixed by its seed.

**Agents.** The local policy (deterministic rules for an explicit task, or
the top of the scorecard when no task is given) and the cloud brain, both
running the same mind. The reference controller is the lab's hand-tuned
`tidy` brain, which reads privileged identities.

**Protocol.** Each experiment states its predictions in the ledger before
held-out runs. Development uses seeds 0 to 15 (lives 0 to 3 for
Milestone 3b). Held-out seeds that informed a fix are not reused to judge
it (L-014). Runs last 300 s. Comparisons are paired by seed, report the
mean difference with a 95% t interval and an exact sign-flip permutation
test, and count seeds where each arm wins. A lifetime is ten episodes in
different rooms (room seed 100 × life + episode) with memory kept between
them; arms share the same rooms.

**Measures from truth.** Toys in the basket; toys against a wall; toys
within 0.1 m of their starting place; falls; grasp error; belief error
against true positions; and, for the owner, every reaction she meant to
make.

## 6. Experiments and results

### 6.1 The mind on the lab body (E-008)

| Held-out seeds 16 to 31 | Lab `tidy` | BirdBrain | Difference [95% CI] |
|---|---|---|---|
| Toys in basket (of 6) | 5.19 | 5.31 | +0.13 [−0.31, +0.56], p = 0.77 |
| Falls per run | 0.38 | 0.81 | +0.44 [−0.18, +1.05], p = 0.22 |

Reading only the robot's senses, BirdBrain tidies at the lab controller's
rate. On development seeds it had appeared better (+0.63); that advantage
did not replicate. Grasp failures were bimodal: good grasps landed within
1 cm, failed ones 0.2 to 1.4 m from any toy, so the failures came from
stale or duplicate beliefs (L-005).

### 6.2 The cloud brain (E-010)

Over 370 decisions on 16 seeds, no invalid call reached the body and
validation rejected none. Median latency was 1.96 s (95th percentile
2.91 s), with a median of 1,899 input and 201 output tokens per decision.
The cloud brain tidied +0.06 toys against the local policy (95% CI −0.35 to
+0.47). Its stated probabilities scored a Brier score of 0.226 against
0.247 for counted outcomes and 0.239 for a constant. When the world kept
running during calls, the duck stood still for about 15% of a run (L-008).

### 6.3 Perception (E-011, E-013)

One-to-one association, never merging objects seen together, and a grasp
reach gate cut toy identities per run from 255.6 to 16.7 and the median
far-range basket error from 0.167 m to 0.026 m (E-011). Failed pick
decisions remained common. In 24 traced failures, no target had moved more
than 5 cm. The cause was a fixed confidence decay per "miss" against a
detector whose true hit rate falls with range. The range-aware existence
model, likelihood association, and the two-component error model reduced
failed pick decisions from 48% to 36% and raised runs ending with one
confident basket from 11 to 14 of 16 (E-013). Against the lab controller,
BirdBrain then tidied +0.38 toys (CI −0.01 to +0.76). A rejected change,
discarding imprecise unmatched sightings, lowered tidying and was reverted
(E-012).

### 6.4 Thinking while acting (E-013)

Asking the cloud for the next decision when a skill starts, assuming its
expected effect holds, produced answers that were used 78% of the time but
added one decision per run, no toys (−0.25, CI −0.84 to +0.34), and 35% more
tokens. With skills of 12 to 25 s and calls of about 2 s, waiting was not
the limit on this task. The option is off by default.

### 6.5 Needs and self-generated goals (E-014)

With tidiness as a need and no task, the first held-out round missed its
prediction: 4.06 toys against 5.44 for the task. In three runs a single fall
stopped tidying for the rest of the run. One fall in one trial read as a
33% fall rate, and rest was credited with relieving the safety need. With a
prior on falls, risk weighed by safety, and no uncertainty bonus on tidy
goals, a second round on fresh seeds met every prediction:

| Fresh seeds 32 to 47 | Result |
|---|---|
| Toys in basket, needs alone / explicit task | 5.25 / 5.25 (difference 0.00, CI −0.48 to +0.48) |
| Tidy room: share of time resting, looking around, or exploring | 98% (minimum 95%) |
| Tidy room: toys taken out of the basket | 0 in 16 runs |
| Cloud brain, needs alone | 5.38 toys; the scorecard's top goal in 72% of its choices |

### 6.6 Learning what the owner wants (E-015)

Sixteen lives of ten rooms per arm, per life the mean over rooms 6 to 10,
paired by life against the no-owner control. Round 1 (lives 48 to 63) used
an approval value that ignored the mood. A review found that the need
therefore did not act as a need, and round 2 (fresh lives 64 to 79) uses
the mood-dependent value of section 4.3.

| Owner | Measure | Round 1, minus control | Round 2, minus control | Belief singles out the right kind (round 2) |
|---|---|---|---|---|
| Basket | toys gained in the basket | +2.74 [+1.82, +3.65] | +1.81 [+0.84, +2.79] | `deliver` most approved, 14 of 16 |
| Wall | toys against walls | +3.01 [+2.19, +3.84] | +2.90 [+1.95, +3.85] | `put_by_wall` most approved, 14 of 16 |
| Leave-it | toys unmoved | +1.04 [+0.64, +1.44] | +1.35 [+0.85, +1.85] | a pick most disapproved, 15 of 16 |

With no owner, the duck gained 0.45 toys in the basket and 0.74 against
walls per room in round 2. Each owner arm's own measure exceeded both other
owner arms (all six round 2 intervals above +0.88). A general urge to move
toys would raise every arm's measures alike; this effect is specific to
each owner's preference. Approvals per minute rose from
the first two rooms to the last two (basket 0.09 to 0.31, wall 0.06 to
0.73). Learning curves for the basket and wall owners rise until rooms 6 to
8 and level off.

Two pre-registered predictions missed. The basket owner was predicted at
least 3.5 toys and +2.0 over the control; round 1 reached 3.49 and +2.74,
round 2 2.26 and +1.81. Round 2 changed two things that both lower the
value of delivering: the mood-dependent value, and charging a pick with the
fall risk of the delivery that follows it (deliveries fall 0.2 to 0.4 times
a room). On development lives the round 1 code reached 4.65, round 2 3.85,
and round 2 without the inherited risk 4.10, too few to separate the two.

**The cloud brain** (two lives per arm, five rooms, 1,026 decisions, no
invalid choices) learns from the same beliefs and its own reading of the
reactions. It treated its first delivery as an experiment ("delivering it
tests whether my owner likes toys in the basket") and tidied 5 to 6 toys by
the third and fourth rooms. With the leave-it owner it had nearly stopped
picking by the third room ("picking toys from the open has so far drawn
disapproval, so I'll stay still and not risk annoying her"), leaving all six
toys in place, which the local policy never achieved. With nobody there it
put 1 to 2.5 toys a room in the basket against 0.75 for the local policy:
the language model's prior leans toward tidying, a bias the neutral skill
set does not remove.

## 7. Discussion

**Ground the beliefs before tuning the behavior.** The largest gains in
tidying came from perception bookkeeping: identity, existence, and
association. Each fix replaced a locally reasonable shortcut, such
as greedy matching or a fixed miss penalty, that was globally wrong (L-010).

**Value terms must be differences.** Every scorecard failure in Milestone 3
was a term that credited a goal with something that would happen anyway, or
with a property it did not set out to change (L-012). Small counts need
priors (L-013).

**A need can smuggle in the answer.** Milestone 3's result was true by
construction. Moving the owner's preference out of the need and into what
the duck must learn turned a demonstration into a test (L-015).

**Exploration must be able to fade, and credit needs hindsight.** An
uncertainty bonus never let go; Thompson sampling explores in proportion to
how thin the evidence is (L-016). Splitting each reaction once, by the
beliefs of the moment, left lasting credit on coincident actions;
re-explaining the history removed it (L-017). Both choices are standard
statistics, and both mattered more than any parameter.

**The language model brings priors.** The cloud brain learns faster from
the same evidence, and its prior helps when the owner's preference matches
common human expectations and biases the duck when nobody is there. The
local policy, with no priors, is the cleaner instrument for testing what
the architecture learns.

## 8. Limitations

- **Simulation only.** All results come from Microduck Lab. Its grasp is a
  weld that succeeds with probability falling with alignment error, and its
  detector reports toys and baskets, while the robot's shipped detector
  finds only other Microducks. Toy and basket detection on hardware needs a
  new detector or camera frames sent to a vision-language model.
- **A scripted owner.** She reacts to every change in either direction, at
  a fixed rate and delay, from a fixed vocabulary. Real people praise
  outcomes, intentions, and effort, at varying delays, and change their
  minds. One consequence: picking a toy the leave-it owner dislikes and
  dropping it on the spot earns "no" then "nice", so that lesson is only
  half available.
- **Given knowledge.** The wall map is given; on the robot it would come
  from the range sensor. The duck's descriptions of actions (where a toy
  was picked from) are hand-chosen categories.
- **Credit timing.** The duck credits actions under way when a reaction
  arrives, so the action that follows a change takes part of the credit.
  The wall-owner duck re-picks toys already at a wall for this reason
  (H-016).
- **One room family and one model.** Every experiment uses the same
  playroom layout family and Claude Sonnet 5.5. The cloud owner arm has two
  lives per arm.
- **Thresholds from development.** Prediction thresholds for Milestone 3b
  were set after development lives; the held-out verdicts use fresh lives.

## 9. Roadmap

| # | Milestone | Exit test | Status |
|---|---|---|---|
| 0 | Architecture, setup, ledger | A clean checkout reaches green tests by following `AGENTS.md` | met (E-006) |
| 1 | Body, skills, representation | From senses only, with an explicit task, tidies at the lab controller's rate on held-out seeds | met (E-008) |
| 2 | Cloud brain | At least 200 cloud decisions, no invalid call reaching the body, tidying within 0.5 toys of the local policy | met (E-010) |
| 3 | Needs and self-generated goals | With no task the duck tidies on its own; in a tidy room it mostly rests or explores | met (E-014) |
| 3b | Learning what the owner wants | With approval as its only social need and phrases that carry only valence, it learns each of several hidden preferences within a life, and without an owner it does not tidy | met, basket effect below its predicted size (E-015) |
| 3c | Credit timing and safe deliveries | Credit reactions to actions that ended before them, or learn the delay, and cut churn at walls by half (H-016); halve falls at the basket rim (H-011) | next |
| 4 | Predictions, surprise, causal rules | Generalize the credit and belief machinery of 3b from owner reactions to every action's outcome, with conditions ("a pick beside a wall falls"); the accuracy of predicted outcomes on held-out actions rises across a life and beats counted priors (H-007) | planned |
| 4b | One valence | Falls, an empty battery, new objects found, and the owner's reactions become valence events learned by one mechanism, replacing hand-set scorecard terms without losing the results of E-014 and E-015 | planned |
| 5 | Skills composed by the cloud brain | A compound skill the cloud brain wrote is kept on measured merit and does something no hand-written skill does, or does it better | planned |
| 6 | Lifetimes, agents A to D, changing owners | The developmental agent beats the proactive one on competence gained per room; after the owner's preference changes mid-life the duck recovers within a stated number of rooms | planned |
| 7 | Hardware | On-device keyword spotting for the phrase lists, toy and basket detection, a wall map from the range sensor; the same mind drives the physical Microduck under supervision | planned |

The agents of Milestone 6 are: A, reactive (explicit task, no memory); B,
with persistent beliefs and skill records; C, proactive (needs and
self-generated goals); and D, developmental (C plus predictions, surprise,
reflection, and experiments chosen for expected learning progress).

Open questions that the roadmap does not yet settle:

- How often should the cloud brain be consulted, and how large can a
  briefing grow before cost or latency hurts?
- Would a charging spot make energy a need the duck has to plan for?
- Which objects and properties give curiosity something real to learn
  (pushable against carriable, rolling against sliding)?
- Which loop, recursion, and time budgets keep compound skills useful
  without hiding failures?

## 10. Conclusion

A frozen language model becomes a usable mind for a small robot when local
code gives it measured beliefs, bounded skills, needs, and a memory of
outcomes. The same structure lets the creature learn something nobody told
it: what its owner likes, from her approval and disapproval alone. The next
steps are to make credit assignment respect when changes happen, to extend
the same learning from reactions to every outcome, and to carry the mind
onto the physical duck.

## Appendix A. Parameters

| Parameter | Value | Source |
|---|---|---|
| Control rate | 50 Hz | Microduck Lab |
| Existence prior / limit | log-odds −3 / ±5 | E-013 |
| Detection false-positive rate p_false | 0.1 | E-013 |
| Moving-sighting outlier probability / scale | 0.03 / 16× covariance | E-013 |
| Scorecard weights α, β, γ, δ, ε | 1, 0.5, 0.3, 0.5, 1 | design |
| Scorecard horizon | 600 s | design |
| Fall prior | 0.025 per trial, worth 10 trials | E-014 |
| Give up on a target after | 3 failures | design |
| Owner reaction probability / delay / mishearing | 0.6 / 1 to 5 s / 0.1 | E-015 |
| Credit window | t − 8 s to t − 0.5 s; background weight 0.05 | E-015 |
| Owner-belief prior | Beta(1, 2) for approval and for disapproval | E-015 |
| Mood step / relaxation / approval weight | 0.3 / 120 s / 4 | E-015 |
| Duck's "against a wall" / owner's | 0.25 m / 0.2 m | E-015 |

## Appendix B. Reproduction

```bash
.venv/bin/birdbrain-run --seeds 16 --seed0 16 --seconds 300 --jobs 8 --out rows.jsonl              # local, task
.venv/bin/birdbrain-run --needs --room tidy --seeds 16 --seed0 32 --out tidy.jsonl                   # Milestone 3
.venv/bin/birdbrain-run --owner basket --episodes 10 --seeds 16 --seed0 64 --jobs 4 \
    --tag e015r2-basket --memory data/lifetimes/e015r2-basket --out basket.jsonl                     # Milestone 3b
.venv/bin/python scripts/lifetimes.py none.jsonl basket.jsonl wall.jsonl leave.jsonl                 # E-015 summary
.venv/bin/birdbrain-compare A.jsonl B.jsonl --metric inBasket --metric falls                         # paired comparison
```

Add `--provider bedrock` for the cloud brain. Raw rows for every experiment
are under `experiments/`.

## Appendix C. Code map

| Module | Role |
|---|---|
| `body.py` | The body boundary: `Observation`, `Command`, and the measured `BodyProfile` |
| `lab.py` | The only module that touches Microduck Lab types; copies only what the robot senses |
| `kr.py` | Entities, assertions with intervals, events, and `Position` with covariance |
| `perception.py` | Sightings to beliefs: localization, association, fusion, existence |
| `relations.py`, `expr.py` | Computed relations and the safe expression language over them |
| `skills.py`, `library/*.json` | Primitives, the bounded skill interpreter, and compound skills |
| `mind.py` | The decision loop, briefing, validation, measurement, local policies |
| `needs.py`, `goals.py` | Needs, candidate goals, and the scorecard |
| `reactions.py` | Beliefs about the owner: credit by EM, choice by Thompson sampling |
| `phrases.py`, `phrases.toml` | The owner's phrase lists (editable) and their valence |
| `owner.py` | The scripted owner (simulator side, reads truth) |
| `records.py` | Counted outcomes per skill and per kind of action |
| `providers/bedrock.py` | The cloud brain |
| `run.py`, `evaluation.py` | Seeded runs and lifetimes scored from truth; paired comparison |
| `observability/` | Event journal, run store, and the loopback dashboard server |
