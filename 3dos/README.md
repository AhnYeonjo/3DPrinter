# 3DOS — Multi-Tool 3D Printer Host & UI Control Layer

> **Developer:** Yeonjo Ahn

**3DOS** is a lightweight Klipper host and UI orchestration layer built specifically for **multi-tool StealthChanger 3D printers**. It provides toolhead configuration management, zero-restart calibration, CANbus toolboard health monitoring & auto-recovery, PinkBox/BoxTurtle filament control, and real-time toolchange visualization.

It has **zero external dependencies** and runs out of the box on stock Python 3 on any Raspberry Pi or Linux/macOS host.

![3DOS Dashboard Running on Raspberry Pi](../assets/3dos_raspberry_pi_ui.jpg)

---

## Quick Start

```bash
cd 3dos
./run.sh                  # Dry-run mode; auto-imports T*.cfg from ../voron-toolchanger/config
# or
python3 server.py
```

Open `http://localhost:8088` in your browser.

To connect to a live Klipper / Moonraker printer:

```bash
MOONRAKER_URL=http://localhost:7125 ./run.sh   # Live mode: sends G-code & polls printer state
```

---

## Key Features

- **Zero-Restart Calibration**: Save and apply per-tool XYZ offsets, Pressure Advance (PA), and Input Shaper settings at runtime without running `SAVE_CONFIG` or restarting Klipper firmware.
- **N-1 Graceful Safe Boot & MCU Auto-Recovery**: Scans CANbus UUIDs to generate safe-boot configurations excluding offline toolboards, and diagnoses MCU shutdown causes for automated recovery.
- **Real-Time Tool & Filament Tiles**: Controls active shuttle nozzle temperature, per-tool material/color presets, dual filament sensors (entry & toolhead), and one-click Load / Unload / Purge workflows.
- **Print Workflow, History Analytics & Bed Mesh**: Built-in G-code file manager, print start/cancel controls, cumulative print statistics, SVG bed mesh heatmap, and guided wizards for Tool Offset and Input Shaper calibration.
- **Smart Print Options & Hardware Maintenance**: Toggles for clog detection, first-layer inspection, spaghetti detection, and adaptive bed mesh (KAMP), plus Nevermore carbon filter lifecycle tracking.

---

## Camera Configuration (`cameras.json`)

```json
[
  { "id": "cam0", "label": "Shuttle Cam", "url": "http://<pi>:8080/?action=stream" },
  { "id": "cam1", "label": "Chamber Cam", "url": "http://<pi>:8081/?action=stream" }
]
```

---

## Coexistence with Mainsail & Fluidd

3DOS is designed to run safely alongside Mainsail or Fluidd without conflict:
- **Dedicated Port**: Defaults to port `8088` (configurable via `PORT`), avoiding conflicts with Mainsail (`80`) and Moonraker (`7125`).
- **Non-Destructive Storage**: Writes only to its own JSON stores (`tools.snapshot.json`, `calibration.json`, `options.json`, `maintenance.json`, `cameras.json`) and never overwrites `printer.cfg`.

---

## OrcaSlicer & Touchscreen Kiosk Integration

- **OrcaSlicer Integration**: Set the printer Host URL in OrcaSlicer to `http://<pi>:8088` to embed the 3DOS UI directly inside OrcaSlicer's **Device Tab**.
- **Touchscreen Kiosk (`/touch`)**: Responsive touch interface optimized for `1024×600` and `800×480` displays as a drop-in replacement for KlipperScreen:
  ```bash
  chromium-browser --kiosk http://localhost:8088/touch
  ```

---

## REST API Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/state` | Tool list, active tool, and server mode (`LIVE` / `DRY-RUN`) |
| `GET` | `/api/boards` | Supported CAN toolboard presets |
| `POST` | `/api/tools` | Create or update a toolhead definition |
| `DELETE` | `/api/tools/{n}` | Delete toolhead `Tn` |
| `POST` | `/api/toolchange` | Plan (and in live mode execute) a toolchange to `{"to": n}` |
| `GET` | `/api/export` | Export generated Klipper configuration bundle |
| `GET/POST` | `/api/calibration/{n}` | Read or save tool `Tn` calibration (zero-restart) |
| `POST` | `/api/calibration/{n}/apply` | Re-apply stored runtime calibration G-codes for `Tn` |
| `GET` | `/api/health` | CANbus toolboard online/offline health report |
| `POST` | `/api/health/set` · `/scan` | Simulate board health state or trigger live CANbus scan |
| `GET` | `/api/safeboot` | Generate N-1 safe-boot configuration excluding offline boards |
| `POST` | `/api/recover` | Diagnose MCU shutdown cause and trigger safe auto-restart |
| `GET/POST` | `/api/macros` · `/run` | List categorized Klipper macros or execute a macro |
| `GET/POST` | `/api/filament` · `/run` | Query filament presets/state or run Load / Unload / Purge |
| `GET/POST` | `/api/controls` · `/set` | Query or set bed, chamber, Nevermore, nozzle, and speed factor |
| `GET/POST` | `/api/network` · `/scan` | Query or configure Wi-Fi, static IP, and hostname |
| `GET/POST` | `/api/files` · `/print/start` | Browse G-code files, inspect metadata, and start prints |
