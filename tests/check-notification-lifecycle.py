#!/usr/bin/env python3
"""Owned real Dunst/GTK lifecycle. No real user history, audio, or host session."""
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
from common import Gdk, Gtk, apply_theme, run
from gi.repository import Gio, GLib
from notifications_app import NotificationsWindow
from notification_utils import record_key
from ui_preferences import save_preferences

assert os.getuid() == 1000
assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert os.environ.get("OOONANA_NOTIFICATION_TEST_SESSION") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)


def owner():
    reply = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "NameHasOwner", GLib.Variant("(s)", ("org.freedesktop.Notifications",)), None,
        Gio.DBusCallFlags.NONE, 2000, None)
    return reply.unpack()[0]


assert not owner(), "Refusing existing notification service"


def settle(seconds=0.2):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.02)


def wait(predicate, message):
    end = time.monotonic() + 12
    while True:
        settle(0.03)
        if predicate():
            return
        assert time.monotonic() < end, message


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        process.wait(timeout=4)


findings = []


def check(condition, message):
    if not condition:
        findings.append(message)
        print("NOTIFICATION_LIFECYCLE_FINDING", message, flush=True)


with tempfile.TemporaryDirectory(prefix="ooonana-notification-lifecycle-") as temporary:
    fixture = Path(temporary)
    os.environ["XDG_CONFIG_HOME"] = str(fixture / "config")
    os.environ["XDG_STATE_HOME"] = str(fixture / "state")
    save_preferences(remember_notifications=True)
    config = fixture / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                               if not line.startswith("exec")) + "\n")
    dunst_config = Path("/etc/ooonana/dunstrc")
    assert not re.search(r"(?m)^\s*script\s*=", dunst_config.read_text()), "QA must not execute notification scripts"
    log = (output / "dunst.log").open("w")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=log, stderr=log)
    daemon = window = None
    blocked_directory = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0,
             "Private window manager unavailable")

        def start_daemon():
            process = subprocess.Popen(["dunst", "-config", str(dunst_config)], stdout=log, stderr=log)
            wait(lambda: owner() and process.poll() is None, "Private Dunst unavailable")
            return process

        daemon = start_daemon()

        def send(summary, body="Private lifecycle message"):
            result = subprocess.run(["notify-send", "--print-id", "-a", "Lifecycle QA", "-t", "0",
                "-h", "boolean:suppress-sound:true", summary, body], capture_output=True, text=True, check=True)
            return int(result.stdout.strip())

        def collect():
            assert run(["dunstctl", "close-all"], timeout=2)[0] == 0
            window.refresh_button.clicked()
            wait(lambda: not window.refreshing and not window.action_pending, "Refresh/action did not settle")
            settle()

        def capture(name):
            settle()
            root = Gdk.get_default_root_window()
            Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                str(output / (name + ".png")), "png", [], [])

        long_body = "Details stay readable · 알림 내용\n" * 20
        first_id = send("Focusable details", long_body)
        send("Second private message")
        send("Third private message")
        apply_theme()
        window = NotificationsWindow()
        window.show_all()
        wait(lambda: not window.refreshing and len(window.records) == 3, "Initial messages not collected")
        # Explicit reads below avoid a test-only stop/start racing a periodic read
        # and auto-activating another daemon. Production timer remains unchanged.
        GLib.source_remove(window.timer_id)
        window.timer_id = 0
        window.get_window().focus(Gdk.CURRENT_TIME)
        wait(lambda: window.is_active() and not window.refreshing, "Center not active")

        def details():
            return next(item for item in descendants(window.list) if isinstance(item, Gtk.Expander)
                        and item.get_child().get_text() == long_body)

        def details_visible():
            anchor = details().get_label_widget()
            position = anchor.translate_coordinates(window.scroll, 0, 0)
            return (position is not None and position[1] >= 0 and
                    position[1] + anchor.get_allocated_height() <= window.scroll.get_allocated_height())

        details().set_expanded(True)
        settle()
        anchor = details().get_label_widget()
        position = anchor.translate_coordinates(window.list, 0, 0)
        window.scroll.get_vadjustment().clamp_page(position[1], position[1] + anchor.get_allocated_height())
        details().grab_focus()
        settle()
        assert window.get_focus() is details(), "Could not establish Expander focus"
        assert details_visible(), "Fixture reading header not visible before new message"
        capture("focused-details")
        send("New message during keyboard reading")
        collect()
        wait(lambda: len(window.records) == 4, "New notification absent")
        check(details().get_expanded(), "Changed list collapsed expanded message")
        check(window.get_focus() is details(), "Changed list lost focused message expander")
        check(details_visible(), "Changed list scrolled focused reading header outside viewport")
        capture("changed-list")

        assert run(["dunstctl", "history-clear"], timeout=2)[0] == 0
        send("Live message mixed with saved history")
        collect()
        wait(lambda: len(window.records) == 5, "Saved/live mix unavailable")
        assert sum(bool(item.get("archived")) for item in window.records) == 4
        expected = {record_key(item) for item in window.records}
        original_seen = window.state.seen_path
        window.state.seen_path = fixture / "invalid-read-state"
        window.state.seen_path.mkdir()
        collect()
        check({record_key(item) for item in window.records} == expected, "Read-mark write failure hid saved messages")
        check("read" in window.status.get_text().lower() and
              any(word in window.status.get_text().lower() for word in ("failed", "could not", "unavailable", "not saved")),
              "Read-mark write failure has no visible warning")
        capture("read-state-failure")
        window.state.seen_path = original_seen
        collect()

        blocked_directory = window.state.directory
        blocked_directory.chmod(0o500)
        # Unchanged JSON writes already deduplicate; require a real new write.
        send("New message while saved history is read-only")
        assert run(["dunstctl", "close-all"], timeout=2)[0] == 0
        from notification_utils import parse_history, read_history
        rc, text = read_history()
        assert rc == 0
        expected.update(record_key(item) for item in parse_history(text))
        collect()
        check({record_key(item) for item in window.records} == expected, "Read-only archive hid readable saved messages")
        check(any(word in window.status.get_text().lower() for word in ("save", "storage", "history")),
              "Read-only archive has no visible warning")
        capture("read-only-history")
        blocked_directory.chmod(0o700)
        blocked_directory = None
        collect()
        archived = next(item for item in window.records if item.get("archived") and item["id"] != first_id)
        blocked_directory = window.state.directory
        blocked_directory.chmod(0o500)
        window.remove_record(archived)
        check("remove" in window.action_error.lower(), "Saved removal failure was not recorded")
        collect()
        check("remove" in window.status.get_text().lower(), "Refresh hid failed saved removal")
        check({record_key(item) for item in window.records} == expected, "Failed removal changed saved rows")
        capture("remove-history-failure")
        blocked_directory.chmod(0o700)
        blocked_directory = None
        window.remove_record(archived)
        expected.remove(record_key(archived))
        wait(lambda: not window.refreshing and {record_key(item) for item in window.records} == expected,
             "Saved removal retry did not recover")
        assert not window.action_error, "Successful retry left stale removal error"
        expected_count = len(expected)

        window.pause.set_active(True)
        wait(lambda: not window.action_pending and not window.refreshing and window.pause.get_sensitive(), "DND action stalled")
        assert run(["dunstctl", "is-paused"], timeout=2)[1].strip() == "true"
        stop(daemon)
        wait(lambda: not owner(), "Old daemon still owns service")
        daemon = start_daemon()
        window.refresh_button.clicked()
        wait(lambda: not window.refreshing and window.pause_known, "Restart refresh unavailable")
        assert not window.pause.get_active(), "Restart left stale DND status"
        assert len(window.records) == expected_count and all(item.get("archived") for item in window.records)
        new_id = send("New daemon message with reused ID")
        collect()
        wait(lambda: len(window.records) == expected_count + 1, "Restart lost saved/live records")
        assert new_id == first_id, "Fixture did not reproduce ID reuse"
        archived = next(item for item in window.records if item["id"] == new_id and item.get("archived"))
        window.remove_record(archived)
        wait(lambda: not window.refreshing and len(window.records) == expected_count, "Archived removal stalled")
        assert any(item["id"] == new_id and not item.get("archived") for item in window.records), "Archived removal deleted new live ID"
        capture("restart-id-reuse")
        window.clear_button.clicked()
        wait(lambda: not window.refreshing and not window.action_pending and not window.records, "Clear all failed")
        assert run(["dunstctl", "count", "history"], timeout=2)[1].strip() == "0"
        capture("cleared")
        print("NOTIFICATION_LIFECYCLE_RESULTS", json.dumps(findings), flush=True)
        assert not findings, "; ".join(findings)
        print("NOTIFICATION_LIFECYCLE_OK actual Dunst, nested focus, storage faults, restart/DND, ID reuse, clear", flush=True)
    finally:
        if blocked_directory is not None:
            blocked_directory.chmod(0o700)
        if window is not None:
            window.destroy()
        stop(daemon)
        stop(wm)
        log.close()
