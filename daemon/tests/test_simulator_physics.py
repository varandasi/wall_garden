"""Physics smoke tests for SimulatorBackend.

The simulator is the development substrate — if its behavior is wrong, every
downstream test on the safety loop is wrong too.
"""
from __future__ import annotations

import json
import time

import pytest

from wallgardend.hardware.simulator import (
    DRY_RAW_DEFAULT,
    PUMP_HARD_CAP_S,
    WET_RAW_DEFAULT,
    SimulatorBackend,
)


@pytest.fixture
def sim(tmp_path):
    return SimulatorBackend(
        zones=[1, 2, 3, 4],
        speed=1000.0,                    # very fast so dt advances meaningfully
        seed=42,
        photos_dir=tmp_path / "photos",
    )


def test_initial_moisture_reads_in_calibration_band(sim):
    raw = sim.read_soil(1)
    assert raw is not None
    # Initial moisture is 55% → raw ≈ DRY + 0.55*(WET-DRY) = 26000 + 0.55*(-14000) = 18300
    expected = DRY_RAW_DEFAULT + 0.55 * (WET_RAW_DEFAULT - DRY_RAW_DEFAULT)
    assert abs(raw - expected) < 500   # noise ±500 well above 1σ=50


def test_air_readings_in_plausible_range(sim):
    t = sim.read_air_temp_c()
    rh = sim.read_air_rh_pct()
    lux = sim.read_lux()
    assert t is not None and -10 < t < 60
    assert rh is not None and 0 <= rh <= 100
    assert lux is not None and lux >= 0


def test_pump_drains_reservoir(sim):
    initial = sim.reservoir_ml
    sim.pump_on(1)
    # Force the simulator clock to move by stepping; high speed factor + sleep advances sim time.
    time.sleep(0.05)
    sim.read_soil(1)
    sim.pump_off(1)
    assert sim.reservoir_ml < initial


def test_pump_raises_moisture(sim):
    before = sim.zones[1].moisture_pct
    sim.pump_on(1)
    time.sleep(0.05)
    sim.read_soil(1)   # advances physics
    time.sleep(0.05)
    sim.read_soil(1)
    sim.pump_off(1)
    # Some water has been dosed and should have started wicking in.
    after = sim.zones[1].moisture_pct
    assert after >= before, f"expected moisture rise, before={before} after={after}"


def test_pump_seized_failure_blocks_water(sim):
    sim.failures.pump_seized_zone = 1
    initial_res = sim.reservoir_ml
    sim.pump_on(1)
    time.sleep(0.05)
    sim.read_soil(1)
    sim.pump_off(1)
    assert sim.reservoir_ml == initial_res


def test_disconnected_soil_returns_none(sim):
    sim.failures.disconnect_soil_zone = 2
    assert sim.read_soil(2) is None
    assert sim.read_soil(1) is not None


def test_stuck_soil_returns_constant_value(sim):
    sim.failures.stuck_soil_zone = 3
    first = sim.read_soil(3)
    time.sleep(0.05)
    second = sim.read_soil(3)
    assert first == second
    assert first is not None


def test_reservoir_empty_failure_trips_float(sim):
    sim.failures.reservoir_empty = True
    assert sim.read_reservoir_empty() is True


def test_reservoir_empty_blocks_pump(sim):
    sim.reservoir_ml = 0
    initial_water = sim.zones[1].accumulated_water_ml
    sim.pump_on(1)
    time.sleep(0.05)
    sim.read_soil(1)
    sim.pump_off(1)
    assert sim.zones[1].accumulated_water_ml == initial_water


def test_pump_hard_cap_kills_runaway(sim):
    """Even if the daemon never calls pump_off, the simulator (mirroring the
    Pi backend) must self-cut after PUMP_HARD_CAP_S of sim time."""
    sim.pump_on(1)
    # Advance sim time well past the cap. speed=1000 means 0.05 wall = 50 sim s.
    time.sleep(0.05)
    sim.read_soil(1)
    assert sim.zones[1].pump_on is False, "runaway pump should self-cut"


def test_failure_injection_via_control_file(tmp_path):
    control = tmp_path / "control.json"
    control.write_text(json.dumps({"disconnect_soil_zone": 4}))
    sim = SimulatorBackend(zones=[1, 2, 3, 4], speed=1.0, control_path=control, seed=1)
    # Force a step so the file is read.
    sim.read_soil(1)
    assert sim.failures.disconnect_soil_zone == 4
    assert sim.read_soil(4) is None


def test_diurnal_cycle_changes_lux(sim):
    """Over a long enough simulated stretch, lux should swing between near-zero and bright."""
    seen = []
    for _ in range(50):
        time.sleep(0.01)
        v = sim.read_lux()
        if v is not None:
            seen.append(v)
    assert max(seen) > min(seen) + 1.0  # some variation


def test_capture_photo_writes_jpeg(sim, tmp_path):
    target = tmp_path / "test.jpg"
    sim.capture_photo(str(target))
    assert target.exists()
    assert target.stat().st_size > 100
