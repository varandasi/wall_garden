"""Property tests on the pure safety primitives.

These are the foundation of the system's reliability story — every claimed
safety invariant gets exercised over arbitrary inputs.
"""
from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from wallgardend.safety import (
    PLAUSIBLE_RANGES,
    TickContext,
    ZonePhase,
    dose_for_event,
    is_in_cooldown,
    is_plausible,
    is_stuck,
    next_phase,
    remaining_daily_ml,
    tick_verdict,
)

# --- Plausibility ---------------------------------------------------------


@given(
    kind=st.sampled_from(list(PLAUSIBLE_RANGES.keys())),
    value=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_plausibility_matches_declared_range(kind, value):
    lo, hi = PLAUSIBLE_RANGES[kind]
    assert is_plausible(kind, value) == (lo <= value <= hi)


def test_none_is_implausible():
    for kind in PLAUSIBLE_RANGES:
        assert is_plausible(kind, None) is False


def test_unknown_kind_is_trusted():
    assert is_plausible("brand_new_sensor", 42.0) is True


# --- Hysteresis -----------------------------------------------------------


@given(
    target=st.floats(min_value=10.0, max_value=90.0),
    hyst=st.floats(min_value=2.0, max_value=20.0),
    moisture=st.floats(min_value=0.0, max_value=100.0),
)
def test_hysteresis_no_chatter_in_dead_band(target, hyst, moisture):
    """Inside the dead-band, the phase must not change."""
    low = target - hyst / 2
    high = target + hyst / 2
    if low <= moisture <= high:
        # Whatever the current phase, the next phase equals the current.
        for phase in (ZonePhase.SATISFIED, ZonePhase.THIRSTY):
            assert next_phase(phase, moisture, target, hyst) == phase


def test_hysteresis_enters_thirsty_below_low():
    p = next_phase(ZonePhase.SATISFIED, moisture_pct=40.0, target_pct=50.0, hysteresis_pct=10.0)
    assert p == ZonePhase.THIRSTY


def test_hysteresis_leaves_thirsty_above_high():
    p = next_phase(ZonePhase.THIRSTY, moisture_pct=60.0, target_pct=50.0, hysteresis_pct=10.0)
    assert p == ZonePhase.SATISFIED


def test_hysteresis_thirsty_does_not_satisfy_at_target():
    """A thirsty zone must not flip to satisfied just by reaching target —
    it must cross the upper edge of the dead-band."""
    assert next_phase(ZonePhase.THIRSTY, 50.0, 50.0, 10.0) == ZonePhase.THIRSTY


# --- Caps -----------------------------------------------------------------


@given(
    ml_today=st.floats(min_value=0.0, max_value=1000.0),
    cap=st.floats(min_value=1.0, max_value=1000.0),
)
def test_remaining_daily_ml_never_negative(ml_today, cap):
    assert remaining_daily_ml(ml_today, cap) >= 0.0


@given(
    cap_day=st.floats(min_value=1.0, max_value=1000.0),
    cap_event=st.floats(min_value=1.0, max_value=200.0),
    ml_today_frac=st.floats(min_value=0.0, max_value=1.0),
)
def test_dose_never_exceeds_either_cap(cap_day, cap_event, ml_today_frac):
    """Inductive step: starting from a valid state (ml_today ≤ cap_day),
    no dose returned by dose_for_event can violate either cap."""
    ml_today = cap_day * ml_today_frac
    dose = dose_for_event(
        ml_today=ml_today,
        max_ml_per_day=cap_day,
        max_ml_per_event=cap_event,
    )
    assert dose >= 0.0
    assert dose <= cap_event + 1e-6, "per-event cap violated"
    assert ml_today + dose <= cap_day + 1e-6, "daily cap violated"


def test_dose_never_undoes_prior_overshoot():
    """If somehow ml_today > cap_day (e.g. operator bumped the cap down at
    runtime), dose returns 0 — we never *over*-water further, but we don't
    rewrite history either."""
    assert dose_for_event(ml_today=300, max_ml_per_day=200, max_ml_per_event=50) == 0.0


def test_dose_zero_when_daily_cap_hit():
    assert dose_for_event(ml_today=200, max_ml_per_day=200, max_ml_per_event=50) == 0.0


# --- Cooldown -------------------------------------------------------------


@given(
    elapsed_s=st.floats(min_value=0.0, max_value=86400.0),
    cooldown_min=st.floats(min_value=0.0, max_value=180.0),
)
def test_cooldown_iff_below_window(elapsed_s, cooldown_min):
    assert is_in_cooldown(elapsed_s, cooldown_min) == (elapsed_s < cooldown_min * 60.0)


# --- Stuck-sensor detection -----------------------------------------------


def test_stuck_too_few_samples_innocent():
    assert is_stuck([1.0, 1.0], threshold=0.5) is False


def test_stuck_constant_samples_flagged():
    assert is_stuck([42.0] * 10, threshold=0.5) is True


def test_stuck_normal_variation_not_flagged():
    samples = [50.0 + i * 0.2 for i in range(10)]
    # Range = 1.8, threshold = 0.5 → not stuck.
    assert is_stuck(samples, threshold=0.5) is False


# --- Tick verdict ---------------------------------------------------------


def test_tick_verdict_warmup_blocks_actions():
    v = tick_verdict(TickContext(daemon_uptime_s=10.0, reservoir_empty=False, warmup_s=60.0))
    assert v.allow_actions is False
    assert v.blocking_reason == "warmup_grace"


def test_tick_verdict_reservoir_empty_blocks_actions():
    v = tick_verdict(TickContext(daemon_uptime_s=120.0, reservoir_empty=True, warmup_s=60.0))
    assert v.allow_actions is False
    assert v.blocking_reason == "reservoir_empty"


def test_tick_verdict_allows_when_warm_and_full():
    v = tick_verdict(TickContext(daemon_uptime_s=120.0, reservoir_empty=False, warmup_s=60.0))
    assert v.allow_actions is True


# Quick smoke that hypothesis settings work.
@settings(max_examples=20)
@given(st.floats(min_value=0.0, max_value=100.0))
def test_smoke_floats_finite(x):
    assert not math.isnan(x)
