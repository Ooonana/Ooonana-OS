#!/usr/bin/env python3
"""Real Dunst loss/restart through unchanged production periodic refresh."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme
from gi.repository import Gio, GLib
from notifications_app import NotificationsWindow
from ui_preferences import save_preferences

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert os.environ.get("OOONANA_NOTIFICATION_TEST_SESSION") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
focus_events = []


def owner():
    reply = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "NameHasOwner", GLib.Variant("(s)", ("org.freedesktop.Notifications",)), None,
        Gio.DBusCallFlags.NONE, 2000, None)
    return reply.unpack()[0]


assert not owner(), "Existing notification service: refuse"


def settle(seconds=0.15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


def wait(predicate, message):
    start = time.monotonic()
    while True:
        settle(0.04)
        if predicate():
            print("NOTIFICATION_AUTO_STEP", message, round(time.monotonic() - start, 2), flush=True)
            return
        assert time.monotonic() - start < 15, message


def capture(name):
    settle()
    root = Gdk.get_default_root_window()
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
        str(output / (name + ".png")), "png", [], [])


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        process.wait(timeout=4)


with tempfile.TemporaryDirectory(prefix="ooonana-notification-auto-") as temporary:
    fixture = Path(temporary)
    os.environ.update(XDG_CONFIG_HOME=str(fixture / "config"), XDG_STATE_HOME=str(fixture / "state"))
    save_preferences(remember_notifications=True)
    config = fixture / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                               if not line.startswith("exec")) + "\n")
    dunst_config = Path("/etc/ooonana/dunstrc")
    assert not re.search(r"(?m)^\s*script\s*=", dunst_config.read_text()), "No notification scripts allowed"
    with (output / "services.log").open("w") as log:
        wm = subprocess.Popen(["i3", "-c", str(config)], stdout=log, stderr=log)
        daemon = window = None
        try:
            wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0,
                 "Owned i3 available")

            def start_daemon():
                process = subprocess.Popen(["dunst", "-config", str(dunst_config)], stdout=log, stderr=log)
                wait(lambda: owner() and process.poll() is None, "Owned Dunst available")
                return process

            def send(summary, timeout):
                result = subprocess.run(["notify-send", "--print-id", "-a", "Auto Recovery QA",
                    "-h", "boolean:suppress-sound:true", "-t", str(timeout), summary, "Private 한국어 history"],
                    capture_output=True, text=True, check=True)
                return int(result.stdout.strip())

            daemon = start_daemon()
            old_id = send("Saved before restart", 0)
            apply_theme()
            window = NotificationsWindow()
            window.connect("focus-in-event", lambda *_: focus_events.append(True) or False)
            window.show_all()
            wait(lambda: window.is_active() and not window.refreshing and len(window.records) == 1,
                 "Initial saved record available")
            assert window.timer_id, "Production timer absent"
            focus_count = len(focus_events)
            subprocess.run(["dunstctl", "set-paused", "true"], check=True)
            wait(lambda: not window.refreshing and window.pause_known and window.pause.get_active(),
                 "Periodic DND update")
            capture("paused")
            stop(daemon)
            wait(lambda: not owner(), "Stopped daemon lost bus ownership")
            wait(lambda: not window.refreshing and not window.service_available and not window.pause_known,
                 "Periodic unavailable state")
            assert not owner(), "Fault bus unexpectedly auto-activated a daemon"
            assert len(window.records) == 1 and window.records[0].get("archived")
            assert not window.pause.get_sensitive(), "Unknown DND remains actionable"
            assert "unavailable" in window.status.get_text().lower()
            capture("unavailable")
            daemon = start_daemon()
            wait(lambda: not window.refreshing and window.service_available and window.pause_known
                 and not window.pause.get_active(), "Periodic restart recovery")
            assert len(window.records) == 1 and window.records[0].get("archived")
            new_id = send("New after restart", 1000)
            wait(lambda: not window.refreshing and len(window.records) == 2, "Periodic new expired message")
            assert new_id == old_id, "Expected ID reuse not reproduced"
            assert any("한국어" in record.get("body", "") for record in window.records)
            assert window.timer_id and len(focus_events) == focus_count, "Focus event confounds periodic proof"
            capture("recovered")
            window.destroy()
            assert not window.timer_id, "Closed center left timer running"
            window = None
            print("NOTIFICATION_AUTO_OK real service loss/restart, DND, retained history, ID reuse and unchanged timer", flush=True)
        finally:
            if window is not None:
                window.destroy()
            stop(daemon)
            stop(wm)
