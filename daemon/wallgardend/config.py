"""Daemon configuration — env vars + YAML hardware map.

Runtime knobs (zone thresholds, plant profiles) live in Postgres and are read
every 30 s. Static knobs (I2C addresses, GPIO pins) live in `config/hardware.yml`
and are read once at boot.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide settings sourced from env vars."""

    model_config = SettingsConfigDict(env_prefix="WALLGARDEN_", extra="ignore")

    backend: Literal["simulator", "pi"] = "simulator"
    sim_speed: float = 1.0
    sim_control: Path = Path("simulator/control.json")
    database_url: str = Field(
        default="postgres://wallgarden:wallgarden@localhost:5433/wallgarden_development",
        validation_alias="DATABASE_URL",
    )
    photos_dir: Path = Field(
        default=Path("./tmp/photos"),
        validation_alias="PHOTOS_DIR",
    )
    hardware_yml: Path = Path(__file__).parent.parent / "config" / "hardware.yml"
    loop_hz: float = 1.0
    heartbeat_s: float = 5.0
    warmup_s: float = 60.0
    config_reload_s: float = 30.0
    log_level: str = "INFO"


class ZonePins(BaseModel):
    zone_id: int
    ads_address: int   # 0x48 / 0x49
    ads_channel: int   # 0..3
    pump_gpio: int


class HardwareMap(BaseModel):
    """Static, deployment-time hardware mapping.

    Only consulted by the Pi backend; the simulator ignores it.
    """

    i2c_bus: int = 1
    bme280_address: int = 0x76
    bh1750_address: int = 0x23
    reservoir_float_gpio: int = 17
    lamp_gpio: int = 26
    zones: list[ZonePins] = Field(default_factory=list)


def load_hardware_map(path: Path) -> HardwareMap:
    if not path.exists():
        return HardwareMap()
    with path.open() as fh:
        raw = yaml.safe_load(fh) or {}
    return HardwareMap(**raw)


def load_settings() -> Settings:
    return Settings()
