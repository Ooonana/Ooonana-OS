#!/usr/bin/env python3
"""Real Dunst restart between displayed history and Remove; owned session only."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme
from notifications_app import NotificationsWindow
from notification_utils import parse_history, read_history, record_key
from gi.repository import Gio

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert os.environ.get("OOONANA_NOTIFICATION_TEST_SESSION") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", round(96 * 1024 * float(os.environ["OOONANA_GUI_TEXT_SCALE"])))
apply_theme()
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)


def owner():
    return bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "NameHasOwner", GLib.Variant("(s)", ("org.freedesktop.Notifications",)), None,
        Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]


assert not owner(), "Refuse existing notification service"


def wait(predicate, detail):
    deadline = time.monotonic() + 12
    while not predicate():
        assert time.monotonic() < deadline, detail
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.02)


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        process.wait(timeout=5)


with tempfile.TemporaryDirectory(prefix="ooonana-stale-notification-") as temporary:
    fixture = Path(temporary)
    os.environ.update(XDG_CONFIG_HOME=str(fixture / "config"), XDG_STATE_HOME=str(fixture / "state"))
    config = fixture / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                               if not line.startswith("exec")) + "\n")
    dunst_config = Path("/etc/ooonana/dunstrc")
    assert not re.search(r"(?m)^\s*script\s*=", dunst_config.read_text())
    log = (output / "services.log").open("w")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=log, stderr=log)
    daemon = window = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0,
             "Private window manager unavailable")

        def start_daemon():
            process = subprocess.Popen(["dunst", "-config", str(dunst_config)], stdout=log, stderr=log)
            wait(lambda: process.poll() is None and owner(), "Private Dunst unavailable")
            return process

        def send(title):
            result = subprocess.run(["notify-send", "--print-id", "-a", "Stale action QA", "-t", "0",
                "-h", "boolean:suppress-sound:true", title, "Owned notification; never user history."],
                check=True, capture_output=True, text=True)
            subprocess.run(["dunstctl", "close-all"], check=True)
            return int(result.stdout.strip())

        daemon = start_daemon()
        old_id = send("Message before restart")
        def badge():
            return subprocess.check_output(["ooonana-notification-status"], text=True, timeout=6).strip()
        assert badge().endswith(" 1"), "Actual panel helper missed unread history"
        window = NotificationsWindow()
        window.show_all()
        wait(lambda: not window.refreshing and len(window.records) == 1, "Original history not displayed")
        # Freeze polling solely to deterministically exercise click-before-refresh.
        # The separate auto-recovery probe keeps the production timer unchanged.
        GLib.source_remove(window.timer_id)
        window.timer_id = 0
        window.present()
        wait(window.is_active, "Notification center not focused")
        window.refresh()
        wait(lambda: not window.refreshing, "Read status did not settle")
        assert badge().endswith("%{T-}"), "Actual panel helper retained already-read badge"
        subprocess.run(["ooonana-notification-status", "--toggle"], check=True)
        assert badge().endswith(" DND"), "Actual panel helper missed DND"
        subprocess.run(["ooonana-notification-status", "--toggle"], check=True)
        stale = dict(window.records[0])
        stop(daemon)
        wait(lambda: not owner(), "Old notification service still owns bus name")
        daemon = start_daemon()
        new_id = send("New message after restart")
        assert new_id == old_id, "Dunst ID reuse not reproduced"
        window.remove_record(stale)
        wait(lambda: not window.action_pending and not window.refreshing, "Stale Remove did not settle")
        rc, history = read_history()
        current = parse_history(history)
        assert rc == 0 and len(current) == 1 and current[0]["summary"] == "New message after restart", \
            "Stale Remove deleted a different notification after daemon restart"
        assert window.action_error, "Stale Remove lacks visible refusal"
        assert any(record_key(item) == record_key(current[0]) for item in window.records)
        # Rebuilt rows need a frame-clock allocation/paint before pixel capture.
        deadline = time.monotonic() + .25
        while time.monotonic() < deadline:
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            time.sleep(.01)
        assert window.status.get_text().startswith("Message changed")
        root = Gdk.get_default_root_window()
        frame = window.get_window().get_frame_extents()
        assert 0 <= frame.x and frame.x + frame.width <= root.get_width()
        assert 0 <= frame.y and frame.y + frame.height <= root.get_height()
        Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
            str(output / "stale-remove-refused.png"), "png", [], [])
        window.remove_record(next(item for item in window.records if not item.get("archived")))
        wait(lambda: not window.action_pending and not window.refreshing and not window.records,
             "Fresh exact-message removal did not recover")
        assert not window.action_error
        assert badge().endswith("%{T-}"), "Actual panel helper retained removed message count"
        print("NOTIFICATION_STALE_UI_OK real restart/ID reuse, stale refusal, fresh Remove retry; real panel unread/read/DND badges", flush=True)
    finally:
        if window is not None:
            window.destroy()
        stop(daemon)
        stop(wm)
        log.close()
