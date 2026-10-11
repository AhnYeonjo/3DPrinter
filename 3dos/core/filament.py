"""Bambu-style filament load / unload.

One-tap load/unload per tool with a material picker, exactly like the Bambu
handy panel — but mapped onto the printer's existing macros:

    load    -> FILAMENT_LOAD_MODE TOOL=n MATERIAL=x   (preheat->pickup->purge)
    unload  -> UNLOAD_Tn
    purge   -> FILAMENT_LOAD_PURGE_MORE / DYNAMIC_PURGE
    confirm -> FILAMENT_LOAD_CONFIRM
    cancel  -> FILAMENT_LOAD_CANCEL

Materials come from the printer's _MATERIAL_DB (PLA/PETG/ABS/ASA/TPU/NYLON).
"""
from __future__ import annotations

from . import moonraker, filament_db

MATERIALS = ["PLA", "PETG", "ABS", "ASA", "TPU", "NYLON"]

# typical nozzle print temperature per material (shown in the AMS box)
MAT_TEMP = {"PLA": 210, "PETG": 240, "ABS": 250, "ASA": 250, "TPU": 230, "NYLON": 270}

# Per-tool loaded-filament state, AMS-slot style. Each tool carries: material,
# color swatch, present flag, current/target nozzle temp, and the two runout
# sensors this build has per tool (entry = MDM switch, toolhead = G2SA switch).
# Seeded with a demo set; load/unload mutate it. Live build drives temp from
# extruderN and sensors from the filament_switch_sensor objects.
_STATE: dict[int, dict] = {}
_DEMO = [
    ("ABS", "#e8553b"), ("ABS", "#efe3c8"), ("ABS", "#2b2b2b"),
    ("ABS", "#f0a13b"), ("PETG", "#2f7fe0"), ("TPU", "#1c1c1c"),
]
import json
import os
FILAMENT_SNAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "filament.snapshot.json")

def _load_state():
    global _STATE
    if os.path.exists(FILAMENT_SNAP):
        try:
            with open(FILAMENT_SNAP, "r") as f:
                _STATE = {int(k): v for k, v in json.load(f).items()}
        except Exception:
            pass

def _save_state():
    try:
        with open(FILAMENT_SNAP, "w") as f:
            json.dump(_STATE, f)
    except Exception:
        pass

_load_state()


def _ensure(n, i):
    if n not in _STATE:
        mat, col = _DEMO[i % len(_DEMO)]
        lo, hi, pa = filament_db.TYPE_DEFAULTS.get(mat, (200, 250, 0.02))
        _STATE[n] = {"material": mat, "color": col, "present": True,
                     "preset": "Generic " + mat, "nozzle_min": lo,
                     "nozzle_max": hi, "pa_profile": "Default", "pa_k": pa}
    return _STATE[n]


def state(tools) -> dict:
    out = {}
    if not moonraker.available():
        live_status = None
    else:
        objects = []
        for t in tools:
            n = t.tool_number
            objects.extend([
                f"filament_switch_sensor T{n}_runout_entry",
                f"filament_switch_sensor T{n}_runout_toolhead",
                "extruder" if n == 0 else f"extruder{n}",
                f"fan_generic T{n}_part_fan",
                f"heater_fan T{n}_hotend_fan",
                f"filament_switch_sensor bt_lane{n}_prep"
            ])
        valid_objs = moonraker.object_list()
        if valid_objs:
            objects = [o for o in objects if o in valid_objs]
        q = moonraker.query(objects)
        live_status = q.get("status", {}) if q.get("ok") else None

    for i, t in enumerate(tools):
        n = t.tool_number
        s = _ensure(n, i)
        mat = s["material"]
        present = s["present"]
        # temps + sensors: from Moonraker if live, else demo
        temp, target = 25, (MAT_TEMP.get(mat, 220) if present else 0)
        sensor_entry, sensor_toolhead = present, present
        # per-tool fans: part cooling (controllable) + hotend (auto by temp)
        part_fan, hotend_fan = (30 if present else 0), 0
        if live_status is not None:
            st = live_status
            ex = st.get("extruder" if n == 0 else f"extruder{n}", {})
            temp = round(ex.get("temperature", temp))
            target = round(ex.get("target", target))
            se = st.get(f"filament_switch_sensor T{n}_runout_entry", {})
            st_ = st.get(f"filament_switch_sensor T{n}_runout_toolhead", {})
            sensor_entry = se.get("filament_detected", False)
            sensor_toolhead = st_.get("filament_detected", False)
            pf = st.get(f"fan_generic T{n}_part_fan", {})
            hf = st.get(f"heater_fan T{n}_hotend_fan", {})
            part_fan = round(pf.get("speed", part_fan / 100) * 100)
            hotend_fan = round(hf.get("speed", 0) * 100)
        # PinkBox lane feeder mode (bt = via PinkBox, direct = manual feed).
        # This build's PinkBox has all 6 rails, so every tool is bt by default.
        feeder = "bt"
        bt_prep = False
        if live_status is not None:
            st = live_status
            prep = st.get(f"filament_switch_sensor bt_lane{n}_prep", {})
            if "filament_detected" in prep:
                bt_prep = prep["filament_detected"]
                feeder = "bt" if bt_prep else "direct"
        out[n] = {
            "material": mat, "color": s["color"], "present": present,
            "preset": s.get("preset", "Generic " + mat),
            "nozzle_min": s.get("nozzle_min", 0), "nozzle_max": s.get("nozzle_max", 0),
            "pa_profile": s.get("pa_profile", "Default"), "pa_k": s.get("pa_k", 0.02),
            "feeder": feeder, "bt_prep": bool(bt_prep),
            "temp": temp, "target": target,
            "print_temp": MAT_TEMP.get(mat, 220),
            "sensor_entry": bool(sensor_entry),
            "sensor_toolhead": bool(sensor_toolhead),
            "part_fan": part_fan, "hotend_fan": hotend_fan,
            # a tool is "problem" if loaded-but-no-filament-at-sensors, or empty
            "problem": (not present) or (present and not sensor_toolhead),
        }
    return out


def set_loaded(tool: int, material: str | None = None, color: str | None = None,
               present: bool | None = None):
    s = _STATE.setdefault(tool, {"material": "PLA", "color": "#888", "present": False})
    if material is not None:
        s["material"] = material.upper()
    if color is not None:
        s["color"] = color
    if present is not None:
        s["present"] = present
    _save_state()


def actions(tool: int, material: str = "PLA") -> dict:
    """The macro each Bambu-style button maps to, for a given tool/material."""
    mat = (material or "PLA").upper()
    return {
        "load":    f"FILAMENT_LOAD_MODE TOOL={tool} MATERIAL={mat}",
        "unload":  f"UNLOAD_T{tool}",
        "purge":   "FILAMENT_LOAD_PURGE_MORE",
        "confirm": "FILAMENT_LOAD_CONFIRM",
        "cancel":  "FILAMENT_LOAD_CANCEL",
    }


def pinkbox_present() -> bool:
    """Whether the PinkBox (BoxTurtle on a separate BTT Octopus board) is connected.

    PinkBox runs on its own MCU `[mcu octopus]`. It is "present" only if that MCU
    is actually enumerated by Klipper — i.e. the Octopus is plugged in AND
    boxturtle.cfg is included. If the board is unplugged or the config isn't
    loaded, the `mcu octopus` object is absent → not present.

    Note: the previous version checked whether a filament_switch_sensor was
    *defined* in config, which stays true even when nothing is physically
    connected — that made it always report "connected". Querying the MCU itself
    reflects real presence.
    """
    if not moonraker.available():
        return False                      # Report False (disconnected) if state cannot be verified
    q = moonraker.query(["mcu octopus"])
    return bool(q.get("ok") and
                q.get("status", {}).get("mcu octopus") is not None)


def configure(tool: int, preset: str | None = None, color: str | None = None,
              nozzle_min=None, nozzle_max=None, pa_profile=None, pa_k=None) -> dict:
    """Bambu-style material settings from the slot's gear icon."""
    s = _STATE.setdefault(tool, {"material": "PLA", "color": "#888", "present": True})
    if preset is not None:
        s["preset"] = preset
        p = filament_db.lookup(preset)
        if p:
            s["material"] = p["type"].split("-")[0]  # short label for tile
    if color is not None:
        s["color"] = color
    if nozzle_min is not None:
        s["nozzle_min"] = int(nozzle_min)
    if nozzle_max is not None:
        s["nozzle_max"] = int(nozzle_max)
    if pa_profile is not None:
        s["pa_profile"] = pa_profile
    if pa_k is not None:
        s["pa_k"] = float(pa_k)
    _save_state()
    return {"ok": True, "tool": tool, **{k: s.get(k) for k in
            ("preset", "material", "color", "nozzle_min", "nozzle_max", "pa_profile", "pa_k")}}


def run(tool: int, action: str, material: str = "PLA") -> dict:
    cmds = actions(tool, material)
    if action not in cmds:
        return {"ok": False, "detail": f"unknown action {action}"}
    cmd = cmds[action]
    # reflect into AMS-slot state immediately (optimistic)
    if action == "load":
        set_loaded(tool, material=material, present=True)
    elif action == "unload":
        set_loaded(tool, present=False)
    sent, detail = False, "dry-run"
    if moonraker.available():
        r = moonraker.run_gcode(cmd)
        sent, detail = r["ok"], r["detail"]
    return {"ok": True, "command": cmd, "sent": sent, "detail": detail}
