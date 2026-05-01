# Wall Garden — Development Guide for Agentic Coding

## Stack overview

What's actually in the box (so you don't have to grep):

### Daemon (`daemon/`)

- **Python 3.11**, managed by `uv`. `pyproject.toml` is the source of truth.
- **psycopg 3** (binary) for Postgres — both writes and `LISTEN/NOTIFY`.
- **pydantic** for config models. **structlog** for logs.
- **hypothesis** for property tests on `safety.py`.
- **Pillow** for the camera mock's synthetic plant images.
- **Pi-only optional deps** (`[project.optional-dependencies.pi]`): `adafruit-blinka`, `adafruit-circuitpython-{ads1x15,bme280,bh1750}`, `gpiozero`, `picamera2`. Not installed on macOS.

### Web (`web/`)

- **Ruby 3.4.7, Rails 8.1, PostgreSQL 16** with `pgvector`. **Puma 8 on :3100**.
- **Assets:** Propshaft + importmap-rails. **No Node toolchain.**
- **Frontend:** Hotwire (Turbo + Stimulus), Bootstrap CSS, Bootstrap Icons (`bi bi-*`), `simple_form`. Strict-locals partials (`<%# locals: (zone:) %>`).
- **Auth:** Devise + devise-i18n.
- **Authorization:** Pundit (`app/policies/`, `Pundit::Authorization` in `ApplicationController`).
- **Background jobs:** SolidQueue + SolidCable. `mission_control-jobs` UI at `/jobs`.
- **LLM:** `ruby_llm` wrapped in `app/ai/` (`Ai::Client`, `Ai::VisionClient`, `Ai::Prompts::*`, dedicated error classes). **Never call `ruby_llm` directly outside `app/ai/`.**
- **Translations:** `rails-i18n`. Add `mobility` only when a column needs to be translatable.
- **Search/filter:** Ransack with explicit `ransackable_attributes` allowlists — Ransack silently ignores fields not on the list.
- **Service objects:** `app/services/wall_garden/` (e.g. `WallGarden::AnomalyDetector`, `WallGarden::NtfyDispatcher`).
- **Tests:** RSpec + factory_bot + faker + capybara + selenium-webdriver + simplecov + vcr + webmock + pundit-matchers. **No minitest.**

## Build and test commands

```bash
# Daemon
cd daemon && uv run pytest           # all daemon tests including hypothesis
cd daemon && uv run pytest tests/test_safety.py -k hysteresis
cd daemon && uv run python -m wallgardend.main   # run daemon directly

# Web
cd web && bin/setup
cd web && bin/dev                    # Rails on :3100
cd web && bin/jobs                   # SolidQueue worker
cd web && bin/ci                     # rspec + brakeman + hypothesis
cd web && bundle exec rspec spec/models/zone_spec.rb
cd web && bundle exec rspec spec/features/dashboard_spec.rb
cd web && bin/brakeman               # security scan

# Whole stack
bin/dev                              # web + jobs + daemon via Procfile.dev
WALLGARDEN_SIM_SPEED=60 bin/soak     # 7 simulated days (~3h wall time)
```

## Code style

### Daemon

- `safety.py` is **pure functions only** — no I/O, no time, no random. All inputs explicit. Easy to property-test.
- `hardware/backend.py` is the only place hardware contracts are declared. Daemon code imports the `Protocol`, never concrete backends.
- `simulator.py` and `pi.py` are siblings — `factory.py` selects between them based on `WALLGARDEN_BACKEND`.
- I/O failures return `None`; callers check. Don't raise across the hardware boundary.
- Logging: `structlog` with bound context (`zone_id`, `loop_count`).

### Web

- Every model declares `ransackable_attributes` and `ransackable_associations` allowlists.
- Every controller action is authorized with Pundit (`authorize @zone`).
- Every partial uses strict locals: `<%# locals: (zone:, compact: false) %>`.
- I18n everything: `t('zones.actions.water')`, never bare strings in views.
- LLM calls go through `Ai::Client` only. Prompts live in `app/ai/prompts/`. Tests use VCR cassettes.
- Background jobs catch `Ai::Error` and write an `alerts` row instead of raising — the control loop must never see an LLM failure.

## Project-specific gotchas

- **Postgres-down → no watering.** The daemon refuses to pump if it can't read recent watering events to enforce the daily cap. Test T17.
- **Manual overrides bypass the moisture threshold but not the interlocks or daily cap.** Document this in any "manual water" UI. Test T13 (per slice 7 soak).
- **Pump runtime is hard-capped at 15 s in `pumps.py`** regardless of requested mL. A stuck relay or runaway calculation cannot cause a flood.
- **Warm-up grace:** the first 60 s after daemon start, no pump fires. Don't let tests assert otherwise.
- **`alerts` are idempotent on `code+zone_id+window`.** Don't fire `reservoir_empty` 100 times — fire once, dispatch once, set `dispatched_at`.

## Database and migrations

- Rails migrations are the source of truth for the schema; the daemon reads — never DDL.
- `shared/schema.sql` is a human-readable mirror. If you change a migration, update the mirror in the same commit.
- Models that the daemon writes (sensor_readings, watering_events, alerts, daemon_heartbeats) are **append-only** from the daemon's perspective; Rails owns updates (acknowledgements, dispatch markers).

## Deployment

- Dev: `bin/dev` (foreman). Postgres in Docker.
- Pi (later): Kamal. Rails as the main app; Python daemon as a Kamal accessory container. `--device` access for `/dev/i2c-1`, `/dev/gpiochip0`, `/dev/video0`.
- Fallback: `deploy/systemd/*.service` for direct systemd if Kamal proves heavy on the Pi.

## When in doubt

Look at `/Users/iv/Projectos/culinar/culinari/` — that's the stylistic reference for `app/ai/`, services namespacing, Pundit usage, simple_form, RSpec layout, and binstubs.
