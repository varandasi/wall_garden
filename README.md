# Wall Garden Caretaker

A vertical wall garden agent that keeps your plants alive when you're not around.

A Python control daemon owns the hardware (sensors + pumps + camera) and runs a deterministic safety loop. A Rails 8 dashboard reads the same Postgres database, drives Claude (via `ruby_llm`) for weekly analysis and photo vision, dispatches notifications, and exposes manual controls.

Hardware is currently **mocked** — everything runs against a `SimulatorBackend` that fakes a wall, fakes plants, fakes sensor noise, and fakes failures on demand. Real-Pi support is wired in as a swap-in `PiBackend` for when the hardware arrives.

## Quick start

```bash
bin/setup        # bundle, uv sync, docker compose up, db:setup, seed
bin/dev          # web on :3100, jobs, daemon (simulator)
bin/jobs         # SolidQueue worker (started by bin/dev too)
bin/ci           # rspec + brakeman + hypothesis tests
```

Open `http://localhost:3100` and log in as the seeded user.

## Layout

- `daemon/` — Python control daemon (the hardware-side process)
- `web/` — Rails 8 dashboard, jobs, LLM wrapper (`app/ai/`)
- `shared/` — describes the DB-as-contract between daemon and web
- `deploy/` — Kamal config + systemd fallback for Pi
- `docs/` — architecture, hardware BOM, calibration, runbook

See [AGENTS.md](AGENTS.md) for development conventions.
See [docs/SIMULATOR.md](docs/SIMULATOR.md) for how to inject sensor failures.
See [docs/RUNBOOK.md](docs/RUNBOOK.md) for what each alert means.
# wall_garden
