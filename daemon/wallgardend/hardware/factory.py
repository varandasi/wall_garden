"""Backend factory — chooses simulator or Pi based on settings."""
from __future__ import annotations

from ..config import HardwareMap, Settings
from .backend import HardwareBackend


def make_backend(settings: Settings, hw_map: HardwareMap) -> HardwareBackend:
    if settings.backend == "simulator":
        from .simulator import SimulatorBackend

        return SimulatorBackend.from_settings(settings)
    if settings.backend == "pi":
        # Lazy import — the Pi-only Adafruit deps are absent on macOS.
        from .pi import PiBackend

        return PiBackend(hw_map)
    raise ValueError(f"unknown WALLGARDEN_BACKEND={settings.backend!r}")
