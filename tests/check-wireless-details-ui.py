#!/usr/bin/env python3
"""Owned GTK/i3 advanced wireless forms/lifecycle. Never executes radio commands."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1" and os.getuid() != 0
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme
import wifi_app as wifi
import bluetooth_app as bluetooth
import wireless_ui

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", int(96 * 1024 * float(os.environ.get("OOONANA_GUI_TEXT_SCALE", "1.0"))))
apply_theme()
findings, jobs, actions, notices = [], [], [], []
for module in (wifi, bluetooth):
    module.run = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Unexpected backend command"))
    module.run_async_task = lambda task, done: jobs.append((task, done))
    module.run_async = lambda command, done, **kwargs: actions.append((command, done))
    module.message = lambda _parent, title, *_args, **_kwargs: notices.append(title)
wifi.host_radio_unavailable = bluetooth.host_radio_unavailable = lambda _kind: False
network = dict(ssid="Fixture school network", signal=77, security_label="WPA2 Enterprise", security_kind="enterprise",
               security="WPA2 802.1X", connected=False, ap_count=1, device="wlan0", bssid="00:11:22:33:44:55")
device = dict(address="00:11:22:33:44:66", name="Fixture Bluetooth device", signal=68, rssi=-50, connected=False, paired=False, trusted=False)
wifi_data = dict(wifi_devices=["wlan0"], ready_wifi_devices=["wlan0"], device_states={"wlan0": "disconnected"},
                 access_points=[network], grouped=[network], dbus_ok=True, daemon_ok=True, supplicant_ok=True,
                 radio="enabled", scan_errors=[], snapshot=None, active_name="")
bt_data = dict(dbus_ok=True, daemon_ok=True, has_controller=True, powered="yes", devices={device["address"]: device}, address="00:11:22:33:44:00", log="")


def check(condition, detail):
    if not condition:
        findings.append(detail)
        print("WIRELESS_DETAILS_FINDING: " + detail, flush=True)


def settle(seconds=.2):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.005)


def capture(window, name):
    settle()
    root = Gdk.get_default_root_window()
    rect = window.get_window().get_frame_extents()
    check(0 <= rect.x and rect.x + rect.width <= root.get_width() and
          0 <= rect.y and rect.y + rect.height <= root.get_height(), f"{name}: frame outside display ({rect.x},{rect.y} {rect.width}x{rect.height})")
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(out / (name + ".png")), "png", [], [])


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


def respond(name, inspect=None, title=None):
    def answer():
        dialog = next(item for item in Gtk.Window.list_toplevels() if isinstance(item, Gtk.Dialog) and item.get_visible() and (title is None or item.get_title() == title))
        try:
            capture(dialog, name)
            if inspect:
                inspect(dialog)
        finally:
            dialog.response(Gtk.ResponseType.CANCEL)
        return False
    GLib.timeout_add(350, answer)


def complete_refresh(window, data):
    # Normalize diagnostic baseline after detecting duplicate refresh requests.
    jobs.clear()
    window.refresh_running = False
    window.set_busy(False)
    window.refresh()
    _task, done = jobs.pop()
    done(0, data)
    jobs.clear()


with tempfile.TemporaryDirectory(prefix="ooonana-wireless-details-") as temporary:
    temporary = Path(temporary)
    config = temporary / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines() if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < deadline
            time.sleep(.03)
        parent = Gtk.Window(title="Ooonana QA wireless forms")
        parent.show_all()
        dialog = wifi.WifiCredentialsDialog(parent, network)
        for security in range(7):
            dialog.security.set_active(security)
            for eap in range(4) if security in (4, 5) else (0,):
                dialog.eap.set_active(eap)
                dialog.update_security_fields()
                tls = security in (4, 5) and eap == 2
                check(dialog.password.get_visible() == (security in (2, 3, 6) or security in (4, 5) and not tls), "Security/EAP password visibility wrong")
                check(dialog.client_cert.get_visible() == tls, "Security/EAP client certificate visibility wrong")
        dialog.security.set_active(4)
        dialog.eap.set_active(2)
        dialog.ca_policy.set_active_id("custom")
        dialog.identity.set_text("fixture@example.invalid")
        dialog.password.set_text("  fixture password  ")
        for field in (dialog.ca_cert, dialog.client_cert, dialog.private_key):
            path = temporary / ("fixture-" + field.get_accessible().get_name().replace(" ", "-") + ".pem")
            path.write_text("Owned UI selection fixture, not a real certificate/key.\n")
            field.set_filename(str(path))
        advanced = next(item for item in descendants(dialog) if isinstance(item, Gtk.Expander))
        advanced.set_expanded(True)
        dialog.ipv4_mode.set_active_id("manual")
        dialog.proxy_mode.set_active_id("auto")
        dialog.ipv4_address.set_text("192.0.2.20/24")
        dialog.ipv4_gateway.set_text("192.0.2.1")
        dialog.ipv4_dns.set_text("192.0.2.53, 198.51.100.53")
        dialog.proxy_url.set_text("https://example.invalid/proxy.pac")
        capture(dialog, "wifi-advanced-tls")
        check(dialog.get_destroy_with_parent(), "Credentials dialog survives parent close")
        check(dialog.values()["password"] == "  fixture password  ", "Password whitespace changed")
        dialog.ipv4_address.set_text("not-an-address/99")
        error = dialog.validate()
        check(bool(error), "Malformed manual IPv4 passes UI validation")
        if hasattr(dialog, "show_error") and error:
            dialog.show_error(error)
            capture(dialog, "wifi-inline-validation")
            check(dialog.get_focus() is dialog.ipv4_address, "Invalid field did not receive focus")
            position = dialog.ipv4_address.translate_coordinates(dialog.form_scroll, 0, 0)
            check(position is not None and position[1] >= 0 and position[1] + dialog.ipv4_address.get_allocated_height() <= dialog.form_scroll.get_allocated_height(), "Invalid field remains clipped after focus")
        else:
            check(False, "Credentials lack inline field-error recovery")
        dialog.ipv4_address.set_text("192.0.2.20/24")
        check(not dialog.validate(), "Valid advanced form rejected")
        for field, invalid, valid in ((dialog.ipv4_gateway, "999.2.3.4", "192.0.2.1"),
                                      (dialog.ipv4_dns, "192.0.2.53, invalid", "192.0.2.53, 198.51.100.53"),
                                      (dialog.proxy_url, "", "https://example.invalid/proxy.pac")):
            field.set_text(invalid)
            check(bool(dialog.validate()) and dialog.error_field is field, "Advanced invalid input not identified")
            field.set_text(valid)
        check(dialog.password.get_text() == "  fixture password  ", "Validation changed secret draft")
        # Real picker Cancel; no file selected from user's directories.
        dialog.ca_cert.grab_focus()
        def inspect_picker(picker):
            check(picker.get_modal(), "Certificate picker not modal")
            check(picker.get_destroy_with_parent(), "Certificate picker survives parent close")
            check(picker.get_default_widget() is picker.get_widget_for_response(Gtk.ResponseType.CANCEL), "Certificate picker lacks default Cancel")
        respond("wifi-certificate-picker", inspect_picker, "Choose CA certificate")
        target = dialog.ca_cert if isinstance(dialog.ca_cert, Gtk.Button) else next(item for item in descendants(dialog.ca_cert) if isinstance(item, Gtk.Button))
        before = dialog.ca_cert.get_filename()
        target.clicked()
        settle(.6)
        check(dialog.ca_cert.get_filename() == before, "Certificate Cancel changed selection")
        dialog.destroy()
        parent.destroy()

        for module, cls, data, title in ((wifi, wifi.WifiWindow, wifi_data, "wifi"), (bluetooth, bluetooth.BluetoothWindow, bt_data, "bluetooth")):
            jobs.clear()
            window = cls()
            window.show_all()
            initial = jobs[0][1]
            window.refresh()
            check(len(jobs) == 1, title + ": refresh overlaps startup action")
            jobs.clear()
            window.refresh_running = False
            initial(0, "")
            jobs.clear()
            complete_refresh(window, data)
            window.tree.get_selection().select_path(0)
            capture(window, title + "-populated")
            window.refresh()
            done = jobs[-1][1]
            window.refresh()
            check(not window.toolbar.is_sensitive() and not window.actions.is_sensitive(), title + ": repeated refresh re-enables pending controls")
            done(0, data)
            jobs.clear()
            window.tree.get_selection().select_path(0)
            window.set_busy(True, "Fixture operation pending")
            pulse = window.progress_source
            check(bool(pulse), title + ": busy operation lacks sustained progress")
            window.on_selection_changed(window.tree.get_selection())
            check(window.detail.get_text() == "Fixture operation pending", title + ": selection hides pending operation")
            actions.clear()
            if title == "wifi":
                window.toggle_radio(window.radio_button)
            else:
                window.toggle_power(window.power_button)
            check(not actions, title + ": duplicate action submitted while busy")
            actions.clear()
            window.set_busy(False)
            check(not window.progress_source, title + ": idle progress timer remains")
            motion = wireless_ui.transition_ms
            wireless_ui.transition_ms = lambda: 0
            window.set_busy(True, "Reduced-motion pending operation")
            check(not window.progress_source and not window.progress.get_visible() and window.detail.get_text() == "Reduced-motion pending operation", title + ": reduced motion has animated/hidden feedback")
            window.set_busy(False)
            wireless_ui.transition_ms = motion
            complete_refresh(window, data)
            unavailable = dict(data, dbus_ok=False, daemon_ok=False)
            window.apply_refresh_data(unavailable)
            window.set_busy(False)
            check(not window.scan_button.is_sensitive() and not window.connect_button.is_sensitive(), title + ": stopped services retain live controls")
            check(window.repair_button.is_sensitive(), title + ": service failure has no Repair recovery")
            check(window.detail.get_tooltip_text() == window.detail.get_text(), title + ": stale details tooltip")
            complete_refresh(window, data)
            window.tree.get_selection().select_path(0)
            if title == "bluetooth":
                respond("bluetooth-remove-cancel", lambda remove: check(remove.get_default_widget() is remove.get_widget_for_response(Gtk.ResponseType.CANCEL), "Bluetooth Remove lacks default Cancel"))
                window.device_action("remove")
                check(not actions, "Bluetooth Remove Cancel dispatched command")
            respond(title + "-reset-cancel", lambda reset: (
                check(reset.get_destroy_with_parent(), title + ": reset dialog survives parent close"),
                check(reset.get_default_widget() is reset.get_widget_for_response(Gtk.ResponseType.CANCEL), title + ": reset lacks default Cancel")))
            window.reset_hardware(None)
            check(not actions, title + ": Cancel submitted hardware reset")
            window.refresh_running = False
            complete_refresh(window, data)
            window.tree.get_selection().select_path(0)
            if title == "wifi":
                window.toggle_radio(window.radio_button)
            else:
                window.toggle_power(window.power_button)
            late = actions[-1][1]
            before = len(notices)
            window.destroy()
            check(not window.progress_source, title + ": closed progress timer remains")
            jobs.clear()
            try:
                late(1, "Fixture delayed service denial")
            except Exception as error:
                check(False, title + ": closed callback raises " + type(error).__name__)
            check(len(notices) == before and not jobs, title + ": closed callback creates dialogs/refresh")
            actions.clear()
            settle()
            parent_close = cls()
            parent_close.show_all()
            jobs.clear()
            parent_close.set_busy(False)
            GLib.timeout_add(200, lambda: (parent_close.destroy(), False)[1])
            parent_close.reset_hardware(None)
            check(parent_close.closed and not actions, title + ": closing confirmation parent submitted reset")
            jobs.clear()
    finally:
        wm.terminate()
        wm.wait(timeout=5)

if findings:
    raise SystemExit(1)
print("WIRELESS_DETAILS_UI_OK advanced fields/certificates; secret preservation; busy/duplicate/closed refusal; safe reset")
