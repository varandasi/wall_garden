# Architecture

Two long-running processes plus one Postgres database, on dev (macOS) and on the Pi.

```
+----------------------+        +----------------------+
| wallgardend (Python) |  -->   | Postgres (sensor +   |  <--  | wallgarden-rails (Ruby) |
| - hardware backend   |        |   watering events,   |       | - dashboard, jobs       |
| - safety loop @ 1 Hz |        |   commands, alerts)  |       | - app/ai/ + ruby_llm    |
| - command runner     |  <--   |                      |  -->  | - ntfy + email          |
| - photographer       |        +----------------------+       | - Devise + Pundit       |
+----------------------+                                       +-------------------------+
```

The contract between the daemon and the web app is the database. Postgres
`LISTEN/NOTIFY` triggers wake the daemon when Rails writes a `commands` row,
and wake `AlertDispatcherJob` when a daemon alert fires.

## Hardware abstraction

Every hardware capability hides behind a `Protocol` in
`daemon/wallgardend/hardware/backend.py`. A factory selects between
`SimulatorBackend` (development) and `PiBackend` (real hardware) based on
the `WALLGARDEN_BACKEND` environment variable. The control loop only ever
imports the protocol — it doesn't know whether it's talking to a Pi camera
or a synthetic plant renderer.

## Safety-critical core

`daemon/wallgardend/safety.py` is **pure functions only** — no I/O, no time,
no randomness. `decide_watering` is the heart of the safety logic and is
property-tested with hypothesis. The control loop is a thin orchestration
shell on top.

Hard guards (in priority order):

1. Hardware-level pump runtime cap of 15 s in `pumps` (Pi) and the simulator.
2. Per-event mL cap.
3. Per-day mL cap.
4. Cooldown between events.
5. Reservoir-empty interlock (debounced).
6. Plausibility filter on every reading.
7. Stuck/disconnected sensor detection per-zone.
8. systemd watchdog (30 s) + Pi hardware watchdog (`dtparam=watchdog=on`).
9. Warm-up grace (no pump in first 60 s).
10. Postgres-down → no watering (cap arithmetic needs history).

## LLM layer

All LLM calls go through `web/app/ai/` (Client + VisionClient + Prompts).
Models: `claude-sonnet-4-6` for analysis & vision, `claude-haiku-4-5-20251001`
for digests, anomaly explanations, and chat. Prompt caching marks the
system prompt + plant profiles + last week's report as cacheable.
`WallGarden::CostGuard` skips non-essential jobs when month-to-date spend
exceeds `MONTHLY_LLM_COST_CAP_USD`.
