# Shared contract

The Python daemon and the Rails app communicate **only through Postgres**. There is no HTTP, no Redis, no MQTT.

## Tables the daemon writes

- `sensor_readings` (append-only) — every reading at 1 Hz with `quality` flag.
- `watering_events` (insert + update on completion) — pump runs.
- `daemon_heartbeats` (append-only) — every 5 s. Rails reads to detect daemon death.
- `alerts` (insert) — when a safety interlock fires.
- `commands` (update of `claimed_at`, `completed_at`, `status`, `result`) — claims rows Rails inserted.
- `photos` (insert) — when `photographer.py` writes a JPEG.

## Tables Rails writes

- `commands` (insert) — `water_zone`, `toggle_lamp`, `snapshot`, `recalibrate`. Daemon claims with `SELECT ... FOR UPDATE SKIP LOCKED`.
- `zones`, `plant_profiles` — runtime config the daemon re-reads every 30 s.
- `alerts.dispatched_at`, `alerts.acknowledged_at` — Rails owns dispatch state.
- `llm_analyses` — Rails owns; daemon never reads.
- `users` — Devise.

## Wake mechanism

Postgres `LISTEN/NOTIFY`. After Rails inserts a `commands` row it does `NOTIFY wallgarden_commands` (via `AFTER INSERT` trigger). The daemon `LISTEN`s on the same channel and wakes immediately, falling back to a 2 s poll if `NOTIFY` is missed.

Same pattern in reverse for alerts: `AFTER INSERT ON alerts → NOTIFY wallgarden_alerts → AlertDispatcherJob enqueued`.

## Schema source of truth

Rails migrations under `web/db/migrate/`. The file at `shared/schema.sql` is a human-readable mirror — keep them in sync when migrations change.
