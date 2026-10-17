#!/usr/bin/env python3
"""Owned i3/GTK UI states, mocked radios/notifications. No hardware changes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1" and os.getuid() != 0
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, Pango, apply_theme
import wifi_app as wifi
import bluetooth_app as bluetooth
import notifications_app as notifications

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--baseline", action="store_true")
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
Gtk.main_quit = lambda *_args: None
apply_theme()
failures = []


def check(condition, text):
    if not condition:
        failures.append(text)


def settle(seconds=0.16):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.005)


def capture(window, name):
    settle()
    screen = Gdk.get_default_root_window()
    rectangle = window.get_window().get_frame_extents()
    check(0 <= rectangle.x and rectangle.x + rectangle.width <= screen.get_width() and
          0 <= rectangle.y and rectangle.y + rectangle.height <= screen.get_height(),
          f"{name}: frame outside screen ({rectangle.x},{rectangle.y} {rectangle.width}x{rectangle.height})")
    Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height()).savev(
        str(args.output / (name + ".png")), "png", [], [])


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


def exercise_more(window, expected, name):
    control = window.more_button
    window.get_window().focus(Gdk.CURRENT_TIME)
    settle()
    control.grab_focus()
    subprocess.run(["xdotool", "key", "--clearmodifiers", "space"], check=True)
    settle()
    popover = control.get_popover()
    check(popover.get_visible(), name + " More is not keyboard reachable")
    labels = {item.get_label() for item in descendants(popover) if isinstance(item, Gtk.Button)}
    check(expected <= labels, name + " More lost secondary actions")
    capture(window, name + "-more")
    subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"], check=True)
    # Native popover may finish its dismissal transition after returning focus.
    deadline = time.monotonic() + 2
    while popover.get_visible() and time.monotonic() < deadline:
        settle(0.02)
    check(not popover.get_visible(), name + " More does not dismiss with Escape")
    check(window.get_focus() is control, name + " More does not restore keyboard focus")


jobs, actions = [], []
for module in (wifi, bluetooth, notifications):
    module.run_async_task = lambda task, done: jobs.append((task, done))
    module.run_async = lambda command, done, **kwargs: actions.append((command, done))
    module.run = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Unexpected backend command"))
    module.message = lambda *_args, **_kwargs: None
wifi.WifiWindow.initial_refresh = lambda _self: None
bluetooth.BluetoothWindow.initial_refresh = lambda _self: None
# Populated fixtures model native adapters, not this WSL host's absent radios.
wifi.host_radio_unavailable = bluetooth.host_radio_unavailable = lambda _kind: False
network_name = "Nearby network with a long name"
network = dict(ssid=network_name, signal=77, security_label="WPA2/WPA3 Personal",
               security_kind="personal", security="WPA2 PSK", connected=True,
               ap_count=2, device="wlan0", bssid="00:11:22:33:44:55")

with tempfile.TemporaryDirectory(prefix="ooonana-wireless-ui-") as temporary:
    configuration = Path(temporary) / "i3.conf"
    configuration.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                                       if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(configuration)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < deadline
            time.sleep(0.03)
        window = wifi.WifiWindow()
        window.show_all()
        window.apply_refresh_data(dict(wifi_devices=["wlan0"], ready_wifi_devices=["wlan0"],
            device_states={"wlan0": "connected"}, access_points=[network], grouped=[network],
            dbus_ok=True, daemon_ok=True, supplicant_ok=True, radio="enabled", scan_errors=[],
            snapshot=dict(addresses=["192.0.2.10/24"], connectivity="full", state=100), active_name=network_name))
        window.tree.get_selection().select_path(0)
        capture(window, "wifi-populated")
        check(window.tree.get_allocated_height() >= 90, "Wi-Fi list has insufficient room for three rows")
        check(window.tree.get_column(1).get_width() >= 170, "Compact Wi-Fi hides distinguishing network names")
        exercise_more(window, {"Signal map", "CSI 3D", "Wi-Fi Aware", "Profiles", "Repair service", "Reset adapter"}, "wifi")
        window.set_busy(True, "Connecting to fixture")
        check(not window.connect_button.is_sensitive(), "Wi-Fi Connect still enabled while busy")
        check(not window.toolbar.is_sensitive(), "Wi-Fi toolbar still permits overlapping actions")
        window.set_busy(False)
        dialog = wifi.ManualNetworkDialog(window, ["wlan0"], network_name)
        capture(dialog, "wifi-hidden-network")
        check(dialog.get_focus() is dialog.ssid, "Hidden-network form does not focus network name")
        dialog.destroy()
        dialog = wifi.WifiCredentialsDialog(window, network)
        capture(dialog, "wifi-personal")
        check(dialog.password.get_input_purpose() == Gtk.InputPurpose.PASSWORD, "Wi-Fi password has nonsecret input purpose")
        dialog.security.set_active(4)
        dialog.eap.set_active(2)
        dialog.update_security_fields()
        capture(dialog, "wifi-enterprise-tls")
        check(not dialog.password.get_visible() and dialog.client_cert.get_visible(), "TLS field visibility wrong")
        dialog.security.set_active(0)
        dialog.update_security_fields()
        check(not dialog.identity.get_visible() and not dialog.password.get_visible(), "Open network retains credential fields")
        dialog.destroy()
        window.destroy()

        window = bluetooth.BluetoothWindow()
        window.show_all()
        long_name = "Portable Bluetooth device · 긴 장치 이름 " * 5
        device = dict(address="00:11:22:33:44:66", name=long_name, signal=68, rssi=-50,
                      connected=False, paired=False, trusted=False)
        window.apply_refresh_data(dict(dbus_ok=True, daemon_ok=True, has_controller=True,
            powered="yes", devices={device["address"]: device}, address="00:11:22:33:44:00", log=""))
        window.tree.get_selection().select_path(0)
        capture(window, "bluetooth-long-device")
        check(window.tree.get_allocated_height() >= 90, "Bluetooth list has insufficient room for three rows")
        check(window.tree.get_column(0).get_width() >= 170, "Compact Bluetooth hides distinguishing device names")
        cell = window.tree.get_column(0).get_cells()[0]
        check(cell.get_property("ellipsize") == Pango.EllipsizeMode.END, "Bluetooth device column is unbounded")
        exercise_more(window, {"Signal map", "Blueman", "Repair service", "Reset adapter"}, "bluetooth")
        dialog = bluetooth.PairDialog(window, device)
        capture(dialog, "bluetooth-pin")
        check(bool(dialog.entry.get_accessible().get_name()), "Bluetooth PIN has no accessible label")
        dialog.destroy()
        window.destroy()

        class State:
            def merge(self, records, remember):
                return [{**record, "archived": False} for record in records]

            def mark_read(self, records):
                pass

            def clear_saved(self):
                clear_calls.append(True)

        notifications.NotificationState = State
        preferences = {"remember_notifications": False}
        clear_calls, save_failures = [], []
        notifications.load_preferences = lambda: preferences.copy()
        def save_preferences(**values):
            if save_failures:
                raise OSError("Private fixture preference write denied")
            preferences.update(values)
        notifications.save_preferences = save_preferences
        window = notifications.NotificationsWindow()
        window.show_all()
        record = dict(id=1, timestamp=0, appname="Fixture app", summary="Short message", body="Short detail")

        def reply(rc=0, records=None, paused=False):
            _task, done = jobs.pop()
            done(rc, (json.dumps([[record] if records is None else records]), paused))
            settle()

        reply()
        # Focus-in can queue another read. Settle it before testing focus,
        # rather than trying to focus a still-insensitive Remove control.
        for _attempt in range(3):
            if jobs:
                reply()
        remove = next(item for item in descendants(window.list) if isinstance(item, Gtk.Button))
        window.get_window().focus(Gdk.CURRENT_TIME)
        settle()
        for _attempt in range(3):
            if jobs:
                reply()
        remove.grab_focus()
        settle()
        assert window.get_focus() is remove, "Fixture did not establish Remove keyboard focus"
        previous_rows = window.list.get_children()
        window.refresh()
        reply()
        check(window.list.get_children() == previous_rows, "Unchanged notification refresh rebuilds rows")
        check(window.get_focus() is remove, "Unchanged notification refresh destroys keyboard focus")
        window.refresh()
        window.remember.grab_focus()
        reply()
        check(window.get_focus() is window.remember, "Refresh steals focus moved by user")
        window.remember.set_active(True)
        reply()
        check(preferences["remember_notifications"], "Remember toggle was not saved")
        window.remember.set_active(False)
        reply()
        check(not preferences["remember_notifications"] and len(clear_calls) == 1,
              "Privacy opt-out failed to request clearing saved history")
        save_failures.append(True)
        window.remember.set_active(True)
        check(not window.remember.get_active(), "Failed preference save falsely enables retention")
        check("Could not save preference" in window.status.get_text(), "Preference failure missing")
        save_failures.clear()
        window.pause.handler_block(window.pause_handler)
        window.pause.set_active(True)
        window.pause.handler_unblock(window.pause_handler)
        window.refresh()
        reply(paused=None)
        check(window.pause.get_active() and not window.pause.get_sensitive(),
              "Unknown DND status falsely reported as off/available")
        check("unavailable" in (window.pause.get_tooltip_text() or ""), "Unknown DND has no recovery explanation")
        long_record = dict(id=2, timestamp=0, appname="Long application · 응용 프로그램 " * 4,
                           summary="Long notification heading " * 9,
                           body=("Line with long notification details · 알림 내용\n" * 80))
        window.refresh()
        reply(records=[long_record, record])
        capture(window, "notifications-long")
        body = next(item for item in descendants(window.list) if isinstance(item, Gtk.Label) and
                    "Line with long" in item.get_text())
        check(body.get_allocated_height() <= 180, "Notification body pushes Remove/recovery off screen")
        expander = next(item for item in descendants(window.list) if isinstance(item, Gtk.Expander))
        expander.set_expanded(True)
        settle()
        check(expander.get_child().get_text() == long_record["body"][:4096], "Expanded message lost original text")
        check(not body.get_visible(), "Expanded message duplicates preview")
        expander.set_expanded(False)
        settle()
        check(body.get_visible(), "Collapsed message lost preview")
        actions.clear()
        window.perform(["set-paused", "true"])
        window.perform(["set-paused", "true"])
        check(len(actions) == 1, "Notification action submitted twice")
        _command, done = actions.pop()
        done(1, "Permission denied fixture")
        reply()
        check("failed" in window.status.get_text().lower(), "Notification refresh hides failed-action feedback")
        window.refresh()
        reply(rc=1, records=[])
        capture(window, "notifications-unavailable")
        check(any("unavailable" in item.get_text().lower() for item in descendants(window.list)
                  if isinstance(item, Gtk.Label)), "Unavailable notifications falsely show normal empty state")
        window.destroy()
        check(not window.timer_id, "Closed notifications retain refresh timer")
    finally:
        wm.terminate()
        wm.wait(timeout=5)

for failure in failures:
    print("WIRELESS_NOTIFICATION_FINDING: " + failure, flush=True)
if failures and not args.baseline:
    raise SystemExit(1)
if not failures:
    print("WIRELESS_NOTIFICATION_UI_OK managed dialogs; list space; secret labels; stable refresh focus; message/error states")
