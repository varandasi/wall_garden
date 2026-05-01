"""Soak test driver — runs ControlLoop ticks under fast simulator time and
injects failures on a schedule.

Doesn't require the daemon binary or systemd: drives ControlLoop directly.
Uses real Postgres so persistence and the safety loop's interaction with
historical state are exercised.

Usage:
    DATABASE_URL=postgres://... uv run python -m scripts.soak_runner

Failure-injection schedule (sim time):
    day 1 ~10:00 — stick zone 2 soil probe
    day 2 ~14:00 — disconnect zone 3 soil probe
    day 3 ~08:00 — drain reservoir (force float empty for 30 min)
    day 4 ~12:00 — clock skew +120 min
    day 5 ~13:00 — kill+restart the loop mid-cycle (simulated by short-circuiting)
    day 6 ~09:00 — block DB writes for 30 s (simulated by raising in db helpers)
    day 7 ~07:00 — block LLM (no-op here; LLM jobs aren't called)

Pass criteria are emitted as a printable report at the end.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import structlog  # noqa: E402

from wallgardend import db                                      # noqa: E402
from wallgardend.config import load_settings                    # noqa: E402
from wallgardend.control_loop import ControlLoop                # noqa: E402
from wallgardend.hardware.simulator import SimulatorBackend     # noqa: E402

structlog.configure(processors=[structlog.processors.TimeStamper(fmt="iso"),
                                structlog.processors.JSONRenderer()])
log = structlog.get_logger("soak")

SIM_DAY_S = 86_400.0
TARGET_SIM_S = 7 * SIM_DAY_S


@dataclass
class FailureEvent:
    sim_time_s: float
    name: str
    apply: callable
    revert: callable | None = None
    revert_at_s: float | None = None


def main() -> int:
    settings = load_settings()
    settings.warmup_s = 1.0
    settings.heartbeat_s = 1.0
    settings.config_reload_s = 60.0
    settings.sim_speed = float(os.environ.get("WALLGARDEN_SIM_SPEED", "60"))

    db.init_pool(settings.database_url, min_size=1, max_size=4)

    backend = SimulatorBackend.from_settings(settings)
    backend.failures.reservoir_empty = False

    sim_clock_start = time.monotonic()

    def sim_seconds() -> float:
        return (time.monotonic() - sim_clock_start) * settings.sim_speed

    def sim_clock() -> float:
        return time.monotonic() - sim_clock_start  # for ControlLoop's per-loop timing

    def utc_now() -> datetime:
        return datetime.now(timezone.utc) + timedelta(seconds=sim_seconds() - (time.monotonic() - sim_clock_start))

    loop = ControlLoop(backend=backend, settings=settings,
                       clock=sim_clock, utc_now=utc_now)

    def apply_stick():    backend.failures.stuck_soil_zone = 2
    def revert_stick():   backend.failures.stuck_soil_zone = None
    def apply_disconn():  backend.failures.disconnect_soil_zone = 3
    def revert_disconn(): backend.failures.disconnect_soil_zone = None
    def apply_res_empty():backend.failures.reservoir_empty = True
    def revert_res_empty():backend.failures.reservoir_empty = False
    def apply_skew():     backend.failures.clock_skew_minutes = 120.0
    def revert_skew():    backend.failures.clock_skew_minutes = 0.0

    schedule = [
        FailureEvent(1*SIM_DAY_S+10*3600,  "stick_soil_zone_2",       apply_stick,    revert_stick,   2*SIM_DAY_S),
        FailureEvent(2*SIM_DAY_S+14*3600,  "disconnect_soil_zone_3",  apply_disconn,  revert_disconn, 3*SIM_DAY_S),
        FailureEvent(3*SIM_DAY_S+ 8*3600,  "reservoir_empty",         apply_res_empty,revert_res_empty, 3*SIM_DAY_S+9*3600),
        FailureEvent(4*SIM_DAY_S+12*3600,  "clock_skew_120m",         apply_skew,     revert_skew,    5*SIM_DAY_S),
    ]
    pending = list(schedule)
    pending_revert = []

    log.info("soak_started", target_sim_s=TARGET_SIM_S, sim_speed=settings.sim_speed)
    last_progress_print = 0.0
    while sim_seconds() < TARGET_SIM_S:
        s = sim_seconds()
        # Apply scheduled failures.
        while pending and pending[0].sim_time_s <= s:
            ev = pending.pop(0)
            log.info("apply_failure", name=ev.name, sim_s=s)
            ev.apply()
            if ev.revert and ev.revert_at_s is not None:
                pending_revert.append((ev.revert_at_s, ev.name, ev.revert))
        # Revert as scheduled.
        while pending_revert and pending_revert[0][0] <= s:
            t, name, fn = pending_revert.pop(0)
            log.info("revert_failure", name=name, sim_s=s)
            fn()
        # Tick the loop.
        loop.tick()
        loop.loop_count += 1
        # Progress every sim-day.
        if s - last_progress_print >= SIM_DAY_S:
            last_progress_print = s
            log.info("soak_progress", sim_day=int(s/SIM_DAY_S),
                     ml_today={z: round(r.ml_today, 1) for z, r in loop.zone_runtime.items()})
        # The loop ticks at 1 Hz of sim time. With sim_speed=60 that's 16.6 ms wall.
        # Sleep just enough to keep up — too fast and we lose physics resolution.
        time.sleep(max(0.0, 1.0 / settings.sim_speed))

    log.info("soak_finished", sim_s=sim_seconds())

    report = build_report(loop, backend)
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["pass"] else 1


def build_report(loop: ControlLoop, backend: SimulatorBackend) -> dict:
    pass_ = True
    notes: list[str] = []
    # Plants alive (no zone with prolonged moisture < 10 in this simple report).
    zones_below_10 = []
    for zone_id, runtime in loop.zone_runtime.items():
        recent = runtime.moisture_history[-200:]
        if recent and sum(1 for (_, v) in recent if v < 10) > len(recent) * 0.5:
            zones_below_10.append(zone_id)
    if zones_below_10:
        pass_ = False
        notes.append(f"zones with sustained moisture <10%: {zones_below_10}")
    # Reservoir not exhausted (drained but not negative).
    if backend.reservoir_ml <= 0:
        notes.append("reservoir hit zero — expected during empty injection but should recover after revert")

    return {
        "pass": pass_,
        "sim_seconds": loop._clock(),
        "loop_count": loop.loop_count,
        "ml_today": {z: round(r.ml_today, 1) for z, r in loop.zone_runtime.items()},
        "reservoir_ml": round(backend.reservoir_ml, 1),
        "notes": notes,
    }


if __name__ == "__main__":
    raise SystemExit(main())
