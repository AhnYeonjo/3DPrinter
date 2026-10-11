"""Thin Moonraker client.

3DOS speaks to the printer through Moonraker's HTTP API (same surface OrcaSlicer
already targets). In the PoC this is optional: if MOONRAKER_URL is unset or
unreachable, the server stays in dry-run mode and tool-change plans are returned
without being executed. Standard library only — no `requests` dependency.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
import urllib.parse

MOONRAKER_URL = os.environ.get("MOONRAKER_URL", "").rstrip("/")


def available() -> bool:
    return bool(MOONRAKER_URL)


def _post(path: str, payload: dict, timeout=5):
    url = f"{MOONRAKER_URL}{path}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def run_gcode(script: str) -> dict:
    """Send a G-code script to the printer. Returns {ok, detail}."""
    if not available():
        return {"ok": False, "detail": "MOONRAKER_URL not configured (dry-run)"}
    try:
        _post("/printer/gcode/script", {"script": script})
        return {"ok": True, "detail": "sent"}
    except (urllib.error.URLError, OSError) as e:
        return {"ok": False, "detail": str(e)}


def query(objects: list[str], timeout=3) -> dict:
    """Generic printer.objects.query for an arbitrary object list.
    Returns {ok, status} where status maps object name -> fields."""
    if not available():
        return {"ok": False, "detail": "dry-run"}
    try:
        q = "&".join(urllib.parse.quote(o) for o in objects)
        url = f"{MOONRAKER_URL}/printer/objects/query?{q}"
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        return {"ok": True, "status": data.get("result", {}).get("status", {})}
    except (urllib.error.URLError, OSError) as e:
        return {"ok": False, "detail": str(e)}


_OBJECT_LIST_CACHE = None
def object_list(timeout=3) -> set[str]:
    """Fetch the list of valid printer objects, cached indefinitely for the process."""
    global _OBJECT_LIST_CACHE
    if not available():
        return set()
    if _OBJECT_LIST_CACHE is not None:
        return _OBJECT_LIST_CACHE
    try:
        url = f"{MOONRAKER_URL}/printer/objects/list"
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        _OBJECT_LIST_CACHE = set(data.get("result", {}).get("objects", []))
        return _OBJECT_LIST_CACHE
    except (urllib.error.URLError, OSError):
        return set()


def printer_status(timeout=3) -> dict:
    if not available():
        return {"ok": False, "detail": "dry-run", "state": "offline"}
    try:
        url = (f"{MOONRAKER_URL}/printer/objects/query"
               "?print_stats&toolhead&heater_bed&virtual_sdcard&extruder&display_status")
        with urllib.request.urlopen(url, timeout=timeout) as r:
            raw = json.loads(r.read().decode())
            return {"ok": True, "data": {"status": raw.get("result", {}).get("status", {})}}
    except (urllib.error.URLError, OSError) as e:
        return {"ok": False, "detail": str(e), "state": "offline"}


def get_console(count: int = 100, timeout=3) -> dict:
    if not available():
        return {"ok": False, "detail": "dry-run", "result": {"gcode_store": []}}
    try:
        url = f"{MOONRAKER_URL}/server/gcode_store?count={count}"
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return {"ok": True, "data": json.loads(r.read().decode())}
    except (urllib.error.URLError, OSError) as e:
        return {"ok": False, "detail": str(e), "result": {"gcode_store": []}}
