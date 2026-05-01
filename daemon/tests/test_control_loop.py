"""ControlLoop integration tests against FakeBackend with an injected clock.

Tests run with no real time and no real DB: monkeypatch silences `db.*`
writes into in-memory captures, and FakeClock advances via `clock.advance()`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from wallgardend.config import Settings
from wallgardend.control_loop import ControlLoop
from wallgardend.safety import PUMP_HARD_CAP_S, ZoneConfig, ZonePhase

from .fakes import FakeBackend, FakeClock, silence_db


@pytest.fixture
def settings():
    s = Settings()
    s.warmup_s = 0.0     # tests bypass warm-up grace
    s.heartbeat_s = 1.0
    s.config_reload_s = 9999.0
    return s


@pytest.fixture
def cfgs():
    return [
        ZoneConfig(
            zone_id=zid,
            target_moisture_pct=55.0,
            hysteresis_pct=8.0,
            max_ml_per_day=200.0,
            max_ml_per_event=50.0,
            cooldown_minutes=10.0,
            pump_ml_per_sec=1.5,
            moisture_dry_raw=26000,
            moisture_wet_raw=12000,
            enabled=True,
        )
        for zid in (1, 2, 3, 4)
    ]


@pytest.fixture
def utc_anchor():
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def loop_factory(settings, cfgs, utc_anchor):
    """Build a fresh loop with FakeBackend + FakeClock + injected utc_now."""
    def _make(monkeypatch):
        captured = silence_db(monkeypatch)
        backend = FakeBackend()
        clock = FakeClock(0.0)
        utc_holder = {"t": utc_anchor}

        def utc_now():
            return utc_holder["t"]

        loop = ControlLoop(
            backend=backend,
            settings=settings,
            zone_configs=cfgs,
            clock=clock,
            utc_now=utc_now,
        )
        return loop, backend, clock, captured, utc_holder
    return _make


# --- Basic tick behaviour --------------------------------------------------


def test_tick_persists_sensor_readings(loop_factory, monkeypatch):
    loop, backend, clock, captured, _ = loop_factory(monkeypatch)
    loop.tick()
    kinds = {r["kind"] for r in captured["sensor_readings"]}
    assert {"air_temp_c", "air_rh_pct", "lux", "reservoir"} <= kinds
    assert "soil_moisture_pct" in kinds


def test_heartbeats_fire_at_configured_cadence(loop_factory, monkeypatch):
    loop, backend, clock, captured, _ = loop_factory(monkeypatch)
    loop.tick()
    assert len(captured["heartbeats"]) == 1
    clock.advance(0.5)
    loop.tick()
    assert len(captured["heartbeats"]) == 1   # cadence is 1 s
    clock.advance(0.6)
    loop.tick()
    assert len(captured["heartbeats"]) == 2


# --- Reservoir interlock ---------------------------------------------------


def test_reservoir_empty_blocks_pumps_and_alerts(loop_factory, monkeypatch):
    loop, backend, clock, captured, _ = loop_factory(monkeypatch)
    backend.reservoir_empty = True
    backend.soil_pct = {1: 30.0, 2: 30.0, 3: 30.0, 4: 30.0}  # all very thirsty
    loop.tick()
    assert backend.pumps_on == set()
    codes = {a["code"] for a in captured["alerts"]}
    assert "reservoir_empty" in codes


# --- Auto watering pump cycle ---------------------------------------------


def test_thirsty_zone_starts_pump_and_completes_cycle(loop_factory, monkeypatch):
    loop, backend, clock, captured, _ = loop_factory(monkeypatch)
    backend.soil_pct[1] = 30.0   # well below dead-band low (51)
    loop.tick()
    assert 1 in backend.pumps_on, "pump should have started"
    runtime = loop.zone_runtime[1]
    assert runtime.pumping_until is not None
    expected_dose = min(50.0, PUMP_HARD_CAP_S * 1.5)   # 50 mL cap_event vs 22.5 mL pump cap → 22.5
    assert runtime.pumping_planned_ml == pytest.approx(expected_dose, rel=1e-3)

    # Advance past the pump duration; next tick should turn it off and finalize.
    clock.advance(runtime.pumping_until - clock.t + 0.1)
    loop.tick()
    assert 1 not in backend.pumps_on
    assert runtime.pumping_until is None
    assert runtime.ml_today == pytest.approx(expected_dose, rel=1e-3)
    assert len(captured["watering_events"]) == 1
    assert len(captured["completed_events"]) == 1


def test_satisfied_zone_does_not_pump(loop_factory, monkeypatch):
    loop, backend, clock, captured, _ = loop_factory(monkeypatch)
    backend.soil_pct = {1: 70.0, 2: 70.0, 3: 70.0, 4: 70.0}
    for _ in range(3):
        loop.tick()
        clock.advance(1.0)
    assert backend.pumps_on == set()
    assert captured["watering_events"] == []


# --- Daily cap -------------------------------------------------------------


def test_daily_cap_caps_total_water_per_zone(loop_factory, monkeypatch):
    loop, backend, clock, captured, _ = loop_factory(monkeypatch)
    backend.soil_pct = {1: 30.0, 2: 100.0, 3: 100.0, 4: 100.0}  # only zone 1 thirsty
    cfg = next(c for c in loop.zone_configs if c.zone_id == 1)
    # Override per-event cap to make the test fast, daily cap stays 200.
    # Run many cycles, advancing time past cooldown each iteration.
    safeguard = 0
    while loop.zone_runtime[1].ml_today < cfg.max_ml_per_day - 1 and safeguard < 200:
        loop.tick()
        # Advance to end of any pump cycle plus the cooldown.
        clock.advance(PUMP_HARD_CAP_S + cfg.cooldown_minutes * 60.0 + 1.0)
        safeguard += 1
    # One more decide tick to surface the daily-cap alert.
    loop.tick()
    rt = loop.zone_runtime[1]
    assert rt.ml_today <= cfg.max_ml_per_day + 1e-6
    # Once the cap is hit, the loop refuses further water and emits an alert.
    codes = {a["code"] for a in captured["alerts"]}
    assert any(c.startswith("daily_cap_hit_zone_1") for c in codes)


def test_day_rollover_resets_ml_today(loop_factory, monkeypatch):
    loop, backend, clock, captured, utc_holder = loop_factory(monkeypatch)
    loop.zone_runtime[1].ml_today = 150.0
    loop.tick()
    # Cross midnight UTC.
    utc_holder["t"] = utc_holder["t"] + timedelta(hours=12) + timedelta(seconds=1)
    loop.tick()
    assert loop.zone_runtime[1].ml_today == 0.0


# --- Cooldown --------------------------------------------------------------


def test_cooldown_prevents_immediate_re_water(loop_factory, monkeypatch):
    loop, backend, clock, captured, _ = loop_factory(monkeypatch)
    backend.soil_pct[1] = 30.0
    loop.tick()                                  # pump starts
    pumping_until = loop.zone_runtime[1].pumping_until
    clock.advance(pumping_until - clock.t + 0.1)
    loop.tick()                                  # pump completes; cooldown starts
    backend.soil_pct[1] = 30.0                   # still thirsty
    clock.advance(60.0)                          # 1 min — well inside 10 min cooldown
    loop.tick()
    assert 1 not in backend.pumps_on


# --- Manual command via DB queue ------------------------------------------


def test_manual_water_command_triggers_watering(loop_factory, monkeypatch):
    loop, backend, clock, captured, _ = loop_factory(monkeypatch)
    backend.soil_pct = {1: 70.0, 2: 70.0, 3: 70.0, 4: 70.0}   # all satisfied
    captured["claimed_commands"].append({
        "id": 99, "kind": "water_zone", "payload": {"zone_id": 2}, "status": "pending",
    })
    loop.tick()
    assert 2 in backend.pumps_on, "manual command should ignore hysteresis"
    # Command was completed in the DB.
    assert any(c["id"] == 99 and c["ok"] for c in captured["completed_commands"])


def test_lamp_command_toggles(loop_factory, monkeypatch):
    loop, backend, clock, captured, _ = loop_factory(monkeypatch)
    captured["claimed_commands"].append({
        "id": 100, "kind": "toggle_lamp", "payload": {"on": True}, "status": "pending",
    })
    loop.tick()
    assert backend.lamp_on is True


# --- Sensor disconnect ----------------------------------------------------


def test_disconnected_zone_disables_only_itself(loop_factory, monkeypatch):
    loop, backend, clock, captured, _ = loop_factory(monkeypatch)
    backend.soil_pct = {1: None, 2: 30.0, 3: 30.0, 4: 30.0}   # zone 1 disconnected
    for _ in range(10):
        loop.tick()
        clock.advance(1.0)
    # Zone 1 never gets a pump.
    assert 1 not in backend.pumps_on
    # Other zones get their pumps eventually.
    pumped = {r.zone_id for r in loop.zone_runtime.values() if r.pumping_until is not None or r.ml_today > 0}
    assert {2, 3, 4} <= pumped
    codes = {a["code"] for a in captured["alerts"]}
    assert "soil_sensor_disconnected" in codes


# --- Warm-up grace --------------------------------------------------------


def test_warmup_grace_blocks_pumps(loop_factory, monkeypatch, settings):
    settings.warmup_s = 60.0      # restore the default
    loop, backend, clock, captured, _ = loop_factory(monkeypatch)
    backend.soil_pct[1] = 30.0
    loop.tick()
    assert 1 not in backend.pumps_on
    clock.advance(61.0)
    loop.tick()
    assert 1 in backend.pumps_on
