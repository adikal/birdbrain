# Architecture

BirdBrain separates long-lived cognition from the body it controls. All major
events are recorded so a run can be inspected, replayed, and compared.

## System context

```text
                        +----------------------+
                        | BirdBrain Dashboard  |
                        | live state + replay  |
                        +----------^-----------+
                                   | events
+-------------+  observations  +---+------------------+  memory  +-----------+
| Environment +--------------->+ Agent Runtime       +<-------->+ Memory    |
| Adapter     +<---------------+ perception/planning |          | Service   |
+------+------+    actions     +---+---------+--------+          +-----------+
       |                           |         |
+------v------+               +----v----+ +--v----------------+
| MuJoCo     |               | Cloud   | | Skills + Goal     |
| Microduck  |               | LLM     | | Learning          |
+-------------+               +---------+ +-------------------+
```

## Components

### Agent runtime

Owns the perceive-deliberate-act loop. It constructs bounded cognition requests,
selects goals and skills, enforces action policies, and publishes structured
events. The runtime must remain functional when cloud cognition is unavailable.

### Cognition provider

Wraps cloud LLM calls behind a provider-neutral interface. Inputs and outputs are
structured and traceable. Secrets never enter event logs or prompts by default.

#### AWS Bedrock provider

AWS Bedrock is the next cloud provider target. The adapter will call the
Bedrock Runtime Converse API through `boto3`, translate BirdBrain's bounded
cognition request into the common message format, and validate the result
against the same goal-and-skill schema used by other providers. Model and region
selection will remain configuration rather than runtime policy.

Local development will use the standard AWS credential chain so existing AWS
profiles, SSO sessions, temporary credentials, IAM roles, and Bedrock bearer
tokens can work without credentials appearing in source code. The runtime
identity requires `bedrock:InvokeModel`; streaming will additionally require
`bedrock:InvokeModelWithResponseStream`. The selected model must be available in
the configured region and enabled for the AWS account. Some third-party models
can require AWS Marketplace permissions or a one-time provider use-case form.

The adapter will record provider, model, region, request latency, token usage,
and sanitized error categories for dashboard inspection. It will never record
credentials or raw authentication metadata. AWS charges remain external to
BirdBrain, so per-run budgets and cost telemetry will be enforced before the
provider becomes the default. Authentication failures, throttling, unavailable
models, timeouts, or malformed responses immediately return control to the
deterministic local cognition baseline.

### Memory service

Maintains three distinct stores:

- episodic events: append-only observations, actions, outcomes, and reflections;
- semantic wiki: consolidated facts with provenance, confidence, and revision;
- working memory: small task context with explicit expiry.

### Goals and skills

Goals carry motivation, evidence, priority, constraints, and completion tests.
Skills expose preconditions, parameters, execution status, and learned outcome
models. Self-generated goals pass novelty, safety, and resource-budget gates.

### Environment adapter

The adapter normalizes observations, actions, reset, time, and capability
discovery. The first implementation targets MuJoCo Microduck; hardware later
implements the same boundary with stricter safety limits.

### BirdBrain dashboard

The dashboard is an observability client, not a second source of truth. It shows
the world model, current mind state, goal pecking order, memories, experiments,
failures, and replayable cognitive history.

### Cognition baseline

The first end-to-end policy is deliberately deterministic: it turns normalized
observations into episodic records and sourced wiki facts, retrieves relevant
episodes, ranks bounded candidate goals, constructs a short plan, and invokes a
named skill. Each boundary emits an event so a future cloud LLM provider can
replace deliberation without changing memory, execution, evaluation, or the
dashboard contract.

The implemented optional cloud provider calls the OpenAI Responses API with a
strict JSON schema. AWS Bedrock will implement the same bounded contract through
the Converse API. A cloud model can select only a candidate goal and a
registered skill; it cannot emit actuator values. Provider credentials stay
outside source and event data, failures emit a trace event, and the
deterministic policy immediately takes over.

Episodic records are periodically consolidated into semantic observation
profiles with source run IDs. Materially incompatible object positions become
explicit belief conflicts. The skill library records attempts, outcomes, and
bounded control amplitudes, making every parameter update replayable.

## Event model

Every observation, state transition, model call, memory mutation, selected goal,
skill invocation, action, and outcome receives a run ID, monotonic sequence,
wall-clock time, simulation time, and schema version. Large sensor payloads are
stored as content-addressed artifacts referenced by events.

The first recorder appends each envelope to a per-run JSONL log and maintains an
atomic summary index. The local read-only bridge exposes live Server-Sent Events
plus a run catalog and bounded historical replay API; recordings can therefore
be reopened after the runtime restarts.

The evaluator derives completion, anomaly, stability, confidence, and cognitive
cycle metrics solely from immutable events. Its 0–100 score is a regression
signal rather than a claim about general intelligence; comparisons retain every
component delta so score changes remain explainable.

## Safety boundary

The runtime validates actions against adapter capabilities, resource budgets,
and an independent policy layer. A watchdog can halt motion without consulting
the LLM. Simulation is the default environment until explicit hardware gates are
satisfied.

## Initial technology direction

- Python 3.11+ core runtime and simulator integration
- typed internal event schemas and append-only local storage first
- MuJoCo for deterministic embodied experiments
- web dashboard fed by a read-only event stream
- provider-neutral cloud cognition interface

Technology choices for durable databases and the dashboard framework remain
deliberately open until traces from the first simulator loop reveal their actual
requirements.
