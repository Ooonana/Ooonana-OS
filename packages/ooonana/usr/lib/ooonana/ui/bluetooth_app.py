#!/usr/bin/env python3
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    Gtk,
    apply_theme,
    ask_text,
    button,
    header,
    label,
    launch,
    message,
    page_intro,
    read_file,
    run,
    run_async,
)


class BluetoothWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Bluetooth")
        self.set_default_size(920, 620)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.headerbar = header(
            self,
            "Bluetooth",
            "BlueZ device manager",
            "bluetooth-symbolic",
        )
        self.refresh_button = button(
            "Refresh", "view-refresh-symbolic", lambda *_: self.refresh()
        )
        self.headerbar.pack_end(self.refresh_button)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_border_width(20)
        self.add(root)
        root.pack_start(
            page_intro(
                "Bluetooth devices",
                "Power adapter, scan nearby devices, then pair, trust, and connect.",
            ),
            False,
            False,
            0,
        )

        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.service_status = label("Service: checking", "status-warn")
        self.adapter_status = label("Adapter: checking", "status-warn")
        self.power_status = label("Power: checking", "status-warn")
        status_row.pack_start(self.service_status, False, False, 0)
        status_row.pack_start(self.adapter_status, False, False, 0)
        status_row.pack_start(self.power_status, False, False, 0)
        root.pack_start(status_row, False, False, 0)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.power_button = button(
            "Power on", "bluetooth-active-symbolic", self.toggle_power, "suggested-action"
        )
        self.scan_button = button(
            "Scan", "edit-find-symbolic", self.scan_devices
        )
        toolbar.pack_start(self.power_button, False, False, 0)
        toolbar.pack_start(self.scan_button, False, False, 0)
        toolbar.pack_start(
            button("Blueman", "preferences-system-bluetooth-symbolic", lambda *_: launch(["blueman-manager"])),
            False,
            False,
            0,
        )
        toolbar.pack_end(
            button("Repair service", "emblem-system-symbolic", self.repair_service),
            False,
            False,
            0,
        )
        root.pack_start(toolbar, False, False, 0)

        self.store = Gtk.ListStore(str, str, str, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        columns = [
            ("Device", 0),
            ("Address", 1),
            ("Paired", 2),
            ("Trusted", 3),
            ("Connected", 4),
        ]
        for title, index in columns:
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=index)
            column.set_resizable(True)
            column.set_expand(index == 0)
            self.tree.append_column(column)
        self.tree.get_selection().connect("changed", self.on_selection_changed)
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
        for widget in (
            self.pair_button,
            self.trust_button,
            self.connect_button,
            self.disconnect_button,
            self.remove_button,
        ):
            actions.pack_start(widget, False, False, 0)
            widget.set_sensitive(False)
        root.pack_start(actions, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_no_show_all(True)
        root.pack_start(self.progress, False, False, 0)
        self.detail = label("Select device to manage it.", "muted")
        self.detail.set_selectable(True)
        root.pack_start(self.detail, False, False, 0)

        self.connect("destroy", Gtk.main_quit)
        self.repair_then_refresh()

    @staticmethod
    def btctl(*args, timeout=12):
        return run(["bluetoothctl", *args], admin=True, timeout=timeout)

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

    def repair_then_refresh(self):
        self.set_busy(True, "Starting Bluetooth service")

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(
                    self,
                    "Bluetooth repair failed",
                    output or f"Exit status {rc}. Check /var/log/ooonana-services.log.",
                    Gtk.MessageType.ERROR,
                )
            self.refresh()

        run_async(
            ["ooonana-service-repair", "bluetooth"],
            done,
            admin=True,
            timeout=30,
        )

    def refresh(self):
        self.store.clear()
        daemon_rc, _daemon = run(["pidof", "bluetoothd"], timeout=2)
        show_rc, show = self.btctl("show", timeout=5)
        has_controller = show_rc == 0 and "Controller " in show

        self.set_state(
            self.service_status,
            "Service: running" if daemon_rc == 0 else "Service: stopped",
            "good" if daemon_rc == 0 else "bad",
        )
        self.set_state(
            self.adapter_status,
            "Adapter: ready" if has_controller else "Adapter: not detected",
            "good" if has_controller else "bad",
        )

        powered = "no"
        address = ""
        if has_controller:
            for line in show.splitlines():
                clean = line.strip()
                if clean.startswith("Controller "):
                    address = clean.split()[1]
                elif clean.startswith("Powered:"):
                    powered = clean.split(":", 1)[1].strip()
        self.set_state(
            self.power_status,
            f"Power: {powered}",
            "good" if powered == "yes" else "warn",
        )
        self.power_button.set_label("Power off" if powered == "yes" else "Power on")
        self.power_button.set_sensitive(has_controller)
        self.scan_button.set_sensitive(has_controller and powered == "yes")

        devices_rc, devices = self.btctl("devices", timeout=6)
        if devices_rc == 0:
            for line in devices.splitlines():
                parts = line.split(maxsplit=2)
                if len(parts) < 2 or parts[0] != "Device":
                    continue
                mac = parts[1]
                name = parts[2] if len(parts) > 2 else mac
                _info_rc, info = self.btctl("info", mac, timeout=5)
                values = {"Paired": "no", "Trusted": "no", "Connected": "no"}
                for info_line in info.splitlines():
                    clean = info_line.strip()
                    for key in values:
                        if clean.startswith(key + ":"):
                            values[key] = clean.split(":", 1)[1].strip()
                self.store.append(
                    [name, mac, values["Paired"], values["Trusted"], values["Connected"]]
                )
        if not has_controller:
            log = read_file("/var/log/bluetoothd.log", "No bluetoothd log available.")
            self.detail.set_text(
                "No controller found. Repair reloads btusb/btintel/btrtl/btqca, clears rfkill, "
                "restarts BlueZ, then retriggers udev.\n\n" + log[-1200:]
            )
        elif len(self.store) == 0:
            self.detail.set_text(
                f"Adapter {address or 'ready'}. No known devices. Press Scan to discover nearby devices."
            )
        else:
            self.detail.set_text(f"{len(self.store)} known device(s). Select one for actions.")

    def selected_device(self):
        model, tree_iter = self.tree.get_selection().get_selected()
        return model[tree_iter][1] if tree_iter else ""

    def on_selection_changed(self, selection):
        model, tree_iter = selection.get_selected()
        active = tree_iter is not None
        for widget in (
            self.pair_button,
            self.trust_button,
            self.connect_button,
            self.disconnect_button,
            self.remove_button,
        ):
            widget.set_sensitive(active)
        if active:
            self.detail.set_text(
                f"{model[tree_iter][0]}\n{model[tree_iter][1]}\n"
                f"Paired: {model[tree_iter][2]}  Trusted: {model[tree_iter][3]}  "
                f"Connected: {model[tree_iter][4]}"
            )

    def toggle_power(self, widget):
        target = "off" if "off" in widget.get_label().lower() else "on"
        self.run_bt_action(["power", target], f"Turning Bluetooth {target}")

    def scan_devices(self, _widget):
        self.set_busy(True, "Scanning for 10 seconds")

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "Bluetooth scan failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh()

        run_async(
            ["bluetoothctl", "--timeout", "10", "scan", "on"],
            done,
            admin=True,
            timeout=15,
        )

    def device_action(self, action):
        mac = self.selected_device()
        if not mac:
            message(self, "Select device", "Choose Bluetooth device first.")
            return
        if action == "pair":
            self.run_bt_action(["pair", mac], f"Pairing {mac}", follow=["trust", mac])
        else:
            self.run_bt_action([action, mac], f"{action.title()} {mac}")

    def run_bt_action(self, args, progress_text, follow=None):
        self.set_busy(True, progress_text)

        def done(rc, output):
            if rc == 0 and follow:
                run(["bluetoothctl", *follow], admin=True, timeout=12)
            self.set_busy(False)
            if rc != 0:
                message(self, "Bluetooth action failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh()

        run_async(["bluetoothctl", *args], done, admin=True, timeout=30)

    def repair_service(self, _widget):
        self.set_busy(True, "Repairing Bluetooth")

        def done(rc, output):
            self.set_busy(False)
            self.refresh()
            if rc != 0:
                message(self, "Bluetooth repair failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)

        run_async(
            ["ooonana-service-repair", "force"],
            done,
            admin=True,
            timeout=40,
        )


def main():
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana Bluetooth")
        print("actions: power scan pair trust connect disconnect remove repair")
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
