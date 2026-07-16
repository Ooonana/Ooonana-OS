#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    Gtk,
    apply_theme,
    button,
    header,
    label,
    launch,
    message,
    page_intro,
    read_file,
    run,
    run_async,
    run_async_task,
)
from signal_map import SignalMapWindow  # noqa: E402
from wireless_utils import parse_bluetooth_info  # noqa: E402


class PairDialog(Gtk.Dialog):
    def __init__(self, parent, device):
        super().__init__(title=f"Pair {device['name']}", transient_for=parent, modal=True)
        self.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Pair", Gtk.ResponseType.OK)
        self.set_default_size(500, -1)
        area = self.get_content_area()
        area.set_border_width(16)
        area.set_spacing(10)
        area.pack_start(label("Enter a PIN only when the device requires one."), False, False, 0)
        self.entry = Gtk.Entry()
        self.entry.set_visibility(False)
        self.entry.set_placeholder_text("Automatic confirmation")
        area.pack_start(self.entry, False, False, 0)
        self.show_all()

    def pin(self):
        return self.entry.get_text()


class BluetoothWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Bluetooth")
        self.set_default_size(980, 660)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.devices = {}
        self.signal_window = None

        self.headerbar = header(self, "Bluetooth", "BlueZ device manager", "bluetooth-symbolic")
        self.refresh_button = button("Refresh", "view-refresh-symbolic", lambda *_: self.refresh())
        self.headerbar.pack_end(self.refresh_button)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_border_width(20)
        self.add(root)
        root.pack_start(page_intro("Bluetooth devices", "Discover, pair, trust, and connect through BlueZ."), False, False, 0)

        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.service_status = label("Service: checking", "status-warn")
        self.adapter_status = label("Adapter: checking", "status-warn")
        self.power_status = label("Power: checking", "status-warn")
        status_row.pack_start(self.service_status, False, False, 0)
        status_row.pack_start(self.adapter_status, False, False, 0)
        status_row.pack_start(self.power_status, False, False, 0)
        root.pack_start(status_row, False, False, 0)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.power_button = button("Power on", "bluetooth-active-symbolic", self.toggle_power, "suggested-action")
        self.scan_button = button("Scan", "edit-find-symbolic", self.scan_devices)
        toolbar.pack_start(self.power_button, False, False, 0)
        toolbar.pack_start(self.scan_button, False, False, 0)
        toolbar.pack_start(button("Signal map", "find-location-symbolic", self.show_signal_map), False, False, 0)
        toolbar.pack_start(button("Blueman", "preferences-system-bluetooth-symbolic", lambda *_: launch(["blueman-manager"])), False, False, 0)
        toolbar.pack_end(button("Repair service", "emblem-system-symbolic", self.repair_service), False, False, 0)
        root.pack_start(toolbar, False, False, 0)

        self.store = Gtk.ListStore(str, str, int, str, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        for title, index in (("Device", 0), ("Address", 1), ("Signal", 2), ("Paired", 3), ("Trusted", 4), ("Connected", 5)):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=index)
            column.set_resizable(True)
            column.set_expand(index == 0)
            self.tree.append_column(column)
        self.tree.get_selection().connect("changed", self.on_selection_changed)
        self.tree.connect("row-activated", lambda *_: self.activate_selected())
        scroll = Gtk.ScrolledWindow()
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(self.tree)
        root.pack_start(scroll, True, True, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.pair_button = button("Pair", "emblem-ok-symbolic", lambda *_: self.device_action("pair"))
        self.trust_button = button("Trust", "security-high-symbolic", lambda *_: self.device_action("trust"))
        self.connect_button = button("Connect", "network-transmit-receive-symbolic", lambda *_: self.device_action("connect"), "suggested-action")
        self.disconnect_button = button("Disconnect", "network-offline-symbolic", lambda *_: self.device_action("disconnect"))
        self.remove_button = button("Remove", "edit-delete-symbolic", lambda *_: self.device_action("remove"), "destructive-action")
        for widget in (self.pair_button, self.trust_button, self.connect_button, self.disconnect_button, self.remove_button):
            actions.pack_start(widget, False, False, 0)
            widget.set_sensitive(False)
        root.pack_start(actions, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_no_show_all(True)
        root.pack_start(self.progress, False, False, 0)
        self.detail = label("Select a device to manage it.", "muted")
        self.detail.set_selectable(True)
        root.pack_start(self.detail, False, False, 0)

        self.connect("destroy", Gtk.main_quit)
        self.initial_refresh()

    @staticmethod
    def btctl(*args, timeout=12, input_text=None):
        return run(["bluetoothctl", *args], admin=True, timeout=timeout, input_text=input_text)

    @staticmethod
    def set_state(widget, text, state):
        widget.set_text(text)
        context = widget.get_style_context()
        for css in ("status-good", "status-warn", "status-bad"):
            context.remove_class(css)
        context.add_class(f"status-{state}")

    def set_busy(self, busy, text=""):
        self.refresh_button.set_sensitive(not busy)
        self.power_button.set_sensitive(not busy)
        self.scan_button.set_sensitive(not busy)
        if busy:
            self.progress.set_no_show_all(False)
            self.progress.show()
            self.progress.pulse()
            self.progress.set_text(text)
            self.progress.set_show_text(bool(text))
        else:
            self.progress.hide()

    def initial_refresh(self):
        daemon_rc, _daemon = run(["/bin/busybox", "pidof", "bluetoothd"], timeout=2)
        if daemon_rc == 0:
            self.refresh()
            return
        self.set_busy(True, "Starting Bluetooth service")

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "Bluetooth repair failed", output or f"Exit status {rc}. Check /var/log/ooonana-services.log.", Gtk.MessageType.ERROR)
            self.refresh()

        run_async(["ooonana-service-repair", "bluetooth"], done, admin=True, timeout=20)

    def refresh(self):
        self.store.clear()
        daemon_rc, _daemon = run(["/bin/busybox", "pidof", "bluetoothd"], timeout=2)
        show_rc, show = self.btctl("show", timeout=6)
        has_controller = show_rc == 0 and "Controller " in show
        self.set_state(self.service_status, "Service: running" if daemon_rc == 0 else "Service: stopped", "good" if daemon_rc == 0 else "bad")
        self.set_state(self.adapter_status, "Adapter: ready" if has_controller else "Adapter: not detected", "good" if has_controller else "bad")

        powered = "no"
        address = ""
        if has_controller:
            for line in show.splitlines():
                clean = line.strip()
                if clean.startswith("Controller "):
                    address = clean.split()[1]
                elif clean.startswith("Powered:"):
                    powered = clean.split(":", 1)[1].strip()
        self.set_state(self.power_status, f"Power: {powered}", "good" if powered == "yes" else "warn")
        self.power_button.set_label("Power off" if powered == "yes" else "Power on")
        self.power_button.set_sensitive(has_controller)
        self.scan_button.set_sensitive(has_controller and powered == "yes")

        discovered = {}
        devices_rc, devices = self.btctl("devices", timeout=8)
        if devices_rc == 0:
            for line in devices.splitlines():
                parts = line.split(maxsplit=2)
                if len(parts) < 2 or parts[0] != "Device":
                    continue
                mac = parts[1].upper()
                fallback_name = parts[2] if len(parts) > 2 else mac
                info_rc, info = self.btctl("info", mac, timeout=6)
                values = parse_bluetooth_info(info if info_rc == 0 else "")
                values.update({"address": mac, "name": values["alias"] or values["name"] or fallback_name})
                discovered[mac] = values
        self.devices = discovered
        for mac, values in sorted(discovered.items(), key=lambda item: (item[1]["connected"], item[1]["paired"], item[1]["signal"]), reverse=True):
            self.store.append([
                values["name"], mac, values["signal"],
                "yes" if values["paired"] else "no",
                "yes" if values["trusted"] else "no",
                "yes" if values["connected"] else "no",
            ])
        self.update_signal_map()
        if not has_controller:
            log = read_file("/var/log/bluetoothd.log", "No bluetoothd log available.")
            self.detail.set_text("No controller found. Repair reloads Bluetooth modules, clears RFKill, restarts BlueZ, then retriggers udev.\n\n" + log[-1200:])
        elif not discovered:
            self.detail.set_text(f"Adapter {address or 'ready'}. No known devices. Press Scan to discover nearby devices.")
        else:
            self.detail.set_text(f"{len(discovered)} device(s). Signal appears while devices advertise during a scan.")

    def selected_device(self):
        model, tree_iter = self.tree.get_selection().get_selected()
        return self.devices.get(model[tree_iter][1]) if tree_iter else None

    def on_selection_changed(self, selection):
        _model, tree_iter = selection.get_selected()
        active = tree_iter is not None
        for widget in (self.pair_button, self.trust_button, self.connect_button, self.disconnect_button, self.remove_button):
            widget.set_sensitive(active)
        device = self.selected_device()
        if device:
            self.pair_button.set_sensitive(not device["paired"])
            self.trust_button.set_sensitive(not device["trusted"])
            self.connect_button.set_sensitive(not device["connected"])
            self.disconnect_button.set_sensitive(device["connected"])
            self.detail.set_text(
                f"{device['name']}\n{device['address']} | Signal: {device['signal']}%\n"
                f"Paired: {'yes' if device['paired'] else 'no'}  Trusted: {'yes' if device['trusted'] else 'no'}  Connected: {'yes' if device['connected'] else 'no'}"
            )

    def toggle_power(self, widget):
        target = "off" if "off" in widget.get_label().lower() else "on"
        self.run_bt_action(["power", target], f"Turning Bluetooth {target}")

    def scan_devices(self, _widget):
        self.set_busy(True, "Scanning for 12 seconds")

        def task():
            self.btctl("power", "on", timeout=8)
            self.btctl("pairable", "on", timeout=8)
            return self.btctl("--timeout", "12", "scan", "on", timeout=18)

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "Bluetooth scan failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh()

        run_async_task(task, done)

    def device_action(self, action):
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
            self.run_bt_action([action, device["address"]], f"{action.title()} {device['name']}")

    def activate_selected(self):
        device = self.selected_device()
        if not device:
            return
        if device["paired"]:
            self.connect_device(device)
        else:
            self.ask_pair(device)

    def ask_pair(self, device):
        dialog = PairDialog(self, device)
        response = dialog.run()
        pin = dialog.pin()
        dialog.destroy()
        if response == Gtk.ResponseType.OK:
            self.pair_device(device, pin)

    def pair_device(self, device, pin):
        self.set_busy(True, f"Pairing {device['name']}")

        def task():
            mac = device["address"]
            self.btctl("power", "on", timeout=8)
            self.btctl("pairable", "on", timeout=8)
            answers = ""
            if pin:
                answers += pin + "\n"
            answers += "yes\n"
            rc, output = self.btctl("--timeout", "40", "--agent", "KeyboardDisplay", "pair", mac, timeout=48, input_text=answers)
            info_rc, info = self.btctl("info", mac, timeout=8)
            state = parse_bluetooth_info(info if info_rc == 0 else "")
            if not state["paired"]:
                return rc or 1, output or "BlueZ did not confirm pairing. Try Blueman for device-specific passkey entry."
            trust_rc, trust_output = self.btctl("trust", mac, timeout=12)
            if trust_rc != 0:
                return trust_rc, trust_output
            connect_rc, connect_output = self.btctl("--timeout", "30", "connect", mac, timeout=38)
            if connect_rc != 0:
                return connect_rc, (output + "\nPaired and trusted, but connection failed:\n" + connect_output).strip()
            return 0, (output + "\n" + connect_output).strip()

        self.finish_device_task(task)

    def connect_device(self, device):
        self.set_busy(True, f"Connecting {device['name']}")

        def task():
            mac = device["address"]
            if not device["trusted"]:
                rc, output = self.btctl("trust", mac, timeout=12)
                if rc != 0:
                    return rc, output
            return self.btctl("--timeout", "30", "connect", mac, timeout=38)

        self.finish_device_task(task)

    def finish_device_task(self, task):
        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "Bluetooth action failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh()

        run_async_task(task, done)

    def run_bt_action(self, args, progress_text):
        self.set_busy(True, progress_text)

        def done(rc, output):
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
            {"key": mac, "name": values["name"], "signal": values["signal"]}
            for mac, values in self.devices.items()
            if values["signal"] > 0
        ])

    def repair_service(self, _widget):
        self.set_busy(True, "Repairing Bluetooth")

        def done(rc, output):
            self.set_busy(False)
            self.refresh()
            if rc != 0:
                message(self, "Bluetooth repair failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)

        run_async(["ooonana-service-repair", "force-bluetooth"], done, admin=True, timeout=30)


def main():
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana Bluetooth")
        print("actions: power scan pair agent trust connect disconnect remove map repair")
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
