"""Print-option toggles — practical safety and print-quality features.

Each toggle is persisted in 3DOS and, where Klipper can act on it, mapped to a
real command:
    clog_detection      -> ENABLE_FILAMENT_SENSORS / DISABLE_FILAMENT_SENSORS
                           (this build has T*_clog filament_motion_sensor)
    adaptive_bed_mesh   -> PRINT_START runs BED_MESH_CALIBRATE ADAPTIVE=1
    first_layer_detect  -> nozzle-cam AI check of first layer (needs camera AI)
    spaghetti_detect    -> live failure detection (needs camera AI, e.g. Obico)

The two camera-AI features store intent here; 3DOS wires them to the nozzle/
chamber cam pipeline. Until that runs they act as flags PRINT_START can read.
"""
from __future__ import annotations

import json
import os
from . import moonraker

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "options.json")

DEFAULTS = {
    "clog_detection": True,
    "first_layer_detect": True,
    "spaghetti_detect": False,
    "adaptive_bed_mesh": True,
}

META = {
    "clog_detection":    ("Clog Detection", "Pauses if extrusion commands occur without filament movement (T*_clog motion sensor)"),
    "first_layer_detect":("First Layer Inspection", "Inspects first-layer quality via nozzle camera before continuing"),
    "spaghetti_detect":  ("Spaghetti Detection", "Real-time print failure (spaghetti) detection during printing"),
    "adaptive_bed_mesh": ("Adaptive Bed Mesh", "Probes only the active print area before each print (ADAPTIVE=1)"),
}

_STATE = None


def _load():
    global _STATE
    if _STATE is None:
        _STATE = dict(DEFAULTS)
        if os.path.exists(PATH):
            try:
                with open(PATH) as f:
                    _STATE.update(json.load(f))
            except Exception:
                pass
    return _STATE


def _save():
    with open(PATH, "w") as f:
        json.dump(_STATE, f, indent=2)


def state() -> dict:
    s = _load()
    return {"options": [
        {"key": k, "value": bool(s.get(k, DEFAULTS[k])),
         "label": META[k][0], "desc": META[k][1]} for k in DEFAULTS]}


def set_option(key: str, value: bool) -> dict:
    s = _load()
    if key not in DEFAULTS:
        return {"ok": False, "detail": f"unknown option {key}"}
    s[key] = bool(value)
    _save()
    cmd = None
    if key == "clog_detection":
        cmd = "ENABLE_FILAMENT_SENSORS" if value else "DISABLE_FILAMENT_SENSORS"
    sent = False
    if cmd and moonraker.available():
        sent = moonraker.run_gcode(cmd).get("ok", False)
    return {"ok": True, "key": key, "value": bool(value),
            "command": cmd, "sent": sent}
