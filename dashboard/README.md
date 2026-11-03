# BirdBrain dashboard

A buildless, read-only view of one run's event log, served by
`birdbrain-dashboard` at `http://127.0.0.1:8790` (loopback only).

- **What I see:** the duck's head-camera image (rendered from the camera
  pose the detector recorded, with its 116° × 60° field of view) and every
  detection the mind received in that frame, labelled with the object it
  was taken to be. A dashed box is a detection the mind could not place.
  The same field of view is shaded on the map.
- **Bird's-eye view:** what the duck believes is where, each object with its
  uncertainty, the current target, and the duck's trail. "Show simulator
  truth" overlays the true toy positions; they come from viewer-only `TRUTH`
  events and never reach the mind.
- **What's on my mind:** the current action as a tool call, its reason, the
  expected effect, the counted-outcome and model probabilities, and what the
  skill is doing this tick. Chips show decisions, fallbacks, rejected
  choices, tokens, and median cloud latency.
- **Decisions and outcomes:** each choice with its provider, probability,
  outcome, and surprise.
- **Skill record** and **objects I know about:** the mind's statistics and
  beliefs at the selected time.
- **Thought stream** and **raw inspector:** every event, filterable.
- **Rewind the Quack:** the timeline scrubs through 2 Hz snapshots;
  `?run=<id>&t=<seconds>` opens a recorded run at a time.

Start it with `birdbrain-dashboard` to replay recorded runs, or
`birdbrain-dashboard --live --seed 3 [--provider bedrock] [--speed 4]` to
watch a live playroom. Camera images are recorded in live runs (turn off
with `--no-camera`) and in `birdbrain-run --camera` runs.
