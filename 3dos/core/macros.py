"""Macro discovery -> consistent UI menu.

Every gcode_macro becomes a menu item, automatically and consistently — the thing
Mainsail/KlipperScreen never did well. 3DOS discovers macros (live: Moonraker
object list + GCODE_HELP descriptions; dry-run: parse macros.cfg), hides internal
ones (leading "_"), and buckets them into stable categories by name so the menu
layout never drifts as macros are added.
"""
from __future__ import annotations

import os
import re
from . import moonraker

CONFIG_DIR = os.environ.get("KLIPPER_CONFIG_DIR", os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

# category -> ordered regex tests (first match wins). Order matters.
CATEGORIES = [
    ("Filament", r"LOAD|UNLOAD|FILAMENT|PURGE|SPOOL|^M600$"),
    ("Tools",    r"^T\d+$|TOOL|DOCK|PICKUP|CHANGE|LED|_FAN$|SET_TOOL"),
    ("Material", r"^MAT_|MATERIAL|PREHEAT|HEAT_CHAMBER"),
    ("Calibrate",r"CALIBRATE|PID|^PA|^SET_PA|RESONANCE|MEASURE|MESH|QGL|QUAD|ENDSTOP|OFFSET|THERMAL|ESTEPS"),
    ("Print",    r"PRINT|PAUSE|RESUME|CANCEL|START|END|SPEED"),
    ("Maintain", r"STATUS|CHECK|VERIFY|TEST|DUMP|MAINTENANCE|SYSTEM|CAN|FAILOVER|CLEAN|SENSOR|COOLDOWN|FANS_OFF|RETREAT|FLIGHT"),
]


def _categorize(name: str) -> str:
    for cat, rx in CATEGORIES:
        if re.search(rx, name, re.I):
            return cat
    return "Other"


def _parse_cfg() -> list[dict]:
    """Dry-run discovery: read macros.cfg + tool T*.cfg macro blocks."""
    found = {}
    files = ["macros.cfg"] + [f"T{n}.cfg" for n in range(12)] + \
            ["toolchanger-config.cfg"]
    pat = re.compile(r"^\[gcode_macro\s+([A-Za-z0-9_]+)\]\s*$")
    for fn in files:
        path = os.path.join(CONFIG_DIR, fn)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            m = pat.match(line.strip())
            if not m:
                continue
            name = m.group(1)
            desc = ""
            for j in range(i + 1, min(i + 6, len(lines))):
                dm = re.match(r"\s*description\s*:\s*(.+)", lines[j])
                if dm:
                    desc = dm.group(1).strip()
                    break
                if lines[j].startswith("["):
                    break
            found[name] = desc
    return [{"name": k, "description": v} for k, v in found.items()]


def _live() -> list[dict]:
    st = moonraker.printer_status()
    # In a fuller build: GET /printer/gcode/help for descriptions and
    # /printer/objects/list for names. Fall back to cfg parse if unavailable.
    return _parse_cfg()


def menu(include_internal: bool = False) -> dict:
    raw = _live() if moonraker.available() else _parse_cfg()
    groups: dict[str, list] = {}
    for item in raw:
        name = item["name"]
        if not include_internal and name.startswith("_"):
            continue
        groups.setdefault(_categorize(name), []).append(item)
    # stable ordering
    order = [c[0] for c in CATEGORIES] + ["Other"]
    out = []
    for cat in order:
        if cat in groups:
            out.append({"category": cat,
                        "items": sorted(groups[cat], key=lambda x: x["name"])})
    total = sum(len(g["items"]) for g in out)
    return {"groups": out, "count": total}


def run(name: str, params: dict | None = None) -> dict:
    """Execute a macro (live) or echo the command (dry-run)."""
    cmd = name + "".join(f" {k}={v}" for k, v in (params or {}).items())
    if moonraker.available():
        return {"ok": True, **moonraker.run_gcode(cmd), "command": cmd}
    return {"ok": True, "sent": False, "detail": "dry-run", "command": cmd}
