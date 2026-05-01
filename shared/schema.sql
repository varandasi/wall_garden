-- shared/schema.sql — human-readable mirror of the canonical Rails schema.
-- Update this file in the same commit as any web/db/migrate/ change.
-- The daemon does NOT execute DDL; Rails owns migrations.

CREATE EXTENSION IF NOT EXISTS vector;

-- Devise users.
CREATE TABLE users (
  id               BIGSERIAL PRIMARY KEY,
  email            TEXT NOT NULL UNIQUE,
  encrypted_password TEXT NOT NULL,
  reset_password_token TEXT UNIQUE,
  reset_password_sent_at TIMESTAMPTZ,
  remember_created_at TIMESTAMPTZ,
  role             TEXT NOT NULL DEFAULT 'member',  -- member | admin
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE plant_profiles (
  id                  BIGSERIAL PRIMARY KEY,
  common_name         TEXT NOT NULL,
  scientific_name     TEXT,
  notes               TEXT,
  ideal_moisture_min  NUMERIC(5,2),
  ideal_moisture_max  NUMERIC(5,2),
  ideal_lux_min       INTEGER,
  ideal_temp_c_min    NUMERIC(4,1),
  ideal_temp_c_max    NUMERIC(4,1),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE zones (
  id                   BIGSERIAL PRIMARY KEY,
  name                 TEXT NOT NULL,
  plant_profile_id     BIGINT REFERENCES plant_profiles(id),
  ads_address          SMALLINT NOT NULL,
  ads_channel          SMALLINT NOT NULL,
  pump_gpio            SMALLINT NOT NULL,
  pump_ml_per_sec      NUMERIC(6,3) NOT NULL DEFAULT 1.5,
  moisture_dry_raw     INTEGER NOT NULL DEFAULT 26000,
  moisture_wet_raw     INTEGER NOT NULL DEFAULT 12000,
  target_moisture_pct  NUMERIC(5,2) NOT NULL DEFAULT 55.0,
  hysteresis_pct       NUMERIC(5,2) NOT NULL DEFAULT 8.0,
  max_ml_per_day       INTEGER NOT NULL DEFAULT 200,
  max_ml_per_event     INTEGER NOT NULL DEFAULT 50,
  cooldown_minutes     INTEGER NOT NULL DEFAULT 60,
  enabled              BOOLEAN NOT NULL DEFAULT TRUE,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sensor_readings (
  id        BIGSERIAL PRIMARY KEY,
  taken_at  TIMESTAMPTZ NOT NULL,
  zone_id   BIGINT REFERENCES zones(id),
  kind      TEXT NOT NULL,
  raw       NUMERIC(10,3),
  value     NUMERIC(10,3) NOT NULL,
  unit      TEXT NOT NULL,
  quality   SMALLINT NOT NULL DEFAULT 1
);
CREATE INDEX idx_readings_taken ON sensor_readings (taken_at DESC);
CREATE INDEX idx_readings_zone_kind_time ON sensor_readings (zone_id, kind, taken_at DESC);

CREATE TABLE watering_events (
  id                BIGSERIAL PRIMARY KEY,
  zone_id           BIGINT NOT NULL REFERENCES zones(id),
  started_at        TIMESTAMPTZ NOT NULL,
  ended_at          TIMESTAMPTZ,
  planned_ml        INTEGER NOT NULL,
  actual_ml         INTEGER,
  trigger           TEXT NOT NULL,         -- auto | manual | llm_suggestion
  pre_moisture_pct  NUMERIC(5,2),
  post_moisture_pct NUMERIC(5,2),
  aborted_reason    TEXT
);
CREATE INDEX idx_watering_events_zone_day ON watering_events (zone_id, started_at);

CREATE TABLE commands (
  id            BIGSERIAL PRIMARY KEY,
  kind          TEXT NOT NULL,
  payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
  status        TEXT NOT NULL DEFAULT 'pending',
  requested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  claimed_at    TIMESTAMPTZ,
  completed_at  TIMESTAMPTZ,
  result        JSONB,
  requested_by  TEXT
);
CREATE INDEX idx_commands_pending ON commands (status, requested_at) WHERE status = 'pending';

CREATE TABLE alerts (
  id              BIGSERIAL PRIMARY KEY,
  fired_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  severity        TEXT NOT NULL,             -- info | warn | critical
  source          TEXT NOT NULL,             -- daemon | rails | llm
  code            TEXT NOT NULL,             -- reservoir_empty | sensor_stuck | daemon_down | ...
  zone_id         BIGINT REFERENCES zones(id),
  message         TEXT NOT NULL,
  dispatched_at   TIMESTAMPTZ,
  acknowledged_at TIMESTAMPTZ
);

CREATE TABLE daemon_heartbeats (
  id          BIGSERIAL PRIMARY KEY,
  beat_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  loop_count  BIGINT NOT NULL,
  last_error  TEXT
);

CREATE TABLE photos (
  id              BIGSERIAL PRIMARY KEY,
  taken_at        TIMESTAMPTZ NOT NULL,
  path            TEXT NOT NULL,
  zone_id         BIGINT REFERENCES zones(id),
  llm_analysis_id BIGINT,
  embedding       vector(1536)
);

CREATE TABLE llm_analyses (
  id                BIGSERIAL PRIMARY KEY,
  ran_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  kind              TEXT NOT NULL,           -- weekly_report | photo | anomaly | digest | chat
  model             TEXT NOT NULL,
  input_tokens      INTEGER,
  output_tokens     INTEGER,
  cache_read_tokens INTEGER,
  prompt_summary    TEXT,
  output            TEXT NOT NULL,
  cost_usd          NUMERIC(8,4)
);

-- LISTEN/NOTIFY triggers (Slice 4 wires AlertDispatcherJob to these).
CREATE OR REPLACE FUNCTION notify_alerts() RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify('wallgarden_alerts', NEW.id::text);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER alerts_after_insert
AFTER INSERT ON alerts
FOR EACH ROW EXECUTE FUNCTION notify_alerts();

CREATE OR REPLACE FUNCTION notify_commands() RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify('wallgarden_commands', NEW.id::text);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER commands_after_insert
AFTER INSERT ON commands
FOR EACH ROW EXECUTE FUNCTION notify_commands();
