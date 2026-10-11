"""Network info + Wi-Fi/IP settings for 3DOS.

Raspberry Pi OS Bookworm+ uses NetworkManager, so all reads/writes go through
`nmcli`. Reads are safe; writes (Wi-Fi connect, IP mode, hostname) require root
or polkit permissions. If nmcli is missing or unprivileged, setters return
{ok: False, ...} and the UI remains read-only.
"""
from __future__ import annotations
import shutil, socket, subprocess
import threading, time


def _run(args, timeout=12):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def _has_nmcli() -> bool:
    return shutil.which("nmcli") is not None


# ---- Read State -------------------------------------------------------------

def state() -> dict:
    """Snapshot of current network interfaces and active Wi-Fi connection."""
    if not _has_nmcli():
        return {"ok": True, "nmcli": False, "hostname": socket.gethostname(),
                "interfaces": [], "wifi": None}

    ifaces = []
    # DEVICE:TYPE:STATE:CONNECTION (-t = terse, ':' separated)
    rc, out, _ = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"])
    for line in (out.splitlines() if rc == 0 else []):
        dev, typ, st, con = (line.split(":") + ["", "", "", ""])[:4]
        if typ in ("loopback",) or not dev:
            continue
        info = {"device": dev, "type": typ, "state": st, "connection": con,
                "ip": None, "mac": None, "gateway": None, "dns": []}
        # Details: IP4.ADDRESS, GENERAL.HWADDR, IP4.GATEWAY, IP4.DNS
        rc2, out2, _ = _run(["nmcli", "-t", "-f",
                             "IP4.ADDRESS,IP4.GATEWAY,IP4.DNS,GENERAL.HWADDR",
                             "device", "show", dev])
        if rc2 == 0:
            for l in out2.splitlines():
                if l.startswith("IP4.ADDRESS"):
                    info["ip"] = l.split(":", 1)[1]           # e.g. 192.168.0.42/24
                elif l.startswith("IP4.GATEWAY"):
                    info["gateway"] = l.split(":", 1)[1] or None
                elif l.startswith("IP4.DNS"):
                    v = l.split(":", 1)[1]
                    if v:
                        info["dns"].append(v)
                elif l.startswith("GENERAL.HWADDR"):
                    info["mac"] = l.split(":", 1)[1].replace("\\:", ":")
        ifaces.append(info)

    # Active Wi-Fi (ACTIVE:SSID:SIGNAL:SECURITY)
    wifi = None
    rc3, out3, _ = _run(["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY",
                         "dev", "wifi"])
    for l in (out3.splitlines() if rc3 == 0 else []):
        parts = l.split(":")
        if parts and parts[0] == "yes":
            wifi = {"ssid": parts[1], "signal": _int(parts[2]),
                    "security": parts[3] if len(parts) > 3 else ""}
            break

    return {"ok": True, "nmcli": True, "hostname": socket.gethostname(),
            "interfaces": ifaces, "wifi": wifi}


def scan() -> dict:
    """Scan nearby Wi-Fi networks (--rescan yes forces a fresh scan)."""
    if not _has_nmcli():
        return {"ok": False, "detail": "nmcli not available", "networks": []}
    rc, out, err = _run(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY",
                         "dev", "wifi", "list", "--rescan", "yes"], timeout=20)
    if rc != 0:
        return {"ok": False, "detail": err, "networks": []}
    seen, nets = set(), []
    for l in out.splitlines():
        ssid, sig, sec = (l.split(":") + ["", "", ""])[:3]
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        nets.append({"ssid": ssid, "signal": _int(sig),
                     "secure": bool(sec and sec != "--")})
    nets.sort(key=lambda n: n["signal"], reverse=True)
    return {"ok": True, "networks": nets}


# ---- Modify Settings (requires root / sudoers / polkit) --------------------

def connect_wifi(ssid: str, psk: str = "") -> dict:
    if not _has_nmcli():
        return {"ok": False, "detail": "nmcli not available"}
    args = ["nmcli", "dev", "wifi", "connect", ssid]
    if psk:
        args += ["password", psk]
    rc, out, err = _run(args, timeout=30)
    return {"ok": rc == 0, "detail": out or err}


def set_ip(device: str, mode: str, address: str = "", gateway: str = "",
           dns: str = "") -> dict:
    """mode='dhcp' or 'static'. address must be in CIDR notation (e.g. 192.168.0.50/24)."""
    if not _has_nmcli():
        return {"ok": False, "detail": "nmcli not available"}
    # Look up active connection name for device
    rc, con, _ = _run(["nmcli", "-t", "-f", "GENERAL.CONNECTION",
                       "device", "show", device])
    con = con.split(":", 1)[1] if rc == 0 and ":" in con else ""
    if not con:
        return {"ok": False, "detail": f"No active connection found for {device}"}
    if mode == "dhcp":
        cmds = [["nmcli", "con", "mod", con, "ipv4.method", "auto",
                 "ipv4.addresses", "", "ipv4.gateway", "", "ipv4.dns", ""]]
    else:
        if not address:
            return {"ok": False, "detail": "Static IP address (CIDR) required"}
        cmds = [["nmcli", "con", "mod", con,
                 "ipv4.addresses", address,
                 "ipv4.gateway", gateway,
                 "ipv4.dns", dns,
                 "ipv4.method", "manual"]]
    cmds.append(["nmcli", "con", "up", con])   # Re-apply connection
    for c in cmds:
        rc, out, err = _run(c, timeout=30)
        if rc != 0:
            return {"ok": False, "detail": err or out, "cmd": " ".join(c)}

    # Start 60-second safety rollback timer when switching to static IP
    if mode == "static":
        _start_rollback_timer(con)

    return {"ok": True, "detail": f"{device} -> {mode} applied (auto-reverts in 60s unless committed)" if mode == "static" else f"{device} -> {mode} applied"}

_commit_flag = False
_timer_gen = 0

def _start_rollback_timer(con: str):
    global _commit_flag, _timer_gen
    _commit_flag = False
    _timer_gen += 1
    my_gen = _timer_gen

    def timer_thread():
        time.sleep(60)
        if not _commit_flag and _timer_gen == my_gen:
            print(f"Network rollback triggered for {con}. Reverting to DHCP.")
            _run(["nmcli", "con", "mod", con, "ipv4.method", "auto", "ipv4.addresses", "", "ipv4.gateway", "", "ipv4.dns", ""])
            _run(["nmcli", "con", "up", con])

    threading.Thread(target=timer_thread, daemon=True).start()

def commit() -> dict:
    """Confirm and persist static IP configuration."""
    global _commit_flag
    _commit_flag = True
    return {"ok": True, "detail": "Configuration committed"}

def set_hostname(name: str) -> dict:
    if not name.strip():
        return {"ok": False, "detail": "Empty hostname"}
    rc, out, err = _run(["hostnamectl", "set-hostname", name.strip()])
    return {"ok": rc == 0, "detail": out or err}


def _int(s):
    try:
        return int(s)
    except Exception:
        return 0
