# BirdBrain design

This document describes what BirdBrain is meant to become and the smallest
design that can get there. It changes as experiments in
[`ledger.md`](ledger.md) confirm or refute its assumptions; a design change
should cite the ledger entry that motivated it.

## 1. North star

A fully autonomous, curious, and creative artificial creature. The duck lives
in a room for weeks of simulated time. Nobody hands it a task list. It has
needs and values, notices what is worth doing, tries things, forms beliefs
about how its world works, tests those beliefs, and builds skills it can
reuse. After a thousand episodes it should be measurably better at deciding
what to do, at understanding unfamiliar objects, and at acting on that
understanding than it was after its first hundred, with the same frozen
foundation model throughout.

The milestone after that is physical: move the same mind, with its memories,
onto a real Microduck and measure how much of its competence survives.

## 2. Inspirations

These sources are starting points for ideas. We take what helps, change what
does not fit a cloud-brained robot duck, and try ideas of our own. A
departure from a source needs no justification beyond a ledger result.

**Steve Grand's *Creatures*.** The spirit of the project: a small creature
with its own needs, living one continuous life and learning from what its
actions cause. BirdBrain borrows that spirit and none of the mechanism.

**Max Bennett's *A Brief History of Intelligence*.** Bennett describes
intelligence as five breakthroughs, each built on the ones before:
steering, reinforcing, simulating, mentalizing, and speaking. The framework is
a useful checklist for what a grounded mind needs:

| Breakthrough | In animals | In BirdBrain |
|---|---|---|
| Steering | Approach what is good, avoid what is bad | A few needs with valence; safety reflexes in the skills and the body |
| Reinforcing | Learn from the gap between expected and actual outcome; curiosity | Every action carries a prediction; surprise is measured; skill and rule evidence update from outcomes |
| Simulating | Imagine actions and their results before acting; replay the past | The cloud brain imagines likely outcomes from memory before choosing; after a failure it asks what would have worked |
| Mentalizing | Model one's own mind and the minds of others | A self-model of what this body can reach, push, carry, and how reliably; a model of the owner's preferences |
| Speaking | Share knowledge through language | Provided by the language model. BirdBrain's part is grounding: plain-language beliefs carry evidence, and what the owner says becomes a belief that outcomes confirm or revise |

Large language models arrived at the fifth breakthrough first, and
BirdBrain uses that capability as it comes. The models can also imagine a
great deal, but what they imagine is untested against a body and its
consequences. BirdBrain's job is to supply the
earlier layers: needs that give the cloud brain something to care about,
prediction error from its own body, and a world model that reality keeps
correcting.

**Recent agent and robotics research.** Skill libraries that grow from
experience (Voyager, ASPIRE); separation of raw experience, wiki knowledge,
and executable skills (WikiSkill); learning from prediction errors without
changing model weights (WorldEvolver); executable precondition and effect
rules learned by exploration (OneLife); curiosity from expectation mismatch
(GLANCE); autotelic agents that generate their own goals; and a cloud model
reasoning over a robot's local skills (HomeBody). BirdBrain reuses these ideas
where they fit. What is open is their combination over one persistent life:
goals that arise from the creature's own needs and uncertainty, experiments
chosen for expected learning progress, beliefs tested against reality, and
skills that improve with use.

## 3. Design principles

- **The cloud brain thinks; local code grounds and guards.** A frozen
  foundation model proposes goals, chooses actions, predicts, and reflects.
  Local code supplies measured evidence, enforces the action space, runs the
  body, and takes over when the cloud is unavailable.
- **Few general mechanisms.** One loop, one action form (a tool call), one
  skill language (bounded programs over primitives), and one representation
  (assertions, events, and causal rules with evidence). Special cases are a sign the
  general mechanism is wrong.
- **Complexity on evidence.** A component is added when a ledger entry shows
  the simpler design failing at something the north star needs.
- **The mind sees what the robot sees.** Cognition reads the robot's senses
  and its own memory. The simulator's true state scores the agent and never
  reaches it.
- **Reuse the body.** Locomotion, grasping, and sensing come from Pollen's
  policies and Microduck Lab. BirdBrain does not train motor policies.
- **Frozen model, living memory.** All learning lives in memory and skill
  parameters, so it is inspectable, reversible, and portable across models.
- **Everything is an event.** If it is not in the event log, it did not
  happen as far as debugging and evaluation are concerned.

## 4. System overview

```text
┌─ Cloud brain (Bedrock, Sonnet 5.5) ─────────────── at decision points ─┐
│  propose goals · choose the next action · predict · reflect            │
└───────────────▲──────────────────────────────────┬─────────────────────┘
          briefing                          tool call
┌───────────────┴──────── Local mind ──────────────▼─────────────────────┐
│  perceive → beliefs · needs · scorecard · validate · measure outcome   │
│  memory: events · assertions · causal rules · skills · fallback        │
└──────────────────────────────────────────────────┬─────────────────────┘
                                            active skill
┌─ Skills (50 Hz) ─────────────────────────────────▼─────────────────────┐
│  closed-loop routine: senses → intent, until done, failed, or timeout  │
└──────────────────────────────────────────────────┬─────────────────────┘
                                                 intent
┌─ Body ───────────────────────────────────────────▼─────────────────────┐
│  Microduck Lab World (simulation)  or  Pollen robotd (hardware)        │
└────────────────────────────────────────────────────────────────────────┘
```

BirdBrain runs inside Microduck Lab as a registered brain. Each 50 Hz tick
the lab hands it a `Senses` snapshot and receives an `Intent`. The active
skill answers every tick. The cloud brain is consulted at decision points:
when a skill finishes or fails, when something surprising is perceived, or on
a slow timer.

## 5. Core concepts

Everything the dashboard shows and everything memory stores is one of these.

| Concept | What it is | Example |
|---|---|---|
| **Entity** | A thing the duck knows about, including itself and places | `toy#2` of class `toy`; `self`; `basket#1` |
| **Assertion** | A relation or property that held over a time interval, with evidence | `at(toy#2, (0.91, 0.40) ± 0.05)` from t = 12.0, seen in episode 41 |
| **Event** | Something that happened over an interval, with participants | the duck ran `pick(toy#2)` from t = 40.8 to 42.3; a surprise; a fall |
| **Causal rule** | Conditions, an action, and its typical effects, with evidence | `pick(x)` when near and facing `x` → `holding(self, x)`, 7 of 9 |
| **Need** | A small number in [0, 1] with a direction | energy 0.8, curiosity 0.4, tidiness 0.6, safety 0.1 |
| **Goal** | A desired assertion, with its source | `inside(toy#2, basket#1)`, from tidiness |
| **Skill** | A named, parameterized, bounded program with measured statistics | `pick(x)`, success 0.78, mean 4.2 s |

An **action** is a tool call: a skill name and arguments that name entities
the duck currently believes in, for example `pick(x="toy#2")`. The tools are
the skills, so this is the cloud brain's whole output vocabulary for acting.
"Beliefs" in this document means assertions and causal rules together.

## 6. Actions and skills

Actions are built from first principles in three levels.

| Level | What | Examples | Defined by |
|---|---|---|---|
| L0, body primitives | Exactly what the body offers, identical in the lab and on the robot | `move(vx, vy, wz)`, `head(pose)`, `beak(open \| close)`, `reflex(ground_pick \| kick_left \| kick_right \| sit_toggle)` | The body |
| L1, control primitives | A small fixed set of closed-loop routines aimed at any entity, each ending on a condition | `turn(angle)`, `turn_toward(x)`, `walk_toward(x, stop_at, avoid)`, `wander(t)`, `stand(t)`, `require(cond)`, `doubt(x)` | Local code (`skills.py`); the only control code BirdBrain writes |
| L2, compound skills | Programs composed from L1 and L2 skills, stored as data | `pick(x)`, `deliver()`, `back_off()`, `look_around()`, `explore()`, `rest()`, `tidy_room()` | JSON in `src/birdbrain/library/`; hand-written first, later composed by the cloud brain |

A compound skill is a small structured program in a bounded language with
five constructs:

- **sequence:** steps in order;
- **if:** a condition chooses between branches;
- **repeat until:** a loop with a required iteration limit;
- **bind:** a query result named for later steps, `x := nearest(toy, not inside(basket))`;
- **call:** run another skill with arguments; recursion is allowed up to a depth limit.

Any step may carry an `until` condition, a timeout, and an `on_fail`
handler. Conditions and queries are expressions over the representation in
section 7, so skills and knowledge share one vocabulary.

```text
tidy_room():                                   budget 300 s
  repeat max 10 until not exists(toy, not inside(basket)):
    x := nearest(toy, not inside(basket))
    if x is none:
      look_around()
    else:
      pick(x)            on_fail: push_toward(x, basket)
      carry_to(basket)
      beak(open)
      back_off()
```

The language can express any behavior that fits within its budgets, and
every skill run ends as done, failed, or out of budget. Bounded termination
keeps outcomes, statistics, and predictions well defined and keeps the body
safe; open-ended computation lives one level up, in the life loop and the
cloud brain's reasoning between skills. A small interpreter runs the
programs and records every step as an event, so a failure can be traced to
the step that caused it.

Skills are stored as data so they are safe to run, easy to inspect, and
measured individually. Generated code, as in Voyager and ASPIRE, is the
alternative to revisit if the data form proves too limiting.

## 7. Representation

BirdBrain uses a small general representation and commits to no specific
formalism yet. It is designed so that event calculus, an RDF-style graph with
a time ontology, or PDDL-style action schemas could be adopted later without
changing what is stored.

- **Entities.** Objects the duck has seen, the duck itself, and derived
  places (for example `beyond(x, basket, 0.45)`, a point past a toy on the
  ray from the basket). Perception infers identity from position: the
  detector reports only a class. Two entities found to be one object are
  merged and the merge is recorded as `same_as`.
- **Assertions.** Every fact is `relation(arguments)` or
  `property(entity, value)` with a valid-time interval, the time it was last
  observed, a confidence, and its sources (events). Facts are never
  overwritten: when the world changes, the old assertion's interval closes
  and a new one opens, which keeps history queryable.
- **Identity.** Each camera frame's sightings are assigned one-to-one to
  known entities, best match first; objects seen in the same frame are
  never merged; a grasp claims only a toy within reach of the beak (ledger
  E-011).
- **Space.** Positions are values with a 2-D error covariance in a named
  frame (odometry first). Range from a camera is far less certain than
  bearing, so a sighting's error ellipse is long along the ray, and fusion
  is a Kalman update with a variance floor (ledger L-006). The noise is
  measured against simulator truth; the update discounts whichever of
  estimate and measurement is less precise when they disagree; baskets do
  not drift while unseen and toys drift slowly (ledger E-011). Spatial relations such as `near`, `facing`, and
  `inside` are computed from positions when queried, so they never go stale.
- **Time.** Intervals on assertions and events support "now", "last seen",
  and "before or after this event" queries.
- **Events.** Actions, perceptions, surprises, and falls are events with an
  interval, participants, and outcome. Episodes are action events.
- **Causality.** A causal rule generalizes over action events: conditions,
  the skill and its argument classes, effects, and evidence. Every skill,
  primitive or compound, is described by such a rule, learned from its own
  runs. A contradiction splits a rule by condition and keeps both cases.
- **Text.** Every assertion and rule renders as a plain sentence for the
  cloud brain's briefing. Code works with the structure; the model reads
  the sentence.

The vocabulary of relations starts with what skills and goals need (`at`,
`near`, `facing`, `holding`, `inside`, `class`, `visible`) and grows only when
a skill, goal, or rule needs a new one.

## 8. The life loop

1. **Perceive** (local). Turn new detections and odometry into assertions
   about entities. An entity that should be visible and is not loses
   confidence.
2. **Brief** (local). Assemble a bounded briefing: needs, relevant assertions
   and rules with their evidence, recent episodes, surprises, skill statistics, the
   current goal, and a scorecard of candidate goals (section 9).
3. **Think** (cloud). The cloud brain may keep or change the goal, propose a
   new one, and chooses the next action as a tool call. It states the outcome
   it expects, its confidence, and a one-line reason. It can consider a few
   alternatives and their likely outcomes before choosing; that imagined
   comparison is recorded with the decision.
4. **Check** (local). Reject any call naming an unknown skill or object, or
   violating a safety rule. On rejection, timeout, or error, the fallback
   policy chooses instead, and the event records why.
5. **Act** (local). Run the skill until it reports done, failed, or timed out.
6. **Measure** (local). Compare the outcome with the prediction, update skill
   statistics and the evidence on the rules involved, and update needs. A
   large mismatch is a surprise.
7. **Reflect** (cloud, after surprises and periodically). The cloud brain
   proposes new or revised rules, lessons, and compound skills. They enter
   memory with zero evidence and gain or lose confidence only from measured
   outcomes.

## 9. Motivation

Needs give the cloud brain something to care about. They are a short list of
numbers in its briefing, updated by local code: tidiness rises with believed
clutter, curiosity with uncertain beliefs and untested skills, energy falls
with activity, and safety pressure rises after falls or bumps. The owner's
preferences enter as a need (tidiness) and its weight. The duck can discover
any number of goals in their service; it does not invent its ultimate values.

For each candidate goal, local code computes a measured scorecard following
the form agreed in the original design discussion:

```text
U(g) = α·ΔV(g) + β·LP(g) + γ·IG(g) − δ·C(g) − ε·R(g)
```

- `ΔV`: expected reduction in need pressure if `g` succeeds, times its
  measured probability of success.
- `LP`: recent learning progress on the beliefs and skills `g` would use.
- `IG`: how uncertain the beliefs `g` would test are.
- `C`: expected time and energy, from skill statistics.
- `R`: risk, from falls and failures in similar episodes.

The scorecard is evidence for the cloud brain, which makes the choice. The
fallback policy picks the top-scoring goal. Recording both lets the ledger
ask whether the cloud brain's choices beat the scorecard and when. All terms
are computed from observed outcomes, and the weights start fixed and simple.

Need-driven behavior alone can produce a duck that rests in a corner, and
curiosity alone a duck that pokes objects forever. The no-action baseline in
section 15 checks that activity is useful.

## 10. Learning without weight updates

- **Behavioral:** better choices, because the briefing carries skill
  statistics and rule evidence that reflect real outcomes.
- **Knowledge:** assertions and causal rules gain or lose evidence. A
  contradicted rule is split by condition, keeping both cases (for example,
  `pick` succeeds when aligned and fails when approached at an angle).
- **Procedural:** skill parameters tuned from outcomes; new compound skills
  composed from existing ones; redundant ones merged or retired.

A causal rule, with the sentence the cloud brain reads:

```text
pick(x: toy)
  conditions: near(self, x, 0.12), facing(self, x, 0.1)
  effects:    holding(self, x)
  evidence:   7 successes in 9 trials; episodes 41, 57, ...; last tested t = 104.4
  text:       "Toys can be picked up when the duck is close and facing them (7 of 9)."
```

Every action carries a **prediction** that code can check: an assertion
expected to hold, a deadline, and a probability, for example
`holding(self, toy#2)` within 5 s with p = 0.8. **Surprise** is how unlikely
the observed outcome was under that prediction (its negative log
probability). **Learning progress** is the change in prediction error or
skill success over a sliding window of episodes.

Every rule and prediction records its **provenance**: whether its
probability came from the language model's prior or from counted outcomes,
and which simulator mechanics it depends on. For example, the lab models a
grasp as a weld that succeeds with probability 1 − (alignment error /
tolerance)², so rules about picking learned in simulation are marked as
depending on that model. How surprises from unreliable observations, such as
a missed detection, should be filtered is left to experiment (ledger H-008).

## 11. Memory

| Store | Form | Written when |
|---|---|---|
| Events | Append-only JSONL: actions with outcomes, perceptions, surprises | As they happen |
| Assertions | Append-only JSONL; an interval closes when a fact stops holding | Perception and measurement |
| Causal rules | JSON documents with conditions, effects, evidence, text | Measurement and reflection |
| Skills | JSON programs plus parameters, trials, successes, durations | Authoring and every skill outcome |
| Working memory | In process: current goal, active skill, last briefing | Each decision |

Memory survives restarts and episode resets, and writes are atomic. Retrieval
starts as exact lookup by entity, relation, and skill, with an in-memory
index for current assertions; a SQLite index comes when queries get slow; similarity search is
added only when lookup is shown to be insufficient.

## 12. The cloud brain

The default provider is AWS Bedrock through the Converse API with the
standard AWS credential chain, model `us.anthropic.claude-sonnet-5-5`, region
from configuration. The skills are offered as tools, so the answer is a
structured tool call that local code validates. Over 370 decisions the
median call took 1.96 s with about 1,900 input and 200 output tokens
(ledger E-010); every call's latency and tokens are recorded, and a run can
carry a token budget.

| Provider | Role |
|---|---|
| `bedrock` | The cloud brain |
| `local` | Fallback, tests, and agent A: deterministic rules for the current goal |

The prototype's OpenAI adapter was removed with the stand-in body; another
provider is one class implementing `choose(request) -> Choice`. Sonnet 5.5
on Bedrock rejects a forced tool choice and the `temperature` parameter
(ledger E-009), so the provider asks with `toolChoice: auto` and a reply
without a tool call falls back.

The cloud brain never emits actuator values, and its calls happen at
decision points outside the 50 Hz loop.

The model's own stated probability is recorded beside the rule-based
prediction and the observed outcome on every decision. Nothing uses it yet;
the record exists so its calibration can be measured (ledger H-007) before
deciding how much weight the model's priors should get.

## 13. Body interface

BirdBrain consumes Microduck Lab's brain contract:

- `Senses`: time; latest 8×8 ToF frame and detection frame with their ages;
  forward speed; odometry `(x, y, yaw)`; whether the beak holds something;
  the running reflex skill; whether the body is bumping something.
- `Intent`: twist `(vx, vy, wz)`; head `(neck_pitch, head_pitch, head_yaw,
  head_roll)`; beak `open` or `close`; an optional reflex skill such as
  `ground_pick`; a one-line note.

The same intents exist on the robot as Pollen `robotd` JSON-RPC calls, so
moving to hardware changes one layer:

| Intent field | Simulation | Hardware |
|---|---|---|
| twist | lab World command | `robot.move {vx, vy, vyaw}` |
| head | lab World head target | `robot.head {neck_pitch, head_pitch, head_yaw, head_roll}` |
| reflex skill | lab skill cycle | `robot.do {skill: ground_pick, kick_left, ...}` |
| senses | lab sensors with noise presets | `robot.subscribe`, ToF stream, camera detector |

Skills respect the measured behavior of the shipped walker, recorded in the
lab's `walker_facts.py`: forward commands below about 0.2 m/s, and turn
commands below about 1.0 rad/s from standstill, produce no motion.

## 14. Observability

Every briefing, cloud call, tool call, validation, fallback, skill outcome,
prediction and surprise, belief change, and need change is a versioned event
with run id, sequence, wall time, and sim time, recorded to per-run JSONL.
Two viewers read the same run:

- the **BirdBrain dashboard** for the mind: needs, goals and their
  scorecard, the current action with its prediction and reason, predictions
  versus outcomes, beliefs with evidence, skill statistics, and replay;
- the **Microduck Lab `/sim` page** and `record-world` for the body: the
  room, the duck, its sensors, and video.

Each milestone adds the dashboard view its own events need.

## 15. Evaluation

A **lifetime** is a sequence of episodes in one world family. Between
episodes the room is reset and changed; the duck's memory is kept. The
evaluator reads the simulator's true state, which the agent never sees.

All agents use the same cloud model and the same action budget:

| Agent | Capabilities |
|---|---|
| A, reactive | Executes an explicit task with fixed skills; no memory. Microduck Lab's `tidy` brain is the reference |
| B, memory | A plus persistent beliefs and skill statistics |
| C, proactive | B plus needs and self-generated goals, no task given |
| D, developmental | C plus predictions, surprise, reflection, and learning-progress-driven experiments |

Measures: useful tasks initiated without instruction; improvement on
unfamiliar objects and rooms across the lifetime; competence gained per
episode, per token, and per simulated hour; prediction accuracy on novel
interventions; retention across long gaps; recovery after the room or the
owner's preferences change; and how often the agent correctly does nothing.

Every comparison uses fixed seeds, reports the number of seeds and the
spread, and is written to the ledger with the commit that produced it.

## 16. Safety

Skills bound every intent to the body's command ranges. The lab's fall
detection and the robot's own safety layer stay authoritative. Local code can
stop all motion without consulting the cloud brain. Simulation is the only
environment until a hardware readiness review passes.

## 17. Milestones

Each milestone ends with a measurable exit test recorded in the ledger. The
order roughly follows Bennett's: a body that steers safely, then learning
from outcomes, then imagination, self-model, and language-borne knowledge.

| # | Milestone | Exit test |
|---|---|---|
| 0 | Architecture, setup, ledger | A clean checkout reaches green tests by following `AGENTS.md` (**met**, E-006) |
| 1 | Body, skills, representation | BirdBrain runs in the playroom from `Senses` only; L1 primitives, the skill interpreter, and hand-written compound skills exist; with the local fallback and an explicit tidy goal it matches the lab `tidy` brain's toys-in-basket rate on held-out seeds; the stand-in MuJoCo duck is removed (**met**, E-008) |
| 2 | Cloud brain | At least 200 cloud decisions over at least 5 seeds with no invalid call reaching the body; fallback rate, latency, and tokens reported; tidying within 0.5 toys of the local policy on the same seeds (**met**, E-010) |
| 3 | Needs and self-generated goals | With no task given, the duck starts tidying on its own, and in an already tidy room it mostly rests or explores |
| 4 | Predictions, surprise, causal rules | Prediction accuracy on held-out actions rises across a lifetime of episodes |
| 5 | Skills composed by the cloud brain | A compound skill the cloud brain wrote is kept on measured merit and does something no hand-written skill does, or does it better |
| 6 | Lifetimes and agents A to D | D beats C on competence gained per episode across seeds, with the spread reported |
| 7 | Hardware readiness | The same mind drives the physical Microduck through `robotd` under supervision |

## 18. Open questions

- How should thinking overlap acting, so the duck does not stand idle for
  the 2 s of each cloud call (ledger L-008, H-010)?
- How often should the cloud brain be consulted, and how large can a
  briefing be before cost or latency hurts?
- How should energy work in a world without a charger: a simulated battery
  restored by resting, or a charging spot added to the room?
- Which objects and properties give curiosity something real to learn in the
  playroom (pushable versus carriable, rolling versus sliding)?
- When do entities need explicit spatial memory beyond tracked positions?
- Which loop, recursion, and time budgets keep compound skills useful without
  hiding failures?
- Which noise preset should experiments use: `datasheet` throughout, or
  `ideal` while mechanisms are developed?

## 19. Code map

| Module | Role |
|---|---|
| `body.py` | The body boundary: `Observation`, `Command`, and the measured `BodyProfile` |
| `lab.py` | The only module that touches Microduck Lab types; copies only what the robot senses |
| `kr.py` | Entities, assertions with intervals, events, and `Position` with covariance |
| `perception.py` | Sightings to assertions: localization, association, fusion, merging, misses |
| `relations.py`, `expr.py` | Computed relations and the safe expression language over them |
| `skills.py`, `library/*.json` | Primitives, the bounded skill interpreter, and compound skills |
| `mind.py` | The decision loop, briefing, validation, predictions, skill records, local policy |
| `providers/bedrock.py` | The cloud brain |
| `run.py`, `evaluation.py` | Seeded runs scored from simulator truth, and paired comparison |
| `observability/` | Event journal, run store, and the loopback dashboard server |
