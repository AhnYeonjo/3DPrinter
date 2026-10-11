"""In-memory tool store, seeded from existing T*.cfg when available.

The PoC keeps state in memory + a JSON snapshot so it runs with zero database.
On startup it tries to adopt the printer's real configuration by importing
T0.cfg..Tn.cfg from CONFIG_DIR; if none are found it falls back to a 6-tool
SHT36 demo set.
"""
from __future__ import annotations

import json
import os
from .model import Tool, Dock, Extruder, Offsets, InputShaper
from .klipper import import_tool_cfg

CONFIG_DIR = os.environ.get("KLIPPER_CONFIG_DIR", os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
SNAPSHOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "tools.snapshot.json")


class ToolStore:
    def __init__(self):
        self.tools: dict[int, Tool] = {}
        self.active: int | None = None
        self.load()

    # ---- persistence ----
    def load(self):
        newer = False
        snap_mtime = os.path.getmtime(SNAPSHOT) if os.path.exists(SNAPSHOT) else 0
        
        for n in range(12):
            p = os.path.join(CONFIG_DIR, f"T{n}.cfg")
            if os.path.exists(p) and os.path.getmtime(p) > snap_mtime:
                newer = True
                break

        if os.path.exists(SNAPSHOT) and not newer:
            self._load_snapshot()
        elif not self._import_from_klipper():
            self._seed_demo()
        elif newer:
            self.save()

    def save(self):
        with open(SNAPSHOT, "w") as f:
            json.dump({"active": self.active,
                       "tools": [t.to_dict() for t in self.sorted()]}, f, indent=2)

    def _load_snapshot(self):
        with open(SNAPSHOT) as f:
            data = json.load(f)
        self.active = data.get("active")
        for d in data["tools"]:
            t = Tool.from_dict(d)
            self.tools[t.tool_number] = t

    def _import_from_klipper(self) -> bool:
        found = False
        for n in range(0, 12):
            path = os.path.join(CONFIG_DIR, f"T{n}.cfg")
            if os.path.exists(path):
                with open(path, encoding="utf-8", errors="ignore") as f:
                    self.tools[n] = import_tool_cfg(f.read(), n)
                found = True
        if found:
            self.active = min(self.tools)
        return found

    def _seed_demo(self):
        parks = [15.5, 77.5, 139.5, 201.5, 263.5]
        for n in range(5):
            self.tools[n] = Tool(
                tool_number=n, name=f"T{n}", board_type="SHT36",
                canbus_uuid=f"demo{n:08x}", mcu_alias=f"SHT{n}",
                dock=Dock(park_x=parks[n], park_y=-11.0, park_z=296.96),
                offsets=Offsets(), extruder=Extruder(), shaper=InputShaper(),
            )
        self.active = 0

    # ---- queries / mutations ----
    def sorted(self) -> list[Tool]:
        return [self.tools[k] for k in sorted(self.tools)]

    def get(self, n: int) -> Tool | None:
        return self.tools.get(n)

    def upsert(self, t: Tool):
        self.tools[t.tool_number] = t
        self.save()

    def delete(self, n: int):
        self.tools.pop(n, None)
        if self.active == n:
            self.active = min(self.tools) if self.tools else None
        self.save()

    def next_number(self) -> int:
        n = 0
        while n in self.tools:
            n += 1
        return n

    def set_active(self, n: int):
        if n in self.tools:
            self.active = n
            self.save()
