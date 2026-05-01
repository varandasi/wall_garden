"""Test fakes — a deterministic HardwareBackend and a no-op DB module."""
from __future__ import annotations

from typing import Any


class FakeBackend:
    """Backend that returns canned values and records actuator calls.

    Soil "moisture" is set in percent (0..100); the `read_soil` accessor maps
    back to ADC counts using the default calibration so the control loop's
    `raw_to_pct` produces the expected pct.
    """

    DRY_RAW = 26000
    WET_RAW = 12000

    def __init__(self) -> None:
        self.soil_pct: dict[int, float | None] = {1: 100.0, 2: 100.0, 3: 100.0, 4: 100.0}
        self.temp: float | None = 22.0
        self.rh: float | None = 60.0
        self.lux: float | None = 5000.0
        self.reservoir_empty: bool = False
        self.pumps_on: set[int] = set()
        self.lamp_on: bool = False
        self.photos_taken: list[str] = []
        self.shutdown_called: bool = False

    def read_soil(self, zone_id: int):
        pct = self.soil_pct.get(zone_id)
        if pct is None:
            return None
        return int(self.DRY_RAW + (self.WET_RAW - self.DRY_RAW) * pct / 100.0)

    def read_air_temp_c(self):
        return self.temp

    def read_air_rh_pct(self):
        return self.rh

    def read_lux(self):
        return self.lux

    def read_reservoir_empty(self):
        return self.reservoir_empty

    def pump_on(self, zone_id: int) -> None:
        self.pumps_on.add(zone_id)

    def pump_off(self, zone_id: int) -> None:
        self.pumps_on.discard(zone_id)

    def lamp(self, on: bool) -> None:
        self.lamp_on = on

    def capture_photo(self, path: str) -> None:
        # Write a minimal stub file so file-exists assertions pass without
        # pulling in Pillow.
        from pathlib import Path
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01")  # JPEG-ish magic
        self.photos_taken.append(path)

    def shutdown(self) -> None:
        self.pumps_on.clear()
        self.shutdown_called = True


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def silence_db(monkeypatch: Any) -> dict[str, list[Any]]:
    """Patch the daemon's `db` module so all writes become in-memory captures.

    Returns a dict whose keys are `inserts/heartbeats/alerts/...` lists you can
    inspect in tests.
    """
    from wallgardend import db

    captured: dict[str, list[Any]] = {
        "sensor_readings": [],
        "heartbeats": [],
        "alerts": [],
        "watering_events": [],
        "completed_events": [],
        "completed_commands": [],
        "claimed_commands": [],
    }

    def insert_sensor_reading(**kw):
        captured["sensor_readings"].append(kw)

    def insert_heartbeat(loop_count, last_error=None):
        captured["heartbeats"].append((loop_count, last_error))

    def insert_alert(**kw):
        captured["alerts"].append(kw)

    def fetch_zones():
        return []  # tests construct ZoneConfigs explicitly

    def claim_pending_command():
        return captured["claimed_commands"].pop(0) if captured["claimed_commands"] else None

    def complete_command(cmd_id, *, ok, result=None):
        captured["completed_commands"].append({"id": cmd_id, "ok": ok, "result": result})

    _next_id = [1]

    def start_watering_event(**kw):
        eid = _next_id[0]
        _next_id[0] += 1
        captured["watering_events"].append({"id": eid, **kw})
        return eid

    def complete_watering_event(**kw):
        captured["completed_events"].append(kw)

    monkeypatch.setattr(db, "insert_sensor_reading", insert_sensor_reading)
    monkeypatch.setattr(db, "insert_heartbeat", insert_heartbeat)
    monkeypatch.setattr(db, "insert_alert", insert_alert)
    monkeypatch.setattr(db, "fetch_zones", fetch_zones)
    monkeypatch.setattr(db, "claim_pending_command", claim_pending_command)
    monkeypatch.setattr(db, "complete_command", complete_command)
    monkeypatch.setattr(db, "start_watering_event", start_watering_event)
    monkeypatch.setattr(db, "complete_watering_event", complete_watering_event)
    return captured
