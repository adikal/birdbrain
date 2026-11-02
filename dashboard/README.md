# BirdBrain dashboard

The dashboard is a buildless, responsive debugging surface for the agent. The
first version uses a deterministic sample run so the observability schema and
interactions can evolve independently of the runtime transport.

It includes:

- top-down observed and remembered world state;
- goals, rationale, attention, confidence, energy, and active skill;
- body telemetry and actuator targets;
- filterable event trace and raw JSON inspection;
- anomalies and belief conflicts;
- timeline scrubbing and replay ("Rewind the Quack").

To preview locally:

```bash
python -m http.server 4173 --directory dashboard
```

Then open `http://127.0.0.1:4173`.

The next integration replaces the sample-frame generator in `app.js` with the
same versioned event snapshots emitted by the Python runtime, using a local
read-only HTTP and WebSocket bridge.
