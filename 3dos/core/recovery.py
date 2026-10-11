"""MCU failure root-cause analysis + automatic one-shot recovery.

When a CAN toolboard drops out or Klipper enters shutdown, Klipper's default UI
only shows a raw `Lost communication with MCU 'SHT4'` message and halts. 3DOS
classifies the failure from the error text + a fresh CAN scan, recommends the fix,
and (optionally) fires the recovery itself: regenerate a safe-boot config that
drops any board still missing, then FIRMWARE_RESTART — automatically, once.

Diagnosis encodes the same knowledge as the printer's QUERY_CAN_STATUS macro
(tx_queue_len, UTOC/U2C 1 Mbit bandwidth, bus termination, dropped bytes).
"""
from __future__ import annotations

import re
from . import moonraker, health


# (regex on the Klipper/Moonraker error, cause id, human cause, recommended fix)
RULES = [
    (r"timer too close|Timer too close",
     "timing", "MCU timing exceeded (host CPU overload or CANbus latency)",
     "Verify CAN bitrate is 1Mbit, increase tx_queue_len (>=1024), check host load"),
    (r"Unable to connect|Lost communication|got EOF|No response",
     "comm_lost", "Lost communication with MCU (toolboard not responding)",
     "Check toolboard 24V power, CAN wiring & termination -> regenerate safe-boot and auto-restart"),
    (r"can.?bus.*(uuid).*not found|Unable to find canbus|canbus_uuid",
     "uuid_missing", "Configured CAN UUID not detected on bus",
     "Board disconnected or unpowered. Boot in N-1 safe mode excluding the offline tool"),
    (r"version mismatch|Firmware version|mcu .* version",
     "fw_mismatch", "MCU firmware version mismatch",
     "Reflash Klipper firmware on the affected board to match the host version — restart alone will not fix"),
    (r"tx_queue|queue overflow|bytes_retransmit|drop",
     "bus_overload", "CAN bus overload / retransmission buildup",
     "Increase tx_queue_len, verify 1Mbit bitrate, harness length, and 120-ohm termination"),
    (r"ADC out of range|adc",
     "thermal", "ADC out of range (thermistor open or shorted)",
     "Inspect thermistor wiring — hardware inspection required before restarting"),
    (r"shutdown|Shutdown",
     "shutdown", "MCU is in shutdown state",
     "Inspect klippy.log for root cause, then run FIRMWARE_RESTART"),
]


def diagnose(error_text: str, tools) -> dict:
    """Classify a failure and decide whether auto-restart is safe."""
    cause, human, fix = "unknown", "Unclassified MCU error", "Check klippy.log and run FIRMWARE_RESTART"
    for rx, cid, h, f in RULES:
        if re.search(rx, error_text or "", re.I):
            cause, human, fix = cid, h, f
            break

    # correlate with live board health
    scan = health.scan(tools)
    offline = [n for n, s in scan.items() if not s["online"]]

    # auto-restart is safe for comm/uuid/timing/overload; NOT for fw/thermal
    auto_safe = cause in ("comm_lost", "uuid_missing", "timing", "bus_overload",
                          "shutdown")
    return {
        "cause": cause, "cause_text": human, "recommended_fix": fix,
        "offline_tools": offline,
        "auto_restart_safe": auto_safe,
        "raw": (error_text or "")[:400],
    }


def recover(tools, error_text: str = "", execute: bool = False) -> dict:
    """Diagnose then (optionally) self-heal: drop missing boards + restart once."""
    dx = diagnose(error_text, tools)
    safe_cfg = health.generate_safe_boot(tools)
    actions = []

    if dx["offline_tools"]:
        actions.append(f"Regenerate safe-boot config excluding offline tools {dx['offline_tools']}")
    actions.append("FIRMWARE_RESTART")

    executed = False
    detail = "dry-run (proposal only)"
    if execute and dx["auto_restart_safe"] and moonraker.available():
        r = moonraker.run_gcode("FIRMWARE_RESTART")
        executed, detail = r["ok"], r["detail"]
    elif execute and not dx["auto_restart_safe"]:
        detail = "Auto-restart held — hardware inspection required first"

    return {"diagnosis": dx, "planned_actions": actions,
            "safe_boot_cfg": safe_cfg, "executed": executed, "detail": detail}
