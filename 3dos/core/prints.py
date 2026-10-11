"""Print history & statistics (Moonraker server/history) + per-tool usage accumulator."""
from __future__ import annotations
import json, os
from . import moonraker

TOOLSTAT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "tool_stats.json")

def history(limit=20) -> dict:
    r = moonraker.get_json(f"/server/history/list?limit={limit}&order=desc")
    if not r.get("ok"):
        return {"ok": False, "detail": r.get("detail"), "jobs": []}
    jobs = r["data"].get("jobs", []) if isinstance(r["data"], dict) else []
    return {"ok": True, "jobs": [{
        "filename": j.get("filename"), "status": j.get("status"),
        "print_duration": j.get("print_duration"),
        "filament_used": j.get("filament_used"),
        "start_time": j.get("start_time"), "end_time": j.get("end_time"),
    } for j in jobs]}

def totals() -> dict:
    r = moonraker.get_json("/server/history/totals")
    t = (r.get("data") or {}).get("job_totals", {}) if r.get("ok") else {}
    # Aggregate recent jobs to compute success rate percentage
    h = history(limit=200)
    jobs = h.get("jobs", [])
    done = sum(1 for j in jobs if j["status"] == "completed")
    n = len(jobs)
    return {"ok": True,
            "total_jobs": t.get("total_jobs"),
            "total_print_time": t.get("total_print_time"),   # seconds
            "total_filament": t.get("total_filament_used"),  # mm
            "longest_print": t.get("longest_print"),
            "success_rate": round(done / n * 100) if n else None,
            "sample": n}

def tool_stats() -> dict:
    """Per-tool usage accumulator (tracked by 3DOS since Moonraker does not split by tool)."""
    if os.path.exists(TOOLSTAT):
        try:
            with open(TOOLSTAT) as f: return {"ok": True, "tools": json.load(f)}
        except Exception: pass
    return {"ok": True, "tools": {}}

def record_tool(tool: int, seconds: float = 0, filament_mm: float = 0):
    """Called from toolchange.py / print completion hook to accumulate per-tool time & filament."""
    data = tool_stats()["tools"]
    k = str(tool)
    d = data.setdefault(k, {"active_s": 0, "filament_mm": 0, "changes": 0})
    d["active_s"] += seconds; d["filament_mm"] += filament_mm; d["changes"] += 1
    with open(TOOLSTAT, "w") as f: json.dump(data, f, indent=2)
