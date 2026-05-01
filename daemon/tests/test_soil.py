"""Soil calibration math."""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from wallgardend.soil import raw_to_pct


def test_dry_reads_zero():
    assert raw_to_pct(raw=26000, dry_raw=26000, wet_raw=12000) == 0.0


def test_wet_reads_hundred():
    assert raw_to_pct(raw=12000, dry_raw=26000, wet_raw=12000) == 100.0


def test_midpoint_reads_fifty():
    assert raw_to_pct(raw=19000, dry_raw=26000, wet_raw=12000) == 50.0


def test_below_dry_clamps_to_zero():
    assert raw_to_pct(raw=27000, dry_raw=26000, wet_raw=12000) == 0.0


def test_above_wet_clamps_to_hundred():
    assert raw_to_pct(raw=10000, dry_raw=26000, wet_raw=12000) == 100.0


def test_equal_calibration_is_safe():
    # Bad calibration shouldn't divide by zero.
    assert raw_to_pct(raw=18000, dry_raw=20000, wet_raw=20000) == 50.0


@given(
    raw=st.integers(min_value=0, max_value=32767),
    dry=st.integers(min_value=15000, max_value=30000),
    wet=st.integers(min_value=5000, max_value=14000),
)
def test_pct_always_in_range(raw, dry, wet):
    pct = raw_to_pct(raw, dry, wet)
    assert 0.0 <= pct <= 100.0
