"""Pure-function safety primitives — interlocks, plausibility, hysteresis, caps,
and the per-zone watering decision.

NO I/O, NO time, NO randomness. Every input is explicit. This module is
exhaustively property-tested via `tests/test_safety.py`.

The control loop is a thin shell around `decide_watering`: it reads sensors,
maintains in-memory `ZoneRuntime`, calls this module to compute intent, then
executes the intent through the hardware backend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# --- Constants -------------------------------------------------------------

# Hardware-level pump runtime cap. The Pi backend's pump_on() also enforces
# this with a Timer; the control loop must respect it when sizing doses so
# the recorded watering_event matches what's actually delivered.
PUMP_HARD_CAP_S = 15.0

# Sensor failure thresholds.
SENSOR_DISCONNECT_THRESHOLD = 5      # consecutive None reads → disable that zone
STUCK_WINDOW_S = 30 * 60.0           # 30 min rolling window for stuck detection
STUCK_DELTA_PCT = 0.5                # max-min < this in window → stuck
STUCK_MIN_SAMPLES = 5                # need at least this many readings to judge

# Float-switch debounce window: how many consecutive "empty" reads count.
RESERVOIR_DEBOUNCE_READS = 3


PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = {
    "soil_moisture_pct": (0.0, 100.0),
    "air_temp_c": (-10.0, 60.0),
    "air_rh_pct": (0.0, 100.0),
    "lux": (0.0, 100_000.0),
}


def is_plausible(kind: str, value: float | None) -> bool:
    if value is None:
        return False
    rng = PLAUSIBLE_RANGES.get(kind)
    if rng is None:
        return True
    lo, hi = rng
    return lo <= value <= hi


# --- Hysteresis state machine ---------------------------------------------


class ZonePhase(str, Enum):
    SATISFIED = "satisfied"
    THIRSTY = "thirsty"


def next_phase(
    current: ZonePhase,
    moisture_pct: float,
    target_pct: float,
    hysteresis_pct: float,
) -> ZonePhase:
    low = target_pct - hysteresis_pct / 2.0
    high = target_pct + hysteresis_pct / 2.0
    if current == ZonePhase.SATISFIED and moisture_pct < low:
        return ZonePhase.THIRSTY
    if current == ZonePhase.THIRSTY and moisture_pct > high:
        return ZonePhase.SATISFIED
    return current


# --- Caps ------------------------------------------------------------------


def remaining_daily_ml(ml_today: float, max_ml_per_day: float) -> float:
    return max(0.0, max_ml_per_day - ml_today)


def dose_for_event(
    *,
    ml_today: float,
    max_ml_per_day: float,
    max_ml_per_event: float,
) -> float:
    return max(0.0, min(max_ml_per_event, remaining_daily_ml(ml_today, max_ml_per_day)))


def is_in_cooldown(seconds_since_last_event: float, cooldown_minutes: float) -> bool:
    return seconds_since_last_event < cooldown_minutes * 60.0


# --- Stuck-sensor detection ------------------------------------------------


def is_stuck(samples: list[float], threshold: float = STUCK_DELTA_PCT) -> bool:
    if len(samples) < STUCK_MIN_SAMPLES:
        return False
    return (max(samples) - min(samples)) < threshold


# --- Composite tick verdict ------------------------------------------------


@dataclass
class TickContext:
    daemon_uptime_s: float
    reservoir_empty: bool
    warmup_s: float


@dataclass
class TickVerdict:
    allow_actions: bool
    blocking_reason: str | None = None


def tick_verdict(ctx: TickContext) -> TickVerdict:
    if ctx.daemon_uptime_s < ctx.warmup_s:
        return TickVerdict(False, "warmup_grace")
    if ctx.reservoir_empty:
        return TickVerdict(False, "reservoir_empty")
    return TickVerdict(True, None)


# --- Per-zone configuration and runtime state -----------------------------


@dataclass(frozen=True)
class ZoneConfig:
    zone_id: int
    target_moisture_pct: float
    hysteresis_pct: float
    max_ml_per_day: float
    max_ml_per_event: float
    cooldown_minutes: float
    pump_ml_per_sec: float
    moisture_dry_raw: int
    moisture_wet_raw: int
    enabled: bool = True


@dataclass
class ZoneRuntime:
    """Mutable per-zone state held in-process by the control loop."""

    zone_id: int
    phase: ZonePhase = ZonePhase.SATISFIED
    ml_today: float = 0.0
    last_event_finished_at: float | None = None       # monotonic seconds
    consecutive_failures: int = 0
    pumping_until: float | None = None                 # monotonic seconds
    pumping_event_id: int | None = None
    pumping_pre_moisture: float | None = None
    pumping_planned_ml: float = 0.0
    pumping_started_mono: float | None = None
    moisture_history: list[tuple[float, float]] = field(default_factory=list)
    stuck_alerted: bool = False
    disconnect_alerted: bool = False

    def trim_history(self, now_mono: float, window_s: float = STUCK_WINDOW_S) -> None:
        cutoff = now_mono - window_s
        self.moisture_history = [(t, v) for (t, v) in self.moisture_history if t >= cutoff]


# --- Alert request (control loop converts these to DB rows) ---------------


@dataclass(frozen=True)
class AlertRequest:
    code: str
    severity: str       # 'info' | 'warn' | 'critical'
    message: str
    zone_id: int | None = None


# --- Watering decision -----------------------------------------------------


@dataclass(frozen=True)
class WaterDecision:
    zone_id: int
    planned_ml: float       # cap-respecting requested amount
    duration_s: float       # = min(planned_ml / rate, PUMP_HARD_CAP_S)
    pre_moisture_pct: float


def decide_watering(
    cfg: ZoneConfig,
    runtime: ZoneRuntime,
    moisture_pct: float | None,
    now_mono: float,
    *,
    interlocks_open: bool,
    manual_override: bool = False,
) -> tuple[WaterDecision | None, list[AlertRequest]]:
    """Pure decision function: given the current state of one zone, decide
    whether to start a watering event and what alerts to raise.

    `manual_override=True` skips the hysteresis and cooldown checks (used by
    operator-issued commands) but never the daily-cap or interlock gates.
    """
    alerts: list[AlertRequest] = []
    if not cfg.enabled:
        return None, alerts

    # --- Sensor disconnect ---
    if moisture_pct is None:
        runtime.consecutive_failures += 1
        if runtime.consecutive_failures >= SENSOR_DISCONNECT_THRESHOLD and not runtime.disconnect_alerted:
            alerts.append(AlertRequest(
                code="soil_sensor_disconnected",
                severity="warn",
                message=f"Zone {cfg.zone_id} soil probe failed {SENSOR_DISCONNECT_THRESHOLD} consecutive reads",
                zone_id=cfg.zone_id,
            ))
            runtime.disconnect_alerted = True
        return None, alerts

    # Recovered from a disconnect; reset the latch so a future failure alerts again.
    if runtime.consecutive_failures > 0:
        runtime.consecutive_failures = 0
        runtime.disconnect_alerted = False

    # --- Stuck-sensor detection (only on valid history) ---
    samples = [v for (_t, v) in runtime.moisture_history]
    if is_stuck(samples):
        if not runtime.stuck_alerted:
            alerts.append(AlertRequest(
                code="soil_sensor_stuck",
                severity="warn",
                message=f"Zone {cfg.zone_id} soil probe stuck (Δ<{STUCK_DELTA_PCT}% over {STUCK_WINDOW_S/60:.0f} min)",
                zone_id=cfg.zone_id,
            ))
            runtime.stuck_alerted = True
        return None, alerts
    runtime.stuck_alerted = False

    # --- Hysteresis ---
    runtime.phase = next_phase(
        runtime.phase, moisture_pct, cfg.target_moisture_pct, cfg.hysteresis_pct
    )

    # If a pump cycle is already in flight for this zone, do nothing this tick.
    if runtime.pumping_until is not None:
        return None, alerts

    # Manual override implies a thirsty intent regardless of phase.
    wants_water = manual_override or runtime.phase == ZonePhase.THIRSTY
    if not wants_water:
        return None, alerts

    if not interlocks_open:
        return None, alerts

    # Cooldown applies even with manual override only when over-pumping recently.
    if not manual_override and runtime.last_event_finished_at is not None:
        if is_in_cooldown(now_mono - runtime.last_event_finished_at, cfg.cooldown_minutes):
            return None, alerts

    # Daily + per-event cap.
    dose = dose_for_event(
        ml_today=runtime.ml_today,
        max_ml_per_day=cfg.max_ml_per_day,
        max_ml_per_event=cfg.max_ml_per_event,
    )
    if dose <= 0:
        if runtime.ml_today >= cfg.max_ml_per_day:
            alerts.append(AlertRequest(
                code=f"daily_cap_hit_zone_{cfg.zone_id}",
                severity="warn",
                message=f"Zone {cfg.zone_id} hit daily cap {cfg.max_ml_per_day:.0f} mL",
                zone_id=cfg.zone_id,
            ))
        return None, alerts

    # Hard pump-runtime cap clamps actual delivery.
    duration_s = min(dose / cfg.pump_ml_per_sec, PUMP_HARD_CAP_S)
    planned_ml = duration_s * cfg.pump_ml_per_sec
    return (
        WaterDecision(
            zone_id=cfg.zone_id,
            planned_ml=planned_ml,
            duration_s=duration_s,
            pre_moisture_pct=moisture_pct,
        ),
        alerts,
    )
