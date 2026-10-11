"""StealthChanger tool-change orchestration.

plan_toolchange() turns a (from_tool -> to_tool) request into the ordered list of
moves a StealthChanger dock performs: park the current tool along its dropoff
path, then pick the new tool along its pickup path. The same routine is used to:
  - render the dock animation in the web UI (return value = list of points), and
  - emit a real G-code program when execute=True (sent to Klipper via Moonraker).

This mirrors klipper-toolchanger-easy's pickup_gcode / dropoff_gcode so the
dry-run preview matches what the printer will actually do.
"""
from __future__ import annotations

from .model import Tool


def _path_moves(tool: Tool, path: list[dict], label: str) -> list[dict]:
    """Expand a relative dock path into absolute XYZ moves."""
    d = tool.dock
    moves = []
    for seg in path:
        y = d.park_y + float(seg.get("y", 0))
        z = d.park_z + float(seg.get("z", 0))
        speed = d.path_speed * float(seg.get("f", 1.0))
        moves.append({
            "x": round(d.park_x, 3), "y": round(y, 3), "z": round(z, 3),
            "f": int(speed), "verify": bool(seg.get("verify", 0)),
            "phase": label, "tool": tool.tool_number,
        })
    return moves


def plan_toolchange(from_tool: Tool | None, to_tool: Tool) -> dict:
    """Return a structured plan: list of moves + generated G-code."""
    moves: list[dict] = []

    if from_tool is not None and from_tool.tool_number != to_tool.tool_number:
        # approach current dock at safe height, then follow dropoff path
        d = from_tool.dock
        moves.append({"x": d.park_x, "y": d.safe_y, "z": d.park_z,
                      "f": d.fast_speed, "phase": "approach-dropoff",
                      "tool": from_tool.tool_number, "verify": False})
        moves += _path_moves(from_tool, d.dropoff_path, "dropoff")

    # approach new dock and follow pickup path
    d = to_tool.dock
    moves.append({"x": d.park_x, "y": d.safe_y, "z": d.park_z,
                  "f": d.fast_speed, "phase": "approach-pickup",
                  "tool": to_tool.tool_number, "verify": False})
    moves += _path_moves(to_tool, d.pickup_path, "pickup")

    gcode = _to_gcode(from_tool, to_tool, moves)
    return {
        "from": from_tool.tool_number if from_tool else None,
        "to": to_tool.tool_number,
        "move_count": len(moves),
        "moves": moves,
        "gcode": gcode,
    }


def _to_gcode(from_tool, to_tool, moves) -> str:
    lines = ["G90  ; absolute"]
    if from_tool and from_tool.tool_number != to_tool.tool_number:
        lines.append(f"; ---- park T{from_tool.tool_number} ----")
    lines.append(f"; ---- pick T{to_tool.tool_number} ----")
    for m in moves:
        verify = "  ; VERIFY tool detected" if m["verify"] else ""
        lines.append(f"G0 X{m['x']} Y{m['y']} Z{m['z']} F{m['f']}{verify}")
    lines.append(f"SET_GCODE_OFFSET X={to_tool.offsets.x} Y={to_tool.offsets.y} "
                 f"Z={to_tool.offsets.z}")
    lines.append(f"; T{to_tool.tool_number} active")
    return "\n".join(lines)
