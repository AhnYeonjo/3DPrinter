"""No-restart calibration layer.

The whole point of 3DOS: calibration is the *source of truth here*, in a 3DOS-owned
JSON store — NOT in printer.cfg. Klipper's SAVE_CONFIG forces a restart only because
it rewrites the config file. But the values it would write are all applicable at
runtime via plain G-code:

    gcode offset (X/Y/Z)  -> SET_GCODE_OFFSET
    pressure advance      -> SET_PRESSURE_ADVANCE
    input shaper          -> SET_INPUT_SHAPER
    probe / tool Z         -> folded into gcode Z offset

So 3DOS saves instantly (write JSON), and *applies* instantly (emit G-code). On
printer connect and on every tool change, 3DOS re-pushes the stored calibration.
No FIRMWARE_RESTART, no SAVE_CONFIG, ever — for these values.

PID is the lone exception: Klipper has no runtime PID setter, so a PID change is
the one calibration that still needs a single config write + fast restart. Handled
separately and flagged in needs_restart().
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field

STORE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "calibration.json")


@dataclass
class Calibration:
    tool_number: int
    # hot-applicable (no restart)
    offset_x: float = 0.0
    offset_y: float = 0.0
    offset_z: float = 0.0
    pressure_advance: float = 0.04
    shaper_type_x: str = "ei"
    shaper_freq_x: float = 82.0
    shaper_damping_x: float = 0.1
    shaper_type_y: str = "ei"
    shaper_freq_y: float = 61.8
    shaper_damping_y: float = 0.1
    # cold (needs one restart) — kept for completeness
    pid_kp: float | None = None
    pid_ki: float | None = None
    pid_kd: float | None = None
    updated_at: str = ""

    def extruder_name(self) -> str:
        return "extruder" if self.tool_number == 0 else f"extruder{self.tool_number}"

    def apply_gcode(self) -> list[str]:
        """Runtime commands that apply this calibration with NO restart."""
        ex = self.extruder_name()
        return [
            f"SET_GCODE_OFFSET X={self.offset_x} Y={self.offset_y} Z={self.offset_z}",
            f"SET_PRESSURE_ADVANCE EXTRUDER={ex} ADVANCE={self.pressure_advance}",
            (f"SET_INPUT_SHAPER "
             f"SHAPER_TYPE_X={self.shaper_type_x} SHAPER_FREQ_X={self.shaper_freq_x} "
             f"DAMPING_RATIO_X={self.shaper_damping_x} "
             f"SHAPER_TYPE_Y={self.shaper_type_y} SHAPER_FREQ_Y={self.shaper_freq_y} "
             f"DAMPING_RATIO_Y={self.shaper_damping_y}"),
        ]

    def needs_restart(self) -> bool:
        """True only if a cold value (PID) is set — everything else is hot."""
        return any(v is not None for v in (self.pid_kp, self.pid_ki, self.pid_kd))


class CalibrationStore:
    def __init__(self):
        self.cals: dict[int, Calibration] = {}
        self._load()

    def _load(self):
        if os.path.exists(STORE_PATH):
            with open(STORE_PATH) as f:
                for d in json.load(f).get("calibrations", []):
                    self.cals[d["tool_number"]] = Calibration(**d)

    def _save(self):
        with open(STORE_PATH, "w") as f:
            json.dump({"calibrations": [asdict(c) for c in self.cals.values()]},
                      f, indent=2)

    def get(self, n: int) -> Calibration:
        return self.cals.get(n) or Calibration(tool_number=n)

    def seed_from_tool(self, tool):
        """Initialize a tool's calibration from its imported cfg values (once)."""
        if tool.tool_number in self.cals:
            return
        self.cals[tool.tool_number] = Calibration(
            tool_number=tool.tool_number,
            offset_x=tool.offsets.x, offset_y=tool.offsets.y, offset_z=tool.offsets.z,
            pressure_advance=tool.extruder.pressure_advance,
            shaper_type_x=tool.shaper.type_x, shaper_freq_x=tool.shaper.freq_x,
            shaper_damping_x=tool.shaper.damping_x,
            shaper_type_y=tool.shaper.type_y, shaper_freq_y=tool.shaper.freq_y,
            shaper_damping_y=tool.shaper.damping_y,
        )

    def save(self, cal: Calibration, when: str = "") -> Calibration:
        cal.updated_at = when
        self.cals[cal.tool_number] = cal
        self._save()
        return cal
