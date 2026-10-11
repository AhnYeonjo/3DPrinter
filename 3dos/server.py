#!/usr/bin/env python3
"""3DOS — a Klipper host/UI control layer for multitool StealthChanger printers.

PoC scope: the multitool configuration + tool-change orchestration surface that
replaces the Mainsail/Moonraker tooling for a 6+ tool StealthChanger build.

Zero third-party dependencies — runs on the stock Python that ships with a Pi.
    python3 server.py            # http://localhost:8088
    MOONRAKER_URL=http://localhost:7125 python3 server.py   # live mode

REST API:
    GET    /api/state                  full snapshot (tools + active + boards)
    GET    /api/boards                 supported CAN board presets
    POST   /api/tools                  create/update a tool (JSON Tool)
    DELETE /api/tools/{n}              remove a tool
    POST   /api/tools/{n}/activate     mark tool active (no motion)
    POST   /api/toolchange             {"to": n}  -> plan (+execute if live)
    GET    /api/export                 generated Klipper config bundle (text)
    GET    /api/printer                Moonraker status passthrough
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core.store import ToolStore
from core.model import Tool, BOARD_PRESETS
from core.klipper import generate_tool_cfg, generate_toolchanger_cfg
from core.toolchange import plan_toolchange
from core.calibration import CalibrationStore, Calibration
from core import (moonraker, health, recovery, macros, filament, controls,
                  filament_db, options, maintenance, objects, cameras, network,
                  jobs, prints, toolcal, shapercal)
import datetime

STORE = ToolStore()
CALS = CalibrationStore()
for _t in STORE.sorted():
    CALS.seed_from_tool(_t)
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
PORT = int(os.environ.get("PORT", "8088"))
HOST = os.environ.get("HOST", "0.0.0.0")   # Default 0.0.0.0 to allow external LAN/Tailscale connections
API_TOKEN = os.environ.get("API_TOKEN")


class Handler(BaseHTTPRequestHandler):
    server_version = "3DOS/0.1"

    def _check_auth(self):
        if not API_TOKEN:
            return True
        if self.path.startswith("/api/"):
            auth = self.headers.get("Authorization", "")
            return auth == f"Bearer {API_TOKEN}" or self.headers.get("X-Api-Key") == API_TOKEN
        return True

    # ---- helpers ----
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text, code=200):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        ctype = self.headers.get("Content-Type", "")
        if self.command == "POST" and not ctype.startswith("application/json"):
            raise ValueError("Invalid Content-Type, expected application/json")
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _snapshot(self) -> dict:
        return {
            "active": STORE.active,
            "live": moonraker.available(),
            "tools": [t.to_dict() for t in STORE.sorted()],
        }

    # ---- routing ----
    def do_GET(self):
        if not self._check_auth():
            return self._json({"error": "unauthorized"}, 401)
        try:
            return self._do_GET_inner()
        except Exception as e:
            return self._json({"error": str(e)}, 400)

    def _do_GET_inner(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            return self._serve_file("index.html", "text/html; charset=utf-8")
        if p in ("/touch", "/touch.html"):
            return self._serve_file("touch.html", "text/html; charset=utf-8")
        if p == "/api/macros":
            return self._json(macros.menu())
        if p == "/api/filament":
            return self._json({"materials": filament.MATERIALS,
                               "tools": [t.tool_number for t in STORE.sorted()]})
        if p == "/api/filament/state":
            return self._json(filament.state(STORE.sorted()))
        if p == "/api/pinkbox":
            return self._json({"present": filament.pinkbox_present()})
        if p == "/api/controls":
            st = controls.state()
            maintenance.tick(st.get("nevermore", {}).get("speed", 0),
                             False)  # printing flag wired in live build
            return self._json(st)
        if p == "/api/filament/presets":
            return self._json({"presets": filament_db.presets()})
        if p == "/api/options":
            return self._json(options.state())
        if p == "/api/network":
            return self._json(network.state())
        if p == "/api/network/scan":
            return self._json(network.scan())
        if p == "/api/maintenance":
            return self._json(maintenance.state())
        if p == "/api/objects":
            return self._json(objects.state())
        if p == "/api/cameras":
            return self._json({"cameras": cameras.list_cameras()})
        if p == "/api/state":
            return self._json(self._snapshot())
        if p == "/api/boards":
            return self._json({k: {"label": v["label"], "bus": v["bus"],
                                   "has_accel": v["has_accel"]}
                               for k, v in BOARD_PRESETS.items()})
        if p == "/api/printer":
            return self._json(moonraker.printer_status())
        if p == "/api/console":
            return self._json(moonraker.get_console())
        if p == "/api/export":
            return self._text(self._export_bundle())
        if p == "/api/health":
            return self._json(health.status(STORE.sorted()))
        if p == "/api/safeboot":
            return self._text(health.generate_safe_boot(STORE.sorted()))
        m = re.match(r"^/api/calibration/(\d+)$", p)
        if m:
            from dataclasses import asdict
            return self._json(asdict(CALS.get(int(m.group(1)))))
        
        # New routes for prints, jobs, bedmesh
        if p == "/api/files":
            return self._json(jobs.files())
        if p == "/api/files/meta":
            qs = self.path.split("?", 1)
            fn = urllib.parse.parse_qs(qs[1]).get("filename", [""])[0] if len(qs) > 1 else ""
            return self._json(jobs.meta(fn))
        if p == "/api/thumb":
            qs = self.path.split("?", 1)
            path = urllib.parse.parse_qs(qs[1]).get("path", [""])[0] if len(qs) > 1 else ""
            if not path or not moonraker.available():
                return self._text("Not found", 404)
            import urllib.request
            try:
                # e.g. path = /server/files/gcodes/...
                url = moonraker.MOONRAKER_URL + path
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5) as r:
                    self.send_response(200)
                    self.send_header("Content-Type", r.headers.get("Content-Type", "image/png"))
                    self.send_header("Cache-Control", "max-age=86400")
                    self.end_headers()
                    self.wfile.write(r.read())
                    return
            except Exception:
                return self._text("Not found", 404)
        if p == "/api/history":
            return self._json(prints.history())
        if p == "/api/history/totals":
            return self._json(prints.totals())
        if p == "/api/history/tools":
            return self._json(prints.tool_stats())
        if p == "/api/bedmesh":
            q = moonraker.query(["bed_mesh"])
            bm = q.get("status", {}).get("bed_mesh", {}) if q.get("ok") else {}
            return self._json({"ok": True,
                "matrix": bm.get("probed_matrix") or bm.get("mesh_matrix") or [],
                "min": bm.get("mesh_min"), "max": bm.get("mesh_max"),
                "profile": bm.get("profile_name")})

        return self._text("not found", 404)

    def do_POST(self):
        if not self._check_auth():
            return self._json({"error": "unauthorized"}, 401)
        try:
            return self._do_POST_inner()
        except Exception as e:
            return self._json({"error": str(e)}, 400)

    def _do_POST_inner(self):
        p = self.path.split("?")[0]
        if p == "/api/tools":
            t = Tool.from_dict(self._body())
            STORE.upsert(t)
            return self._json({"ok": True, "tool": t.to_dict()})
        m = re.match(r"^/api/tools/(\d+)/activate$", p)
        if m:
            STORE.set_active(int(m.group(1)))
            return self._json({"ok": True, "active": STORE.active})
        if p == "/api/toolchange":
            return self._toolchange(self._body())
        m = re.match(r"^/api/calibration/(\d+)$", p)
        if m:
            return self._save_calibration(int(m.group(1)), self._body())
        m = re.match(r"^/api/calibration/(\d+)/apply$", p)
        if m:
            return self._apply_calibration(int(m.group(1)))
        if p == "/api/health/set":
            b = self._body()
            health.set_online(b["uuid"], bool(b["online"]))
            return self._json({"ok": True, **health.status(STORE.sorted())})
        if p == "/api/health/scan":
            return self._json(health.scan(STORE.sorted()))
        if p == "/api/recover":
            b = self._body()
            return self._json(recovery.recover(STORE.sorted(),
                              b.get("error", ""), bool(b.get("execute"))))
        if p == "/api/macros/run":
            b = self._body()
            return self._json(macros.run(b["name"], b.get("params")))
        if p == "/api/filament/run":
            b = self._body()
            return self._json(filament.run(int(b["tool"]), b["action"],
                              b.get("material", "PLA")))
        if p == "/api/filament/config":
            b = self._body()
            return self._json(filament.configure(
                int(b["tool"]), preset=b.get("preset"), color=b.get("color"),
                nozzle_min=b.get("nozzle_min"), nozzle_max=b.get("nozzle_max"),
                pa_profile=b.get("pa_profile"), pa_k=b.get("pa_k")))
        if p == "/api/options/set":
            b = self._body()
            return self._json(options.set_option(b["key"], b["value"]))
        if p == "/api/network/wifi":
            b = self._body()
            return self._json(network.connect_wifi(b["ssid"], b.get("psk")))
        if p == "/api/network/ip":
            b = self._body()
            return self._json(network.set_ip(b["device"], b["mode"],
                              b.get("address", ""), b.get("gateway", ""),
                              b.get("dns", "")))
        if p == "/api/network/hostname":
            b = self._body()
            return self._json(network.set_hostname(b["name"]))
        if p == "/api/network/commit":
            return self._json(network.commit())
        if p == "/api/maintenance/reset-filter":
            return self._json(maintenance.reset_filter())
        if p == "/api/maintenance/set":
            b = self._body()
            return self._json(maintenance.set_interval(b["interval"]))
        if p == "/api/objects/exclude":
            b = self._body()
            return self._json(objects.exclude(b["name"], bool(b.get("undo"))))
        if p == "/api/cameras":
            return self._json(cameras.upsert(self._body()))
        if p == "/api/controls/set":
            b = self._body()
            return self._json(controls.apply(b["what"], b["value"],
                              b.get("tool")))
        if p == "/api/gcode":
            b = self._body()
            script = b.get("script", "")
            if moonraker.available():
                r = moonraker.run_gcode(script)
                return self._json({"ok": r["ok"], "sent": r["ok"],
                                   "detail": r["detail"], "script": script})
            return self._json({"ok": True, "sent": False, "detail": "dry-run",
                               "script": script})
        
        # New POST route for print start
        if p == "/api/print/start":
            b = self._body()
            return self._json(jobs.start(b["filename"]))

        if p == "/api/toolcal/prepare":
            return self._json(toolcal.prepare())
        if p == "/api/toolcal/tool":
            return self._json(toolcal.calibrate_tool(int(self._body()["tool"]), CALS))
        if p == "/api/toolcal/finish":
            return self._json(toolcal.finish())
            
        if p == "/api/shapercal/tool":
            return self._json(shapercal.measure_tool(int(self._body()["tool"]), CALS))

        return self._text("not found", 404)

    def do_DELETE(self):
        if not self._check_auth():
            return self._json({"error": "unauthorized"}, 401)
        try:
            return self._do_DELETE_inner()
        except Exception as e:
            return self._json({"error": str(e)}, 400)

    def _do_DELETE_inner(self):
        m = re.match(r"^/api/tools/(\d+)$", self.path.split("?")[0])
        if m:
            STORE.delete(int(m.group(1)))
            return self._json({"ok": True})
        return self._text("not found", 404)

    # ---- actions ----
    def _toolchange(self, body):
        to = STORE.get(int(body.get("to")))
        if not to:
            return self._json({"ok": False, "detail": "unknown tool"}, 400)
        frm = STORE.get(STORE.active) if STORE.active is not None else None
        plan = plan_toolchange(frm, to)
        # re-push the new tool's stored calibration at runtime — no restart needed
        cal_gcode = CALS.get(to.tool_number).apply_gcode()
        plan["gcode"] += "\n; ---- restore T%d calibration (no restart) ----\n" % to.tool_number
        plan["gcode"] += "\n".join(cal_gcode)
        result = {"ok": True, "plan": plan, "executed": False,
                  "calibration_restored": cal_gcode}
        if moonraker.available() and body.get("execute"):
            r = moonraker.run_gcode(f"T{to.tool_number}\n" + "\n".join(cal_gcode))
            result["executed"] = r["ok"]
            result["detail"] = r["detail"]
            if r["ok"]:
                prints.record_tool(to.tool_number, 0, 0)
        STORE.set_active(to.tool_number)
        return self._json(result)

    def _save_calibration(self, n, body):
        """Save calibration to 3DOS store (instant) and apply via runtime G-code
        (no SAVE_CONFIG, no restart). PID changes are flagged separately."""
        body["tool_number"] = n
        cal = Calibration(**{k: v for k, v in body.items()
                             if k in Calibration.__dataclass_fields__})
        when = datetime.datetime.now().isoformat(timespec="seconds")
        CALS.save(cal, when)
        gcode = cal.apply_gcode()
        sent = False
        detail = "dry-run (no MOONRAKER_URL)"
        if moonraker.available():
            r = moonraker.run_gcode("\n".join(gcode))
            sent, detail = r["ok"], r["detail"]
        return self._json({
            "ok": True, "saved_at": when, "restart_required": cal.needs_restart(),
            "apply_gcode": gcode, "sent": sent, "detail": detail,
            "note": ("PID set — one fast restart needed for that value only"
                     if cal.needs_restart()
                     else "applied live — no restart"),
        })

    def _apply_calibration(self, n):
        cal = CALS.get(n)
        gcode = cal.apply_gcode()
        sent = False
        detail = "dry-run"
        if moonraker.available():
            r = moonraker.run_gcode("\n".join(gcode))
            sent, detail = r["ok"], r["detail"]
        return self._json({"ok": True, "apply_gcode": gcode,
                           "sent": sent, "detail": detail})

    def _export_bundle(self) -> str:
        parts = ["#  ===== 3DOS generated Klipper config bundle =====\n"]
        parts.append(generate_toolchanger_cfg(STORE.sorted()))
        for t in STORE.sorted():
            parts.append(f"\n#  ---------- tools/{t.name}.cfg ----------\n")
            parts.append(generate_tool_cfg(t))
        return "\n".join(parts)

    def _serve_file(self, name, ctype):
        path = os.path.join(WEB_DIR, name)
        if not os.path.exists(path):
            return self._text("missing web asset", 404)
        with open(path, "rb") as f:
            body = f.read()
        if API_TOKEN and name in ("index.html", "touch.html"):
            meta = f'\n<meta name="api-token" content="{API_TOKEN}">\n</head>'.encode()
            body = body.replace(b"</head>", meta)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if name in ("index.html", "touch.html"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # quieter console
        pass


def main():
    # 3DOS coexists with Mainsail/Fluidd — it is purely additive:
    #   - listens on its OWN port (default 8088; Mainsail=80, Moonraker=7125, Fluidd=80/8819)
    #   - only READS Moonraker + SENDS G-code (Moonraker is multi-client safe)
    #   - writes ONLY its own *.json in this folder; never edits printer.cfg / Klipper config
    if PORT in (80, 443, 7125, 8819):
        print(f"[warn] PORT {PORT} may clash with Mainsail/Moonraker/Fluidd — "
              f"use a free port (e.g. PORT=8088).")
    # Security: Set HOST=127.0.0.1 when running behind an authenticated reverse proxy
    #   to block direct external access to port 8088 (default: 0.0.0.0).
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    mode = "LIVE (Moonraker)" if moonraker.available() else "DRY-RUN"
    print(f"3DOS server [{mode}]  ->  http://localhost:{PORT}   (coexists with Mainsail)")
    print(f"  tools loaded: {len(STORE.tools)}  active: T{STORE.active}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
