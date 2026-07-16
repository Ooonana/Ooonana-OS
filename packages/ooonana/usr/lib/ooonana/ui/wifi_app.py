#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    GLib,
    Gtk,
    apply_theme,
    button,
    command_exists,
    header,
    label,
    launch,
    message,
    page_intro,
    run,
    run_async,
    run_async_task,
)
from signal_map import SignalMapWindow  # noqa: E402
from wireless_utils import (  # noqa: E402
    group_wifi_access_points,
    parse_iw_wifi,
    parse_nmcli_wifi,
    security_kind,
)


SECURITY_OPTIONS = (
    ("Open", "open", "--"),
    ("Enhanced Open (OWE)", "owe", "OWE"),
    ("WPA/WPA2 Personal", "personal", "WPA2 PSK"),
    ("WPA3 Personal", "personal", "WPA3 SAE"),
    ("WPA/WPA2 Enterprise", "enterprise", "WPA2 802.1X"),
    ("WPA3 Enterprise", "enterprise", "WPA3 802.1X"),
    ("WEP", "wep", "WEP"),
)


def add_grid_row(grid, row, text, widget):
    prompt = label(text)
    grid.attach(prompt, 0, row, 1, 1)
    grid.attach(widget, 1, row, 1, 1)
    return row + 1


def text_entry(secret=False, placeholder=""):
    entry = Gtk.Entry()
    entry.set_visibility(not secret)
    entry.set_hexpand(True)
    if placeholder:
        entry.set_placeholder_text(placeholder)
    return entry


class WifiCredentialsDialog(Gtk.Dialog):
    def __init__(self, parent, network):
        super().__init__(title=f"Connect to {network['ssid']}", transient_for=parent, modal=True)
        self.network = network
        self.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Connect", Gtk.ResponseType.OK)
        self.set_default_size(560, -1)
        area = self.get_content_area()
        area.set_border_width(16)
        area.set_spacing(12)
        area.pack_start(
            label(f"{network['security_label']}  |  {network.get('ap_count', 1)} access point(s)", "muted"),
            False,
            False,
            0,
        )
        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        area.pack_start(grid, False, False, 0)

        self.password = text_entry(secret=True)
        self.identity = text_entry(placeholder="user@example.org")
        self.anonymous_identity = text_entry(placeholder="anonymous@example.org")
        self.domain = text_entry(placeholder="school.example.org")
        self.eap = Gtk.ComboBoxText()
        for value in ("PEAP", "TTLS", "TLS", "PWD"):
            self.eap.append_text(value)
        self.eap.set_active(0)
        self.phase2 = Gtk.ComboBoxText()
        for value in ("MSCHAPv2", "PAP", "GTC", "CHAP"):
            self.phase2.append_text(value)
        self.phase2.set_active(0)
        self.system_ca = Gtk.CheckButton.new_with_label("Use system CA certificates")
        self.system_ca.set_active(True)
        self.ca_cert = Gtk.FileChooserButton.new("Choose CA certificate", Gtk.FileChooserAction.OPEN)
        self.client_cert = Gtk.FileChooserButton.new("Choose client certificate", Gtk.FileChooserAction.OPEN)
        self.private_key = Gtk.FileChooserButton.new("Choose private key", Gtk.FileChooserAction.OPEN)
        self.private_key_password = text_entry(secret=True)

        kind = network["security_kind"]
        row = 0
        if kind in ("personal", "wep"):
            row = add_grid_row(grid, row, "Password", self.password)
        elif kind == "enterprise":
            row = add_grid_row(grid, row, "EAP method", self.eap)
            row = add_grid_row(grid, row, "Identity", self.identity)
            row = add_grid_row(grid, row, "Anonymous identity", self.anonymous_identity)
            row = add_grid_row(grid, row, "Password", self.password)
            row = add_grid_row(grid, row, "Inner authentication", self.phase2)
            row = add_grid_row(grid, row, "Server domain", self.domain)
            grid.attach(self.system_ca, 1, row, 1, 1)
            row += 1
            row = add_grid_row(grid, row, "CA certificate", self.ca_cert)
            row = add_grid_row(grid, row, "Client certificate", self.client_cert)
            row = add_grid_row(grid, row, "Private key", self.private_key)
            add_grid_row(grid, row, "Private key password", self.private_key_password)
        self.show_all()

    def values(self):
        return {
            "password": self.password.get_text(),
            "identity": self.identity.get_text().strip(),
            "anonymous_identity": self.anonymous_identity.get_text().strip(),
            "domain": self.domain.get_text().strip(),
            "eap": (self.eap.get_active_text() or "PEAP").lower(),
            "phase2": (self.phase2.get_active_text() or "MSCHAPv2").lower(),
            "system_ca": self.system_ca.get_active(),
            "ca_cert": self.ca_cert.get_filename() or "",
            "client_cert": self.client_cert.get_filename() or "",
            "private_key": self.private_key.get_filename() or "",
            "private_key_password": self.private_key_password.get_text(),
        }

    def validate(self):
        values = self.values()
        kind = self.network["security_kind"]
        if kind in ("personal", "wep") and not values["password"]:
            return "Password is required."
        if kind == "enterprise":
            if not values["identity"]:
                return "Enterprise identity is required."
            if values["eap"] == "tls":
                if not values["client_cert"] or not values["private_key"]:
                    return "EAP-TLS needs a client certificate and private key."
            elif not values["password"]:
                return "Enterprise password is required for this EAP method."
            if not values["ca_cert"] and not values["system_ca"]:
                return "Choose a CA certificate or enable system CA certificates."
            if values["system_ca"] and not values["ca_cert"] and not values["domain"]:
                return "Enter the school server domain when using system CA certificates."
        return ""


class ManualNetworkDialog(Gtk.Dialog):
    def __init__(self, parent, devices, ssid=""):
        super().__init__(title="Other Wi-Fi network", transient_for=parent, modal=True)
        self.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Continue", Gtk.ResponseType.OK)
        self.set_default_size(520, -1)
        area = self.get_content_area()
        area.set_border_width(16)
        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        area.pack_start(grid, False, False, 0)
        self.ssid = text_entry(placeholder="Network name")
        self.ssid.set_text(ssid)
        self.security = Gtk.ComboBoxText()
        for title, _kind, _raw in SECURITY_OPTIONS:
            self.security.append_text(title)
        self.security.set_active(2)
        self.device = Gtk.ComboBoxText()
        for value in devices:
            self.device.append_text(value)
        if devices:
            self.device.set_active(0)
        row = add_grid_row(grid, 0, "Network name", self.ssid)
        row = add_grid_row(grid, row, "Security", self.security)
        add_grid_row(grid, row, "Adapter", self.device)
        self.show_all()

    def network(self):
        index = self.security.get_active()
        _title, kind, raw = SECURITY_OPTIONS[index if index >= 0 else 2]
        ssid = self.ssid.get_text().strip()
        return {
            "ssid": ssid,
            "security": raw,
            "security_kind": kind,
            "security_label": SECURITY_OPTIONS[index if index >= 0 else 2][0],
            "device": self.device.get_active_text() or "",
            "bssid": "",
            "signal": 0,
            "ap_count": 0,
            "access_points": [],
            "hidden": True,
            "connected": False,
        }


class WifiWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Wi-Fi")
        self.set_default_size(980, 660)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.networks = {}
        self.access_points = []
        self.wifi_devices = []
        self.signal_window = None

        bar = header(self, "Wi-Fi", "NetworkManager", "network-wireless-symbolic")
        self.refresh_button = button("Refresh", "view-refresh-symbolic", lambda *_: self.refresh(scan=True))
        bar.pack_end(self.refresh_button)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_border_width(20)
        self.add(root)
        root.pack_start(page_intro("Wireless networks", "Nearby access points, saved profiles, and enterprise security."), False, False, 0)

        status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.service_label = label("Service: checking", "status-warn")
        self.radio_label = label("Radio: checking", "status-warn")
        self.active_label = label("Connection: checking", "status-warn")
        status.pack_start(self.service_label, False, False, 0)
        status.pack_start(self.radio_label, False, False, 0)
        status.pack_start(self.active_label, True, True, 0)
        root.pack_start(status, False, False, 0)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.radio_button = button("Wi-Fi on", "network-wireless-symbolic", self.toggle_radio, "suggested-action")
        self.scan_button = button("Scan", "edit-find-symbolic", lambda *_: self.refresh(scan=True))
        toolbar.pack_start(self.radio_button, False, False, 0)
        toolbar.pack_start(self.scan_button, False, False, 0)
        toolbar.pack_start(button("Other network", "list-add-symbolic", self.connect_manual), False, False, 0)
        toolbar.pack_start(button("Signal map", "find-location-symbolic", self.show_signal_map), False, False, 0)
        toolbar.pack_start(button("3D mode", "video-display-symbolic", self.launch_ruview), False, False, 0)
        toolbar.pack_start(button("Profiles", "document-edit-symbolic", lambda *_: launch(["nm-connection-editor"])), False, False, 0)
        toolbar.pack_end(button("Repair service", "emblem-system-symbolic", self.repair_service), False, False, 0)
        root.pack_start(toolbar, False, False, 0)

        self.store = Gtk.ListStore(str, str, int, str, int, str, str, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        for title, index in (("Connected", 0), ("Network", 1), ("Signal", 2), ("Security", 3), ("APs", 4), ("Device", 5)):
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
        self.connect_button = button("Connect", "network-transmit-receive-symbolic", lambda *_: self.connect_selected(), "suggested-action")
        self.disconnect_button = button("Disconnect", "network-offline-symbolic", lambda *_: self.disconnect_active())
        self.connect_button.set_sensitive(False)
        actions.pack_start(self.connect_button, False, False, 0)
        actions.pack_start(self.disconnect_button, False, False, 0)
        root.pack_start(actions, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_no_show_all(True)
        root.pack_start(self.progress, False, False, 0)
        self.detail = label("Select a network to connect.", "muted")
        self.detail.set_selectable(True)
        root.pack_start(self.detail, False, False, 0)

        self.connect("destroy", Gtk.main_quit)
        self.initial_refresh()

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
        for widget in (self.refresh_button, self.radio_button, self.scan_button):
            widget.set_sensitive(not busy)
        if busy:
            self.progress.show()
            self.progress.pulse()
            self.progress.set_text(text)
            self.progress.set_show_text(bool(text))
        else:
            self.progress.hide()

    def initial_refresh(self):
        daemon_rc, _daemon = run(["/bin/busybox", "pidof", "NetworkManager"], timeout=2)
        if daemon_rc == 0:
            self.refresh(scan=True)
            return
        self.set_busy(True, "Starting NetworkManager")

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "NetworkManager repair failed", output or f"Exit status {rc}. Check /var/log/ooonana-services.log.", Gtk.MessageType.ERROR)
            self.refresh(scan=True)

        run_async(["ooonana-service-repair", "wifi"], done, admin=True, timeout=20)

    def refresh(self, scan=False):
        daemon_rc, _daemon = run(["/bin/busybox", "pidof", "NetworkManager"], timeout=2)
        _radio_rc, radio = self.nmcli("-t", "-f", "WIFI", "radio", timeout=4)
        devices_rc, devices = self.nmcli("-t", "--escape", "yes", "-f", "DEVICE,TYPE,STATE", "device", "status", timeout=5)
        active_rc, active = self.nmcli("-t", "--escape", "yes", "-f", "NAME,DEVICE", "connection", "show", "--active", timeout=5)
        self.wifi_devices = []
        if devices_rc == 0:
            from wireless_utils import split_nmcli_terse
            for line in devices.splitlines():
                parts = split_nmcli_terse(line)
                if len(parts) == 3 and parts[1] == "wifi":
                    self.wifi_devices.append(parts[0])

        scan_errors = []
        if scan:
            for device in self.wifi_devices:
                self.nmcli("device", "set", device, "managed", "yes", timeout=5)
                run(["ip", "link", "set", "dev", device, "up"], admin=True, timeout=5)
                run(["iw", "dev", device, "set", "power_save", "off"], admin=True, timeout=5)
                rc, output = self.nmcli("device", "wifi", "rescan", "ifname", device, timeout=25)
                if rc != 0 and output:
                    scan_errors.append(f"{device}: {output.splitlines()[-1]}")

        self.set_state(self.service_label, "Service: running" if daemon_rc == 0 else "Service: stopped", "good" if daemon_rc == 0 else "bad")
        self.set_state(self.radio_label, f"Radio: {radio or 'unknown'} | Adapter: {'ready' if self.wifi_devices else 'not detected'}", "good" if radio == "enabled" and self.wifi_devices else "warn")
        active_lines = [line for line in active.splitlines() if line and not line.endswith(":lo") and ":" in line]
        active_name = active_lines[0].split(":", 1)[0] if active_rc == 0 and active_lines else "offline"
        self.set_state(self.active_label, f"Connection: {active_name}", "good" if active_name != "offline" else "warn")
        self.radio_button.set_label("Wi-Fi off" if radio == "enabled" else "Wi-Fi on")

        list_rc, networks = self.nmcli(
            "-t", "--escape", "yes", "-f", "IN-USE,BSSID,SSID,SIGNAL,SECURITY,DEVICE",
            "device", "wifi", "list", "--rescan", "yes" if scan else "no",
            timeout=30 if scan else 15,
        )
        access_points = parse_nmcli_wifi(networks) if list_rc == 0 else []
        if not access_points:
            for device in self.wifi_devices:
                iw_rc, iw_output = run(["iw", "dev", device, "scan"], admin=True, timeout=30)
                if iw_rc == 0:
                    access_points.extend(parse_iw_wifi(iw_output, device))
                elif iw_output:
                    scan_errors.append(f"{device}: {iw_output.splitlines()[-1]}")
        self.access_points = access_points
        grouped = group_wifi_access_points(access_points)
        self.networks = {network["ssid"]: network for network in grouped}
        self.store.clear()
        for network in grouped:
            self.store.append([
                "yes" if network["connected"] else "",
                network["ssid"], network["signal"], network["security_label"],
                network["ap_count"], network.get("device", ""), network.get("bssid", ""),
                network["security_kind"], network["ssid"],
            ])
        self.update_signal_map()
        if not self.wifi_devices:
            self.detail.set_text("Wi-Fi adapter not detected. Repair reloads firmware, clears RFKill, retriggers udev, then restarts NetworkManager.")
        elif not grouped:
            detail = "No networks found after NetworkManager and direct hardware scans."
            if scan_errors:
                detail += " " + " | ".join(dict.fromkeys(scan_errors))
            self.detail.set_text(detail)
        else:
            self.detail.set_text(f"{len(grouped)} network name(s), {len(access_points)} access point(s). Duplicate SSIDs are grouped.")

    @staticmethod
    def parse_iw_scan(output):
        return [(item["ssid"], item["signal"], item["security"]) for item in parse_iw_wifi(output)]

    def selected_network(self):
        model, tree_iter = self.tree.get_selection().get_selected()
        return self.networks.get(model[tree_iter][8]) if tree_iter else None

    def on_selection_changed(self, selection):
        _model, tree_iter = selection.get_selected()
        self.connect_button.set_sensitive(tree_iter is not None)
        network = self.selected_network()
        if network:
            warning = " Mixed security is present; secured access points are preferred." if network.get("mixed_security") else ""
            self.detail.set_text(
                f"{network['ssid']} | signal {network['signal']}% | {network['security_label']} | "
                f"{network['ap_count']} access point(s) | strongest {network.get('bssid') or 'unknown'}.{warning}"
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

    def connect_manual(self, _widget):
        dialog = ManualNetworkDialog(self, self.wifi_devices)
        if dialog.run() == Gtk.ResponseType.OK:
            network = dialog.network()
            dialog.destroy()
            if not network["ssid"]:
                message(self, "Other network", "Network name is required.", Gtk.MessageType.ERROR)
                return
            self.connect_network(network)
            return
        dialog.destroy()

    def connect_selected(self):
        network = self.selected_network()
        if network:
            self.connect_network(network)

    def connect_network(self, network):
        if network["security_kind"] == "unknown":
            dialog = ManualNetworkDialog(self, self.wifi_devices, network["ssid"])
            if dialog.run() != Gtk.ResponseType.OK:
                dialog.destroy()
                return
            selected = dialog.network()
            dialog.destroy()
            selected["hidden"] = False
            selected["access_points"] = network.get("access_points", [])
            selected["ap_count"] = network.get("ap_count", 0)
            selected["signal"] = network.get("signal", 0)
            selected["bssid"] = network.get("bssid", "")
            network = selected
        credentials = {}
        if network["security_kind"] in ("personal", "wep", "enterprise"):
            dialog = WifiCredentialsDialog(self, network)
            while True:
                response = dialog.run()
                if response != Gtk.ResponseType.OK:
                    dialog.destroy()
                    return
                error = dialog.validate()
                if not error:
                    credentials = dialog.values()
                    dialog.destroy()
                    break
                message(dialog, "Missing connection details", error, Gtk.MessageType.ERROR)
        self.set_busy(True, f"Connecting to {network['ssid']}")

        def task():
            return self.connect_task(network, credentials)

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "Connection failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh(scan=rc != 0)

        run_async_task(task, done)

    @staticmethod
    def profile_name(ssid):
        clean = " ".join(ssid.split())[:72]
        return f"Ooonana Wi-Fi - {clean}"

    def connect_task(self, network, credentials):
        ssid = network["ssid"]
        device = network.get("device") or (self.wifi_devices[0] if self.wifi_devices else "")
        if device:
            run(["nmcli", "device", "wifi", "rescan", "ifname", device, "ssid", ssid], admin=True, timeout=25)
        if network["security_kind"] == "enterprise":
            return self.connect_enterprise(network, credentials, device)
        if network["security_kind"] == "owe":
            return self.connect_owe(network, device)

        profile = self.profile_name(ssid)
        base = ["nmcli", "--wait", "35", "device", "wifi", "connect", ssid]
        if credentials.get("password"):
            base.extend(["password", credentials["password"]])
        if network["security_kind"] == "wep":
            password = credentials.get("password", "")
            is_hex = len(password) in (10, 26) and all(char in "0123456789abcdefABCDEF" for char in password)
            base.extend(["wep-key-type", "key" if len(password) in (5, 13) or is_hex else "phrase"])
        if device:
            base.extend(["ifname", device])
        base.extend(["name", profile])
        if network.get("hidden"):
            base.extend(["hidden", "yes"])

        candidates = [item for item in network.get("access_points", []) if item.get("security_kind") == network["security_kind"]]
        errors = []
        for access_point in candidates:
            run(["nmcli", "connection", "delete", profile], admin=True, timeout=12)
            command = [*base, "bssid", access_point["bssid"]]
            rc, output = run(command, admin=True, timeout=45)
            if rc == 0:
                return rc, output
            errors.append(f"{access_point['bssid']}: {output}")
        run(["nmcli", "connection", "delete", profile], admin=True, timeout=12)
        rc, output = run(base, admin=True, timeout=45)
        if rc == 0:
            return rc, output
        errors.append(output)
        return rc, "\n".join(item for item in errors if item)

    def connect_owe(self, network, device):
        profile = self.profile_name(network["ssid"])
        run(["nmcli", "connection", "delete", profile], admin=True, timeout=12)
        command = ["nmcli", "connection", "add", "type", "wifi", "con-name", profile, "ssid", network["ssid"]]
        if device:
            command.extend(["ifname", device])
        rc, output = run(command, admin=True, timeout=20)
        if rc != 0:
            return rc, output
        rc, output = run(
            [
                "nmcli", "connection", "modify", profile,
                "connection.autoconnect", "yes",
                "ipv4.method", "auto",
                "ipv6.method", "auto",
                "802-11-wireless-security.key-mgmt", "owe",
            ],
            admin=True,
            timeout=20,
        )
        if rc != 0:
            return rc, output
        return self.activate_profile(profile, network, device, "owe")

    def activate_profile(self, profile, network, device, security):
        errors = []
        candidates = [item for item in network.get("access_points", []) if item.get("security_kind") == security]
        for access_point in candidates:
            up = ["nmcli", "--wait", "40", "connection", "up", profile]
            if device:
                up.extend(["ifname", device])
            up.extend(["ap", access_point["bssid"]])
            rc, output = run(up, admin=True, timeout=50)
            if rc == 0:
                return rc, output
            errors.append(f"{access_point['bssid']}: {output}")
        up = ["nmcli", "--wait", "40", "connection", "up", profile]
        if device:
            up.extend(["ifname", device])
        rc, output = run(up, admin=True, timeout=50)
        if rc == 0:
            return rc, output
        errors.append(output)
        return rc, "\n".join(item for item in errors if item)

    def connect_enterprise(self, network, credentials, device):
        profile = self.profile_name(network["ssid"])
        run(["nmcli", "connection", "delete", profile], admin=True, timeout=12)
        command = ["nmcli", "connection", "add", "type", "wifi", "con-name", profile, "ssid", network["ssid"]]
        if device:
            command.extend(["ifname", device])
        rc, output = run(command, admin=True, timeout=20)
        if rc != 0:
            return rc, output

        properties = [
            "connection.autoconnect", "yes",
            "ipv4.method", "auto",
            "ipv6.method", "auto",
            "802-11-wireless-security.key-mgmt", "wpa-eap",
            "802-1x.eap", credentials["eap"],
            "802-1x.identity", credentials["identity"],
        ]
        if network.get("hidden"):
            properties.extend(["802-11-wireless.hidden", "yes"])
        if credentials["anonymous_identity"]:
            properties.extend(["802-1x.anonymous-identity", credentials["anonymous_identity"]])
        if credentials["domain"]:
            properties.extend(["802-1x.domain-suffix-match", credentials["domain"]])
        if credentials["ca_cert"]:
            properties.extend(["802-1x.ca-cert", credentials["ca_cert"]])
        else:
            properties.extend(["802-1x.system-ca-certs", "yes" if credentials["system_ca"] else "no"])
        if credentials["eap"] == "tls":
            properties.extend([
                "802-1x.client-cert", credentials["client_cert"],
                "802-1x.private-key", credentials["private_key"],
            ])
            if credentials["private_key_password"]:
                properties.extend(["802-1x.private-key-password", credentials["private_key_password"]])
        else:
            properties.extend([
                "802-1x.phase2-auth", credentials["phase2"],
                "802-1x.password", credentials["password"],
            ])
        rc, output = run(["nmcli", "connection", "modify", profile, *properties], admin=True, timeout=25)
        if rc != 0:
            return rc, output

        return self.activate_profile(profile, network, device, "enterprise")

    def disconnect_active(self):
        rc, active = self.nmcli("-t", "--escape", "yes", "-f", "NAME,TYPE", "connection", "show", "--active")
        from wireless_utils import split_nmcli_terse
        names = [fields[0] for fields in (split_nmcli_terse(line) for line in active.splitlines()) if len(fields) == 2 and fields[1] == "802-11-wireless"]
        if rc != 0 or not names:
            message(self, "Wi-Fi", "No active Wi-Fi connection.")
            return
        self.set_busy(True, f"Disconnecting {names[0]}")

        def done(result, output):
            self.set_busy(False)
            if result != 0:
                message(self, "Disconnect failed", output or f"Exit status {result}", Gtk.MessageType.ERROR)
            self.refresh()

        run_async(["nmcli", "connection", "down", names[0]], done, admin=True, timeout=20)

    def show_signal_map(self, _widget):
        if self.signal_window is None or not self.signal_window.get_visible():
            self.signal_window = SignalMapWindow("Wi-Fi signal map", "wireless")
        self.update_signal_map()
        self.signal_window.show_all()
        self.signal_window.present()

    def update_signal_map(self):
        if not self.signal_window:
            return
        self.signal_window.update_items([
            {
                "key": item.get("bssid") or f"{item['ssid']}-{index}",
                "name": f"{item['ssid']} {item.get('bssid', '')[-5:]}",
                "signal": item.get("signal", 0),
            }
            for index, item in enumerate(self.access_points)
        ])

    def launch_ruview(self, _widget):
        runtime = ""
        for candidate in ("ruview-pointcloud", "wifi-densepose-pointcloud"):
            if command_exists(candidate):
                runtime = candidate
                break
        if runtime:
            launch([runtime, "serve", "--bind", "127.0.0.1:9880"])

            def open_viewer():
                launch(["xdg-open", "http://127.0.0.1:9880"])
                return False

            GLib.timeout_add_seconds(2, open_viewer)
            return

        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text="RuView 3D runtime is not installed",
        )
        dialog.format_secondary_text(
            "Full 3D sensing needs CSI hardware such as ESP32-S3 or a supported research NIC. "
            "This laptop can use the RSSI signal map; RuView can also run simulated data."
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.add_button("Open RuView", Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            launch(["xdg-open", "https://github.com/ruvnet/RuView"])
        dialog.destroy()

    def repair_service(self, _widget):
        self.set_busy(True, "Repairing network service")

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "Network repair failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh(scan=True)

        run_async(["ooonana-service-repair", "force-wifi"], done, admin=True, timeout=30)


def main():
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana Wi-Fi")
        print("actions: radio scan grouped-ssid personal enterprise certificates map 3d-mode ruvnet-ruview disconnect repair")
        print("OOONANA_WIFI_NATIVE_OK")
        return 0
    apply_theme()
    window = WifiWindow()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
