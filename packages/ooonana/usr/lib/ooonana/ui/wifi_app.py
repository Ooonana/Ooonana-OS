#!/usr/bin/env python3
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
    run,
    run_async,
)


class WifiWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Wi-Fi")
        self.set_default_size(900, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        bar = header(self, "Wi-Fi", "NetworkManager", "network-wireless-symbolic")
        self.refresh_button = button(
            "Refresh", "view-refresh-symbolic", lambda *_: self.refresh(scan=True)
        )
        bar.pack_end(self.refresh_button)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_border_width(20)
        self.add(root)
        root.pack_start(
            page_intro(
                "Wireless networks",
                "Scan, connect, disconnect, and manage saved NetworkManager connections.",
            ),
            False,
            False,
            0,
        )

        status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.service_label = label("Service: checking", "status-warn")
        self.radio_label = label("Radio: checking", "status-warn")
        self.active_label = label("Connection: checking", "status-warn")
        status.pack_start(self.service_label, False, False, 0)
        status.pack_start(self.radio_label, False, False, 0)
        status.pack_start(self.active_label, True, True, 0)
        root.pack_start(status, False, False, 0)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.radio_button = button(
            "Wi-Fi on", "network-wireless-symbolic", self.toggle_radio, "suggested-action"
        )
        toolbar.pack_start(self.radio_button, False, False, 0)
        toolbar.pack_start(
            button("Connection editor", "document-edit-symbolic", lambda *_: launch(["nm-connection-editor"])),
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

        self.store = Gtk.ListStore(str, str, int, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        columns = [
            ("Connected", 0),
            ("Network", 1),
            ("Signal", 2),
            ("Security", 3),
            ("Device", 4),
        ]
        for title, index in columns:
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=index)
            column.set_resizable(True)
            column.set_expand(index == 1)
            self.tree.append_column(column)
        self.tree.get_selection().connect("changed", self.on_selection_changed)
        self.tree.connect("row-activated", lambda *_: self.connect_selected())
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.tree)
        root.pack_start(scroll, True, True, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.connect_button = button(
            "Connect", "network-transmit-receive-symbolic", lambda *_: self.connect_selected(), "suggested-action"
        )
        self.disconnect_button = button(
            "Disconnect", "network-offline-symbolic", lambda *_: self.disconnect_active()
        )
        self.connect_button.set_sensitive(False)
        actions.pack_start(self.connect_button, False, False, 0)
        actions.pack_start(self.disconnect_button, False, False, 0)
        root.pack_start(actions, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_no_show_all(True)
        root.pack_start(self.progress, False, False, 0)
        self.detail = label("Select network to connect.", "muted")
        root.pack_start(self.detail, False, False, 0)

        self.connect("destroy", Gtk.main_quit)
        self.repair_then_refresh()

    @staticmethod
    def nmcli(*args, timeout=12):
        return run(["nmcli", *args], admin=True, timeout=timeout)

    @staticmethod
    def set_state(widget, text, state):
        widget.set_text(text)
        context = widget.get_style_context()
        for css in ("status-good", "status-warn", "status-bad"):
            context.remove_class(css)
        context.add_class(f"status-{state}")

    def set_busy(self, busy, text=""):
        self.refresh_button.set_sensitive(not busy)
        self.radio_button.set_sensitive(not busy)
        if busy:
            self.progress.show()
            self.progress.pulse()
            self.progress.set_text(text)
            self.progress.set_show_text(bool(text))
        else:
            self.progress.hide()

    def repair_then_refresh(self):
        self.set_busy(True, "Starting NetworkManager")

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(
                    self,
                    "NetworkManager repair failed",
                    output or f"Exit status {rc}. Check /var/log/ooonana-services.log.",
                    Gtk.MessageType.ERROR,
                )
            self.refresh(scan=True)

        run_async(
            ["ooonana-service-repair", "wifi"],
            done,
            admin=True,
            timeout=30,
        )

    def refresh(self, scan=False):
        if scan:
            self.nmcli("device", "wifi", "rescan", timeout=10)
        state_rc, state = self.nmcli("-t", "-f", "STATE", "general", timeout=4)
        radio_rc, radio = self.nmcli("-t", "-f", "WIFI", "radio", timeout=4)
        active_rc, active = self.nmcli(
            "-t", "-f", "NAME,DEVICE", "connection", "show", "--active", timeout=5
        )
        self.set_state(
            self.service_label,
            f"Service: {state or 'not ready'}",
            "good" if state_rc == 0 else "bad",
        )
        self.set_state(
            self.radio_label,
            f"Radio: {radio or 'unknown'}",
            "good" if radio == "enabled" else "warn",
        )
        active_name = active.splitlines()[0].split(":", 1)[0] if active_rc == 0 and active else "offline"
        self.set_state(
            self.active_label,
            f"Connection: {active_name}",
            "good" if active_name != "offline" else "warn",
        )
        self.radio_button.set_label("Wi-Fi off" if radio == "enabled" else "Wi-Fi on")

        self.store.clear()
        list_rc, networks = self.nmcli(
            "-t",
            "--escape",
            "no",
            "-f",
            "IN-USE,SSID,SIGNAL,SECURITY,DEVICE",
            "device",
            "wifi",
            "list",
            timeout=12,
        )
        if list_rc == 0:
            seen = set()
            for line in networks.splitlines():
                parts = line.split(":", 4)
                if len(parts) != 5:
                    continue
                in_use, ssid, signal, security, device = parts
                if not ssid or ssid in seen:
                    continue
                seen.add(ssid)
                try:
                    signal_value = int(signal)
                except ValueError:
                    signal_value = 0
                self.store.append(
                    ["yes" if in_use == "*" else "", ssid, signal_value, security or "Open", device]
                )
        if len(self.store) == 0:
            self.detail.set_text(
                "No networks found. Enable Wi-Fi, press Refresh, or use Repair Service."
            )
        else:
            self.detail.set_text(f"{len(self.store)} network(s) found.")

    def selected(self):
        model, tree_iter = self.tree.get_selection().get_selected()
        return model[tree_iter] if tree_iter else None

    def on_selection_changed(self, selection):
        model, tree_iter = selection.get_selected()
        self.connect_button.set_sensitive(tree_iter is not None)
        if tree_iter:
            row = model[tree_iter]
            self.detail.set_text(
                f"{row[1]} - signal {row[2]}% - security {row[3]} - device {row[4] or 'auto'}"
            )

    def toggle_radio(self, widget):
        target = "off" if "off" in widget.get_label().lower() else "on"
        self.set_busy(True, f"Turning Wi-Fi {target}")

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "Wi-Fi action failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh(scan=target == "on")

        run_async(["nmcli", "radio", "wifi", target], done, admin=True, timeout=20)

    def connect_selected(self):
        row = self.selected()
        if row is None:
            return
        ssid = row[1]
        security = row[3]
        command = ["nmcli", "device", "wifi", "connect", ssid]
        if security and security != "Open":
            password = ask_text(self, f"Connect to {ssid}", "Wi-Fi password", secret=True)
            if not password:
                return
            command.extend(["password", password])
        self.set_busy(True, f"Connecting to {ssid}")

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "Connection failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh()

        run_async(command, done, admin=True, timeout=45)

    def disconnect_active(self):
        rc, active = self.nmcli("-t", "-f", "NAME", "connection", "show", "--active")
        name = active.splitlines()[0] if rc == 0 and active else ""
        if not name:
            message(self, "Wi-Fi", "No active connection.")
            return
        self.set_busy(True, f"Disconnecting {name}")

        def done(result, output):
            self.set_busy(False)
            if result != 0:
                message(self, "Disconnect failed", output or f"Exit status {result}", Gtk.MessageType.ERROR)
            self.refresh()

        run_async(["nmcli", "connection", "down", name], done, admin=True, timeout=20)

    def repair_service(self, _widget):
        self.set_busy(True, "Repairing network service")

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "Network repair failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh(scan=True)

        run_async(
            ["ooonana-service-repair", "force"],
            done,
            admin=True,
            timeout=40,
        )


def main():
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana Wi-Fi")
        print("actions: radio scan connect disconnect editor repair")
        print("OOONANA_WIFI_NATIVE_OK")
        return 0
    apply_theme()
    window = WifiWindow()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
