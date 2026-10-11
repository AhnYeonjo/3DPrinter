"""G-code file listing, metadata inspection, and print start via Moonraker."""
from __future__ import annotations
import urllib.parse
from . import moonraker

def files() -> dict:
    """List files in the gcodes root directory sorted by modification time (newest first)."""
    r = moonraker.get_json("/server/files/list?root=gcodes")
    if not r.get("ok"):
        return {"ok": False, "detail": r.get("detail"), "files": []}
    items = r["data"] if isinstance(r["data"], list) else r["data"].get("files", [])
    items.sort(key=lambda f: f.get("modified", 0), reverse=True)
    return {"ok": True, "files": [
        {"path": f["path"], "size": f.get("size", 0),
         "modified": f.get("modified", 0)} for f in items]}

def meta(filename: str) -> dict:
    """Fetch thumbnail, estimated time, filament usage, and multi-tool mapping metadata."""
    q = urllib.parse.quote(filename)
    r = moonraker.get_json(f"/server/files/metadata?filename={q}")
    if not r.get("ok"):
        return {"ok": False, "detail": r.get("detail")}
    d = r["data"]
    # Convert relative thumbnail paths to HTTP URLs relative to the file's directory
    import posixpath
    base = posixpath.dirname(filename)
    thumbs = []
    for t in d.get("thumbnails", []):
        rel = posixpath.normpath(posixpath.join(base, t["relative_path"]))
        thumbs.append({"w": t.get("width"), "h": t.get("height"),
                       "url": f"/server/files/gcodes/{urllib.parse.quote(rel)}"})
    thumbs.sort(key=lambda t: t["w"] or 0, reverse=True)   # Largest thumbnail first
    return {"ok": True,
            "estimated_time": d.get("estimated_time"),      # seconds
            "filament_total_mm": d.get("filament_total"),
            "filament_weight_g": d.get("filament_weight_total"),
            "layer_count": d.get("layer_count"),
            "object_height": d.get("object_height"),
            "slicer": d.get("slicer"),
            # Multi-tool: populated when exported by slicer; otherwise empty list
            "tools": d.get("referenced_tools", []),
            "filament_names": d.get("filament_name", "").split(";") if d.get("filament_name") else [],
            "thumbnails": thumbs}

def start(filename: str) -> dict:
    """Start printing the selected G-code file."""
    if not moonraker.available():
        return {"ok": False, "detail": "dry-run"}
    q = urllib.parse.quote(filename)
    try:
        moonraker._post(f"/printer/print/start?filename={q}", {})
        return {"ok": True, "detail": f"Print started: {filename}"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}
