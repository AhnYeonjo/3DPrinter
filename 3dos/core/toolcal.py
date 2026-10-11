"""Automated per-tool X/Y/Z offset measurement via sexbolt contact probing -> save to CALS."""
from __future__ import annotations
from . import moonraker

def _gcode(script: str, timeout=300) -> dict:
    """Extended timeout helper for multi-pass contact probing."""
    if not moonraker.available():
        return {"ok": False, "detail": "dry-run"}
    return moonraker.run_gcode(script, timeout=timeout)

def prepare() -> dict:
    """Home axes and locate sexbolt reference sensor with T0 once at wizard start."""
    r = _gcode("G28\nSELECT_TOOL T=0\nCLEAN_NOZZLE\nTOOL_LOCATE_SENSOR")
    return {"ok": r.get("ok"), "detail": r.get("detail")}

def calibrate_tool(n: int, cals) -> dict:
    """Pick up tool n, probe the sexbolt sensor, and store the measured XYZ offset in CALS."""
    if not moonraker.available():
        return {"ok": False, "detail": "dry-run"}
    _gcode(f"SELECT_TOOL T={n}\nCLEAN_NOZZLE")
    r = _gcode(f"TOOL_CALIBRATE_TOOL_OFFSET")
    if not r.get("ok"):
        return {"ok": False, "detail": r.get("detail"), "tool": n}
    # Read measured results from gcode_move homing_origin or tools_calibrate status
    q = moonraker.query(["gcode_move", "tools_calibrate"])
    st = q.get("status", {}) if q.get("ok") else {}
    ho = st.get("gcode_move", {}).get("homing_origin", [0, 0, 0, 0])
    tc = st.get("tools_calibrate", {})
    ox, oy, oz = tc.get("last_x_result", ho[0]), tc.get("last_y_result", ho[1]), tc.get("last_z_result", ho[2])
    # Save to CALS (zero-restart)
    cal = cals.get(n)
    cal.offset_x, cal.offset_y, cal.offset_z = round(ox, 4), round(oy, 4), round(oz, 4)
    cals.save(cal, when="tool-offset wizard")
    return {"ok": True, "tool": n, "offset": {"x": cal.offset_x, "y": cal.offset_y, "z": cal.offset_z}}

def finish() -> dict:
    return {"ok": bool(_gcode("UNSELECT_TOOL\nG28 Z").get("ok"))}
