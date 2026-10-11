# Custom Hotend CAN Expansion Board — Engineering Specification (v2)

> **Developer:** Yeonjo Ahn

## 1. Overview & Architecture

This document specifies the hardware design for a compact **RP2040 + CANbus (`can2040`) hotend expansion board** mounted near the hotend assembly of a StealthChanger toolhead.

### Functional Scope
- **Hotend Heater Control**: Up to **100W @ 24V (4.17A)** via a logic-level low-side N-Channel MOSFET (`TO-252`).
- **Hotend Thermistor Input**: High-accuracy ADC input with a `4.7kΩ 0.1%/1%` pull-up resistor and RC filtering.
- **Hotend Cooling Fan**: 24V 2-wire low-side PWM switching (`AO3400` + `SS14` flyback diode).
- **MDM Filament Motion Sensor**: Digital pulse channel for filament motion and clog detection.
- **Filament Runout Switch**: Digital presence switch input.

---

## 2. Current Budget (@ 24V DC)

| Load | Current @ 24V |
|---|---|
| Hotend Heater (100W max) | **4.17A** (80W = 3.33A) |
| Hotend Cooling Fan | ~0.30A |
| Logic Rail (24V → 5V Buck → RP2040 + CAN + Sensors) | ~0.05A |
| **Total Peak Board Current** | **≈ 4.50A** |

All input connectors, fuses, and heater copper pours are rated for **≥ 4.5A continuous**.

---

## 3. Bill of Materials (BOM — 0805 Hand-Solderable)

### [A] MCU & CANbus Transceiver
| Component | Specification | Qty | Notes |
|---|---|---|---|
| MCU Module | Waveshare RP2040-Zero | 1 | Castellated mount; onboard USB-C for initial Katapult flash |
| CAN Transceiver | `SN65HVD230` (`SOIC-8`, 3.3V) | 1 | Direct 3.3V logic interface to RP2040 `TXD`/`RXD` |
| Slope Control Resistor | `13kΩ` 0805 (`RS` → `GND`) | 1 | Slew-rate control for 250k–1Mbit CAN |
| CAN Bus ESD TVS | `PESD1CAN` (`SOT-23`) | 1 | Surge protection across `CANH` / `CANL` |
| CAN Termination | `120Ω` 0805 | 1 | Populated via jumper only on terminal bus node |
| 3.3V Decoupling | `100nF` (0.1µF) 50V X7R 0805 | 1 | Placed adjacent to `SN65HVD230` `VCC` |

### [B] Hotend Heater Power Stage (≤ 100W / 4.2A)
| Component | Specification | Qty | Notes |
|---|---|---|---|
| Heater MOSFET | **Logic-Level N-Ch `TO-252`** (`IRLR7843` or `AOD4184A`, 30V, ultra-low $R_{DS(on)}$ @ $V_{GS}=2.5\text{V}$) | 1 | Fully enhanced from 3.3V GPIO gate drive |
| Gate Resistor | `10Ω` 0805 | 1 | Dampens gate ringing |
| Gate Pull-Down | `100kΩ` 0805 | 1 | Prevents unintended heater activation during MCU reset |
| Heater Line TVS (Opt.) | `SMBJ33A` | 1 | Suppresses inductive cable transients |

### [C] Thermistor Sensing Network
| Component | Specification | Qty | Notes |
|---|---|---|---|
| Pull-Up Resistor | `4.7kΩ` 1% (0.1% recommended) 0805 → `3.3V` | 1 | Reference pull-up for NTC thermistor |
| ADC Filter Capacitor | `100nF` (0.1µF) 0805 | 1 | High-frequency noise filtering on `GP26` |

### [D] Hotend Fan Switching Stage
| Component | Specification | Qty | Notes |
|---|---|---|---|
| Fan MOSFET | `AO3400` (`SOT-23`, Logic-Level N-Ch) | 1 | Low-side 24V fan switch |
| Gate / Pull-Down | `10Ω` 0805 / `100kΩ` 0805 | 1 ea | Gate drive & reset safety |
| Flyback Diode | `SS14` Schottky (`SMA`) | 1 | Mandatory for inductive fan load |

### [E] DC-DC Power Supply (24V → 5V Logic Buck)
| Component | Specification | Qty | Notes |
|---|---|---|---|
| Buck Converter IC | `MP4560` (55V / 2A, `SOP-8`) | 1 | Supplies logic rail only (< 0.1A); heater bypasses buck |
| Power Inductor | `10µH`, $I_{sat} \ge 1.5\text{A}$ | 1 | Shielded SMD inductor |
| Input Capacitors | `10µF` 50V X7R 1206 ×2 + `100nF` 50V 0805 ×1 | 3 | Placed close to `VIN` pin |
| Output Capacitors | `22µF` 16V X7R 0805 | 2 | Low-ESR output filtering |
| Feedback Divider | Upper `68kΩ` / Lower `13kΩ` 1% 0805 | 1 ea | Sets $V_{out} \approx 4.98\text{V}$ |
| Bootstrap Capacitor | `100nF` 50V X7R 0805 | 1 | `BST` to `SW` |

### [F] Input Protection & Connectors
| Component | Specification | Qty | Notes |
|---|---|---|---|
| Input Fuse | **6.3A – 7A Fast-Acting SMD Fuse** ($\ge 32\text{V}$) | 1 | Standard fuse (avoid PTC due to high ambient chamber temp) |
| Input Rail TVS | `SMBJ33A` | 1 | 24V rail transient suppression |
| Power + CAN Connector | **Molex Micro-Fit 3.0 4-Pin** (`24V`, `GND`, `CANH`, `CANL`) | 1 | Rated ≥ 8.5A per contact |
| Heater Connector | **Molex Micro-Fit 3.0 2-Pin** | 1 | High-current heater output (do not use JST-XH) |
| Fan / Thermistor / Sensors | JST-XH / JST-PH 2-Pin & 3-Pin | 4 | Fan (2P), Thermistor (2P), MDM (3P), Runout (2/3P) |

---

## 4. Power Distribution & Grounding Topology

```text
24V Input (Micro-Fit 3.0, ~4.5A)
 ├─ [Fuse 6.3~7A] → [24V Power Rail] + [TVS SMBJ33A]
 │    ├─ Heater (+) ── Heater Cartridge ── TO-252 MOSFET Drain (Low-Side, 4.2A)
 │    ├─ Hotend Fan (+) ── 24V Fan ── AO3400 Drain (Low-Side) ∥ SS14 Flyback
 │    └─ MP4560 Buck → 5V → RP2040-Zero (5V Pin)
 │                            └─ Onboard LDO → 3.3V → SN65HVD230, Pull-Ups, Thermistor Ref
 └─ Star Ground (Single-Point Join between High-Current Heater Return & Analog/CAN Logic GND)
```

- **Star Grounding**: Keep the 4.2A heater return path isolated from the thermistor `AGND` and CAN logic `GND`, joining them only at the input power connector ground pad to prevent PWM ground bounce on temperature readings.

---

## 5. RP2040 GPIO Pin Assignment

| Function | GPIO Pin | Direction | Notes |
|---|---|---|---|
| CAN `RX` / `TX` | `GP4` / `GP5` | Bi-Dir | `can2040` PIO state machine |
| **Hotend Heater PWM** | `GP6` | Output | Drives `TO-252` MOSFET gate |
| **Hotend Thermistor** | `GP26` (`ADC0`) | Analog In | `4.7kΩ` pull-up to `3.3V` |
| Hotend Cooling Fan | `GP7` | Output | Drives `AO3400` MOSFET gate |
| MDM Motion Pulse | `GP8` | Input | Pull-up enabled (`^`) |
| Filament Runout Switch | `GP9` | Input | Pull-up enabled (`^`) |

---

## 6. Klipper Configuration Template

```ini
[mcu hotend]
canbus_uuid: <BOARD_CANBUS_UUID>

[extruder]
step_pin: SHT36:gpio7
dir_pin: SHT36:gpio6
enable_pin: !SHT36:gpio14
heater_pin: hotend:gpio6
sensor_pin: hotend:gpio26
sensor_type: Generic 3950
pullup_resistor: 4700
min_temp: 0
max_temp: 300
control: pid

[heater_fan hotend_fan]
pin: hotend:gpio7
heater: extruder
heater_temp: 50.0

[filament_motion_sensor mdm]
switch_pin: ^hotend:gpio8
detection_length: 7.0
extruder: extruder
runout_gcode:
    PAUSE

[filament_switch_sensor runout]
switch_pin: ^hotend:gpio9
runout_gcode:
    PAUSE
```
