"""Toolboard health + graceful boot.

Today a single CAN toolboard that fails to enumerate stops Klipper from starting
at all — you hunt down the bad board and FIRMWARE_RESTART. 3DOS flips that around:

  1. Scan the CAN bus for present UUIDs BEFORE Klipper starts.
  2. Compare against the configured tools.
  3. Generate a printer.cfg that *includes only the boards that are present*, and
     comments out the missing ones (and their [tool] blocks).
  4. Klipper boots with the surviving N-1 tools instead of erroring out.

The operator still gets one fast, automatic restart when the board set changes —
but never the manual "which board is dead, fix, restart" loop, and never a dead
printer because tool 4 didn't wake up.

Real hardware scan uses Klipper's canbus_query (`~/klippy-env/bin/python
lib/canboot/flash_can.py -q` or `klipper/scripts/canbus_query.py canX`). Here the
scan is pluggable: set_online() injects a result so the PoC is demonstrable
without hardware; on a Pi, replace _scan_can() with the real query.
"""
from __future__ import annotations

import glob
import os
import subprocess


# In-memory health snapshot: uuid -> online?  (None = unknown/never scanned)
_ONLINE: dict[str, bool] = {}


def _canbus_scripts() -> list[str]:
    """Locate canbus_query.py regardless of the active Linux user home (esahn/pi, etc.)."""
    cands = []
    home = os.path.expanduser("~")          # Resolves to /home/esahn when running under User=esahn
    for base in (home, "/home/pi", "/root"):
        cands.append(os.path.join(base, "klipper/scripts/canbus_query.py"))
    cands += glob.glob("/home/*/klipper/scripts/canbus_query.py")
    cands += glob.glob("/usr/share/klipper/scripts/canbus_query.py")
    out, seen = [], set()
    for c in cands:
        if c not in seen and os.path.isfile(c):
            seen.add(c); out.append(c)
    return out


def _python_bin() -> str:
    """Prefer Klipper virtualenv python; fall back to system python3."""
    for p in (os.path.expanduser("~/klippy-env/bin/python"),
              "/home/pi/klippy-env/bin/python"):
        if os.path.isfile(p):
            return p
    for p in glob.glob("/home/*/klippy-env/bin/python"):
        return p
    return "python3"


def _scan_can(interface: str = "can0") -> set[str]:
    """Return UUIDs seen on the bus. Best-effort; empty set if tool unavailable."""
    py = _python_bin()
    for script in _canbus_scripts():
        try:
            out = subprocess.run([py, script, interface],
                                 capture_output=True, text=True, timeout=8)
            uuids = set()
            for line in (out.stdout or "").splitlines():
                if "canbus_uuid=" in line:
                    uuids.add(line.split("canbus_uuid=")[1].split(",")[0].strip())
            if uuids:
                return uuids
        except Exception:
            continue
    return set()


def scan(tools, interface: str = "can0") -> dict:
    """Scan and update health for the given tools. Returns per-tool status."""
    seen = _scan_can(interface)
    result = {}
    for t in tools:
        uuid = t.canbus_uuid
        # if a real scan returned data, trust it; else fall back to injected state
        if seen:
            online = uuid in seen
            _ONLINE[uuid] = online
        else:
            online = _ONLINE.get(uuid, True)  # optimistic default until told otherwise
        result[t.tool_number] = {"uuid": uuid, "online": online,
                                 "board": t.board_type}
    return result


def set_online(uuid: str, online: bool):
    """Inject health state (PoC / simulation / manual override)."""
    _ONLINE[uuid] = online


def status(tools) -> dict:
    out = {}
    for t in tools:
        out[t.tool_number] = {"uuid": t.canbus_uuid,
                              "online": _ONLINE.get(t.canbus_uuid, True),
                              "board": t.board_type}
    return out


def generate_safe_boot(tools) -> str:
    """printer.cfg tool-include block with offline boards commented out."""
    lines = ["#  ===== 3DOS safe-boot tool includes =====",
             "#  Offline toolboards are commented out so the printer still starts.",
             "#  Re-run scan + regenerate when a board comes back.\n"]
    online_n = []
    for t in tools:
        ok = _ONLINE.get(t.canbus_uuid, True)
        if ok:
            lines.append(f"[include toolchanger/tools/{t.name}.cfg]   "
                         f"# {t.board_type} {t.canbus_uuid} — ONLINE")
            online_n.append(t.tool_number)
        else:
            lines.append(f"#[include toolchanger/tools/{t.name}.cfg]  "
                         f"# {t.board_type} {t.canbus_uuid} — OFFLINE, skipped")
    lines.append(f"\n#  Booting with tools: {online_n}")
    return "\n".join(lines)
