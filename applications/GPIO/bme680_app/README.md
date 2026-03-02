# BME680 IAQ - Flipper Zero / Kiisu v4b

A full-featured BME680 environmental sensor application for Flipper Zero and compatible devices (Kiisu v4b, Momentum firmware, etc.).

Reads temperature, humidity, pressure, gas resistance, and calculates an Indoor Air Quality (IAQ) score, comfort index, and heat index in real time.

## Features

- **Temperature** — Celsius or Fahrenheit (configurable)
- **Humidity** — Relative humidity with dew point calculation
- **Pressure** — Barometric pressure in hPa
- **Gas Resistance** — VOC-correlated resistance from the BME680 heater
- **IAQ Score** — Calculated 0–500 Indoor Air Quality index with visual bar
- **Comfort Index** — Combined temp + humidity assessment (Comfortable, Cold, Hot, Dry, Humid, etc.)
- **Heat Index** — "Feels like" temperature using the Rothfusz regression
- **Absolute Humidity** — In g/m³
- **Configurable Alarms** — IAQ, temperature, and humidity thresholds with LED, vibration, and sound alerts
- **SD Card Logging** — CSV files with timestamps, one file per session
- **Auto-Retry Sensor Detection** — Continuously scans for the sensor, no restart needed
- **Dual I2C Address Support** — Automatically tries 0x76 and 0x77

## Pages

Navigate between pages using **Left** and **Right** buttons.

### Page 1 — Overview

Displays temperature, humidity, pressure, dew point, IAQ score with a progress bar, and reading count. Shows `LOG` indicator when SD logging is active. Alarm warnings appear as an inverted bar at the bottom when triggered.

### Page 2 — Gas & Air Quality

Displays gas resistance in Ohms/kOhm, gas validity and heater stability status, heater temperature setting, reading interval, and total reading count.

### Page 3 — Comfort

Displays comfort status, feels-like (heat index) temperature, absolute humidity in g/m³, and dew point.

## Controls

### Data Pages (Overview / Gas / Comfort)

| Button | Action |
|--------|--------|
| **OK** (short press) | Force an immediate sensor reading |
| **OK** (long press) | Open Settings & Alarms menu |
| **Left / Right** | Switch between pages |
| **Up / Down** | Force an immediate sensor reading |
| **Back** | Exit the application |

### Settings & Alarms Menu

| Button | Action |
|--------|--------|
| **Up / Down** | Navigate menu items |
| **Left / Right** | Change selected value |
| **OK** | Toggle ON/OFF items |
| **Back** | Close menu, return to data view |

## Settings & Alarms Menu

Accessible via **long press OK** from any data page. All settings and alarms are in one scrollable list:

**General Settings**
- I2C Address — 0x76 or 0x77 (reinitializes sensor on change)
- Temperature Unit — Celsius or Fahrenheit (auto-converts alarm thresholds)
- Reading Interval — 1 to 10 seconds
- Heater Temperature — 200 to 400°C (in 20° steps)

**Alarms**
- IAQ Alarm — ON/OFF, threshold 25–500 (in steps of 25)
- Temperature Alarm — ON/OFF, low and high bounds
- Humidity Alarm — ON/OFF, low and high bounds (in steps of 5%)

**Alarm Outputs**
- LED — Off / Red / Green / Orange
- Vibration — ON/OFF
- Sound — ON/OFF

**Logging**
- Log to SD — ON/OFF
- Log Interval — Write every 1 to 60 readings

## SD Card Logging

When enabled, logs sensor data to CSV files on the SD card.

**Location:** `/ext/apps_data/bme680/`

**Filename format:** `YYYY-MM-DD_HHMMSS.csv` (timestamp of when logging was started)

**CSV columns:**

| Column | Description |
|--------|-------------|
| timestamp | Unix timestamp (seconds since 1970) |
| date | Date as YYYY-MM-DD |
| time | Time as HH:MM:SS |
| temp_c | Temperature in °C |
| humidity | Relative humidity in % |
| pressure_hpa | Barometric pressure in hPa |
| gas_ohm | Gas resistance in Ohms |
| gas_valid | 1 = valid reading, 0 = not valid |
| heat_stable | 1 = heater stabilized, 0 = not stable |
| iaq | Calculated IAQ score (0–500) |

A new file is created each time logging is toggled ON.

## IAQ Scale

| Score | Rating | Description |
|-------|--------|-------------|
| 0–50 | Excellent | Clean air |
| 51–100 | Good | Acceptable |
| 101–150 | Moderate | Sensitive individuals affected |
| 151–200 | Poor | Noticeable discomfort |
| 201–300 | Unhealthy | Significant discomfort |
| 301–500 | Hazardous | Serious health risk |

The IAQ score is calculated from humidity deviation (optimal at 40% RH) and logarithmic gas resistance mapping. The gas sensor needs a few minutes to stabilize after startup — IAQ will show "Stabilizing..." until valid readings are available.

## Wiring

Connect the BME680 sensor to the Flipper Zero GPIO header:

| BME680 Pin | Flipper Pin | GPIO |
|------------|-------------|------|
| VCC | 3.3V (Pin 9) | — |
| GND | GND (Pin 18) | — |
| SDA | Pin 15 | C1 |
| SCL | Pin 16 | C0 |

The app uses the external I2C bus. No pull-up resistors are needed if your BME680 breakout board includes them (most do).

## Building

Requires [ufbt](https://github.com/flipperdevices/flipperzero-ufbt) (micro Flipper Build Tool).

```bash
# Clone or download the project
cd bme680_app

# Build
ufbt build

# Flash directly to Flipper via USB
ufbt launch
```

The compiled `.fap` file will be in the `dist` folder.

## Compatibility

Tested on:
- Kiisu v4b (Momentum firmware)

Should work on:
- Official Flipper Zero firmware
- Unleashed firmware
- Momentum firmware
- Any firmware exposing the standard Flipper HAL I2C API

## Credits

- BME680 compensation algorithms based on the [Bosch BME680 datasheet](https://www.bosch-sensortec.com/products/environmental-sensors/gas-sensors/bme680/)
- I2C communication pattern reverse-engineered from the Bosch bme68x driver implementation

## License

MIT
