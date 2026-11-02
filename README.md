# BirdBrain

**Small duck. Big thoughts.**

BirdBrain is a research platform for a persistent autonomous embodied agent. It
combines cloud-LLM cognition, durable semantic and episodic memory,
self-generated goals, learned skills, and an inspectable dashboard. Development
starts in a MuJoCo-based Microduck simulator and is designed to transfer to
physical hardware later.

## Principles

- **Persistent:** identity, memory, goals, and learning survive process restarts.
- **Embodied:** cognition is grounded in observations and actions through a
  simulator-or-hardware adapter.
- **Inspectable:** every decision can be traced in the BirdBrain dashboard.
- **Safe by construction:** actions are bounded, interruptible, and auditable.
- **Adapter-first:** cognition does not depend on a specific simulator or robot.

## Repository layout

```text
src/birdbrain/       Core Python package
src/birdbrain/assets First Microduck MJCF arena
dashboard/            BirdBrain debugging dashboard
tests/               Minimal unit tests
docs/architecture.md System boundaries and data flow
docs/roadmap.md      Staged development plan
```

## Quick start

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,sim]'
pytest
```

The `sim` extra installs the pinned MuJoCo engine and its canonical Python
bindings. MuJoCo's native library is bundled in that package; no separate
system-wide simulator installation is required.

The initial MuJoCo environment includes an articulated Microduck with five
position-controlled joints, proprioceptive sensors, movable toys, a charging
zone, and a bounded test arena. It runs without a display through the
`MujocoMicroduckAdapter`.

Run the live debugging dashboard and simulator bridge with:

```bash
source .venv/bin/activate
birdbrain-dashboard
```

Open `http://127.0.0.1:8787` to inspect versioned live events. Runs are durably
recorded as JSONL under `data/runs`; the run selector can reopen and replay a
completed session after a restart. The private hosted dashboard uses the same
interface in sample-data mode.

The baseline cognition loop records observations and episodes, updates a
provenance-aware semantic wiki, ranks self-generated goals, creates plans, and
invokes simulator skills. Completed runs receive a deterministic regression
score, and the dashboard can compare two traces metric by metric. Durable memory
is stored under `data/memory`.

See [the architecture](docs/architecture.md) and [roadmap](docs/roadmap.md) for
the planned system.

## Status

Phase 0: foundations. Interfaces are intentionally small while the research
questions and simulator integration are validated.
