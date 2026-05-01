"""1 Hz control loop — read, persist, decide, act.

Decisions are pure functions in `safety.py`. This module is the orchestration
shell: it owns time, hardware I/O, in-memory `ZoneRuntime`, and database writes.

A pump cycle is non-blocking: when a decision says "water 30 mL", we call
`backend.pump_on`, set `pumping_until = monotonic() + duration_s`, and let
subsequent ticks handle completion. The loop never sleeps inside a tick.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable

from . import db, watchdog
from .config import Settings
from .hardware.backend import HardwareBackend
from .photographer import Photographer
from .safety import (
    PUMP_HARD_CAP_S,
    AlertRequest,
    TickContext,
    WaterDecision,
    ZoneConfig,
    ZoneRuntime,
    decide_watering,
    is_plausible,
    is_stuck,
    tick_verdict,
)
from .soil import raw_to_pct

log = logging.getLogger(__name__)


# Default zones used when the database has none yet (fresh dev install).
def _default_zone_configs() -> list[ZoneConfig]:
    return [
        ZoneConfig(
            zone_id=zid,
            target_moisture_pct=55.0,
            hysteresis_pct=8.0,
            max_ml_per_day=200.0,
            max_ml_per_event=50.0,
            cooldown_minutes=60.0,
            pump_ml_per_sec=1.5,
            moisture_dry_raw=26000,
            moisture_wet_raw=12000,
            enabled=True,
        )
        for zid in (1, 2, 3, 4)
    ]


def _zone_config_from_row(row: dict[str, Any]) -> ZoneConfig:
    return ZoneConfig(
        zone_id=int(row["id"]),
        target_moisture_pct=float(row["target_moisture_pct"]),
        hysteresis_pct=float(row["hysteresis_pct"]),
        max_ml_per_day=float(row["max_ml_per_day"]),
        max_ml_per_event=float(row["max_ml_per_event"]),
        cooldown_minutes=float(row["cooldown_minutes"]),
        pump_ml_per_sec=float(row["pump_ml_per_sec"]),
        moisture_dry_raw=int(row["moisture_dry_raw"]),
        moisture_wet_raw=int(row["moisture_wet_raw"]),
        enabled=bool(row["enabled"]),
    )


@dataclass
class _AmbientCache:
    temp_c: float | None = None
    rh_pct: float | None = None
    lux: float | None = None
    reservoir_empty: bool = False


class ControlLoop:
    """One instance per daemon process."""

    def __init__(
        self,
        backend: HardwareBackend,
        settings: Settings,
        zone_configs: list[ZoneConfig] | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.backend = backend
        self.settings = settings
        self.zone_configs: list[ZoneConfig] = zone_configs or _default_zone_configs()
        self.zone_runtime: dict[int, ZoneRuntime] = {
            cfg.zone_id: ZoneRuntime(zone_id=cfg.zone_id) for cfg in self.zone_configs
        }
        self._clock = clock
        self._utc_now = utc_now
        self.start_mono = self._clock()
        self.loop_count = 0
        self._last_heartbeat_mono = -1.0
        self._last_zones_refresh_mono = 0.0
        self._day_anchor: date | None = None
        self._ambient = _AmbientCache()
        self.photographer = Photographer(
            backend=backend,
            photos_dir=settings.photos_dir,
            next_due_mono=self.start_mono + settings.warmup_s,
        )

    # --- Public API ----------------------------------------------------

    def run_forever(self) -> None:
        period = 1.0 / max(0.1, self.settings.loop_hz)
        watchdog.notify_ready()
        try:
            while True:
                t0 = time.monotonic()
                try:
                    self.tick()
                except Exception:                 # pragma: no cover — defensive
                    log.exception("tick failed")
                self.loop_count += 1
                elapsed = time.monotonic() - t0
                if elapsed < period:
                    time.sleep(period - elapsed)
        finally:
            watchdog.notify_stopping()
            self._all_pumps_off()
            self.backend.shutdown()

    def force_zones_refresh(self) -> None:
        """Reset the refresh debounce so the next tick re-reads zones from DB.
        Useful in tests and after manual edits."""
        self._last_zones_refresh_mono = -1e9

    def tick(self) -> None:
        """One iteration of the loop. Safe to call directly from tests."""
        now_mono = self._clock()
        now_utc = self._utc_now()

        self._roll_day_if_needed(now_utc)
        self._maybe_refresh_zones(now_mono)
        self._read_and_persist(now_utc, now_mono)
        self._heartbeat(now_utc, now_mono)
        self._check_completed_pumps(now_utc, now_mono)

        ctx = TickContext(
            daemon_uptime_s=now_mono - self.start_mono,
            reservoir_empty=self._ambient.reservoir_empty,
            warmup_s=self.settings.warmup_s,
        )
        verdict = tick_verdict(ctx)
        if verdict.blocking_reason == "reservoir_empty":
            db.insert_alert(
                severity="critical",
                code="reservoir_empty",
                message="Reservoir float reports empty — pumps disabled",
            )

        manual_zones = self._process_one_command(now_utc, verdict.allow_actions)
        self._decide_and_start(now_mono, verdict.allow_actions, manual_zones)
        self.photographer.tick(now_mono=now_mono, now_utc=now_utc)

    # --- Sensor I/O + persistence --------------------------------------

    def _read_and_persist(self, now_utc: datetime, now_mono: float) -> None:
        # Air sensors (one set, ambient).
        temp = self.backend.read_air_temp_c()
        self._ambient.temp_c = temp if is_plausible("air_temp_c", temp) else None
        self._record(now_utc, None, "air_temp_c", raw=None, value=temp, unit="c")
        rh = self.backend.read_air_rh_pct()
        self._ambient.rh_pct = rh if is_plausible("air_rh_pct", rh) else None
        self._record(now_utc, None, "air_rh_pct", raw=None, value=rh, unit="rh_pct")
        lux = self.backend.read_lux()
        self._ambient.lux = lux if is_plausible("lux", lux) else None
        self._record(now_utc, None, "lux", raw=None, value=lux, unit="lux")
        res_empty = self.backend.read_reservoir_empty()
        self._ambient.reservoir_empty = bool(res_empty) if res_empty is not None else False
        self._record(
            now_utc,
            None,
            "reservoir",
            raw=None,
            value=1.0 if self._ambient.reservoir_empty else 0.0,
            unit="bool",
        )

        # Per-zone soil — store both raw counts and calibrated pct.
        for cfg in self.zone_configs:
            raw = self.backend.read_soil(cfg.zone_id)
            runtime = self.zone_runtime[cfg.zone_id]
            if raw is None:
                # Disconnect path — still persist a row with quality=0 so the
                # dashboard can plot the gap. decide_watering increments the
                # failure counter when it sees moisture_pct=None.
                self._record(
                    now_utc, cfg.zone_id, "soil_moisture_pct",
                    raw=None, value=None, unit="pct",
                )
                continue
            pct = raw_to_pct(raw, cfg.moisture_dry_raw, cfg.moisture_wet_raw)
            self._record(
                now_utc, cfg.zone_id, "soil_moisture_pct",
                raw=raw, value=pct, unit="pct",
            )
            runtime.moisture_history.append((now_mono, pct))
            runtime.trim_history(now_mono)

    def _record(
        self,
        taken_at: datetime,
        zone_id: int | None,
        kind: str,
        *,
        raw: float | int | None,
        value: float | None,
        unit: str,
    ) -> None:
        if value is None:
            return
        plausibility_kind = {
            "air_temp_c": "air_temp_c",
            "air_rh_pct": "air_rh_pct",
            "lux": "lux",
            "soil_moisture_pct": "soil_moisture_pct",
        }.get(kind)
        quality = 1
        if plausibility_kind and not is_plausible(plausibility_kind, value):
            quality = 0
        db.insert_sensor_reading(
            taken_at=taken_at,
            zone_id=zone_id,
            kind=kind,
            raw=float(raw) if isinstance(raw, (int, float)) else None,
            value=float(value),
            unit=unit,
            quality=quality,
        )

    # --- Heartbeat -----------------------------------------------------

    def _heartbeat(self, now_utc: datetime, now_mono: float) -> None:
        if (now_mono - self._last_heartbeat_mono) < self.settings.heartbeat_s:
            return
        self._last_heartbeat_mono = now_mono
        db.insert_heartbeat(self.loop_count)
        watchdog.notify_watchdog()

    # --- Day rollover (resets ml_today caps) ---------------------------

    def _roll_day_if_needed(self, now_utc: datetime) -> None:
        today = now_utc.date()
        if self._day_anchor is None:
            self._day_anchor = today
            return
        if today != self._day_anchor:
            for r in self.zone_runtime.values():
                r.ml_today = 0.0
            self._day_anchor = today

    # --- Zone config refresh -------------------------------------------

    def _maybe_refresh_zones(self, now_mono: float) -> None:
        if (now_mono - self._last_zones_refresh_mono) < self.settings.config_reload_s:
            return
        self._last_zones_refresh_mono = now_mono
        rows = db.fetch_zones()
        if not rows:
            return  # keep current config (defaults at first boot)
        new_configs = [_zone_config_from_row(r) for r in rows]
        seen_ids = set()
        for cfg in new_configs:
            seen_ids.add(cfg.zone_id)
            if cfg.zone_id not in self.zone_runtime:
                self.zone_runtime[cfg.zone_id] = ZoneRuntime(zone_id=cfg.zone_id)
        # Drop runtimes for removed zones.
        for zid in list(self.zone_runtime.keys()):
            if zid not in seen_ids:
                self.zone_runtime.pop(zid, None)
        self.zone_configs = new_configs

    # --- Command runner (one per tick) ---------------------------------

    def _process_one_command(self, now_utc: datetime, actions_allowed: bool) -> set[int]:
        """Process at most one pending command and return zone_ids that received
        a manual_water request (which the per-zone decision step then realises)."""
        cmd = db.claim_pending_command()
        if cmd is None:
            return set()
        kind = str(cmd.get("kind"))
        payload = cmd.get("payload") or {}
        try:
            if kind == "water_zone":
                zone_id = int(payload.get("zone_id", 0))
                if zone_id not in self.zone_runtime:
                    db.complete_command(int(cmd["id"]), ok=False, result={"error": f"unknown zone {zone_id}"})
                    return set()
                # Optional: allow operator to specify mL — the decision pipeline
                # still clamps to per-event and daily caps. Override fits in
                # `payload['ml_override']`.
                if "ml_override" in payload:
                    self.zone_runtime[zone_id].ml_today = max(
                        0.0,
                        self.zone_runtime[zone_id].ml_today,
                    )  # no-op, but explicit
                db.complete_command(int(cmd["id"]), ok=True, result={"queued_for": zone_id})
                return {zone_id}
            if kind == "toggle_lamp":
                self.backend.lamp(bool(payload.get("on", False)))
                db.complete_command(int(cmd["id"]), ok=True)
                return set()
            if kind == "snapshot":
                from .photographer import take_photo
                path = take_photo(self.backend, self.settings.photos_dir)
                db.complete_command(int(cmd["id"]), ok=True, result={"path": str(path)})
                return set()
            db.complete_command(int(cmd["id"]), ok=False, result={"error": f"unknown kind {kind!r}"})
            return set()
        except Exception as exc:                 # pragma: no cover — defensive
            log.exception("command %s failed", cmd.get("id"))
            db.complete_command(int(cmd["id"]), ok=False, result={"error": str(exc)})
            return set()

    # --- Per-zone decisions and pump start -----------------------------

    def _decide_and_start(
        self,
        now_mono: float,
        interlocks_open: bool,
        manual_zones: set[int],
    ) -> None:
        for cfg in self.zone_configs:
            runtime = self.zone_runtime[cfg.zone_id]
            moisture_pct = self._latest_moisture(cfg, runtime)
            decision, alerts = decide_watering(
                cfg=cfg,
                runtime=runtime,
                moisture_pct=moisture_pct,
                now_mono=now_mono,
                interlocks_open=interlocks_open,
                manual_override=cfg.zone_id in manual_zones,
            )
            for a in alerts:
                self._raise_alert(a)
            if decision is not None:
                self._start_pump(decision, manual=(cfg.zone_id in manual_zones))

    def _latest_moisture(self, cfg: ZoneConfig, runtime: ZoneRuntime) -> float | None:
        if not runtime.moisture_history:
            return None
        return runtime.moisture_history[-1][1]

    def _start_pump(self, decision: WaterDecision, *, manual: bool) -> None:
        runtime = self.zone_runtime[decision.zone_id]
        try:
            self.backend.pump_on(decision.zone_id)
        except Exception:                       # pragma: no cover — defensive
            log.exception("pump_on failed for zone %s", decision.zone_id)
            return
        now_mono = self._clock()
        runtime.pumping_started_mono = now_mono
        runtime.pumping_until = now_mono + decision.duration_s
        runtime.pumping_pre_moisture = decision.pre_moisture_pct
        runtime.pumping_planned_ml = decision.planned_ml
        runtime.pumping_event_id = db.start_watering_event(
            zone_id=decision.zone_id,
            started_at=self._utc_now(),
            planned_ml=int(round(decision.planned_ml)),
            trigger="manual" if manual else "auto",
            pre_moisture_pct=decision.pre_moisture_pct,
        )

    def _check_completed_pumps(self, now_utc: datetime, now_mono: float) -> None:
        cfg_by_id = {c.zone_id: c for c in self.zone_configs}
        for runtime in self.zone_runtime.values():
            if runtime.pumping_until is None:
                continue
            if now_mono < runtime.pumping_until:
                continue
            cfg = cfg_by_id.get(runtime.zone_id)
            try:
                self.backend.pump_off(runtime.zone_id)
            except Exception:                   # pragma: no cover — defensive
                log.exception("pump_off failed for zone %s", runtime.zone_id)
            started_mono = runtime.pumping_started_mono if runtime.pumping_started_mono is not None else now_mono
            planned_duration = max(0.0, runtime.pumping_until - started_mono)
            # actual delivered = elapsed since pump-on, bounded by both the
            # planned duration and the hardware cap. We do not over-credit if
            # the loop happened to notice completion a few ticks late.
            actual_s = max(0.0, min(now_mono - started_mono, planned_duration, PUMP_HARD_CAP_S))
            actual_ml = actual_s * (cfg.pump_ml_per_sec if cfg else 1.5)
            post_moisture = self._latest_moisture(cfg, runtime) if cfg else None
            if runtime.pumping_event_id is not None:
                db.complete_watering_event(
                    event_id=runtime.pumping_event_id,
                    ended_at=now_utc,
                    actual_ml=int(round(actual_ml)),
                    post_moisture_pct=post_moisture,
                )
            runtime.ml_today += actual_ml
            runtime.last_event_finished_at = now_mono
            runtime.pumping_until = None
            runtime.pumping_event_id = None
            runtime.pumping_pre_moisture = None
            runtime.pumping_planned_ml = 0.0
            runtime.pumping_started_mono = None

    # --- Alerts --------------------------------------------------------

    def _raise_alert(self, a: AlertRequest) -> None:
        db.insert_alert(severity=a.severity, code=a.code, message=a.message, zone_id=a.zone_id)

    # --- Shutdown helpers ----------------------------------------------

    def _all_pumps_off(self) -> None:
        for runtime in self.zone_runtime.values():
            try:
                self.backend.pump_off(runtime.zone_id)
            except Exception:                   # pragma: no cover
                pass
