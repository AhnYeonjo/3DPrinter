"""Object skip — Klipper [exclude_object] (like Bambu's "skip objects").

This build already has [exclude_object], so each printed object is defined in the
G-code (EXCLUDE_OBJECT_DEFINE) and any one can be cancelled mid-print with
EXCLUDE_OBJECT NAME=<name>. Moonraker exposes the live state on the
`exclude_object` printer object: objects (name + center + polygon),
excluded_objects, current_object.

state()   -> bed size + objects + which are excluded + the one printing now
exclude() -> skip an object (EXCLUDE_OBJECT NAME=...)
"""
from __future__ import annotations

from . import moonraker

BED = 350  # Voron 2.4 350mm

# demo objects (dry-run) so the bed map is visible without a live print
_DEMO = [
    {"name": "front_left_bracket", "center": [90, 95],
     "polygon": [[60, 65], [120, 65], [120, 125], [60, 125]]},
    {"name": "front_right_gear", "center": [255, 95],
     "polygon": [[225, 65], [285, 65], [285, 125], [225, 125]]},
    {"name": "rear_left_clip", "center": [95, 255],
     "polygon": [[70, 225], [120, 225], [120, 285], [70, 285]]},
    {"name": "rear_right_mount", "center": [255, 258],
     "polygon": [[220, 225], [290, 225], [290, 290], [220, 290]]},
    {"name": "center_spacer", "center": [175, 178],
     "polygon": [[150, 158], [200, 158], [200, 198], [150, 198]]},
]


_EXCLUDED: set[str] = set()  # dry-run tracking (no Moonraker)


def state() -> dict:
    if not moonraker.available():
        return {"live": False, "bed": BED, "objects": _DEMO,
                "excluded": sorted(_EXCLUDED), "current": "center_spacer"}
    q = moonraker.query(["exclude_object"])
    if not q.get("ok"):
        return {"live": False, "bed": BED, "objects": [], "excluded": [],
                "current": None, "detail": q.get("detail")}
    eo = q["status"].get("exclude_object", {})
    return {
        "live": True, "bed": BED,
        "objects": eo.get("objects", []),
        "excluded": eo.get("excluded_objects", []),
        "current": eo.get("current_object"),
    }


def exclude(name: str, undo: bool = False) -> dict:
    cmd = (f"EXCLUDE_OBJECT NAME={name} RESET=1" if undo
           else f"EXCLUDE_OBJECT NAME={name}")
    if moonraker.available():
        r = moonraker.run_gcode(cmd)
        return {"ok": r["ok"], "command": cmd, "sent": r["ok"], "detail": r["detail"]}
    # dry-run: track locally so the bed map reflects the change
    _EXCLUDED.discard(name) if undo else _EXCLUDED.add(name)
    return {"ok": True, "command": cmd, "sent": False, "detail": "dry-run"}
