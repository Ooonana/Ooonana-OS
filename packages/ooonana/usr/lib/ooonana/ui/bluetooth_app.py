#!/usr/bin/env python3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    GLib,
    Gtk,
    Pango,
    apply_theme,
    button,
    flow_row,
    fit_dialog,
    header,
    host_radio_unavailable,
    label,
    launch,
    message,
    more_actions,
    page_intro,
    read_file,
    run,
    run_async,
    run_async_task,
    system_dbus_ready,
)
from signal_map import SignalMapWindow  # noqa: E402
from wireless_ui import WirelessWindowState  # noqa: E402
from wireless_utils import clean_display_name, parse_bluetooth_info, parse_bluetooth_scan  # noqa: E402


SERVICE_START_TIMEOUT = 90
SERVICE_REPAIR_TIMEOUT = 150


class PairDialog(Gtk.Dialog):
    def __init__(self, parent, device):
        super().__init__(title=f"Pair {device['name']}", transient_for=parent, modal=True)
        self.set_destroy_with_parent(True)
        self.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Pair", Gtk.ResponseType.OK)
        fit_dialog(self, 500)
        area = self.get_content_area()
        area.set_border_width(16)
        area.set_spacing(10)
        area.pack_start(label("Enter a PIN only when the device requires one."), False, False, 0)
        self.entry = Gtk.Entry()
        self.entry.set_visibility(False)
        self.entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.entry.get_accessible().set_name("PIN (optional)")
        self.entry.set_placeholder_text("Automatic confirmation")
        area.pack_start(self.entry, False, False, 0)
        self.show_all()
        self.entry.grab_focus()
        self.entry.set_activates_default(True)
        self.set_default_response(Gtk.ResponseType.OK)

    def pin(self):
        return self.entry.get_text()


class BluetoothWindow(WirelessWindowState, Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Bluetooth")
        self.init_wireless_state()
        self.has_controller = False
        self.powered = False
        self.set_default_size(940, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.devices = {}
        self.scan_observations = {}
        self.signal_window = None
        self.refresh_running = False
        self.refresh_pending = False

        self.headerbar = header(self, "Bluetooth", "BlueZ device manager", "bluetooth-symbolic")
        self.refresh_button = button("Refresh", "view-refresh-symbolic", lambda *_: self.refresh())
        self.headerbar.pack_end(self.refresh_button)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_border_width(20)
        viewport = Gtk.ScrolledWindow()
        viewport.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        viewport.add(root)
        root.set_focus_vadjustment(viewport.get_vadjustment())
        self.add(viewport)
        fit_dialog(self, 940, 500)
        root.pack_start(page_intro("Bluetooth devices", "Discover, pair, trust, and connect through BlueZ."), False, False, 0)

        self.service_status = label("Service: checking", "status-warn")
        self.adapter_status = label("Adapter: checking", "status-warn")
        self.power_status = label("Power: checking", "status-warn")
        for status_label in (self.service_status, self.adapter_status, self.power_status):
            status_label.set_lines(2)
            status_label.set_ellipsize(Pango.EllipsizeMode.END)
        status_row = flow_row((self.service_status, self.adapter_status, self.power_status), 3)
        root.pack_start(status_row, False, False, 0)

        self.power_button = button("Power on", "bluetooth-active-symbolic", self.toggle_power, "suggested-action")
        self.scan_button = button("Scan", "edit-find-symbolic", self.scan_devices)
        self.repair_button = button("Repair service", "emblem-system-symbolic", self.repair_service)
        self.hardware_reset_button = button("Reset adapter", "view-refresh-symbolic", self.reset_hardware)
        self.more_button = more_actions([
            button("Signal map", "find-location-symbolic", self.show_signal_map),
            button("Blueman", "preferences-system-bluetooth-symbolic", lambda *_: launch(["blueman-manager"])),
            self.repair_button,
            self.hardware_reset_button,
        ], "More Bluetooth tools and repair actions")
        self.toolbar = flow_row([self.power_button, self.scan_button, self.more_button], max_children=3)
        root.pack_start(self.toolbar, False, False, 0)

        self.store = Gtk.ListStore(str, str, int, str, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        for title, index in (("Device", 0), ("Address", 1), ("Signal", 2), ("Paired", 3), ("Trusted", 4), ("Connected", 5)):
            renderer = Gtk.CellRendererText()
            if index == 0:
                renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
                renderer.set_property("max-width-chars", 24)
            column = Gtk.TreeViewColumn(title, renderer, text=index)
            column.set_resizable(True)
            column.set_expand(index == 0)
            self.tree.append_column(column)
        self.tree.get_selection().connect("changed", self.on_selection_changed)
        self.tree.set_tooltip_column(0)
        self.tree.connect("row-activated", lambda *_: self.activate_selected())
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(90)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(self.tree)
        root.pack_start(scroll, True, True, 0)

        self.pair_button = button("Pair", "emblem-ok-symbolic", lambda *_: self.device_action("pair"))
        self.trust_button = button("Trust", "security-high-symbolic", lambda *_: self.device_action("trust"))
        self.connect_button = button("Connect", "network-transmit-receive-symbolic", lambda *_: self.device_action("connect"), "suggested-action")
        self.disconnect_button = button("Disconnect", "network-offline-symbolic", lambda *_: self.device_action("disconnect"))
        self.remove_button = button("Remove", "edit-delete-symbolic", lambda *_: self.device_action("remove"), "destructive-action")
        device_buttons = (self.pair_button, self.trust_button, self.connect_button, self.disconnect_button, self.remove_button)
        self.device_actions = more_actions([self.trust_button, self.disconnect_button, self.remove_button], "More selected-device actions")
        self.device_actions.set_label("Device actions")
        actions = flow_row([self.pair_button, self.connect_button, self.device_actions], max_children=3, min_children=1)
        for widget in device_buttons:
            widget.set_sensitive(False)
        root.pack_start(actions, False, False, 0)
        self.actions = actions

        self.progress = Gtk.ProgressBar()
        self.progress.set_no_show_all(True)
        root.pack_start(self.progress, False, False, 0)
        self.detail = label("Select a device to manage it.", "muted")
        self.detail.set_lines(3)
        self.detail.set_ellipsize(Pango.EllipsizeMode.END)
        self.detail.set_selectable(True)
        root.pack_start(self.detail, False, False, 0)

        self.connect("destroy", self.on_destroy)
        self.connect("size-allocate", self.resized)
        self.resized(self, self.get_default_size())
        self.initial_refresh()

    def resized(self, _window, allocation):
        # Address is available in selection details; preserve device-name room.
        self.tree.get_column(1).set_visible(allocation.width >= 760)

    @staticmethod
    def btctl(*args, timeout=12, input_text=None):
        return run(["bluetoothctl", *args], admin=True, timeout=timeout, input_text=input_text)

    @staticmethod
    def set_state(widget, text, state):
        widget.set_text(text)
        widget.set_tooltip_text(text)
        context = widget.get_style_context()
        for css in ("status-good", "status-warn", "status-bad", "status-neutral"):
            context.remove_class(css)
        context.add_class(f"status-{state}")

    def update_controls(self):
        available = self.can_act()
        native = available and not host_radio_unavailable("bluetooth")
        ready = native and self.services_ready and self.has_controller and self.powered
        self.toolbar.set_sensitive(native)
        self.actions.set_sensitive(native)
        self.refresh_button.set_sensitive(available)
        self.power_button.set_sensitive(native and self.services_ready and self.has_controller)
        self.scan_button.set_sensitive(ready)
        self.repair_button.set_sensitive(native)
        self.hardware_reset_button.set_sensitive(native)
        device = self.selected_device()
        active = ready and device is not None
        self.pair_button.set_sensitive(active and not device["paired"])
        self.trust_button.set_sensitive(active and not device["trusted"])
        self.connect_button.set_sensitive(active and not device["connected"])
        self.disconnect_button.set_sensitive(active and device["connected"])
        self.remove_button.set_sensitive(active)

    def initial_refresh(self):
        if self.show_host_adapter_state():
            return
        self.set_busy(True, "Starting Bluetooth service")

        def task():
            dbus_ok = system_dbus_ready()
            daemon_rc, _daemon = run(["/bin/busybox", "pidof", "bluetoothd"], timeout=2)
            if dbus_ok and daemon_rc == 0:
                return 0, ""
            return run(
                ["ooonana-service-repair", "bluetooth"],
                admin=True,
                timeout=SERVICE_START_TIMEOUT,
            )

        def done(rc, output):
            if self.closed:
                return
            self.set_busy(False)
            if rc != 0:
                message(self, "Bluetooth repair failed", output or f"Exit status {rc}. Check /var/log/ooonana-services.log.", Gtk.MessageType.ERROR)
            self.refresh()

        run_async_task(task, done)

    def refresh(self):
        if self.closed or self.dialog_open:
            return
        if self.busy:
            return
        if self.show_host_adapter_state():
            return
        if self.refresh_running:
            self.refresh_pending = True
            return
        self.refresh_running = True
        self.set_busy(True, "Refreshing Bluetooth")

        def task():
            return 0, self.collect_refresh_data()

        def done(rc, data):
            if self.closed:
                return
            self.refresh_running = False
            if rc != 0:
                self.services_ready = False
                self.show_detail("Bluetooth refresh failed. Try Refresh or Repair service from More.")
                message(self, "Bluetooth refresh failed", str(data), Gtk.MessageType.ERROR)
            else:
                self.apply_refresh_data(data)
            self.set_busy(False)
            pending = self.refresh_pending
            self.refresh_pending = False
            if pending:
                GLib.idle_add(self.refresh)

        run_async_task(task, done)

    def show_host_adapter_state(self):
        if not host_radio_unavailable("bluetooth"):
            return False
        self.set_state(self.service_status, "Bluetooth managed by Windows", "neutral")
        self.set_state(self.adapter_status, "No controller passed into WSL", "neutral")
        self.set_state(self.power_status, "Host controls available in Windows", "neutral")
        self.toolbar.set_sensitive(False)
        self.actions.set_sensitive(False)
        self.show_detail("Use Windows controls for host Bluetooth. Pass a USB Bluetooth controller into WSL for native device management.")
        return True

    def collect_refresh_data(self):
        dbus_ok = system_dbus_ready()
        daemon_rc, _daemon = run(["/bin/busybox", "pidof", "bluetoothd"], timeout=2)
        show_rc, show = self.btctl("show", timeout=6)
        has_controller = show_rc == 0 and "Controller " in show

        powered = "no"
        address = ""
        if has_controller:
            for line in show.splitlines():
                clean = line.strip()
                if clean.startswith("Controller "):
                    address = clean.split()[1]
                elif clean.startswith("Powered:"):
                    powered = clean.split(":", 1)[1].strip()
        discovered = {}
        observations = dict(self.scan_observations)
        devices_rc, devices = self.btctl("devices", timeout=8)
        if devices_rc == 0:
            for line in devices.splitlines():
                parts = line.split(maxsplit=2)
                if len(parts) < 2 or parts[0] != "Device":
                    continue
                mac = parts[1].upper()
                fallback_name = clean_display_name(parts[2]) if len(parts) > 2 else mac
                info_rc, info = self.btctl("info", mac, timeout=6)
                values = parse_bluetooth_info(info if info_rc == 0 else "")
                observed = observations.get(mac, {})
                if values["rssi"] is None and observed.get("rssi") is not None:
                    values["rssi"] = observed["rssi"]
                    values["signal"] = observed["signal"]
                values.update({
                    "address": mac,
                    "name": clean_display_name(values["alias"] or values["name"] or fallback_name) or mac,
                })
                if values["name"] == mac and observed.get("name"):
                    values["name"] = observed["name"]
                discovered[mac] = values
        for mac, observed in observations.items():
            if mac in discovered:
                continue
            values = parse_bluetooth_info("")
            values.update(observed)
            values.update({"address": mac, "name": observed.get("name") or mac})
            discovered[mac] = values
        return {
            "dbus_ok": dbus_ok,
            "daemon_ok": daemon_rc == 0,
            "has_controller": has_controller,
            "address": address,
            "powered": powered,
            "devices": discovered,
            "log": read_file("/var/log/bluetoothd.log", "No bluetoothd log available."),
        }

    def apply_refresh_data(self, data):
        selected = self.selected_device()
        self.store.clear()
        services_ready = data["dbus_ok"] and data["daemon_ok"]
        self.services_ready = services_ready
        self.has_controller = data["has_controller"]
        self.powered = data["powered"] == "yes"
        if services_ready:
            service_text = "Services: D-Bus + BlueZ"
        elif not data["dbus_ok"]:
            service_text = "Services: system D-Bus stopped"
        else:
            service_text = "Services: BlueZ stopped"
        has_controller = data["has_controller"]
        powered = data["powered"]
        self.set_state(self.service_status, service_text, "good" if services_ready else "bad")
        self.set_state(self.adapter_status, "Adapter: ready" if has_controller else "Adapter: not detected", "good" if has_controller else "bad")
        self.set_state(self.power_status, f"Power: {powered}", "good" if powered == "yes" else "warn")
        self.power_button.set_label("Power off" if powered == "yes" else "Power on")
        self.power_button.set_sensitive(has_controller)
        self.scan_button.set_sensitive(has_controller and powered == "yes")

        discovered = data["devices"]
        self.devices = discovered
        for mac, values in sorted(discovered.items(), key=lambda item: (item[1]["connected"], item[1]["paired"], item[1]["signal"]), reverse=True):
            self.store.append([
                values["name"], mac, values["signal"],
                "yes" if values["paired"] else "no",
                "yes" if values["trusted"] else "no",
                "yes" if values["connected"] else "no",
            ])
        if selected:
            for row in self.store:
                if row[1] == selected["address"]:
                    self.tree.get_selection().select_iter(row.iter)
                    break
        self.update_signal_map()
        if not has_controller:
            log = data["log"]
            self.show_detail("No controller found. Repair reloads Bluetooth modules, clears RFKill, restarts BlueZ, then retriggers udev.\n\n" + log[-1200:])
        elif not discovered:
            self.show_detail(f"Adapter {data['address'] or 'ready'}. No known devices. Press Scan to discover nearby devices.")
        else:
            self.show_detail(f"{len(discovered)} device(s). Signal appears while devices advertise during a scan.")
        self.update_controls()

    def selected_device(self):
        model, tree_iter = self.tree.get_selection().get_selected()
        return self.devices.get(model[tree_iter][1]) if tree_iter else None

    def on_selection_changed(self, selection):
        if not self.can_act():
            return
        self.update_controls()
        device = self.selected_device()
        if device:
            self.show_detail(
                f"{device['name']}\n{device['address']} | Signal: {device['signal']}%\n"
                f"Paired: {'yes' if device['paired'] else 'no'}  Trusted: {'yes' if device['trusted'] else 'no'}  Connected: {'yes' if device['connected'] else 'no'}"
            )

    def toggle_power(self, widget):
        if not self.can_act():
            return
        target = "off" if "off" in widget.get_label().lower() else "on"
        self.run_bt_action(["power", target], f"Turning Bluetooth {target}")

    def scan_devices(self, _widget):
        if not self.can_act():
            return
        self.set_busy(True, "Scanning for 12 seconds")

        def task():
            self.btctl("power", "on", timeout=8)
            self.btctl("pairable", "on", timeout=8)
            return self.btctl("--timeout", "12", "scan", "on", timeout=18)

        def done(rc, output):
            if self.closed:
                return
            self.set_busy(False)
            self.scan_observations = parse_bluetooth_scan(output)
            if rc != 0:
                message(self, "Bluetooth scan failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh()

        run_async_task(task, done)

    def device_action(self, action):
        if not self.can_act():
            return
        device = self.selected_device()
        if not device:
            message(self, "Select device", "Choose a Bluetooth device first.")
            return
        if action == "pair":
            self.ask_pair(device)
        elif action == "connect":
            if device["paired"]:
                self.connect_device(device)
            else:
                self.ask_pair(device)
        else:
            if action == "remove" and not self.confirm_action("Remove Bluetooth device?",
                    f"Remove {device['name']} from saved devices? Pairing again may require its PIN.", "Remove device"):
                return
            self.run_bt_action([action, device["address"]], f"{action.title()} {device['name']}")

    def activate_selected(self):
        if not self.can_act():
            return
        device = self.selected_device()
        if not device:
            return
        if device["paired"]:
            self.connect_device(device)
        else:
            self.ask_pair(device)

    def ask_pair(self, device):
        if not self.can_act():
            return
        self.dialog_open = True
        dialog = PairDialog(self, device)
        response = dialog.run()
        pin = dialog.pin()
        dialog.destroy()
        self.dialog_open = False
        if response == Gtk.ResponseType.OK and not self.closed:
            self.pair_device(device, pin)

    def pair_device(self, device, pin):
        if not self.can_act():
            return
        self.set_busy(True, f"Pairing {device['name']}")

        def task():
            mac = device["address"]
            self.btctl("power", "on", timeout=8)
            self.btctl("pairable", "on", timeout=8)
            self.btctl("--timeout", "8", "scan", "on", timeout=14)
            answers = ""
            if pin:
                answers += pin + "\n"
            answers += "yes\n"
            rc, output = self.btctl("--timeout", "40", "--agent", "KeyboardDisplay", "pair", mac, timeout=48, input_text=answers)
            state = {}
            info = ""
            for _attempt in range(5):
                info_rc, info = self.btctl("info", mac, timeout=8)
                state = parse_bluetooth_info(info if info_rc == 0 else "")
                if state["paired"]:
                    break
                time.sleep(1)
            if not state["paired"]:
                return rc or 1, (
                    output + "\n" + info
                    + "\nBlueZ did not confirm pairing. Try Blueman for device-specific passkey entry."
                ).strip()
            self.btctl("trust", mac, timeout=12)
            if state["connected"]:
                return 0, output or "BlueZ confirmed pairing and connection."
            connect_rc, connect_output = self.connect_with_retry(mac)
            if connect_rc != 0:
                return connect_rc, (output + "\nPaired and trusted, but connection failed:\n" + connect_output).strip()
            return 0, (output + "\n" + connect_output).strip()

        self.finish_device_task(task)

    def connect_device(self, device):
        if not self.can_act():
            return
        self.set_busy(True, f"Connecting {device['name']}")

        def task():
            mac = device["address"]
            return self.connect_with_retry(mac)

        self.finish_device_task(task)

    def connect_with_retry(self, mac):
        errors = []
        run(["rfkill", "unblock", "bluetooth"], admin=True, timeout=8)
        self.btctl("power", "on", timeout=8)
        self.btctl("pairable", "on", timeout=8)
        trust_rc, trust_output = self.btctl("trust", mac, timeout=12)
        if trust_rc != 0:
            return trust_rc, trust_output

        for attempt in range(3):
            rc, output = self.btctl("--timeout", "30", "connect", mac, timeout=38)
            state, info = self.wait_for_connection_state(mac, timeout=10)
            if state["connected"]:
                return 0, output or "BlueZ confirmed connection."
            errors.append((output + "\n" + info).strip() or "BlueZ did not confirm Connected: yes.")
            if attempt < 2:
                self.btctl("--timeout", "10", "scan", "on", timeout=16)
                time.sleep(1)
        show_rc, show = self.btctl("show", timeout=8)
        if show_rc == 0:
            errors.append("Adapter state:\n" + show)
        return rc or 1, "\n".join(errors)

    def wait_for_connection_state(self, mac, timeout=10):
        deadline = time.monotonic() + timeout
        state = parse_bluetooth_info("")
        info = ""
        while time.monotonic() < deadline:
            info_rc, info = self.btctl("info", mac, timeout=8)
            state = parse_bluetooth_info(info if info_rc == 0 else "")
            if state["connected"]:
                return state, info
            time.sleep(1)
        return state, info

    def finish_device_task(self, task):
        def done(rc, output):
            if self.closed:
                return
            self.set_busy(False)
            if rc != 0:
                message(self, "Bluetooth action failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh()

        run_async_task(task, done)

    def run_bt_action(self, args, progress_text):
        if not self.can_act():
            return
        self.set_busy(True, progress_text)

        def done(rc, output):
            if self.closed:
                return
            self.set_busy(False)
            if rc != 0:
                message(self, "Bluetooth action failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh()

        run_async(["bluetoothctl", *args], done, admin=True, timeout=35)

    def show_signal_map(self, _widget):
        if self.signal_window is None or not self.signal_window.get_visible():
            self.signal_window = SignalMapWindow("Bluetooth signal map", "bluetooth")
        self.update_signal_map()
        self.signal_window.show_all()
        self.signal_window.present()

    def update_signal_map(self):
        if not self.signal_window:
            return
        self.signal_window.update_items([
            {
                "key": mac,
                "name": values["name"],
                "signal": values["signal"] if values["signal"] > 0 else 12,
                "signal_known": values["rssi"] is not None,
                "category": "device",
            }
            for mac, values in self.devices.items()
        ])

    def repair_service(self, _widget):
        if not self.can_act():
            return
        self.set_busy(True, "Repairing Bluetooth")

        def done(rc, output):
            if self.closed:
                return
            self.set_busy(False)
            self.refresh()
            if rc != 0:
                message(self, "Bluetooth repair failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)

        run_async(
            ["ooonana-service-repair", "force-bluetooth"],
            done,
            admin=True,
            timeout=SERVICE_REPAIR_TIMEOUT,
        )

    def reset_hardware(self, _widget):
        if not self.confirm_action("Reset Bluetooth adapter?",
                "Use only when normal service repair fails. Active Bluetooth connections will be interrupted.",
                "Reset adapter"):
            return
        self.set_busy(True, "Resetting Bluetooth adapter")

        def done(rc, output):
            if self.closed:
                return
            self.set_busy(False)
            if rc != 0:
                message(self, "Bluetooth reset failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh()

        run_async(
            ["ooonana-service-repair", "deep-bluetooth"],
            done,
            admin=True,
            timeout=SERVICE_REPAIR_TIMEOUT,
        )


def main():
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana Bluetooth")
        print("actions: power scan pair agent trust connect-retry disconnect remove signal-map repair")
        print("OOONANA_BLUETOOTH_NATIVE_OK")
        return 0
    apply_theme()
    window = BluetoothWindow()
    window.show_all()
    if window.progress.get_visible():
        window.progress.show()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
