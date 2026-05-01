"""Pi backend — real hardware via Adafruit Blinka.

Lazy-imports every Pi-only module so this file is safe to *load* on macOS even
though it can't be *used* there. The factory only constructs PiBackend when
WALLGARDEN_BACKEND=pi.

Wiring assumed (see config/hardware.yml):
    I²C bus 1: BME280 (0x76), BH1750 (0x23), ADS1115 (0x48 [+ 0x49 for >4 zones])
    GPIO 17 (input, pull-up): reservoir float switch (NC → empty when HIGH)
    GPIO from `zones[].pump_gpio`: pump relays (active LOW on most relay HATs)
    GPIO 26: grow-lamp relay
    CSI camera: Pi Camera v3 (libcamera / picamera2)

Hardware-level pump runtime cap of 15 s is enforced here in `pump_on`.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from ..config import HardwareMap
from .backend import HardwareBackend  # noqa: F401  (Protocol satisfaction tested at runtime)

PUMP_HARD_CAP_S = 15.0
RESERVOIR_DEBOUNCE_READS = 3


class PiBackend:
    """Concrete backend for a Raspberry Pi 5 with Blinka-compatible parts.

    Initialisation is lazy — sensor objects are only constructed when first read,
    so a missing optional sensor at boot doesn't sink the whole daemon.
    """

    def __init__(self, hw_map: HardwareMap) -> None:
        self.hw_map = hw_map
        self._lock = threading.Lock()
        self._i2c: Any = None
        self._bme: Any = None
        self._bh: Any = None
        self._ads: dict[int, Any] = {}
        self._ads_channels: dict[tuple[int, int], Any] = {}
        self._pumps: dict[int, Any] = {}
        self._lamp: Any = None
        self._float: Any = None
        self._float_history: list[bool] = []
        self._pump_off_timers: dict[int, threading.Timer] = {}

    # --- Lazy hardware initialisers -------------------------------------

    def _ensure_i2c(self) -> Any:
        if self._i2c is None:
            import board                        # noqa: PLC0415
            self._i2c = board.I2C()
        return self._i2c

    def _ensure_bme(self) -> Any:
        if self._bme is None:
            from adafruit_bme280 import basic as adafruit_bme280  # noqa: PLC0415
            self._bme = adafruit_bme280.Adafruit_BME280_I2C(
                self._ensure_i2c(), address=self.hw_map.bme280_address
            )
        return self._bme

    def _ensure_bh(self) -> Any:
        if self._bh is None:
            import adafruit_bh1750              # noqa: PLC0415
            self._bh = adafruit_bh1750.BH1750(
                self._ensure_i2c(), address=self.hw_map.bh1750_address
            )
        return self._bh

    def _ensure_ads_channel(self, address: int, channel: int) -> Any:
        key = (address, channel)
        if key in self._ads_channels:
            return self._ads_channels[key]
        if address not in self._ads:
            from adafruit_ads1x15 import ads1115 as ads_mod  # noqa: PLC0415
            self._ads[address] = ads_mod.ADS1115(self._ensure_i2c(), address=address)
        from adafruit_ads1x15.analog_in import AnalogIn      # noqa: PLC0415
        chan = AnalogIn(self._ads[address], channel)
        self._ads_channels[key] = chan
        return chan

    def _ensure_pump(self, gpio: int) -> Any:
        if gpio in self._pumps:
            return self._pumps[gpio]
        from gpiozero import OutputDevice  # noqa: PLC0415
        # active_high=False — most relay HATs are active-LOW; flip if your HAT differs.
        pump = OutputDevice(gpio, active_high=False, initial_value=False)
        self._pumps[gpio] = pump
        return pump

    def _ensure_lamp(self) -> Any:
        if self._lamp is None:
            from gpiozero import OutputDevice  # noqa: PLC0415
            self._lamp = OutputDevice(self.hw_map.lamp_gpio, active_high=False, initial_value=False)
        return self._lamp

    def _ensure_float(self) -> Any:
        if self._float is None:
            from gpiozero import Button  # noqa: PLC0415
            # pull_up=True: switch shorts to GND when full → button.is_pressed=True (full).
            # We invert to "empty" semantics in `read_reservoir_empty`.
            self._float = Button(self.hw_map.reservoir_float_gpio, pull_up=True)
        return self._float

    # --- Sensor reads ---------------------------------------------------

    def read_soil(self, zone_id: int) -> int | None:
        zp = next((z for z in self.hw_map.zones if z.zone_id == zone_id), None)
        if zp is None:
            return None
        try:
            chan = self._ensure_ads_channel(zp.ads_address, zp.ads_channel)
            return int(chan.value)
        except Exception:
            return None

    def read_air_temp_c(self) -> float | None:
        try:
            return float(self._ensure_bme().temperature)
        except Exception:
            return None

    def read_air_rh_pct(self) -> float | None:
        try:
            return float(self._ensure_bme().humidity)
        except Exception:
            return None

    def read_lux(self) -> float | None:
        try:
            return float(self._ensure_bh().lux)
        except Exception:
            return None

    def read_reservoir_empty(self) -> bool | None:
        try:
            sensor = self._ensure_float()
            # is_pressed=True means switch closed (full); we want True when EMPTY.
            current_empty = not sensor.is_pressed
            self._float_history.append(current_empty)
            if len(self._float_history) > RESERVOIR_DEBOUNCE_READS:
                self._float_history.pop(0)
            if len(self._float_history) < RESERVOIR_DEBOUNCE_READS:
                return current_empty
            return all(self._float_history)
        except Exception:
            return None

    # --- Actuators ------------------------------------------------------

    def pump_on(self, zone_id: int) -> None:
        zp = next((z for z in self.hw_map.zones if z.zone_id == zone_id), None)
        if zp is None:
            return
        with self._lock:
            self._ensure_pump(zp.pump_gpio).on()
            existing = self._pump_off_timers.pop(zone_id, None)
            if existing:
                existing.cancel()
            timer = threading.Timer(PUMP_HARD_CAP_S, lambda: self.pump_off(zone_id))
            timer.daemon = True
            timer.start()
            self._pump_off_timers[zone_id] = timer

    def pump_off(self, zone_id: int) -> None:
        zp = next((z for z in self.hw_map.zones if z.zone_id == zone_id), None)
        if zp is None:
            return
        with self._lock:
            try:
                self._ensure_pump(zp.pump_gpio).off()
            except Exception:
                pass
            t = self._pump_off_timers.pop(zone_id, None)
            if t:
                t.cancel()

    def lamp(self, on: bool) -> None:
        try:
            (self._ensure_lamp().on if on else self._ensure_lamp().off)()
        except Exception:
            pass

    def capture_photo(self, path: str) -> None:
        from picamera2 import Picamera2  # noqa: PLC0415
        from pathlib import Path        # noqa: PLC0415
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        cam = Picamera2()
        cam.configure(cam.create_still_configuration())
        cam.start()
        try:
            time.sleep(0.5)
            cam.capture_file(path)
        finally:
            cam.stop()
            cam.close()

    def shutdown(self) -> None:
        with self._lock:
            for zid in list(self._pump_off_timers.keys()):
                t = self._pump_off_timers.pop(zid, None)
                if t:
                    t.cancel()
            for pump in self._pumps.values():
                try:
                    pump.off()
                    pump.close()
                except Exception:
                    pass
            self._pumps.clear()
            if self._lamp is not None:
                try:
                    self._lamp.off()
                    self._lamp.close()
                except Exception:
                    pass
                self._lamp = None
