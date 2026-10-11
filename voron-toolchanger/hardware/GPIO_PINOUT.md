# GPIO Pinout Reference

> **Developer:** Yeonjo Ahn

**Target System**: Voron 2.4 350mm AWD + 6-Tool StealthChanger  
**Hardware Stack**: BTT Kraken V1.1 (Main MCU) + Fly-SHT36 V2/V3 ×6 (CAN Toolboards) + BTT Eddy Duo (Probe MCU)  
**Source**: Extracted from active `printer.cfg` and `T0.cfg`–`T5.cfg` configurations, including dual filament sensor pin assignments (`gpio20` / `gpio24` / `gpio16`).

---

## 1. BTT Kraken V1.1 — Main Controller Board

MCU Serial: `/dev/ttyAMA0`

### 1.1 Stepper Motors (TMC5160, SPI Control)

All 8 onboard TMC5160 drivers share SPI3 — **SCLK `PC6` / MOSI `PC8` / MISO `PC7`**

| Stepper | Step Pin | Dir Pin | Enable Pin | CS Pin | Diag / Endstop Pin |
|---|---|---|---|---|---|
| `stepper_x` | `PB9` | `!PB8` | `!PB7` | `PD3` | `diag1: ^!PF2` (Sensorless X) |
| `stepper_x1` | `PC14` | `PC13` | `!PE6` | `PD6` | — |
| `stepper_y` | `PE5` | `!PE4` | `!PE3` | `PD5` | `diag1: ^!PF0` (Sensorless Y) |
| `stepper_y1` | `PE2` | `!PE1` | `!PE0` | `PD4` | — |
| `stepper_z` | `PG9` | `!PG10` | `!PG13` | `PD2` | `endstop: ^!PF4` (Z Max Physical) |
| `stepper_z1` | `PG11` | `PD7` | `!PG12` | `PA15` | — |
| `stepper_z2` | `PB4` | `!PB3` | `!PB5` | `PA9` | — |
| `stepper_z3` | `PG15` | `PB6` | `!PG14` | `PA10` | — |

### 1.2 Heaters & Calibration Probe

| Function | Pin |
|---|---|
| Heated Bed (`heater_bed`) | `PF5` |
| Bed Thermistor | `PB0` |
| `tools_calibrate` (Sexbolt XYZ Offset Probe) | `^!PF3` |

### 1.3 Fans, Lighting & Aux Outputs

| Function | Pin |
|---|---|
| Electronics Bay Fan 1 (`controller_fan`) | `PA0` |
| Electronics Bay Fan 2 (`controller_fan`) | `PA1` |
| Chamber Exhaust/Temp Fan (`temperature_fan chamber`) | `PA2` |
| Chamber Thermistor | `PB1` |
| Nevermore / Chamber Filter Fan (`fan_generic`) | `PA3` |
| Chamber Neopixel Lighting | `PF12` |
| Gantry / Leafcutter Servo (`gantry_servo`) | `PE7` |

> **Note:** The chamber thermistor is integrated into the single `[temperature_fan chamber]` object. Reference chamber temperature in macros via `printer["temperature_fan chamber"].temperature`.

---

## 2. Fly-SHT36 V2/V3 — CANbus Toolboards ×6

All 6 toolboards share an **identical pinout** and are differentiated by their `canbus_uuid` and MCU alias (`SHT0`–`SHT5`).

### 2.1 CANbus UUID Table

| Tool | MCU Alias | `canbus_uuid` |
|---|---|---|
| `T0` | `SHT0` | `7f9b20ff59b3` |
| `T1` | `SHT1` | `7de00df04b02` |
| `T2` | `SHT2` | `6313faf5c5bc` |
| `T3` | `SHT3` | `32fa9fb2c426` |
| `T4` | `SHT4` | `c65da7c80800` |
| `T5` | `SHT5` | `c5ffcfb90f4d` |

### 2.2 Common Toolboard Pinout (`SHTn:gpioX`)

| GPIO Pin | Function |
|---|---|
| `gpio7` | Extruder Step |
| `gpio6` | Extruder Dir |
| `!gpio14` | Extruder Enable |
| `gpio15` | TMC2209 UART (Extruder Driver) |
| `gpio23` | Hotend Heater PWM |
| `gpio27` | Hotend Thermistor (`ATC Semitec 104NT-4-R025H42G`) |
| `^gpio20` | **MDM Entry Switch** — Pre-extruder filament presence switch (`T{n}_runout_entry`) |
| `^gpio16` | **MDM Pulse Channel** — Shared by `mdm_cal_T{n}` (E-step calibration) and `T{n}_clog` (motion sensor) |
| `^gpio24` | **Toolhead Runout Switch** — Post-extruder / pre-hotend switch (`T{n}_runout_toolhead`) |
| `^gpio22` | Tool Probe / Detection Switch (`tool_probe`) |
| `gpio13` | Hotend Cooling Fan (`heater_fan`) |
| `gpio21` | Part Cooling Fan (`fan_generic`) |
| `gpio12` | LIS2DW Accelerometer — SPI CS |
| `gpio2` | LIS2DW Accelerometer — SPI SCLK |
| `gpio3` | LIS2DW Accelerometer — SPI MOSI |
| `gpio4` | LIS2DW Accelerometer — SPI MISO |
| `gpio26` | Toolhead RGB Neopixel LEDs |

> **Shared Sensor Pin Note**: Where two sensor objects share the same GPIO pin on `SHT0`–`SHT5`, `[duplicate_pin_override]` must be declared in `printer.cfg` **before** including `toolchanger-include.cfg`.

---

## 3. BTT Eddy Duo — Bed Probe (Dedicated USB MCU)

Serial: `/dev/serial/by-id/usb-Klipper_rp2040_5044505930818C1C-if00`

Dedicated RP2040 USB MCU used for Quad Gantry Leveling (QGL) and rapid bed mesh scanning.

---

## Appendix — Quick Verification Commands

```gcode
QUERY_ENDSTOPS                                    # Verify Z max (^!PF4) and sensorless diag pins
QUERY_FILAMENT_SENSOR SENSOR=T0_runout_entry      # Verify gpio20 (MDM entry presence switch)
QUERY_FILAMENT_SENSOR SENSOR=T0_runout_toolhead   # Verify gpio24 (post-extruder runout switch)
QUERY_FILAMENT_SENSOR SENSOR=mdm_cal_T0           # Verify gpio16 (MDM encoder pulse channel)
```

```bash
~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0   # Scan active CANbus UUIDs
```
