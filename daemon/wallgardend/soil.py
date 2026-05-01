"""Soil moisture calibration — raw ADC counts to volumetric water content %.

Per-zone calibration is held in the `zones` table (Rails owns the writes).
This module is pure arithmetic so it can be unit-tested cheaply.
"""
from __future__ import annotations


def raw_to_pct(raw: int, dry_raw: int, wet_raw: int) -> float:
    """Convert a capacitive probe ADC reading to a 0..100 moisture percentage.

    Capacitive probes report a HIGH count in air (dry) and a LOW count in water
    (wet). Linear interpolation between the two calibration points.

    Returns 0..100 clamped — anything wildly out of range is reported as 0 or 100
    to keep downstream arithmetic stable; the *plausibility filter* in `safety.py`
    is what flags an implausible reading as quality=0.
    """
    if dry_raw == wet_raw:
        return 50.0  # bad calibration; refuse to divide by zero
    pct = 100.0 * (dry_raw - raw) / (dry_raw - wet_raw)
    if pct < 0:
        return 0.0
    if pct > 100:
        return 100.0
    return pct
