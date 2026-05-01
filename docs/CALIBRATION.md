# Calibration

## Soil probes

Each capacitive probe needs a **dry** reading (in air) and a **wet** reading
(in a cup of water). The values get stored in `zones.moisture_dry_raw` and
`zones.moisture_wet_raw`; `daemon/wallgardend/soil.raw_to_pct` linearly
interpolates between them at runtime.

Procedure per zone:

1. Power up the Pi. Open the dashboard's zone edit page.
2. Hold the probe in air for 30 s. Note the latest raw reading from the zone
   show page (use `bin/rails c` if needed: `Zone.find(1).sensor_readings.where(kind: 'soil_moisture_pct').last.raw`).
3. Plunge the probe into a cup of plain water up to the line, hold for 30 s.
   Note the raw reading.
4. Save those values into `moisture_dry_raw` / `moisture_wet_raw` on the
   zone edit page. The daemon picks up changes within 30 s.

## Pumps

Per zone, pump for 10 s into a graduated cylinder, repeat ×3, average. Divide
by 10 to get `pump_ml_per_sec`. Save it on the zone edit page.

The control loop sizes each watering event from `dose / pump_ml_per_sec`,
clamped at 15 s by the hardware cap. If the pump is much faster or slower
than expected, the daily-cap bookkeeping drifts — recalibrate.
