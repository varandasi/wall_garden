# Simulator

The simulator (`daemon/wallgardend/hardware/simulator.py`) lets you develop
the daemon and the dashboard with no hardware.

## What it models

- Per-zone soil moisture with exponential drying (τ depends on temp + lux)
- Pumping that adds water proportional to time-on, wicking in over ~5 min
- Diurnal cycle: sun curve (lux), temp swing (16..26 °C), RH inversely
  correlated with sun
- Reservoir: finite mL volume; float switch trips when empty
- Per-sensor Gaussian noise
- Synthetic plant photos (Pillow) tinted by per-zone moisture

## Time scaling

```
WALLGARDEN_SIM_SPEED=60     # 60× wall time — 1 sim hour in 1 wall minute
```

A 7-day soak test at speed=60 takes about 3 hours of wall time.

## Failure injection

Edit `daemon/simulator/control.json` (or set the path via `WALLGARDEN_SIM_CONTROL`).
The simulator hot-reloads on every read.

```json
{
  "stuck_soil_zone": 2,
  "disconnect_soil_zone": 3,
  "pump_seized_zone": 1,
  "lux_disconnect": false,
  "air_disconnect": false,
  "reservoir_empty": false,
  "clock_skew_minutes": 0
}
```

Setting any field triggers the named failure. Removing it (or restoring it
to null/false/0) reverts.

## Soak runner

`bin/soak` runs the daemon at sim_speed=60 with a baked-in failure schedule
spanning seven simulated days. It prints a JSON pass/fail report at the end.
