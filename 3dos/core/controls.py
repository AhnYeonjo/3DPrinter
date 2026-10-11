"""Machine controls — bed/chamber temps, Nevermore filter, print speed.

State is read live from Moonraker (dry-run returns demo values matching the
device screenshot). Setters build the correct Klipper command for THIS build's
object names (discovered from the user's printer.cfg):
    Nevermore air filter  -> fan_generic chamber_filter_fan
    chamber temperature    -> temperature_fan chamber
    bed                    -> heater_bed
    print speed            -> M220 (gcode_move.speed_factor)
    per-tool part fan      -> fan_generic T<n>_part_fan
"""
from __future__ import annotations

from . import moonraker

NEVERMORE_FAN = "chamber_filter_fan"
CHAMBER_FAN = "chamber"

# selectable print-speed presets (%) — applied for real via M220
SPEED_PRESETS = [50, 100, 125, 150, 200]


def state() -> dict:
    """bed/chamber temps, nevermore speed %, print speed %."""
    if not moonraker.available():
        return {
            "live": False,
            "bed": {"temp": 28, "target": 0},
            "chamber": {"temp": 30, "target": 0},
            "nevermore": {"speed": 0},
            "speed_factor": 100,
            "presets": SPEED_PRESETS,
        }
    q = moonraker.query([
        "heater_bed", f"temperature_fan {CHAMBER_FAN}",
        f"fan_generic {NEVERMORE_FAN}", "gcode_move",
    ])
    if not q.get("ok"):
        return {"live": False, "detail": q.get("detail"), "presets": SPEED_PRESETS}
    s = q["status"]
    bed = s.get("heater_bed", {})
    cha = s.get(f"temperature_fan {CHAMBER_FAN}", {})
    nev = s.get(f"fan_generic {NEVERMORE_FAN}", {})
    gm = s.get("gcode_move", {})
    return {
        "live": True,
        "bed": {"temp": round(bed.get("temperature", 0)), "target": round(bed.get("target", 0))},
        "chamber": {"temp": round(cha.get("temperature", 0)), "target": round(cha.get("target", 0))},
        "nevermore": {"speed": round(nev.get("speed", 0) * 100)},
        "speed_factor": round(gm.get("speed_factor", 1.0) * 100),
        "presets": SPEED_PRESETS,
    }


def command(what: str, value: float, tool: int | None = None) -> str:
    v = float(value)
    if what == "speed":
        return f"M220 S{int(v)}"
    if what == "nevermore":
        return f"SET_FAN_SPEED FAN={NEVERMORE_FAN} SPEED={max(0,min(1,v/100)):.2f}"
    if what == "bed":
        return f"M140 S{int(v)}"
    if what == "chamber":
        return f"SET_TEMPERATURE_FAN_TARGET TEMPERATURE_FAN={CHAMBER_FAN} TARGET={int(v)}"
    if what == "partfan":
        return f"SET_FAN_SPEED FAN=T{tool}_part_fan SPEED={max(0,min(1,v/100)):.2f}"
    if what == "nozzle":
        ex = "extruder" if tool == 0 else f"extruder{tool}"
        return f"SET_HEATER_TEMPERATURE HEATER={ex} TARGET={int(v)}"
    raise ValueError(f"unknown control {what}")


def apply(what: str, value: float, tool: int | None = None) -> dict:
    cmd = command(what, value, tool)
    if moonraker.available():
        r = moonraker.run_gcode(cmd)
        return {"ok": r["ok"], "command": cmd, "sent": r["ok"], "detail": r["detail"]}
    return {"ok": True, "command": cmd, "sent": False, "detail": "dry-run"}
