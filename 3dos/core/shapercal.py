"""Per-tool resonance measurement -> calibrate_shaper.py analysis -> save recommended shaper to CALS."""
from __future__ import annotations
import glob, os, re, subprocess, time
from . import moonraker

KLIPPER_PY = os.path.expanduser("~/klippy-env/bin/python")
KLIPPER_SCRIPT = os.path.expanduser("~/klipper/scripts/calibrate_shaper.py")
TMP = "/tmp"

def _newest_csv(axis: str, after: float) -> str | None:
    files = [f for f in glob.glob(f"{TMP}/resonances_{axis}*.csv") if os.path.getmtime(f) >= after]
    return max(files, key=os.path.getmtime) if files else None

def _analyze(csv_path: str) -> dict:
    """Run calibrate_shaper.py and parse 'Recommended shaper is X @ Y Hz'."""
    png = csv_path.replace(".csv", ".png")
    try:
        out = subprocess.run([KLIPPER_PY, KLIPPER_SCRIPT, csv_path, "-o", png],
                             capture_output=True, text=True, timeout=300).stdout
    except Exception as e:
        return {"ok": False, "detail": str(e)}
    m = re.search(r"[Rr]ecommended shaper.*?is\s+(\w+)\s*[@(]?\s*([\d.]+)\s*Hz", out)
    if not m:
        m = re.search(r"[Ff]itted shaper '(\w+)' frequency = ([\d.]+) Hz", out)
    if not m:
        return {"ok": False, "detail": "Failed to parse shaper analysis output", "raw": out[-400:]}
    return {"ok": True, "type": m.group(1), "freq": float(m.group(2)),
            "png": os.path.basename(png), "raw": out}

def measure_tool(n: int, cals) -> dict:
    if not moonraker.available():
        return {"ok": False, "detail": "dry-run"}
    t0 = time.time()
    r = moonraker.run_gcode(f"MEASURE_RESONANCE TOOL={n}", timeout=300)
    if not r.get("ok"):
        return {"ok": False, "detail": r.get("detail"), "tool": n}
    res = {"tool": n}
    for axis in ("x", "y"):
        csv = _newest_csv(axis, t0)
        if not csv:
            res[axis] = {"ok": False, "detail": f"Missing {axis} resonance CSV"}
            continue
        res[axis] = _analyze(csv)
    # Persist to CALS store
    cal = cals.get(n)
    if res.get("x", {}).get("ok"):
        cal.shaper_type_x, cal.shaper_freq_x = res["x"]["type"], round(res["x"]["freq"], 1)
    if res.get("y", {}).get("ok"):
        cal.shaper_type_y, cal.shaper_freq_y = res["y"]["type"], round(res["y"]["freq"], 1)
    cals.save(cal, when="shaper wizard")
    res["ok"] = True
    return res
