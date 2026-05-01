# Hardware

For when you stop running against the simulator and start buying parts.

## Bill of materials (Pi 5, 4 zones)

| Item | Recommendation | Notes |
|---|---|---|
| SBC | Raspberry Pi 5, 8 GB | Pi 4 works but throttles in a humid wall enclosure. |
| Storage | Samsung 870 EVO SSD via USB-3 to SATA | SD cards die from Postgres WAL writes within months. |
| PSU | Official Pi 5 27 W USB-C | Underpowered PSUs cause the most "random" Pi crashes. |
| Cooling | Official active cooler | Required if you want sustained 1 Hz logging. |
| Soil moisture (×4) | DFRobot SEN0193 capacitive v2 | Resistive probes corrode in weeks. |
| ADC | ADS1115 (16-bit, 4-channel, I²C 0x48) | Two boards (×2) at 0x48/0x49 cover 8 zones. |
| Air T/RH | BME280 (I²C 0x76) | Bonus pressure reading. SHT31 is fine alternative. |
| Light | BH1750FVI (I²C 0x23) | Lux output is directly meaningful. |
| Camera | Raspberry Pi Camera Module 3 (autofocus) | Use `picamera2` (libcamera). |
| Pumps (×4) | 12 V peristaltic dosing pumps | Self-priming, no back-siphon, predictable mL/s. |
| Pump driver | Waveshare 8-channel relay HAT (B), opto-isolated | One channel per pump + lamp + spare. |
| Reservoir level | Horizontal float switch (NO) | Add a second mid-level switch in v2. |
| Grow lamp | Existing LED grow lamp via SSR (Fotek SSR-25 DA) | Mains wiring physically segregated from Pi. |
| 12 V supply | 12 V 5 A meanwell-class brick | **Separate from the Pi 5 V supply.** Common ground. |
| Tubing | 4 mm ID silicone + drip emitters | Standard hydroponics. |
| Enclosure | IP54 ABS box; drip loops on every wire | Mount Pi above the highest spill line. |

## Pi wiring summary

- I²C bus 1: BME280 (0x76), BH1750 (0x23), ADS1115 (0x48 [+ 0x49])
- GPIO 17 (input, pull-up): reservoir float switch (NC → empty when HIGH)
- GPIO 5/6/13/16 (zones 1..4): pump relays (active LOW on most HATs)
- GPIO 26: grow lamp relay
- CSI camera ribbon: Pi Camera v3
- Active cooler PWM: handled by Pi firmware

`daemon/config/hardware.yml` is the source of truth — edit it after wiring.

## Pre-deploy checklist

1. Bench-test pump dry-run (`bin/dev`, hit "Water now" in the dashboard).
2. Calibrate each soil probe in air and in water; record `moisture_dry_raw` /
   `moisture_wet_raw` per zone.
3. Calibrate each pump's mL/s by pumping into a graduated cylinder for 10 s ×3.
4. Run for 24 h on the bench tray before mounting on the wall.
