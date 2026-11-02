# BirdBrain dashboard

The dashboard is a buildless, responsive debugging surface for the agent. It
automatically connects to the local read-only observability bridge when served
by BirdBrain, and falls back to a deterministic sample run when hosted alone.

It includes:

- top-down observed and remembered world state;
- goals, rationale, attention, confidence, energy, and active skill;
- body telemetry and actuator targets;
- filterable event trace and raw JSON inspection;
- anomalies and belief conflicts;
- timeline scrubbing and replay ("Rewind the Quack");
- scored run selection and side-by-side metric comparison.

The continuous-learning panel reports whether deliberation is local or cloud
backed, model latency and fallback state, memory consolidation/conflicts, and
the latest learned skill amplitude and success rate.

To run it against the real MuJoCo simulator:

```bash
source .venv/bin/activate
birdbrain-dashboard
```

Then open `http://127.0.0.1:8787`. The bridge binds only to localhost by
default and exposes read-only status, snapshot, and Server-Sent Events routes.

The privately hosted Site cannot directly control the simulator. It remains a
safe interactive demo unless a future authenticated relay is introduced.
