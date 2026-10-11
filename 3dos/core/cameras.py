"""Camera stream configuration — read from cameras.json.

Fixed two-camera layout (Shuttle Cam + Chamber Cam). Edit `cameras.json` in the
`3dos/` root directory to update the stream `url` or `label`, then refresh the
browser.

Expected format:
  [
    {"id": "cam0", "label": "Shuttle Cam", "url": "http://<pi>:8080/?action=stream"},
    {"id": "cam1", "label": "Chamber Cam", "url": "http://<pi>:8081/?action=stream"}
  ]
"""
from __future__ import annotations

import json
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "cameras.json")

DEFAULTS = [
    {"id": "cam0", "label": "Shuttle Cam", "url": ""},
    {"id": "cam1", "label": "Chamber Cam", "url": ""},
]


def load() -> dict:
    if not os.path.exists(PATH):
        with open(PATH, "w") as f:
            json.dump(DEFAULTS, f, indent=2, ensure_ascii=False)
    try:
        with open(PATH) as f:
            cams = json.load(f)
        out = []
        for i, d in enumerate(DEFAULTS):
            c = cams[i] if i < len(cams) and isinstance(cams[i], dict) else {}
            out.append({
                "id": d["id"],
                "label": str(c.get("label") or d["label"]),
                "url": str(c.get("url") or "").strip(),
            })
        return {"cameras": out}
    except Exception:
        return {"cameras": DEFAULTS}
