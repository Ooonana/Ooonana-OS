"""Bounded read-only endpoint checks; readiness is not hardware test proof."""
from pathlib import Path
import os
import re
import shutil
import subprocess


def execute(command):
    if command[0] == "pactl":
        # Explicit server disables default auto-spawn during diagnostics.
        server = os.environ.get("PULSE_SERVER") or "unix:" + os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}") + "/pulse/native"
        command = [command[0], "--server=" + server, *command[1:]]
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=2)
        return result.returncode, result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 124, ""


def check_services(run=execute, available=shutil.which, socket_exists=None):
    socket_exists = socket_exists or (lambda: Path("/run/dbus/system_bus_socket").is_socket())
    result = {}
    bus = bool(available("dbus-send") and socket_exists())
    base = ["dbus-send", "--system", "--print-reply", "--reply-timeout=1500",
            "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus",
            "org.freedesktop.DBus.NameHasOwner"]
    if bus:
        code, text = run(base + ["string:org.freedesktop.DBus"])
        bus = code == 0 and bool(re.search(r"boolean\s+true\b", text))
    result["dbus"] = {"state": "ready" if bus else "unreachable", "probe": "system bus reply"}
    owner_query = base[:-1] + ["org.freedesktop.DBus.GetNameOwner"]
    for key, name, path in (("network", "org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager"),
                            ("bluetooth", "org.bluez", "/"),
                            ("wifi-auth", "fi.w1.wpa_supplicant1", "/fi/w1/wpa_supplicant1")):
        if not bus:
            state = "waiting-for-dbus"
        else:
            code, text = run(owner_query + ["string:" + name])
            owner = re.search(r'\bstring\s+"(:[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+)"', text)
            state = "not-ready"
            if code == 0 and owner:
                # Unique names cannot activate a stopped service, even if its
                # well-known ownership disappears between lookup and ping.
                code, _text = run(["dbus-send", "--system", "--print-reply",
                                  "--reply-timeout=1500", "--dest=" + owner[1], path,
                                  "org.freedesktop.DBus.Peer.Ping"])
                state = "ready" if code == 0 else "unresponsive"
        result[key] = {"state": state, "probe": "D-Bus unique-owner endpoint reply"}
    if available("pactl"):
        code, text = run(["pactl", "info"])
        state = "ready" if code == 0 and text.strip() else "not-ready"
    else:
        state = "unavailable"
    result["audio"] = {"state": state, "probe": "audio server reply; no playback"}
    return result
