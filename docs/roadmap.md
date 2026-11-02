# Staged development roadmap

## Phase 0 — Foundations

- define core state, event, cognition, memory, skill, and adapter contracts;
- establish tests, formatting, type checking, and continuous integration;
- document threat model, privacy model, and reproducibility conventions.

**Exit:** a deterministic fake environment can run and replay a short agent loop.

## Phase 1 — MuJoCo Microduck

- create the Microduck body, sensors, actuators, and small test arena;
- implement the MuJoCo adapter and deterministic scenario fixtures;
- add manual controls, emergency stop, action limits, and video capture.

**Exit:** scripted locomotion and object interaction pass repeatable scenarios.

## Phase 2 — Memory and cloud cognition

**Current baseline:** durable episodic memory, a provenance-aware semantic wiki,
retrieval traces, and a provider-neutral deterministic cognition boundary are
implemented. Cloud model adapters, consolidation, and contradiction handling
remain.

- add structured provider-neutral LLM requests with budgets and trace capture;
- implement append-only episodic memory and provenance-aware semantic wiki;
- build retrieval, reflection, consolidation, and contradiction handling.

**Exit:** the agent recalls relevant prior episodes across restarts and explains
which memories influenced a decision.

## Phase 3 — Goals and skills

**Current baseline:** ranked goal proposals, explicit plans, named skill
invocations, and deterministic regression scoring run in MuJoCo. Learned skill
parameters and multi-step task completion remain.

- implement competing goal selection (the "pecking order");
- generate bounded goals from needs, novelty, and unresolved predictions;
- represent skills with preconditions and outcomes; learn from attempts;
- evaluate with fixed seeds, baselines, ablations, and regression scenarios.

**Exit:** the duck autonomously selects and completes a multi-step simulator goal.

## Phase 4 — BirdBrain dashboard

**Current baseline:** live traces, persistent replay, scored run selection, and
side-by-side metric comparison are implemented.

- stream the world model and internal state in real time;
- visualize goals, attention, confidence, memories, surprises, and failures;
- add "Rewind the Quack" timeline replay and run comparison;
- surface costs, latency, safety interventions, and uncertainty.

**Exit:** any decision in an evaluation run can be traced from perception through
memory and deliberation to action and outcome.

## Phase 5 — Hardware readiness

- define hardware capabilities and calibration behind the adapter boundary;
- add degraded/offline behavior, telemetry health checks, and hard watchdogs;
- use simulation-to-real tests, staged authorization, and supervised trials.

**Exit:** a hardware readiness review passes before any autonomous physical run.

## Cross-cutting research practice

Each phase keeps experiment manifests, seeded scenarios, immutable traces,
explicit hypotheses, and decision records. Privacy, cost ceilings, safety limits,
and data retention are tested features rather than afterthoughts.
