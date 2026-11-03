# Instructions for agents working on BirdBrain

Read `README.md` for what BirdBrain is, `docs/design.md` (the technical report) for how it is built,
and `docs/ledger.md` for what has been tried and learned. Keep the ledger
current: it is the project's memory of its own research.

## Workspace layout

BirdBrain is one of two side-by-side checkouts. Microduck Lab holds two more.

| Path | Owner | Role | Edit it? |
|---|---|---|---|
| `birdbrain/` | adikal | The mind, memory, skills, dashboard, experiments | Yes |
| `microduck-lab/` | jonathanhawkins | MuJoCo world, simulated senses, lab brains, `/sim` viewer | No |
| `microduck-lab/microduck/` | pollen-robotics | Robot software (Rust daemons) and shipped ONNX policies | No |
| `microduck-lab/microduck_rl/` | pollen-robotics | MJCF robot models and the GPU training stack | No |

Treat the three upstream checkouts as read-only dependencies. BirdBrain
integrates through Microduck Lab's public Python API (`microduck_local`) and
registers its own brain at runtime. If an upstream change seems necessary,
record the reason in the ledger and ask the owner of this repo first.

## Setup

Requirements: macOS on Apple Silicon or Linux, git, Python 3.12 (Microduck
Lab requires `>=3.12,<3.13`), [uv](https://docs.astral.sh/uv/), and Node 20+
for the lab's browser viewer.

```bash
mkdir birdbrain-workspace && cd birdbrain-workspace
git clone git@github.com:adikal/birdbrain.git
git clone https://github.com/jonathanhawkins/microduck-lab

# Pin the lab. Its setup script then pins Pollen's repos and policies itself.
git -C microduck-lab checkout 8dad9218062f7b0ad29ae6d564305411f5a117c2
(cd microduck-lab && ./scripts/setup.sh)

# One environment for BirdBrain and the lab, in birdbrain/.venv.
cd birdbrain
uv venv -p 3.12 .venv
uv pip install --python .venv/bin/python \
  -e ../microduck-lab/microduck_local \
  -e '.[dev,cloud]'
.venv/bin/pytest
```

`setup.sh` clones `pollen-robotics/microduck_rl` at `badc4e7f` and
`pollen-robotics/microduck` at `2c61dcc` inside `microduck-lab/`, downloads
nine shipped policies from the Hugging Face repo
`pollen-robotics/microduck-policies`, runs `uv sync` and `npm install`, and
runs the lab's smoke tests. Expect `56 passed, 1 skipped`.

BirdBrain installs no simulator of its own. MuJoCo comes from Microduck Lab,
which pins 3.10.x so that MJCF parsing matches Pollen's training stack.

When bumping the Microduck Lab pin, rerun `setup.sh`, the lab's smoke tests,
BirdBrain's tests, and the baseline experiment in the ledger, and record the
bump as a ledger entry.

## Checking the setup

```bash
# BirdBrain's tests.
.venv/bin/pytest

# The lab's own headless recorder: a scripted tidy brain in the playroom.
cd ../microduck-lab/microduck_local
uv run record-world playroom --brain d0=tidy --seconds 120 --seed 1 --stride 10 --out /tmp/rw-tidy
```

`record-world` writes `events.txt`, `sheet.png`, and `world.mp4`. Read
`events.txt` and look at `sheet.png` before describing what the duck did.

## Running and watching

- **Experiments:** `.venv/bin/birdbrain-run --seeds 16 --seconds 300 --jobs 8 --out <rows.jsonl>`
  (add `--provider bedrock` for the cloud brain, `--latency real` to let the
  world run while it thinks). `--needs` gives no task: the duck acts on its
  needs and self-generated goals; `--room tidy` starts every toy in the
  basket. `--speculate` asks for the next decision while a skill runs (off by
  default, ledger E-013). `--memory DIR` keeps skill records across runs
  (forces `--jobs 1`). `--owner basket|wall|leave|none` (Milestone 3b) makes
  the social need approval, with a scripted owner of that hidden preference;
  `--episodes 10` runs each seed as a life of 10 rooms with memory under
  `--memory` (default `data/lifetimes/<tag>`), and
  `scripts/lifetimes.py` summarizes the rows. `--credit moments|underway`
  chooses how reactions are credited (E-016). Causal rules are learned and
  scored in every run (`scripts/predictions.py`); `--rules` also decides with
  them (E-017). The owner's phrases are in
  `src/birdbrain/phrases.toml` (or `BIRDBRAIN_PHRASES`). Compare arms with `.venv/bin/birdbrain-compare A.jsonl B.jsonl`.
  Event logs go to `data/runs/` (set `BIRDBRAIN_RUNS_DIR` to change it).
- **The mind:** `.venv/bin/birdbrain-dashboard --live --seed 3 [--needs] [--room tidy] [--owner basket]`, then open
  `http://127.0.0.1:8790`. Without `--live` it replays recorded runs;
  `?run=<id>&t=<seconds>&truth=1` opens a run at a time with the truth
  overlay on. Live runs record the duck's head-camera image at 2 Hz; add
  `--camera` to `birdbrain-run` to record it (and the truth overlay) for
  replay. It binds to loopback only and checks the Host header; use an SSH
  tunnel for remote viewing.
- **The body:** `.venv/bin/birdbrain-record playroom --brain d0=birdbrain --seconds 120 --out /tmp/rec`
  writes the lab's `world.mp4`, `sheet.png`, and `events.txt` for a
  BirdBrain run. The lab's live viewer (`uv run duck-lab --world playroom`
  in `microduck-lab/microduck_local`, then `npm run dev` in `duck-viewer`)
  shows its own brains.
- **Diagnostics:** `scripts/perception_probe.py`, `pick_probe.py`, and
  `fall_probe.py` compare the mind's beliefs with simulator truth;
  `scripts/outcomes.py` and `scripts/cloud_report.py` summarize recorded
  runs. They read truth for evaluation only and are never imported by the mind.

## Cloud brain (AWS Bedrock)

Credentials come from the standard AWS chain. Never write keys, tokens, or
account secrets into the repository, prompts, or event logs.

```bash
export AWS_PROFILE=default            # any profile with bedrock:InvokeModel
export AWS_REGION=us-west-2
export BIRDBRAIN_BEDROCK_MODEL=us.anthropic.claude-sonnet-5-5
.venv/bin/birdbrain-run --provider bedrock --seeds 1 --seconds 60 --out /tmp/check.jsonl
```

Sonnet 5.5 on Bedrock rejects a forced tool choice and `temperature`
(ledger E-009). A 300 s run makes about 22 decisions and uses about 45k
input tokens.

## Working rules

- **Follow the scientific loop.** State a hypothesis and a prediction in
  `docs/ledger.md` before running an experiment. Record the command, seed,
  and commit, then the numbers, then what they mean and what changes.
- **Measure before assuming.** Read Microduck Lab's measured walker facts
  (`uv run walker-facts`) before writing a skill. For example, forward
  commands below about 0.2 m/s produce no motion with the shipped walker.
- **Borrow ideas freely, follow none blindly.** *Creatures*, *A Brief
  History of Intelligence*, and recent papers are inspiration. Propose
  variations and new ideas as ledger hypotheses and let results decide.
- **Keep it simple.** Prefer one general mechanism over several special
  cases. Add a component only when a ledger entry shows the simpler design
  failing, and link that entry from the code or the design doc.
- **No privileged state in the mind.** Cognition reads `Observation` and its
  own memory. Only `lab.py` touches lab types, and only `run.py` and the
  diagnostic scripts read simulator truth; `tests/test_lab.py` enforces the
  import boundary.
- **Look at the run.** After a behavior change, record a run and read its
  events and contact sheet. A passing test does not show that the duck did
  the right thing.
- **Do not push** to GitHub unless the repository owner asks.
