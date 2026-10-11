"""Maintenance tracking — Nevermore filter life + cumulative runtimes.

3DOS keeps two accumulators that Klipper/Moonraker don't track per-component:
  - nevermore_runtime_s : seconds the Nevermore (chamber_filter_fan) has run.
                          A background sampler adds elapsed time whenever the
                          fan speed > 0. Used against the filter interval to
                          show "filter life remaining" and a replace reminder.
  - total_print_s       : total printing time. Live builds read Moonraker's
                          /server/history/totals; otherwise the local accumulator.

tick() is called periodically by the server with the current Nevermore speed and
print state to advance the accumulators. reset_filter() zeroes the filter clock
when the user installs a new Nevermore filter.
"""
from __future__ import annotations

import json
import os
import time
from . import moonraker

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "maintenance.json")

_S = None
_last_tick = None


def _load():
    global _S
    if _S is None:
        _S = {
            "nevermore_runtime_s": 0,
            "total_print_s": 0,
            "filter_interval_h": 50,     # replace every N hours of filter use
            "filter_installed_at": time.time(),
        }
        if os.path.exists(PATH):
            try:
                with open(PATH) as f:
                    _S.update(json.load(f))
            except Exception:
                pass
    return _S


def _save():
    with open(PATH, "w") as f:
        json.dump(_S, f, indent=2)


def tick(nevermore_speed_pct: float, printing: bool):
    """Advance accumulators since the last call."""
    global _last_tick
    s = _load()
    now = time.time()
    if _last_tick is not None:
        dt = now - _last_tick
        if nevermore_speed_pct and nevermore_speed_pct > 0:
            s["nevermore_runtime_s"] += dt
        if printing:
            s["total_print_s"] += dt
        _save()
    _last_tick = now


def reset_filter() -> dict:
    s = _load()
    s["nevermore_runtime_s"] = 0
    s["filter_installed_at"] = time.time()
    _save()
    return state()


def set_interval(hours: float) -> dict:
    s = _load()
    s["filter_interval_h"] = float(hours)
    _save()
    return state()


def _fmt(sec: float) -> str:
    sec = int(sec)
    h, m = sec // 3600, (sec % 3600) // 60
    return f"{h}h {m}m" if h else f"{m}m"


def state() -> dict:
    s = _load()
    total = s["total_print_s"]
    # prefer Moonraker history total when available
    if moonraker.available():
        try:
            import urllib.request
            url = f"{moonraker.MOONRAKER_URL}/server/history/totals"
            with urllib.request.urlopen(url, timeout=3) as r:
                j = json.loads(r.read().decode())
            total = j.get("result", {}).get("job_totals", {}).get("total_print_time", total)
        except Exception:
            pass
    nev = s["nevermore_runtime_s"]
    interval_s = s["filter_interval_h"] * 3600
    remain = max(0, interval_s - nev)
    return {
        "nevermore_runtime_s": int(nev), "nevermore_runtime": _fmt(nev),
        "total_print_s": int(total), "total_print": _fmt(total),
        "filter_interval_h": s["filter_interval_h"],
        "filter_remaining": _fmt(remain),
        "filter_pct": round(100 * nev / interval_s) if interval_s else 0,
        "filter_due": nev >= interval_s,
    }
