"""Simulator backend — first-class fake hardware that the daemon can be
developed and trusted against on a laptop with no soldering iron.

It models:

- Soil moisture per zone with exponential drying that depends on ambient temp
  and lux. Pumping adds water that wicks in over ~5 minutes (so the control
  loop sees a gradual rise — proves hysteresis works in real conditions).
- Diurnal cycle: a sine sun curve for lux (peak 30k lux), temp swing (16..26°C),
  RH inversely correlated with sun.
- Reservoir: finite mL volume, drains during pump-on, float switch trips empty.
- Sensor noise (Gaussian) per kind with realistic σ.
- Failure injection via env vars or a JSON control file that hot-reloads.
- Time scaling: WALLGARDEN_SIM_SPEED multiplies wall-clock advance, so a 7-day
  soak takes ~3 hours at speed=60.
- Synthetic plant photos: a simple Pillow render of four leaves tinted by zone
  health, plus a `[SIM]` watermark.

The simulator is deliberately deterministic given (start time, control file,
RNG seed) so reproducing soak runs is easy.
"""
from __future__ import annotations

import json
import math
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

from ..config import Settings

# --- Tunable physics constants --------------------------------------------

SIM_DAY_SECONDS = 86_400.0       # one sim "day" lasts 24h of sim time
PEAK_LUX = 30_000.0
LAMP_LUX = 5_000.0
BASE_TEMP_C = 20.0
TEMP_SWING_C = 6.0
BASE_RH_PCT = 75.0
RH_SWING_PCT = 25.0

# Drying: a zone at 50% moisture under nominal conditions decays with this τ.
# Heat and light shorten τ.
DRYING_BASE_TAU_S = 90_000.0     # ~25h: realistic for a small indoor pocket
PUMP_ML_PER_SEC = 1.5             # 90 mL/min — typical small peristaltic pump
WICK_TAU_S = 100.0                # accumulated water wicks in with this τ
ML_TO_MOISTURE_PCT = 0.4          # 1 mL into a small zone bumps moisture 0.4%
PUMP_HARD_CAP_S = 15.0            # absolute pump-runtime cap (mirror Pi backend)

# Soil ADC calibration (typical capacitive probe, 16-bit ADC).
DRY_RAW_DEFAULT = 26_000
WET_RAW_DEFAULT = 12_000

# Sensor noise σ.
SOIL_ADC_NOISE = 50.0
TEMP_NOISE_C = 0.1
RH_NOISE_PCT = 0.5
LUX_NOISE = 30.0

DEFAULT_RESERVOIR_ML = 5_000.0    # 5 L


# --- State ------------------------------------------------------------------


@dataclass
class ZoneSimState:
    zone_id: int
    moisture_pct: float = 55.0     # truth value, not the noisy reading
    pump_on: bool = False
    pump_started_at_sim: float | None = None
    accumulated_water_ml: float = 0.0
    stuck_soil_value_raw: int | None = None   # set when failure injection sticks the probe


@dataclass
class FailureFlags:
    """Failure-injection knobs read from the control JSON file (or env)."""

    stuck_soil_zone: int | None = None
    disconnect_soil_zone: int | None = None
    pump_seized_zone: int | None = None
    lux_disconnect: bool = False
    air_disconnect: bool = False
    reservoir_empty: bool = False        # forces the float switch to trip
    clock_skew_minutes: float = 0.0      # offsets the sim clock seen by `_now()`


@dataclass
class Ambient:
    temp_c: float
    rh_pct: float
    lux: float


# --- Backend ----------------------------------------------------------------


class SimulatorBackend:
    """A complete fake of the wall garden's I/O surface.

    Construct via `from_settings(settings)` which uses env vars for speed/seed.
    """

    def __init__(
        self,
        zones: list[int],
        speed: float = 1.0,
        control_path: Path | None = None,
        seed: int | None = None,
        reservoir_ml: float = DEFAULT_RESERVOIR_ML,
        photos_dir: Path | None = None,
        sim_start_offset_s: float = 12 * 3600,   # start at sim noon for sane tests
    ) -> None:
        self.speed = max(0.0001, speed)
        self.zones: dict[int, ZoneSimState] = {z: ZoneSimState(zone_id=z) for z in zones}
        self.reservoir_ml = reservoir_ml
        self.lamp_on = False
        self.failures = FailureFlags()
        self.control_path = control_path
        self._control_mtime: float = 0.0
        self._wall_start = time.monotonic()
        self._sim_start_offset = sim_start_offset_s
        self._last_step_sim: float = sim_start_offset_s
        self._rng = random.Random(seed)
        self._photos_dir = photos_dir or Path("./tmp/photos")
        self._photo_serial = 0

    @classmethod
    def from_settings(cls, settings: Settings) -> "SimulatorBackend":
        return cls(
            zones=[1, 2, 3, 4],
            speed=settings.sim_speed,
            control_path=settings.sim_control if settings.sim_control else None,
            seed=int(os.environ.get("WALLGARDEN_SIM_SEED", "1337")),
            photos_dir=settings.photos_dir,
        )

    # --- Time -----------------------------------------------------------

    def _now(self) -> float:
        """Sim seconds since `sim_start_offset_s`, advanced by `speed`."""
        elapsed_wall = time.monotonic() - self._wall_start
        return self._sim_start_offset + elapsed_wall * self.speed + self.failures.clock_skew_minutes * 60.0

    # --- Stepping (called implicitly on every read) ---------------------

    def _step(self) -> None:
        now = self._now()
        dt = now - self._last_step_sim
        if dt <= 0:
            return
        self._last_step_sim = now
        self._reload_failures_if_changed()
        ambient = self._ambient_truth(now)
        self._step_zones(dt, ambient)
        # If reservoir is empty (truth or forced), pumps draw nothing.

    def _step_zones(self, dt: float, ambient: Ambient) -> None:
        sim_now = self._now()
        for zone in self.zones.values():
            # Drying — exponential decay toward 0.
            tau = self._drying_tau(ambient)
            zone.moisture_pct *= math.exp(-dt / tau)

            # Pumping with cap-aware integration. If the tick straddles the
            # PUMP_HARD_CAP_S boundary, count only the seconds before the cap.
            seized = self.failures.pump_seized_zone == zone.zone_id
            res_empty = self.reservoir_ml <= 0 or self.failures.reservoir_empty
            if zone.pump_on and zone.pump_started_at_sim is not None:
                pump_age_end = sim_now - zone.pump_started_at_sim
                pump_age_start = max(0.0, pump_age_end - dt)
                effective_pump_s = max(
                    0.0,
                    min(pump_age_end, PUMP_HARD_CAP_S) - min(pump_age_start, PUMP_HARD_CAP_S),
                )
                if effective_pump_s > 0 and not seized and not res_empty:
                    drawn = min(
                        PUMP_ML_PER_SEC * effective_pump_s,
                        max(0.0, self.reservoir_ml),
                    )
                    self.reservoir_ml -= drawn
                    zone.accumulated_water_ml += drawn
                # Cap reached during or before this tick? Self-cut.
                if pump_age_end >= PUMP_HARD_CAP_S:
                    zone.pump_on = False
                    zone.pump_started_at_sim = None

            # Wicking — first-order toward 0.
            if zone.accumulated_water_ml > 0:
                wicked = zone.accumulated_water_ml * (1 - math.exp(-dt / WICK_TAU_S))
                zone.accumulated_water_ml -= wicked
                zone.moisture_pct = min(100.0, zone.moisture_pct + wicked * ML_TO_MOISTURE_PCT)

            zone.moisture_pct = max(0.0, zone.moisture_pct)

    def _drying_tau(self, ambient: Ambient) -> float:
        # Hot + bright dries faster. Floor at half-base so we never get insane decay.
        factor = 1.0 + max(-0.5, (ambient.temp_c - BASE_TEMP_C) / 10.0) + ambient.lux / 60_000.0
        return DRYING_BASE_TAU_S / max(0.5, factor)

    def _ambient_truth(self, now: float) -> Ambient:
        # day_fraction in [0,1); 0=midnight, 0.5=noon
        day_fraction = (now % SIM_DAY_SECONDS) / SIM_DAY_SECONDS
        # sun: 0 at midnight (fraction 0/1), peaks at noon (fraction 0.5)
        sun = max(0.0, math.sin(day_fraction * 2 * math.pi - math.pi / 2))
        lux = sun * PEAK_LUX
        if self.lamp_on:
            lux += LAMP_LUX
        temp_c = BASE_TEMP_C + TEMP_SWING_C * sun
        rh_pct = BASE_RH_PCT - RH_SWING_PCT * sun
        return Ambient(temp_c=temp_c, rh_pct=rh_pct, lux=lux)

    # --- Failure injection ----------------------------------------------

    def _reload_failures_if_changed(self) -> None:
        if not self.control_path or not self.control_path.exists():
            return
        try:
            mtime = self.control_path.stat().st_mtime
        except OSError:
            return
        if mtime <= self._control_mtime:
            return
        try:
            with self.control_path.open() as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return
        self._control_mtime = mtime
        self.failures = FailureFlags(
            stuck_soil_zone=raw.get("stuck_soil_zone"),
            disconnect_soil_zone=raw.get("disconnect_soil_zone"),
            pump_seized_zone=raw.get("pump_seized_zone"),
            lux_disconnect=bool(raw.get("lux_disconnect", False)),
            air_disconnect=bool(raw.get("air_disconnect", False)),
            reservoir_empty=bool(raw.get("reservoir_empty", False)),
            clock_skew_minutes=float(raw.get("clock_skew_minutes", 0.0)),
        )

    # --- Sensor reads ---------------------------------------------------

    def read_soil(self, zone_id: int) -> int | None:
        self._step()
        if self.failures.disconnect_soil_zone == zone_id:
            return None
        zone = self.zones.get(zone_id)
        if zone is None:
            return None
        if self.failures.stuck_soil_zone == zone_id:
            if zone.stuck_soil_value_raw is None:
                # Freeze whatever the probe was reading at the moment of failure.
                zone.stuck_soil_value_raw = self._moisture_to_raw(zone.moisture_pct)
            return zone.stuck_soil_value_raw
        raw = self._moisture_to_raw(zone.moisture_pct)
        return int(raw + self._rng.gauss(0, SOIL_ADC_NOISE))

    def _moisture_to_raw(self, pct: float) -> int:
        # Capacitive probe: higher moisture → lower count.
        frac = max(0.0, min(1.0, pct / 100.0))
        return int(DRY_RAW_DEFAULT + (WET_RAW_DEFAULT - DRY_RAW_DEFAULT) * frac)

    def read_air_temp_c(self) -> float | None:
        self._step()
        if self.failures.air_disconnect:
            return None
        return self._ambient_truth(self._now()).temp_c + self._rng.gauss(0, TEMP_NOISE_C)

    def read_air_rh_pct(self) -> float | None:
        self._step()
        if self.failures.air_disconnect:
            return None
        return self._ambient_truth(self._now()).rh_pct + self._rng.gauss(0, RH_NOISE_PCT)

    def read_lux(self) -> float | None:
        self._step()
        if self.failures.lux_disconnect:
            return None
        return max(0.0, self._ambient_truth(self._now()).lux + self._rng.gauss(0, LUX_NOISE))

    def read_reservoir_empty(self) -> bool | None:
        self._step()
        if self.failures.reservoir_empty:
            return True
        return self.reservoir_ml <= 0.0

    # --- Actuators ------------------------------------------------------

    def pump_on(self, zone_id: int) -> None:
        self._step()
        zone = self.zones.get(zone_id)
        if zone is None:
            return
        if not zone.pump_on:
            zone.pump_on = True
            zone.pump_started_at_sim = self._now()

    def pump_off(self, zone_id: int) -> None:
        self._step()
        zone = self.zones.get(zone_id)
        if zone is None:
            return
        zone.pump_on = False
        zone.pump_started_at_sim = None

    def lamp(self, on: bool) -> None:
        self._step()
        self.lamp_on = on

    def capture_photo(self, path: str) -> None:
        self._step()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        img = self._render_photo()
        img.save(out, format="JPEG", quality=80)

    def shutdown(self) -> None:
        for zone in self.zones.values():
            zone.pump_on = False
            zone.pump_started_at_sim = None
        self.lamp_on = False

    # --- Synthetic photo ------------------------------------------------

    def _render_photo(self) -> Image.Image:
        """Draw a 2x2 grid of leaves tinted by per-zone moisture.

        Green = healthy (moisture ≥ 45). Yellow = thirsty (25..45). Brown = dying (<25).
        A `[SIM]` watermark in the corner signals it's not a real camera.
        """
        self._photo_serial += 1
        w, h = 640, 480
        ambient = self._ambient_truth(self._now())
        # Background tint by ambient lux (dark at night).
        base = int(20 + 200 * (ambient.lux / (PEAK_LUX + LAMP_LUX)))
        bg = (base, base + 20, base)
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)

        cells = [
            ((0, 0), 1),
            ((1, 0), 2),
            ((0, 1), 3),
            ((1, 1), 4),
        ]
        cw, ch = w // 2, h // 2
        for (cx, cy), zone_id in cells:
            zone = self.zones.get(zone_id)
            if zone is None:
                continue
            self._draw_leaf(draw, cx * cw, cy * ch, cw, ch, zone.moisture_pct)
            label_x = cx * cw + 10
            label_y = cy * ch + 10
            draw.text((label_x, label_y), f"Z{zone_id} {zone.moisture_pct:5.1f}%", fill=(255, 255, 255))

        draw.text((w - 80, h - 18), "[SIM]", fill=(255, 100, 100))
        return img

    @staticmethod
    def _draw_leaf(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, moisture_pct: float) -> None:
        # Color: interpolate brown → yellow → green over moisture range.
        if moisture_pct >= 45:
            color = (60, 180, 75)
        elif moisture_pct >= 25:
            t = (moisture_pct - 25) / 20.0
            color = (int(180 - 120 * t), int(180), int(45 + 30 * t))
        else:
            color = (110, 70, 30)
        # Draw two ellipses as a stylized leaf shape.
        cx, cy = x + w // 2, y + h // 2
        draw.ellipse((cx - w // 3, cy - h // 4, cx + w // 3, cy + h // 4), fill=color)
        draw.line((cx - w // 3, cy, cx + w // 3, cy), fill=(30, 60, 30), width=3)
