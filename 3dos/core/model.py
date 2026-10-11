"""3DOS data model — multitool / StealthChanger / CAN board.

A deliberately small, JSON-serializable model. Everything the web UI and the
Klipper config generator need is captured here so a tool can be fully described
in one object and round-tripped to/from a T*.cfg file.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


# Known CAN-bus toolhead boards. pin_map values are the documented Klipper pin
# aliases for each board so the config generator can stay board-agnostic.
BOARD_PRESETS = {
    "SHT36": {
        "label": "Fly SHT36 V3 (CAN)",
        "bus": "can",
        "has_accel": True,        # onboard LIS2DW
        "pins": {
            "extruder_step": "gpio7", "extruder_dir": "gpio6", "extruder_enable": "gpio14",
            "extruder_uart": "gpio15", "heater": "gpio23", "thermistor": "gpio27",
            "probe": "gpio22", "hotend_fan": "gpio13", "part_fan": "gpio21",
            "led": "gpio26", "accel_cs": "gpio12",
        },
    },
    "EBB36": {
        "label": "BTT EBB36 V1.2 (CAN)",
        "bus": "can",
        "has_accel": True,        # onboard ADXL345
        "pins": {
            "extruder_step": "PD0", "extruder_dir": "PD1", "extruder_enable": "PD2",
            "extruder_uart": "PA15", "heater": "PB13", "thermistor": "PA3",
            "probe": "PB6", "hotend_fan": "PA1", "part_fan": "PA0",
            "led": "PD3", "accel_cs": "PB12",
        },
    },
    "EBB42": {
        "label": "BTT EBB42 V1.2 (CAN)",
        "bus": "can",
        "has_accel": True,
        "pins": {
            "extruder_step": "PD0", "extruder_dir": "PD1", "extruder_enable": "PD2",
            "extruder_uart": "PA15", "heater": "PB13", "thermistor": "PA3",
            "probe": "PB6", "hotend_fan": "PA1", "part_fan": "PA0",
            "led": "PD3", "accel_cs": "PB12",
        },
    },
}


@dataclass
class Extruder:
    rotation_distance: float = 47.088
    gear_ratio: str = "9:1"
    microsteps: int = 16
    full_steps_per_rotation: int = 200
    nozzle_diameter: float = 0.4
    filament_diameter: float = 1.75
    max_temp: int = 300
    min_extrude_temp: int = 170
    sensor_type: str = "ATC Semitec 104NT-4-R025H42G"
    run_current: float = 0.8
    pressure_advance: float = 0.04


@dataclass
class Dock:
    """StealthChanger dock geometry + motion paths (relative to park x/y/z)."""
    park_x: float = 0.0
    park_y: float = -11.0
    park_z: float = 296.96
    safe_y: float = 120.0
    close_y: float = 30.0
    fast_speed: int = 10000
    path_speed: int = 900
    pickup_path: list = field(default_factory=lambda: [
        {"z": -10, "y": 16}, {"z": -10, "y": 0},
        {"z": 0, "y": 0, "f": 0.5, "verify": 1},
        {"y": 5.5, "z": 0}, {"y": 9.5, "z": 2.5}, {"y": 9.5, "z": 4},
    ])
    dropoff_path: list = field(default_factory=lambda: [
        {"y": 9.5, "z": 4}, {"y": 9.5, "z": 2.5}, {"y": 5.5, "z": 1.5},
        {"z": 0, "y": 0, "f": 0.5}, {"z": -10, "y": 0}, {"z": -10, "y": 16},
    ])


@dataclass
class InputShaper:
    type_x: str = "ei"
    freq_x: float = 82.0
    type_y: str = "ei"
    freq_y: float = 61.8
    damping_x: float = 0.1
    damping_y: float = 0.1


@dataclass
class Offsets:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Tool:
    tool_number: int
    name: str
    board_type: str = "SHT36"
    canbus_uuid: str = ""
    mcu_alias: str = ""          # e.g. SHT0
    enabled: bool = True
    extruder: Extruder = field(default_factory=Extruder)
    dock: Dock = field(default_factory=Dock)
    offsets: Offsets = field(default_factory=Offsets)
    shaper: InputShaper = field(default_factory=InputShaper)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Tool":
        return Tool(
            tool_number=d["tool_number"],
            name=d.get("name", f"T{d['tool_number']}"),
            board_type=d.get("board_type", "SHT36"),
            canbus_uuid=d.get("canbus_uuid", ""),
            mcu_alias=d.get("mcu_alias", ""),
            enabled=d.get("enabled", True),
            extruder=Extruder(**d.get("extruder", {})),
            dock=Dock(**d.get("dock", {})),
            offsets=Offsets(**d.get("offsets", {})),
            shaper=InputShaper(**d.get("shaper", {})),
        )
