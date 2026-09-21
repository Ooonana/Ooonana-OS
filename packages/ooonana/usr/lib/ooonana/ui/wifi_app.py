#!/usr/bin/env python3
import sys
import time
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
    parse_ip_neighbors,
    parse_iw_wifi,
    parse_nmcli_wifi,
    security_kind,
    split_nmcli_terse,
)


SECURITY_OPTIONS = (
    ("Open", "open", "--"),
    ("Enhanced Open (OWE)", "owe", "OWE"),
    ("WPA2/WPA3 Personal", "personal", "WPA2 PSK"),
    ("WPA3 Personal", "personal", "WPA3 SAE"),
    ("WPA2/WPA3 Enterprise", "enterprise", "WPA2 802.1X"),
    ("WPA3 Enterprise", "enterprise", "WPA3 802.1X"),
    ("WEP", "wep", "WEP"),
)

# Firmware reprobe plus udev settling can exceed one minute on newer laptops.
# Killing the helper early also kills NetworkManager in its process group.
SERVICE_START_TIMEOUT = 120
SERVICE_REPAIR_TIMEOUT = 180
WIFI_DEVICE_READY_TIMEOUT = 60
WIFI_SCAN_SETTLE_TIMEOUT = 30


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
        self.security = Gtk.ComboBoxText()
        for title, _kind, _raw in SECURITY_OPTIONS:
            self.security.append_text(title)
        detected_index = 2
        detected_kind = network.get("security_kind", "unknown")
        detected_raw = (network.get("security") or "").upper()
        if detected_kind == "open":
            detected_index = 0
        elif detected_kind == "owe":
            detected_index = 1
        elif detected_kind == "personal" and "SAE" in detected_raw and "PSK" not in detected_raw:
            detected_index = 3
        elif detected_kind == "enterprise":
            detected_index = 5 if "WPA3" in detected_raw or "SUITE-B" in detected_raw else 4
        elif detected_kind == "wep":
            detected_index = 6
        self.security.set_active(detected_index)
        self.security.connect("changed", self.update_security_fields)
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
        self.ca_policy = Gtk.ComboBoxText()
        self.ca_policy.append("system", "Use system certificates")
        self.ca_policy.append("custom", "Choose CA certificate")
        self.ca_policy.append("insecure", "Do not validate certificate (unsafe)")
        self.ca_policy.set_active_id("system")
        self.ca_cert = Gtk.FileChooserButton.new("Choose CA certificate", Gtk.FileChooserAction.OPEN)
        self.ca_cert.set_sensitive(False)
        self.ca_warning = label(
            "System certificates plus the server domain protect against fake access points.",
            "muted",
        )
        self.ca_warning.set_line_wrap(True)
        self.ca_policy.connect("changed", self.update_ca_policy)
        self.client_cert = Gtk.FileChooserButton.new("Choose client certificate", Gtk.FileChooserAction.OPEN)
        self.private_key = Gtk.FileChooserButton.new("Choose private key", Gtk.FileChooserAction.OPEN)
        self.private_key_password = text_entry(secret=True)

        row = 0
        row = add_grid_row(grid, row, "Security", self.security)
        self.password_row = self.attach_row(grid, row, "Password", self.password)
        row += 1
        self.enterprise_rows = []
        for title, widget in (
            ("EAP method", self.eap),
            ("Identity", self.identity),
            ("Anonymous identity", self.anonymous_identity),
            ("Inner authentication", self.phase2),
            ("Server domain", self.domain),
            ("Certificate validation", self.ca_policy),
            ("CA certificate", self.ca_cert),
        ):
            self.enterprise_rows.append(self.attach_row(grid, row, title, widget))
            row += 1
        grid.attach(self.ca_warning, 1, row, 1, 1)
        self.enterprise_rows.append((self.ca_warning,))
        row += 1
        for title, widget in (
            ("Client certificate", self.client_cert),
            ("Private key", self.private_key),
            ("Private key password", self.private_key_password),
        ):
            self.enterprise_rows.append(self.attach_row(grid, row, title, widget))
            row += 1
        self.show_all()
        self.update_security_fields()

    @staticmethod
    def attach_row(grid, row, text, widget):
        prompt = label(text)
        grid.attach(prompt, 0, row, 1, 1)
        grid.attach(widget, 1, row, 1, 1)
        return prompt, widget

    def selected_security(self):
        index = self.security.get_active()
        return SECURITY_OPTIONS[index if index >= 0 else 2]

    def update_security_fields(self, _widget=None):
        _title, kind, _raw = self.selected_security()
        for widget in self.password_row:
            widget.set_visible(kind in ("personal", "wep", "enterprise"))
        for row in self.enterprise_rows:
            for widget in row:
                widget.set_visible(kind == "enterprise")

    def update_ca_policy(self, _widget=None):
        policy = self.ca_policy.get_active_id() or "system"
        self.ca_cert.set_sensitive(policy == "custom")
        if policy == "insecure":
            self.ca_warning.set_text(
                "Unsafe: server identity is not checked. Use only when network administrator requires it."
            )
            self.ca_warning.get_style_context().add_class("status-bad")
        elif policy == "custom":
            self.ca_warning.set_text("Select CA certificate supplied by network administrator.")
            self.ca_warning.get_style_context().remove_class("status-bad")
        else:
            self.ca_warning.set_text(
                "System certificates plus server domain protect against fake access points."
            )
            self.ca_warning.get_style_context().remove_class("status-bad")

    def values(self):
        security_label, security_kind_value, security_raw = self.selected_security()
        return {
            "security": security_raw,
            "security_kind": security_kind_value,
            "security_label": security_label,
            "password": self.password.get_text(),
            "identity": self.identity.get_text().strip(),
            "anonymous_identity": self.anonymous_identity.get_text().strip(),
            "domain": self.domain.get_text().strip(),
            "eap": (self.eap.get_active_text() or "PEAP").lower(),
            "phase2": (self.phase2.get_active_text() or "MSCHAPv2").lower(),
            "ca_policy": self.ca_policy.get_active_id() or "system",
            "ca_cert": self.ca_cert.get_filename() or "",
            "client_cert": self.client_cert.get_filename() or "",
            "private_key": self.private_key.get_filename() or "",
            "private_key_password": self.private_key_password.get_text(),
        }

    def validate(self):
        values = self.values()
        kind = values["security_kind"]
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
            if values["ca_policy"] == "custom" and not values["ca_cert"]:
                return "Choose a CA certificate."
            if values["ca_policy"] == "system" and not values["domain"]:
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
        toolbar.pack_start(button("CSI 3D", "video-display-symbolic", self.launch_csi_3d), False, False, 0)
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

        run_async(
            ["ooonana-service-repair", "wifi"],
            done,
            admin=True,
            timeout=SERVICE_START_TIMEOUT,
        )

    def refresh(self, scan=False):
        daemon_rc, _daemon = run(["/bin/busybox", "pidof", "NetworkManager"], timeout=2)
        _radio_rc, radio = self.nmcli("-t", "-f", "WIFI", "radio", timeout=4)
        devices_rc, devices = self.nmcli("-t", "--escape", "yes", "-f", "DEVICE,TYPE,STATE", "device", "status", timeout=5)
        active_rc, active = self.nmcli("-t", "--escape", "yes", "-f", "NAME,DEVICE", "connection", "show", "--active", timeout=5)
        self.wifi_devices = []
        if devices_rc == 0:
            for line in devices.splitlines():
                parts = split_nmcli_terse(line)
                if len(parts) == 3 and parts[1] == "wifi":
                    self.wifi_devices.append(parts[0])

        scan_errors = []
        if scan:
            for device in self.wifi_devices:
                managed_rc, managed = self.nmcli("-g", "GENERAL.NM-MANAGED", "device", "show", device, timeout=5)
                if managed_rc != 0 or managed.strip().lower() != "yes":
                    self.nmcli("device", "set", device, "managed", "yes", timeout=5)
                    time.sleep(1)
                run(["ip", "link", "set", "dev", device, "up"], admin=True, timeout=5)
                run(["iw", "dev", device, "set", "power_save", "off"], admin=True, timeout=5)
                ready_rc, ready_output = self.wait_for_device_ready(
                    device, timeout=WIFI_DEVICE_READY_TIMEOUT
                )
                if ready_rc != 0:
                    scan_errors.append(f"{device}: {ready_output.splitlines()[0]}")
                    continue
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
        network = dict(network)
        for key in ("security", "security_kind", "security_label"):
            network[key] = credentials[key]
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
        device_candidates = []
        for candidate in [network.get("device"), *self.wifi_devices]:
            if candidate and candidate not in device_candidates:
                device_candidates.append(candidate)
        if not device_candidates:
            return 1, "No Wi-Fi adapter is available."
        preparation_errors = []
        fresh_access_points = []
        device = ""
        for candidate in device_candidates:
            try:
                candidate_access_points = self.prepare_device(
                    candidate,
                    ssid,
                    network.get("hidden", False),
                )
                if not network.get("hidden", False) and not candidate_access_points:
                    preparation_errors.append(
                        f"{candidate}: {ssid!r} was not visible after a fresh scan."
                    )
                    continue
                fresh_access_points = candidate_access_points
                device = candidate
                break
            except RuntimeError as exc:
                preparation_errors.append(f"{candidate}: {exc}")
        if not device:
            detail = "\n".join(preparation_errors)
            return 1, (
                f"No ready Wi-Fi adapter can currently see {ssid!r}.\n"
                f"{detail}\nRefresh scan, move closer, or use Other network for a hidden SSID."
            )
        if fresh_access_points:
            network = dict(network)
            access_points = list(network.get("access_points", []))
            seen = {
                (item.get("bssid"), item.get("device"), item.get("security_kind"))
                for item in access_points
            }
            for item in fresh_access_points:
                key = (item.get("bssid"), item.get("device"), item.get("security_kind"))
                if item.get("ssid") == ssid and key not in seen:
                    access_points.append(item)
                    seen.add(key)
            network["access_points"] = access_points
        if network["security_kind"] == "enterprise":
            return self.connect_enterprise(network, credentials, device)
        if network["security_kind"] == "owe":
            return self.connect_owe(network, device)
        return self.connect_standard(network, credentials, device)

    @staticmethod
    def scan_access_points(device):
        rc, output = run(
            [
                "nmcli", "-t", "--escape", "yes", "-f",
                "IN-USE,BSSID,SSID,SIGNAL,SECURITY,DEVICE",
                "device", "wifi", "list", "ifname", device, "--rescan", "no",
            ],
            admin=True,
            timeout=15,
        )
        return parse_nmcli_wifi(output) if rc == 0 else []

    @staticmethod
    def prepare_device(device, ssid, hidden=False):
        run(["nmcli", "networking", "on"], admin=True, timeout=8)
        run(["nmcli", "radio", "wifi", "on"], admin=True, timeout=8)
        if not device:
            return []
        managed_rc, managed = run(
            ["nmcli", "-g", "GENERAL.NM-MANAGED", "device", "show", device],
            admin=True,
            timeout=8,
        )
        if managed_rc != 0 or managed.strip().lower() != "yes":
            run(["nmcli", "device", "set", device, "managed", "yes"], admin=True, timeout=8)
        run(["ip", "link", "set", "dev", device, "up"], admin=True, timeout=8)
        run(["iw", "dev", device, "set", "power_save", "off"], admin=True, timeout=8)
        ready_rc, ready_output = WifiWindow.wait_for_device_ready(
            device, timeout=WIFI_DEVICE_READY_TIMEOUT
        )
        if ready_rc != 0:
            raise RuntimeError(ready_output)
        if hidden:
            run(
                ["nmcli", "device", "wifi", "rescan", "ifname", device],
                admin=True,
                timeout=WIFI_SCAN_SETTLE_TIMEOUT,
            )
            return []

        # Rescans are asynchronous. New adapters and campus APs may need
        # multiple scans before NetworkManager has a usable BSSID.
        deadline = time.monotonic() + WIFI_SCAN_SETTLE_TIMEOUT
        next_rescan = 0
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_rescan:
                run(
                    ["nmcli", "device", "wifi", "rescan", "ifname", device],
                    admin=True,
                    timeout=WIFI_SCAN_SETTLE_TIMEOUT,
                )
                next_rescan = now + 5
            access_points = WifiWindow.scan_access_points(device)
            matches = [item for item in access_points if item.get("ssid") == ssid]
            if matches:
                return matches
            time.sleep(2)
        return []

    @staticmethod
    def wait_for_device_ready(device, timeout=WIFI_DEVICE_READY_TIMEOUT):
        deadline = time.monotonic() + timeout
        last_output = ""
        while time.monotonic() < deadline:
            rc, output = run(
                [
                    "nmcli", "-g", "GENERAL.TYPE,GENERAL.NM-MANAGED,GENERAL.STATE,GENERAL.REASON",
                    "device", "show", device,
                ],
                admin=True,
                timeout=6,
            )
            last_output = output
            fields = output.splitlines()
            if rc == 0 and len(fields) >= 3:
                device_type = fields[0].strip().lower()
                managed = fields[1].strip().lower()
                try:
                    state = int(fields[2].strip().split()[0])
                except (ValueError, IndexError):
                    state = 0
                if device_type != "wifi":
                    return 1, f"Device {device} is not a Wi-Fi adapter.\n{output}"
                if managed == "yes" and state >= 30:
                    return 0, output
            time.sleep(1)
        return 1, (
            f"Wi-Fi adapter {device} did not become available after {timeout} seconds.\n"
            f"{last_output}\nTry Repair service once, then Scan."
        )

    @staticmethod
    def profile_uuid(profile):
        rc, output = run(
            ["nmcli", "-g", "connection.uuid", "connection", "show", profile],
            admin=True,
            timeout=10,
        )
        return output.splitlines()[0].strip() if rc == 0 and output.strip() else ""

    @staticmethod
    def add_wifi_profile(profile, ssid, device, hidden=False):
        run(["nmcli", "connection", "delete", profile], admin=True, timeout=12)
        command = [
            "nmcli", "connection", "add", "type", "wifi",
            "con-name", profile, "ssid", ssid,
        ]
        rc, output = run(command, admin=True, timeout=20)
        if rc != 0:
            return rc, output
        properties = [
            "connection.autoconnect", "yes",
            "connection.metered", "unknown",
            "ipv4.method", "auto",
            "ipv6.method", "auto",
            "proxy.method", "none",
            "802-11-wireless.mode", "infrastructure",
            # Scan results shown by this UI are visible networks. Marking every
            # profile hidden makes roaming campus APs fail with SSID_NOT_FOUND.
            "802-11-wireless.hidden", "yes" if hidden else "no",
            "802-11-wireless.powersave", "2",
            # Stable per-network randomization matches modern mobile defaults
            # without changing the address on every reconnect.
            "802-11-wireless.cloned-mac-address", "stable",
        ]
        return run(
            ["nmcli", "connection", "modify", profile, *properties],
            admin=True,
            timeout=20,
        )

    def connect_standard(self, network, credentials, device):
        profile = self.profile_name(network["ssid"])
        rc, output = self.add_wifi_profile(profile, network["ssid"], device, network.get("hidden", False))
        if rc != 0:
            return rc, output

        properties = []
        password = credentials.get("password", "")
        if network["security_kind"] == "personal":
            raw_security = (network.get("security") or "").upper()
            # Transition networks advertise SAE and PSK together. Prefer PSK
            # there; reserve SAE for WPA3-only access points.
            key_mgmt = "sae" if (
                ("SAE" in raw_security or "WPA3" in raw_security)
                and "PSK" not in raw_security
                and "WPA2" not in raw_security
            ) else "wpa-psk"
            properties = [
                "802-11-wireless-security.key-mgmt", key_mgmt,
                "802-11-wireless-security.psk", password,
            ]
        elif network["security_kind"] == "wep":
            is_hex = len(password) in (10, 26) and all(char in "0123456789abcdefABCDEF" for char in password)
            key_type = "1" if len(password) in (5, 13) or is_hex else "2"
            properties = [
                "802-11-wireless-security.key-mgmt", "none",
                "802-11-wireless-security.wep-key0", password,
                "802-11-wireless-security.wep-key-type", key_type,
            ]
        if properties:
            rc, output = run(
                ["nmcli", "connection", "modify", profile, *properties],
                admin=True,
                timeout=20,
            )
            if rc != 0:
                return rc, output
        return self.activate_profile(profile, network, device, network["security_kind"])

    def connect_owe(self, network, device):
        profile = self.profile_name(network["ssid"])
        rc, output = self.add_wifi_profile(profile, network["ssid"], device, network.get("hidden", False))
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
        uuid = self.profile_uuid(profile)
        identifier = ["uuid", uuid] if uuid else ["id", profile]
        errors = []
        candidates = sorted(
            (
                item for item in network.get("access_points", [])
                if item.get("security_kind") == security
                and item.get("bssid")
                and (not device or not item.get("device") or item.get("device") == device)
            ),
            key=lambda item: item.get("signal", 0),
            reverse=True,
        )
        unique_candidates = []
        seen_bssids = set()
        for item in candidates:
            bssid = item["bssid"].upper()
            if bssid not in seen_bssids:
                unique_candidates.append(item)
                seen_bssids.add(bssid)
        candidates = unique_candidates

        # Let NetworkManager choose the strongest matching BSSID first. This is
        # required for roaming networks where one SSID is advertised by many APs.
        up = ["nmcli", "--wait", "60", "connection", "up", *identifier]
        if device:
            up.extend(["ifname", device])
        rc, output = run(up, admin=True, timeout=70)
        if rc == 0:
            return rc, output
        errors.append(output)

        # BSSID retries remain useful for stale scan caches and mixed AP fleets.
        for access_point in candidates:
            up = ["nmcli", "--wait", "60", "connection", "up", *identifier]
            if device:
                up.extend(["ifname", device])
            up.extend(["ap", access_point["bssid"]])
            rc, output = run(up, admin=True, timeout=70)
            if rc == 0:
                return rc, output
            errors.append(f"{access_point['bssid']}: {output}")
            if device:
                run(
                    ["nmcli", "device", "wifi", "rescan", "ifname", device],
                    admin=True,
                    timeout=30,
                )
                time.sleep(1)
        errors.append(self.connection_diagnostics(device))
        return rc, "\n".join(item for item in errors if item)

    @staticmethod
    def connection_diagnostics(device):
        if not device:
            return "No Wi-Fi device selected."
        rc, output = run(
            [
                "nmcli", "-f",
                "GENERAL.DEVICE,GENERAL.TYPE,GENERAL.STATE,GENERAL.REASON,GENERAL.FIRMWARE-MISSING",
                "device", "show", device,
            ],
            admin=True,
            timeout=12,
        )
        if rc != 0:
            return f"Device diagnostics failed: {output}"
        return "Device state:\n" + output

    def connect_enterprise(self, network, credentials, device):
        profile = self.profile_name(network["ssid"])
        rc, output = self.add_wifi_profile(profile, network["ssid"], device, network.get("hidden", False))
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
        raw_security = (network.get("security") or "").upper()
        if "WPA3" in raw_security and "WPA2" not in raw_security:
            properties.extend(["802-11-wireless-security.pmf", "3"])
        if credentials["anonymous_identity"]:
            properties.extend(["802-1x.anonymous-identity", credentials["anonymous_identity"]])
        ca_policy = credentials.get(
            "ca_policy",
            "system" if credentials.get("system_ca", True) else "insecure",
        )
        if credentials["domain"] and ca_policy != "insecure":
            properties.extend(["802-1x.domain-suffix-match", credentials["domain"]])
        if ca_policy == "custom":
            properties.extend(["802-1x.ca-cert", credentials["ca_cert"]])
            properties.extend(["802-1x.system-ca-certs", "no"])
        elif ca_policy == "system":
            properties.extend(["802-1x.system-ca-certs", "yes"])
        else:
            properties.extend(["802-1x.system-ca-certs", "no"])
        if credentials["eap"] == "tls":
            properties.extend([
                "802-1x.client-cert", credentials["client_cert"],
                "802-1x.private-key", credentials["private_key"],
            ])
            if credentials["private_key_password"]:
                properties.extend(["802-1x.private-key-password", credentials["private_key_password"]])
        elif credentials["eap"] in ("peap", "ttls"):
            properties.extend([
                "802-1x.phase2-auth", credentials["phase2"],
                "802-1x.password", credentials["password"],
            ])
        else:
            properties.extend(["802-1x.password", credentials["password"]])
        rc, output = run(["nmcli", "connection", "modify", profile, *properties], admin=True, timeout=25)
        if rc != 0:
            return rc, output

        return self.activate_profile(profile, network, device, "enterprise")

    def disconnect_active(self):
        rc, active = self.nmcli("-t", "--escape", "yes", "-f", "NAME,TYPE", "connection", "show", "--active")
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
        items = [
            {
                "key": item.get("bssid") or f"{item['ssid']}-{index}",
                "name": f"{item['ssid']} {item.get('bssid', '')[-5:]}",
                "signal": item.get("signal", 0),
                "category": "router",
            }
            for index, item in enumerate(self.access_points)
        ]
        neigh_rc, neighbors = run(["ip", "neigh", "show"], timeout=5)
        if neigh_rc == 0:
            items.extend(
                {
                    "key": item["address"],
                    "name": item["name"],
                    "signal": 35,
                    "category": "device",
                    "signal_known": False,
                }
                for item in parse_ip_neighbors(neighbors)
            )
        self.signal_window.update_items(items)

    def launch_csi_3d(self, _widget):
        for command_name in ("wifi-3d-fusion", "wifi3d-fusion"):
            if command_exists(command_name):
                if not launch([command_name]):
                    message(self, "Wi-Fi 3D failed", f"Could not start {command_name}.", Gtk.MessageType.ERROR)
                return

        if command_exists("sensing-server"):
            use_linux_rssi = bool(self.wifi_devices)
            command = [
                "sensing-server", "--source", "wifi" if use_linux_rssi else "simulate",
                "--http-port", "3000", "--ws-port", "3001",
            ]
            if use_linux_rssi:
                command.extend(["--tick-ms", "500"])
            for ui_path in ("/usr/share/ruview/ui", "/opt/ruview/ui"):
                if Path(ui_path).is_dir():
                    command.extend(["--ui-path", ui_path])
                    break
            if not launch(command, admin=use_linux_rssi):
                message(self, "RuView failed", "Could not start sensing-server.", Gtk.MessageType.ERROR)
                return

            viewer = "http://127.0.0.1:3000/ui/observatory.html"

            def probe(attempt=0):
                def done(rc, _output):
                    if rc == 0:
                        launch(["ooonana-browser", viewer])
                    elif attempt < 11:
                        GLib.timeout_add_seconds(1, lambda: probe(attempt + 1) or False)
                    else:
                        message(
                            self,
                            "RuView failed",
                            "sensing-server did not become ready on port 3000.",
                            Gtk.MessageType.ERROR,
                        )

                run_async(["curl", "-fsS", viewer], done, timeout=3)

            probe()
            return

        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text="CSI 3D runtime is not installed",
        )
        dialog.format_secondary_text(
            "Normal laptop Wi-Fi cannot measure a room in 3D. RuView and wifi-3d-fusion "
            "need compatible CSI capture hardware, drivers, and large optional runtimes. "
            "Ooonana keeps the lightweight RSSI signal map preinstalled."
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.add_button("RuView", 1)
        dialog.add_button("wifi-3d-fusion", 2)
        response = dialog.run()
        if response == 1:
            launch(["xdg-open", "https://github.com/ruvnet/RuView"])
        elif response == 2:
            launch(["xdg-open", "https://github.com/MaliosDark/wifi-3d-fusion"])
        dialog.destroy()

    def repair_service(self, _widget):
        self.set_busy(True, "Repairing network service")

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "Network repair failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh(scan=True)

        run_async(
            ["ooonana-service-repair", "force-wifi"],
            done,
            admin=True,
            timeout=SERVICE_REPAIR_TIMEOUT,
        )


def main():
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana Wi-Fi")
        print("actions: radio scan grouped-ssid security-selector certificate-policy router-map device-map csi-3d disconnect repair")
        print("OOONANA_WIFI_NATIVE_OK")
        return 0
    apply_theme()
    window = WifiWindow()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
