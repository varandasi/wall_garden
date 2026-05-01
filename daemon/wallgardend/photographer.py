"""Hourly + on-demand photo capture.

Slice 5: the daemon's control loop calls `tick_photographer` once per tick;
the photographer keeps its own next-photo deadline and acts when it's due.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .hardware.backend import HardwareBackend

log = logging.getLogger(__name__)

DEFAULT_INTERVAL_S = 3600.0   # one shot per hour


@dataclass
class Photographer:
    backend: HardwareBackend
    photos_dir: Path
    interval_s: float = DEFAULT_INTERVAL_S
    next_due_mono: float = 0.0           # 0 => take a photo on first tick

    def tick(self, *, now_mono: float, now_utc: datetime) -> Path | None:
        if now_mono < self.next_due_mono:
            return None
        self.next_due_mono = now_mono + self.interval_s
        return take_photo(self.backend, self.photos_dir, now_utc=now_utc)


def take_photo(
    backend: HardwareBackend,
    photos_dir: Path,
    *,
    zone_id: int | None = None,
    now_utc: datetime | None = None,
) -> Path:
    photos_dir.mkdir(parents=True, exist_ok=True)
    now_utc = now_utc or datetime.now(timezone.utc)
    suffix = f"_z{zone_id}" if zone_id is not None else ""
    out = photos_dir / f"{now_utc:%Y%m%dT%H%M%SZ}{suffix}.jpg"
    backend.capture_photo(str(out))
    db.insert_photo(taken_at=now_utc, path=str(out), zone_id=zone_id)
    log.info("photo captured: %s", out)
    return out
