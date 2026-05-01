"""Pure-function tests for decide_watering.

Property tests cover the core invariants of the safety logic; example tests
nail down the behavior at boundary conditions.
"""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from wallgardend.safety import (
    PUMP_HARD_CAP_S,
    SENSOR_DISCONNECT_THRESHOLD,
    AlertRequest,
    WaterDecision,
    ZoneConfig,
    ZonePhase,
    ZoneRuntime,
    decide_watering,
)


def _cfg(
    *,
    target=55.0,
    hyst=8.0,
    cap_day=200.0,
    cap_event=50.0,
    cooldown_min=60.0,
    rate=1.5,
    enabled=True,
    zone_id=1,
):
    return ZoneConfig(
        zone_id=zone_id,
        target_moisture_pct=target,
        hysteresis_pct=hyst,
        max_ml_per_day=cap_day,
        max_ml_per_event=cap_event,
        cooldown_minutes=cooldown_min,
        pump_ml_per_sec=rate,
        moisture_dry_raw=26000,
        moisture_wet_raw=12000,
        enabled=enabled,
    )


def _runtime(zone_id: int = 1) -> ZoneRuntime:
    return ZoneRuntime(zone_id=zone_id)


# --- Disabled zones -------------------------------------------------------


def test_disabled_zone_never_waters():
    cfg = _cfg(enabled=False)
    rt = _runtime()
    decision, alerts = decide_watering(cfg, rt, moisture_pct=10.0, now_mono=1000.0, interlocks_open=True)
    assert decision is None
    assert alerts == []


# --- Phase / hysteresis ---------------------------------------------------


def test_satisfied_zone_in_dead_band_does_not_water():
    cfg = _cfg(target=55, hyst=8)   # dead band [51..59]
    rt = _runtime()
    rt.phase = ZonePhase.SATISFIED
    decision, _ = decide_watering(cfg, rt, moisture_pct=53.0, now_mono=1000.0, interlocks_open=True)
    assert decision is None
    assert rt.phase == ZonePhase.SATISFIED


def test_satisfied_zone_below_low_becomes_thirsty_and_waters():
    cfg = _cfg()
    rt = _runtime()
    decision, _ = decide_watering(cfg, rt, moisture_pct=40.0, now_mono=1000.0, interlocks_open=True)
    assert decision is not None
    assert rt.phase == ZonePhase.THIRSTY
    assert decision.zone_id == cfg.zone_id


def test_thirsty_zone_above_high_satisfies_and_does_not_water():
    cfg = _cfg(target=55, hyst=8)
    rt = _runtime()
    rt.phase = ZonePhase.THIRSTY
    decision, _ = decide_watering(cfg, rt, moisture_pct=60.0, now_mono=1000.0, interlocks_open=True)
    assert decision is None
    assert rt.phase == ZonePhase.SATISFIED


# --- Interlocks -----------------------------------------------------------


def test_interlock_closed_blocks_watering_even_if_thirsty():
    cfg = _cfg()
    rt = _runtime()
    rt.phase = ZonePhase.THIRSTY
    decision, _ = decide_watering(cfg, rt, moisture_pct=30.0, now_mono=1000.0, interlocks_open=False)
    assert decision is None


# --- Caps -----------------------------------------------------------------


def test_daily_cap_blocks_watering_and_alerts_once():
    cfg = _cfg(cap_day=100, cap_event=50)
    rt = _runtime()
    rt.phase = ZonePhase.THIRSTY
    rt.ml_today = 100.0
    decision, alerts = decide_watering(cfg, rt, moisture_pct=30.0, now_mono=1000.0, interlocks_open=True)
    assert decision is None
    assert any(a.code.startswith("daily_cap_hit") for a in alerts)


def test_dose_respects_per_event_cap_and_pump_cap():
    cfg = _cfg(cap_day=1000, cap_event=200, rate=1.0)   # event cap=200, but rate=1mL/s × 15s cap = 15mL ceiling
    rt = _runtime()
    decision, _ = decide_watering(cfg, rt, moisture_pct=20.0, now_mono=1000.0, interlocks_open=True)
    assert decision is not None
    assert decision.duration_s <= PUMP_HARD_CAP_S + 1e-9
    assert decision.planned_ml <= PUMP_HARD_CAP_S * cfg.pump_ml_per_sec + 1e-9


# --- Cooldown -------------------------------------------------------------


def test_cooldown_blocks_back_to_back_events():
    cfg = _cfg(cooldown_min=10)
    rt = _runtime()
    rt.phase = ZonePhase.THIRSTY
    rt.last_event_finished_at = 1000.0
    decision, _ = decide_watering(cfg, rt, moisture_pct=30.0, now_mono=1300.0, interlocks_open=True)
    # 300 s elapsed; cooldown is 10 min = 600 s → blocked.
    assert decision is None


def test_cooldown_lets_through_after_window():
    cfg = _cfg(cooldown_min=10)
    rt = _runtime()
    rt.phase = ZonePhase.THIRSTY
    rt.last_event_finished_at = 1000.0
    decision, _ = decide_watering(cfg, rt, moisture_pct=30.0, now_mono=1700.0, interlocks_open=True)
    assert decision is not None


# --- Manual override ------------------------------------------------------


def test_manual_override_bypasses_hysteresis():
    cfg = _cfg(target=55, hyst=8)
    rt = _runtime()
    rt.phase = ZonePhase.SATISFIED  # not thirsty by hysteresis
    decision, _ = decide_watering(
        cfg, rt, moisture_pct=53.0, now_mono=1000.0,
        interlocks_open=True, manual_override=True,
    )
    assert decision is not None


def test_manual_override_does_not_bypass_daily_cap():
    cfg = _cfg(cap_day=100)
    rt = _runtime()
    rt.ml_today = 100
    decision, _ = decide_watering(
        cfg, rt, moisture_pct=20.0, now_mono=1000.0,
        interlocks_open=True, manual_override=True,
    )
    assert decision is None


def test_manual_override_does_not_bypass_interlocks():
    cfg = _cfg()
    rt = _runtime()
    decision, _ = decide_watering(
        cfg, rt, moisture_pct=20.0, now_mono=1000.0,
        interlocks_open=False, manual_override=True,
    )
    assert decision is None


# --- Sensor disconnect / stuck -------------------------------------------


def test_disconnect_increments_counter_and_fires_one_alert():
    cfg = _cfg()
    rt = _runtime()
    alerts: list[AlertRequest] = []
    for _ in range(SENSOR_DISCONNECT_THRESHOLD - 1):
        _, a = decide_watering(cfg, rt, moisture_pct=None, now_mono=0, interlocks_open=True)
        alerts.extend(a)
    assert alerts == []
    # Threshold tick fires the alert.
    _, a = decide_watering(cfg, rt, moisture_pct=None, now_mono=0, interlocks_open=True)
    alerts.extend(a)
    assert any(al.code == "soil_sensor_disconnected" for al in alerts)
    # Subsequent ticks do not re-alert (latch).
    _, a = decide_watering(cfg, rt, moisture_pct=None, now_mono=0, interlocks_open=True)
    assert a == []


def test_disconnect_recovery_resets_alert_latch():
    cfg = _cfg()
    rt = _runtime()
    for _ in range(SENSOR_DISCONNECT_THRESHOLD):
        decide_watering(cfg, rt, moisture_pct=None, now_mono=0, interlocks_open=True)
    assert rt.disconnect_alerted is True
    # Recovery
    decide_watering(cfg, rt, moisture_pct=55.0, now_mono=0, interlocks_open=True)
    assert rt.consecutive_failures == 0
    assert rt.disconnect_alerted is False


def test_stuck_history_blocks_watering():
    cfg = _cfg()
    rt = _runtime()
    # Inject 10 readings within 30 min, all the same — stuck.
    rt.moisture_history = [(float(i), 50.0) for i in range(10)]
    decision, alerts = decide_watering(cfg, rt, moisture_pct=50.0, now_mono=600, interlocks_open=True)
    assert decision is None
    assert any(al.code == "soil_sensor_stuck" for al in alerts)


# --- Property test: planned_ml never exceeds either cap ------------------


@given(
    moisture=st.floats(min_value=0.0, max_value=100.0),
    target=st.floats(min_value=10.0, max_value=90.0),
    hyst=st.floats(min_value=2.0, max_value=20.0),
    cap_day=st.floats(min_value=1.0, max_value=1000.0),
    cap_event=st.floats(min_value=1.0, max_value=200.0),
    rate=st.floats(min_value=0.1, max_value=5.0),
    ml_today_frac=st.floats(min_value=0.0, max_value=1.0),
)
def test_property_planned_ml_within_caps(
    moisture, target, hyst, cap_day, cap_event, rate, ml_today_frac
):
    cfg = _cfg(target=target, hyst=hyst, cap_day=cap_day, cap_event=cap_event, rate=rate)
    rt = _runtime()
    rt.phase = ZonePhase.THIRSTY
    rt.ml_today = cap_day * ml_today_frac
    decision, _ = decide_watering(
        cfg, rt, moisture_pct=moisture, now_mono=10_000.0, interlocks_open=True,
    )
    if decision is None:
        return
    assert decision.planned_ml <= cap_event + 1e-6
    assert rt.ml_today + decision.planned_ml <= cap_day + 1e-6
    assert decision.duration_s <= PUMP_HARD_CAP_S + 1e-9
