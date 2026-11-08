# BirdBrain

**Small duck. Big thoughts.**

BirdBrain is a research project to build a persistent, autonomous, creative
artificial creature: a small duck robot that lives in a room, decides for
itself what is worth doing, runs its own experiments, and becomes more capable
over time. A frozen foundation model in the cloud does the thinking. Local
code grounds it in what the duck senses and measures, keeps a durable memory,
and runs the body.

Two books shaped the idea. Steve Grand's *Creatures* supplied the spirit: a
small creature with its own needs, living one continuous life and learning
from what its actions cause. Max Bennett's *A Brief History of Intelligence*
supplied a checklist for a grounded mind: basic needs and reflexes, learning
from prediction errors, imagination, a model of itself and others, and
knowledge carried in language. Language models start with the last of these;
BirdBrain supplies the others.

The body is Pollen Robotics'
[Microduck](https://github.com/pollen-robotics/microduck), a 25 cm biped.
Until the physical robot arrives, the duck lives in
[Microduck Lab](https://github.com/jonathanhawkins/microduck-lab), a MuJoCo
world with Pollen's real robot model, its shipped walking and grasping
policies, and simulated versions of the robot's own senses.

## Central hypothesis

An embodied agent with persistent causal memory, self-generated goals, and a
learning-progress-driven choice of experiments can develop increasingly useful
capabilities over time without updating its foundation model's weights.

## Architecture

BirdBrain is the mind. Microduck Lab and Pollen's software are the body.

```text
┌──────────────────────────────────────────────────────────────┐
│ Cloud brain  (AWS Bedrock, Claude Sonnet 5.5)                │
│   chooses a goal and the next action · states its            │
│   expectation and reason, through a validated tool call      │
├──────────────────────────────────────────────────────────────┤
│ Local mind  (this repo)                                      │
│   beliefs from senses · needs · measured scorecard ·         │
│   validates every action · measures outcomes · fallback      │
│   memory: events · assertions · skill records · owner model  │
├──────────────────────────────────────────────────────────────┤
│ Skills  (50 Hz)                                              │
│   control primitives · compound skills as bounded programs   │
│   senses in, intents out (twist, head, beak, reflex skill)   │
├──────────────────────────────────────────────────────────────┤
│ Body                                                         │
│   simulation: Microduck Lab World, Pollen policies, MuJoCo   │
│   hardware:   Pollen robotd (robot.move / head / do)         │
└──────────────────────────────────────────────────────────────┘
        events ──▶ BirdBrain dashboard (the mind)
        frames ──▶ Microduck Lab /sim viewer (the body)
        true simulator state ──▶ evaluator only
```

The mind sees only what the real robot can sense: the head's 8×8 depth
sensor, the camera's object detections, odometry, and its own telemetry. The
simulator's true state is used to score runs and never reaches the agent.
Because Microduck Lab brains emit the same intents as Pollen's robot daemon,
moving to hardware replaces only the bottom layer.

[`docs/design.md`](docs/design.md) is the technical report: architecture,
methods, experiments and results, limitations, and the roadmap.
[`docs/ledger.md`](docs/ledger.md) is the research ledger, where every
hypothesis, pre-registered prediction, experiment, result, and lesson is
recorded with its commit, seeds, and raw rows.

## Workspace

BirdBrain expects to sit beside Microduck Lab, which in turn holds pinned
checkouts of Pollen's two repositories:

```text
<workspace>/
  birdbrain/                 this repo: the mind, memory, dashboard, experiments
  microduck-lab/             the simulated body and world (pinned commit)
    microduck/               Pollen robot software and shipped policies
    microduck_rl/            Pollen MJCF models and training stack
```

BirdBrain imports Microduck Lab as a library and registers its brain at
runtime. It never edits the upstream repositories.

## Quick start

Requirements: macOS on Apple Silicon or Linux, Python 3.12,
[uv](https://docs.astral.sh/uv/), Node 20+, and git.

[`AGENTS.md`](AGENTS.md) has the exact setup, including the pinned upstream
commits. In short:

```bash
mkdir birdbrain-workspace && cd birdbrain-workspace
git clone git@github.com:adikal/birdbrain.git
git clone https://github.com/jonathanhawkins/microduck-lab
git -C microduck-lab checkout 8dad9218062f7b0ad29ae6d564305411f5a117c2
(cd microduck-lab && ./scripts/setup.sh)
cd birdbrain && uv venv -p 3.12 .venv
uv pip install --python .venv/bin/python -e ../microduck-lab/microduck_local -e '.[dev,cloud]'
.venv/bin/pytest
```

## Running it

```bash
.venv/bin/birdbrain-run --seeds 16 --seconds 300 --jobs 8 --out experiments/mine/rows.jsonl
.venv/bin/birdbrain-run --provider bedrock --seeds 5 --out experiments/mine/cloud.jsonl
.venv/bin/birdbrain-run --needs --seeds 16 --out needs.jsonl                    # no task: needs and goals
.venv/bin/birdbrain-run --owner wall --episodes 10 --seeds 4 --jobs 4 --out wall.jsonl   # learn an owner's wish
.venv/bin/python scripts/lifetimes.py wall.jsonl                               # summarize lifetimes
.venv/bin/python scripts/predictions.py wall.jsonl                             # score predictions
.venv/bin/birdbrain-run --author --episodes 20 --seeds 2 --jobs 2 --tag mine --out authored.jsonl  # cloud writes skills
.venv/bin/birdbrain-run --world world2 --kinds late --episodes 20 --seeds 2 --jobs 2 --tag w2 --out w2.jsonl  # World 2
.venv/bin/birdbrain-run --world world2 --kinds late --agent D --episodes 20 --seeds 2 --jobs 2 --tag d --out d.jsonl  # Milestone 6 agent D
.venv/bin/birdbrain-run --world world2 --agent D --owner basket --owner-change 11:leave --episodes 20 --seeds 2 --tag oc --out oc.jsonl  # she changes her mind
.venv/bin/python scripts/world2_report.py w2.jsonl                              # World 2 measures by room band
.venv/bin/birdbrain-compare A.jsonl B.jsonl          # paired, seed-matched comparison
.venv/bin/birdbrain-dashboard --live --seed 3        # the mind, live, at http://127.0.0.1:8790
.venv/bin/birdbrain-record playroom --brain d0=birdbrain --seconds 120 --out /tmp/rec   # video
```

Runs are scored from simulator truth (toys in the basket, falls, grasps) and
every event the mind produces is recorded under `data/runs/`. The dashboard's
replays are in `data/replays/` (the newest 50 are kept).

## Cloud brain

The cloud brain is Claude Sonnet 5.5 (`us.anthropic.claude-sonnet-5-5`) on
AWS Bedrock, called through the Converse API with the standard AWS
credential chain (profiles, SSO sessions, temporary credentials, or IAM
roles). The identity needs `bedrock:InvokeModel` on that model in the
configured region. Skills are offered as tools whose arguments are the
entities the duck believes in, so the model acts only through calls local
code can check; it never sends motor values. Any invalid, missing, or
failed answer falls back to the local policy and is recorded. Never commit
credentials; model usage is billed to the AWS account.

## Principles

- **Persistent:** identity, memory, goals, and learning survive restarts.
- **Embodied:** cognition is grounded in what the robot can actually sense and do.
- **Honest evaluation:** privileged simulator state scores the agent and is never an input.
- **Inspectable:** every decision can be traced from perception to outcome.
- **Safe by construction:** actions are bounded, interruptible, and auditable.
- **Simple first:** add a mechanism only when an experiment in the ledger shows it is needed.

## Status

Milestones 0 to 5a and World 2 are complete, and Milestone 6's first criterion is met (see the report's results, section 6):

- From the robot's own senses, with an explicit task, the mind tidies as
  well as the lab's hand-tuned controller on held-out rooms (E-008).
- The Bedrock cloud brain made 370 decisions with no invalid action
  reaching the body (E-010).
- With no task, needs and a measured goal scorecard produce the same
  tidying as an explicit task, and in a tidy room the duck rests or
  explores 98% of the time (E-014).
- With its owner's approval as its only social need, and an owner who
  says only whether she likes something (the phrase list is
  `src/birdbrain/phrases.toml`), the duck learns over a life of ten rooms
  which of three hidden preferences she holds: toys in the basket, by the
  walls, or left alone. Without an owner it does not tidy (E-015).
- Two plausible fixes for lost toys and rim falls were measured and refuted;
  truth measures found the real causes (E-016).
- Causal rules, Bayesian logistic models over conditions the duck believes
  hold, predict its own outcomes better than counts on outcomes they had not
  seen. Choosing by their means did worse, so decisions still use counts
  (E-017).

- Three ways of letting the rules choose were all worse in development:
  posterior draws explored risky picks, an upper bound on falls paralysed
  the duck, and the owner model over conditions learned more slowly (E-018).
- The cloud brain writes skills (`--author`). After each room the duck names
  the situation where a skill most clearly fails; the cloud brain writes a
  program for it; the duck tries it against the original and keeps it only
  on evidence. On 16 held-out lives it kept a written skill in 11, and
  success in those situations rose 8 to 10 points with no more falls (E-019).
- Judged fairly (no prior, turns, then Thompson sampling, and under review
  after keeping), written skills still raised success in their situations
  by 7 to 10 points, with a task and with an owner. The duck kept 6 of 44
  and retired 3. With the task the room lost a tenth of a toy, because a
  better written delivery is slower (E-020).

- In World 2 (`--world world2`: 24 kinds of object whose weight, width and
  grip follow how they look, furniture, inner walls, an owner who wants her
  blue things left alone), the playroom's mind tidied 30% of what it could
  carry and learned nothing about objects (E-021). After re-measuring the
  camera at range and letting the rules use each object's size and colour,
  it tidies 40%, mostly leaves alone what it has learned it cannot carry,
  including kinds it never met, and pleases the owner a little more. Falls
  rose, and heavy objects are still not learned well (E-022 to E-025).

- A second round in World 2 (E-026 to E-032): a heavy-tailed prior lets
  the rules believe strong effects (the duck now avoids what makes it
  fall); objects are detected by how wide they look, so small ones are no
  longer forgotten (the playroom gained a third of a toy a room); the duck
  maps what is in its way from its range sensor, walks round it, and
  explores the edge of what it has seen; and with an owner it values her
  reactions correctly and no longer sits idle.

- The cloud brain's general knowledge did not help in World 2: as a prior
  about unfamiliar objects it was confidently wrong (E-036), and deciding
  from the duck's own measurements it did as well as the local policy, at
  about 52,000 tokens a room (E-037).
- Milestone 6 (`--agent A|B|C|D`): on fresh lives, the developmental agent
  (needs, deciding with its rules) gains 11.5 points of tidying from ten
  rooms of experience, and 14.5 more than the proactive agent, whose
  counts per skill gain nothing. The same holds when the duck must learn
  what to do from its owner: D's experience adds 0.51 more to her measure
  a room than C's with the basket owner, and 0.30 (not clear of zero)
  with the owner who wants her blue things left alone (E-040). With a
  task, experience buys safety:
  4.6 fewer failed picks and 0.6 fewer falls a room. Recovery after the
  owner changes her preference (`--owner-change 11:hers`) was not shown;
  that test was too weak (E-038).

Next: a stronger test of recovery after the owner's change (agent D,
basket owner to leave-it owner), then curiosity driven by learning
progress in agent D (H-005). The roadmap is in
[`docs/design.md`](docs/design.md#9-roadmap).
