# Runbook

What each alert means and what to do.

## Critical

### `reservoir_empty`

The float switch reports empty (debounced 3 reads). All pumps are blocked
until you refill.

Action: refill the reservoir. The alert auto-resolves on the next read.

### `daemon_heartbeat_stale`

Rails hasn't seen a daemon heartbeat in > 2 minutes. The control loop is
probably down.

Action: SSH to the Pi, `systemctl status wallgardend`. If failed, check
logs (`journalctl -u wallgardend -n 200`). If the systemd watchdog has
been restart-looping, look for I²C errors or Postgres connectivity issues.

### `pump_runtime_exceeded`

The hardware cap (15 s) cut off a pump that was commanded longer. This
should never happen with the control loop's per-event sizing — investigate
which actor issued the command (`commands` table, `requested_by`).

## Warn

### `soil_sensor_disconnected` (zone N)

Five consecutive `None` reads from a probe. That zone's auto-watering is
disabled.

Action: check the wiring. If still failing, swap the probe.

### `soil_sensor_stuck` (zone N)

Probe readings have moved less than 0.5% over 30 minutes — implausibly
constant. The zone is treated as failed.

Action: verify the probe isn't physically detached or buried in saturated
soil; recalibrate if necessary.

### `daily_cap_hit_zone_N`

Zone N hit its daily mL cap. Auto-watering stops until midnight UTC.

Action: usually nothing — caps exist for a reason. If it happens repeatedly,
you may need a higher cap or more frequent smaller events.

## Info

### `llm_unavailable`

The Anthropic API was unreachable or returned an error. The control loop
is unaffected.

Action: usually nothing. Check `api.anthropic.com` reachability if it persists.

### `llm_cost_cap_hit`

Month-to-date LLM spend exceeded `MONTHLY_LLM_COST_CAP_USD`. Non-essential
jobs (weekly report, photo analysis, chat) are paused.

Action: raise the cap in `.env` or wait for the next month.

### `anomaly_detected`

Statistical detector found a reading > ±2σ from the 7-day baseline. Claude
Haiku wrote a short explanation in the alert message.
