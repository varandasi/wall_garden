"""Postgres access — a thin connection pool + a few high-traffic helpers.

Schema lives in Rails migrations (Rails is the source of truth). The daemon
reads/writes a small fixed set of tables; SQL strings live here next to the
shape of each call.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def init_pool(dsn: str, min_size: int = 1, max_size: int = 4) -> None:
    """Create the process-wide pool. Called once from `main.py`."""
    global _pool
    if _pool is not None:
        return
    _pool = ConnectionPool(
        conninfo=dsn,
        min_size=min_size,
        max_size=max_size,
        kwargs={"row_factory": dict_row, "autocommit": True},
        open=True,
    )


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def conn() -> Iterator[psycopg.Connection]:
    if _pool is None:
        raise RuntimeError("db pool not initialised — call init_pool() first")
    with _pool.connection() as c:
        yield c


# --- Insert helpers ---------------------------------------------------------


def insert_sensor_reading(
    *,
    taken_at,
    zone_id: int | None,
    kind: str,
    raw: float | None,
    value: float,
    unit: str,
    quality: int = 1,
) -> None:
    sql = (
        "INSERT INTO sensor_readings (taken_at, zone_id, kind, raw, value, unit, quality) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)"
    )
    try:
        with conn() as c, c.cursor() as cur:
            cur.execute(sql, (taken_at, zone_id, kind, raw, value, unit, quality))
    except Exception as exc:                # pragma: no cover — defensive
        log.warning("sensor_reading insert failed: %s", exc)


def insert_heartbeat(loop_count: int, last_error: str | None = None) -> None:
    try:
        with conn() as c, c.cursor() as cur:
            cur.execute(
                "INSERT INTO daemon_heartbeats (loop_count, last_error) VALUES (%s, %s)",
                (loop_count, last_error),
            )
    except Exception as exc:                # pragma: no cover
        log.warning("heartbeat insert failed: %s", exc)


def insert_alert(
    *,
    severity: str,
    code: str,
    message: str,
    source: str = "daemon",
    zone_id: int | None = None,
) -> None:
    """Idempotent on (code, zone_id) within a 10-minute window."""
    sql = (
        "INSERT INTO alerts (severity, source, code, zone_id, message) "
        "SELECT %s,%s,%s,%s,%s WHERE NOT EXISTS ("
        "  SELECT 1 FROM alerts WHERE code=%s AND COALESCE(zone_id,-1)=COALESCE(%s,-1) "
        "  AND fired_at > now() - interval '10 minutes')"
    )
    try:
        with conn() as c, c.cursor() as cur:
            cur.execute(sql, (severity, source, code, zone_id, message, code, zone_id))
    except Exception as exc:                # pragma: no cover
        log.warning("alert insert failed: %s", exc)


# --- Reads ------------------------------------------------------------------


def fetch_zones() -> list[dict[str, Any]]:
    sql = "SELECT * FROM zones WHERE enabled = TRUE ORDER BY id"
    try:
        with conn() as c, c.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchall())
    except Exception as exc:                # pragma: no cover
        log.warning("fetch_zones failed: %s", exc)
        return []


def ml_today(zone_id: int) -> float:
    sql = (
        "SELECT COALESCE(SUM(actual_ml), 0) AS s FROM watering_events "
        "WHERE zone_id=%s AND started_at >= date_trunc('day', now() at time zone 'UTC')"
    )
    try:
        with conn() as c, c.cursor() as cur:
            cur.execute(sql, (zone_id,))
            row = cur.fetchone()
            return float(row["s"]) if row else 0.0
    except Exception as exc:                # pragma: no cover
        log.warning("ml_today failed: %s", exc)
        return 0.0


def claim_pending_command() -> dict[str, Any] | None:
    """Atomic claim — at most one runner sees the command."""
    sql = (
        "UPDATE commands SET status='claimed', claimed_at=now() "
        "WHERE id = (SELECT id FROM commands WHERE status='pending' "
        "            ORDER BY requested_at FOR UPDATE SKIP LOCKED LIMIT 1) "
        "RETURNING *"
    )
    try:
        with conn() as c, c.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()
    except Exception as exc:                # pragma: no cover
        log.warning("claim_pending_command failed: %s", exc)
        return None


def insert_photo(*, taken_at, path: str, zone_id: int | None = None) -> int | None:
    sql = (
        "INSERT INTO photos (taken_at, path, zone_id) VALUES (%s, %s, %s) RETURNING id"
    )
    try:
        with conn() as c, c.cursor() as cur:
            cur.execute(sql, (taken_at, path, zone_id))
            row = cur.fetchone()
            return int(row["id"]) if row else None
    except Exception as exc:                # pragma: no cover
        log.warning("insert_photo failed: %s", exc)
        return None


def start_watering_event(
    *,
    zone_id: int,
    started_at,
    planned_ml: int,
    trigger: str,
    pre_moisture_pct: float | None,
) -> int | None:
    sql = (
        "INSERT INTO watering_events (zone_id, started_at, planned_ml, trigger, pre_moisture_pct) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id"
    )
    try:
        with conn() as c, c.cursor() as cur:
            cur.execute(sql, (zone_id, started_at, planned_ml, trigger, pre_moisture_pct))
            row = cur.fetchone()
            return int(row["id"]) if row else None
    except Exception as exc:                # pragma: no cover
        log.warning("start_watering_event failed: %s", exc)
        return None


def complete_watering_event(
    *,
    event_id: int,
    ended_at,
    actual_ml: int,
    post_moisture_pct: float | None,
    aborted_reason: str | None = None,
) -> None:
    sql = (
        "UPDATE watering_events "
        "SET ended_at=%s, actual_ml=%s, post_moisture_pct=%s, aborted_reason=%s "
        "WHERE id=%s"
    )
    try:
        with conn() as c, c.cursor() as cur:
            cur.execute(sql, (ended_at, actual_ml, post_moisture_pct, aborted_reason, event_id))
    except Exception as exc:                # pragma: no cover
        log.warning("complete_watering_event failed: %s", exc)


def complete_command(cmd_id: int, *, ok: bool, result: dict[str, Any] | None = None) -> None:
    sql = (
        "UPDATE commands SET status=%s, completed_at=now(), result=%s::jsonb "
        "WHERE id=%s"
    )
    try:
        import json
        with conn() as c, c.cursor() as cur:
            cur.execute(sql, ("done" if ok else "failed", json.dumps(result or {}), cmd_id))
    except Exception as exc:                # pragma: no cover
        log.warning("complete_command failed: %s", exc)
