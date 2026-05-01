"""Hardware contract — the only place the daemon ever sees concrete I/O.

Daemon code imports `HardwareBackend` (the Protocol). A factory selects the
concrete `SimulatorBackend` or `PiBackend` at boot. New hardware (a different
ADC, a different camera) only needs a new backend that satisfies this Protocol.

Failure semantics: every read returns either a value or `None`. Backends never
raise across this boundary — caller checks for `None` and increments its own
failure counter. This keeps the safety loop free of try/except noise.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class HardwareBackend(Protocol):
    # --- Sensors --------------------------------------------------------

    def read_soil(self, zone_id: int) -> int | None:
        """Raw ADC counts (0..32767 for ADS1115 single-ended). None on I/O failure."""

    def read_air_temp_c(self) -> float | None:
        """Ambient temperature in degrees Celsius."""

    def read_air_rh_pct(self) -> float | None:
        """Ambient relative humidity in percent (0..100)."""

    def read_lux(self) -> float | None:
        """Illuminance in lux."""

    def read_reservoir_empty(self) -> bool | None:
        """True if the float switch reports empty. Backends are responsible for
        debouncing — callers see a stable boolean. None on I/O failure."""

    # --- Actuators ------------------------------------------------------

    def pump_on(self, zone_id: int) -> None:
        """Energize the pump for `zone_id`. Backends MUST enforce a hard
        absolute runtime cap (15 s) regardless of how long it stays on."""

    def pump_off(self, zone_id: int) -> None:
        """De-energize the pump for `zone_id`. Idempotent."""

    def lamp(self, on: bool) -> None:
        """Switch the grow lamp."""

    def capture_photo(self, path: str) -> None:
        """Write a JPEG to `path`. Path is created if missing."""

    # --- Lifecycle ------------------------------------------------------

    def shutdown(self) -> None:
        """Release hardware resources cleanly. Idempotent."""
