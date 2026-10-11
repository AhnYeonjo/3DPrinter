"""Filament preset database (Bambu-branded entries intentionally excluded).

Each preset resolves to a base material type that carries default nozzle temp
range (min/max) and a starting pressure-advance K. The material-settings dialog
lists these and pre-fills temps/PA when a preset is chosen.
"""
from __future__ import annotations

# base type -> (nozzle_min, nozzle_max, pa_k)
TYPE_DEFAULTS = {
    "PLA":     (190, 230, 0.020),
    "PLA-CF":  (210, 240, 0.025),
    "PLA-HS":  (200, 240, 0.018),
    "PETG":    (230, 260, 0.030),
    "PETG-CF": (240, 270, 0.032),
    "ABS":     (240, 280, 0.020),
    "ABS-GF":  (250, 280, 0.022),
    "ASA":     (240, 280, 0.022),
    "ASA-CF":  (250, 285, 0.024),
    "TPU":     (210, 240, 0.050),
    "PC":      (260, 300, 0.040),
    "PA":      (260, 300, 0.045),
    "PA-CF":   (260, 300, 0.045),
    "PET-CF":  (260, 290, 0.035),
    "HIPS":    (230, 260, 0.025),
    "PVA":     (190, 220, 0.030),
}

# (preset name, base type) — NO Bambu products
_PRESETS = [
    ("Generic PLA", "PLA"), ("Generic PLA Silk", "PLA"),
    ("Generic PLA Matte", "PLA"), ("Generic PLA High Speed", "PLA-HS"),
    ("Generic PLA-CF", "PLA-CF"),
    ("Generic PETG", "PETG"), ("Generic PETG HF", "PETG"),
    ("Generic PETG-CF", "PETG-CF"),
    ("Generic ABS", "ABS"), ("Generic ABS-GF", "ABS-GF"),
    ("Generic ASA", "ASA"), ("Generic ASA-CF", "ASA-CF"),
    ("Generic TPU", "TPU"), ("Generic TPU 95A", "TPU"),
    ("Generic PC", "PC"), ("Generic PA (Nylon)", "PA"),
    ("Generic PA-CF", "PA-CF"), ("Generic PET-CF", "PET-CF"),
    ("Generic HIPS", "HIPS"), ("Generic PVA", "PVA"),
    ("Polymaker PolyTerra PLA", "PLA"), ("Polymaker PolyLite PLA", "PLA"),
    ("Polymaker PolyLite ABS", "ABS"), ("Polymaker PolyMax PC", "PC"),
    ("Polymaker PolyMide PA6-CF", "PA-CF"),
    ("eSUN PLA+", "PLA"), ("eSUN PETG", "PETG"), ("eSUN ABS+", "ABS"),
    ("Prusament PLA", "PLA"), ("Prusament PETG", "PETG"), ("Prusament ASA", "ASA"),
    ("Hatchbox PLA", "PLA"), ("Overture PLA", "PLA"), ("Overture PETG", "PETG"),
    ("SUNLU PLA", "PLA"), ("SUNLU PLA Meta", "PLA"), ("Inland PLA", "PLA"),
]


def presets() -> list[dict]:
    out = []
    for name, typ in _PRESETS:
        lo, hi, pa = TYPE_DEFAULTS[typ]
        out.append({"name": name, "type": typ,
                    "nozzle_min": lo, "nozzle_max": hi, "pa_k": pa})
    return out


def lookup(name: str) -> dict | None:
    for p in presets():
        if p["name"] == name:
            return p
    return None
