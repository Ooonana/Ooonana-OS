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
    flow_row,
    header,
    label,
    launch,
    message,
    page_intro,
    run,
    run_async,
    run_async_task,
    system_dbus_ready,
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
SERVICE_START_TIMEOUT = 120
SERVICE_REPAIR_TIMEOUT = 180
WIFI_DEVICE_READY_TIMEOUT = 20
WIFI_SCAN_SETTLE_TIMEOUT = 30
WIFI_ACTIVATION_TIMEOUT = 45


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
        self.set_default_size(620, 720)
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
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(320)
        scroll.add(grid)
        area.pack_start(scroll, True, True, 0)

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
        self.eap.connect("changed", self.update_security_fields)
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
            "System certificates protect against fake access points. Add server domain when school provides it.",
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
        self.tunneled_rows = []
        self.tls_rows = []
        for title, widget in (
            ("EAP method", self.eap),
            ("Identity", self.identity),
            ("Anonymous identity", self.anonymous_identity),
            ("Inner authentication", self.phase2),
            ("Server domain", self.domain),
            ("Certificate validation", self.ca_policy),
            ("CA certificate", self.ca_cert),
        ):
            attached = self.attach_row(grid, row, title, widget)
            self.enterprise_rows.append(attached)
            if title in ("Anonymous identity", "Inner authentication"):
                self.tunneled_rows.append(attached)
            row += 1
        grid.attach(self.ca_warning, 1, row, 1, 1)
        self.enterprise_rows.append((self.ca_warning,))
        row += 1
        for title, widget in (
            ("Client certificate", self.client_cert),
            ("Private key", self.private_key),
            ("Private key password", self.private_key_password),
        ):
            attached = self.attach_row(grid, row, title, widget)
            self.enterprise_rows.append(attached)
            self.tls_rows.append(attached)
            row += 1

        advanced = Gtk.Expander(label="Network options")
        advanced_grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        advanced_grid.set_margin_top(10)
        advanced.add(advanced_grid)
        grid.attach(advanced, 0, row, 2, 1)

        self.mac_policy = Gtk.ComboBoxText()
        self.mac_policy.append("stable", "Stable address per network")
        self.mac_policy.append("random", "Random address each connection")
        self.mac_policy.append("permanent", "Hardware address")
        self.mac_policy.set_active_id("stable")
        self.ipv4_mode = Gtk.ComboBoxText()
        self.ipv4_mode.append("auto", "Automatic (DHCP)")
        self.ipv4_mode.append("manual", "Manual")
        self.ipv4_mode.set_active_id("auto")
        self.ipv4_mode.connect("changed", self.update_advanced_fields)
        self.ipv4_address = text_entry(placeholder="192.168.1.20/24")
        self.ipv4_gateway = text_entry(placeholder="192.168.1.1")
        self.ipv4_dns = text_entry(placeholder="1.1.1.1, 8.8.8.8")
        self.ipv6_mode = Gtk.ComboBoxText()
        self.ipv6_mode.append("auto", "Automatic")
        self.ipv6_mode.append("disabled", "Disabled")
        self.ipv6_mode.set_active_id("auto")
        self.metered = Gtk.ComboBoxText()
        self.metered.append("unknown", "Detect automatically")
        self.metered.append("yes", "Metered")
        self.metered.append("no", "Not metered")
        self.metered.set_active_id("unknown")
        self.proxy_mode = Gtk.ComboBoxText()
        self.proxy_mode.append("none", "None")
        self.proxy_mode.append("auto", "Automatic configuration URL")
        self.proxy_mode.set_active_id("none")
        self.proxy_mode.connect("changed", self.update_advanced_fields)
        self.proxy_url = text_entry(placeholder="https://proxy.example.org/proxy.pac")

        advanced_row = 0
        for title, widget in (
            ("MAC address", self.mac_policy),
            ("IPv4", self.ipv4_mode),
        ):
            advanced_row = add_grid_row(advanced_grid, advanced_row, title, widget)
        self.manual_ip_rows = []
        for title, widget in (
            ("Address / prefix", self.ipv4_address),
            ("Gateway", self.ipv4_gateway),
            ("DNS servers", self.ipv4_dns),
        ):
            attached = self.attach_row(advanced_grid, advanced_row, title, widget)
            self.manual_ip_rows.append(attached)
            advanced_row += 1
        for title, widget in (
            ("IPv6", self.ipv6_mode),
            ("Metered network", self.metered),
            ("Proxy", self.proxy_mode),
        ):
            advanced_row = add_grid_row(advanced_grid, advanced_row, title, widget)
        self.proxy_url_row = self.attach_row(advanced_grid, advanced_row, "Proxy URL", self.proxy_url)
        self.show_all()
        self.update_security_fields()
        self.update_advanced_fields()

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
        eap = (self.eap.get_active_text() or "PEAP").lower()
        for widget in self.password_row:
            widget.set_visible(kind in ("personal", "wep") or (kind == "enterprise" and eap != "tls"))
        for row in self.enterprise_rows:
            for widget in row:
                widget.set_visible(kind == "enterprise")
        for row in self.tunneled_rows:
            for widget in row:
                widget.set_visible(kind == "enterprise" and eap in ("peap", "ttls"))
        for row in self.tls_rows:
            for widget in row:
                widget.set_visible(kind == "enterprise" and eap == "tls")

    def update_advanced_fields(self, _widget=None):
        manual = self.ipv4_mode.get_active_id() == "manual"
        for row in self.manual_ip_rows:
            for widget in row:
                widget.set_visible(manual)
        proxy_auto = self.proxy_mode.get_active_id() == "auto"
        for widget in self.proxy_url_row:
            widget.set_visible(proxy_auto)

    def update_ca_policy(self, _widget=None):
        policy = self.ca_policy.get_active_id() or "system"
        self.ca_cert.set_sensitive(policy == "custom")
        style = self.ca_warning.get_style_context()
        if policy == "insecure":
            self.ca_warning.set_text(
                "Unsafe: server identity is not checked. Use only when network administrator requires it."
            )
            style.add_class("status-bad")
        elif policy == "custom":
            self.ca_warning.set_text("Select CA certificate supplied by network administrator.")
            style.remove_class("status-bad")
        else:
            self.ca_warning.set_text(
                "System certificates protect against fake access points. Add server domain when school provides it."
            )
            style.remove_class("status-bad")

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
            "mac_policy": self.mac_policy.get_active_id() or "stable",
            "ipv4_mode": self.ipv4_mode.get_active_id() or "auto",
            "ipv4_address": self.ipv4_address.get_text().strip(),
            "ipv4_gateway": self.ipv4_gateway.get_text().strip(),
            "ipv4_dns": self.ipv4_dns.get_text().strip(),
            "ipv6_mode": self.ipv6_mode.get_active_id() or "auto",
            "metered": self.metered.get_active_id() or "unknown",
            "proxy_mode": self.proxy_mode.get_active_id() or "none",
            "proxy_url": self.proxy_url.get_text().strip(),
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
        if values["ipv4_mode"] == "manual" and "/" not in values["ipv4_address"]:
            return "Manual IPv4 address needs a prefix, for example 192.168.1.20/24."
        if values["proxy_mode"] == "auto" and not values["proxy_url"]:
            return "Automatic proxy needs a configuration URL."
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
        self.ready_wifi_devices = []
        self.device_states = {}
        self.signal_window = None
        self.refresh_running = False
        self.refresh_pending_scan = False

        bar = header(self, "Wi-Fi", "NetworkManager", "network-wireless-symbolic")
        self.refresh_button = button("Refresh", "view-refresh-symbolic", lambda *_: self.refresh(scan=True))
        bar.pack_end(self.refresh_button)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_border_width(20)
        self.add(root)
        root.pack_start(page_intro("Wireless networks", "Nearby access points, saved profiles, and enterprise security."), False, False, 0)

        self.service_label = label("Service: checking", "status-warn")
        self.radio_label = label("Radio: checking", "status-warn")
        self.active_label = label("Connection: checking", "status-warn")
        status = flow_row((self.service_label, self.radio_label, self.active_label), 3)
        root.pack_start(status, False, False, 0)

        self.radio_button = button("Wi-Fi on", "network-wireless-symbolic", self.toggle_radio, "suggested-action")
        self.scan_button = button("Scan", "edit-find-symbolic", lambda *_: self.refresh(scan=True))
        self.repair_button = button("Repair service", "emblem-system-symbolic", self.repair_service)
        self.hardware_reset_button = button("Reset adapter", "view-refresh-symbolic", self.reset_hardware)
        toolbar = flow_row(
            (
                self.radio_button,
                self.scan_button,
                button("Other network", "list-add-symbolic", self.connect_manual),
                button("Signal map", "find-location-symbolic", self.show_signal_map),
                button("CSI 3D", "video-display-symbolic", self.launch_csi_3d),
                button("Profiles", "document-edit-symbolic", lambda *_: launch(["nm-connection-editor"])),
                self.repair_button,
                self.hardware_reset_button,
            ),
            5,
        )
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
        for widget in (
            self.refresh_button,
            self.radio_button,
            self.scan_button,
            self.repair_button,
            self.hardware_reset_button,
        ):
            widget.set_sensitive(not busy)
        if busy:
            self.progress.show()
            self.progress.pulse()
            self.progress.set_text(text)
            self.progress.set_show_text(bool(text))
        else:
            self.progress.hide()

    def initial_refresh(self):
        self.set_busy(True, "Starting NetworkManager")

        def task():
            dbus_ok = system_dbus_ready()
            daemon_rc, _daemon = run(["/bin/busybox", "pidof", "NetworkManager"], timeout=2)
            supplicant_rc, _supplicant = run(["/bin/busybox", "pidof", "wpa_supplicant"], timeout=2)
            if dbus_ok and daemon_rc == 0 and supplicant_rc == 0:
                return 0, ""
            return run(
                ["ooonana-service-repair", "wifi"],
                admin=True,
                timeout=SERVICE_START_TIMEOUT,
            )

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "NetworkManager repair failed", output or f"Exit status {rc}. Check /var/log/ooonana-services.log.", Gtk.MessageType.ERROR)
            self.refresh(scan=True)

        run_async_task(task, done)

    def refresh(self, scan=False):
        if self.refresh_running:
            self.refresh_pending_scan = self.refresh_pending_scan or scan
            return
        self.refresh_running = True
        self.set_busy(True, "Scanning Wi-Fi" if scan else "Refreshing Wi-Fi")

        def task():
            return 0, self.collect_refresh_data(scan)

        def done(rc, data):
            self.refresh_running = False
            self.set_busy(False)
            if rc != 0:
                message(self, "Wi-Fi refresh failed", str(data), Gtk.MessageType.ERROR)
            else:
                self.apply_refresh_data(data)
            pending_scan = self.refresh_pending_scan
            self.refresh_pending_scan = False
            if pending_scan:
                GLib.idle_add(self.refresh, True)

        run_async_task(task, done)

    def collect_refresh_data(self, scan=False):
        dbus_ok = system_dbus_ready()
        daemon_rc, _daemon = run(["/bin/busybox", "pidof", "NetworkManager"], timeout=2)
        supplicant_rc, _supplicant = run(["/bin/busybox", "pidof", "wpa_supplicant"], timeout=2)
        _radio_rc, radio = self.nmcli("-t", "-f", "WIFI", "radio", timeout=4)
        devices_rc, devices = self.nmcli("-t", "--escape", "yes", "-f", "DEVICE,TYPE,STATE", "device", "status", timeout=5)
        active_rc, active = self.nmcli(
            "-t", "--escape", "yes", "-f", "NAME,DEVICE,TYPE",
            "connection", "show", "--active", timeout=5,
        )
        wifi_devices = []
        ready_wifi_devices = []
        device_states = {}
        if devices_rc == 0:
            for line in devices.splitlines():
                parts = split_nmcli_terse(line)
                if len(parts) == 3 and parts[1] == "wifi":
                    wifi_devices.append(parts[0])
                    device_states[parts[0]] = parts[2]
                    if parts[2].lower() not in ("unavailable", "unmanaged", "unknown"):
                        ready_wifi_devices.append(parts[0])

        scan_errors = []
        if scan:
            for device in wifi_devices:
                ready_rc, ready_output = self.wait_for_device_ready(device, timeout=8)
                if ready_rc != 0:
                    scan_errors.append(f"{device}: {ready_output.splitlines()[0]}")
                    continue
                run(["iw", "dev", device, "set", "power_save", "off"], admin=True, timeout=5)
                rc, output = self.nmcli("device", "wifi", "rescan", "ifname", device, timeout=25)
                if rc != 0 and output:
                    scan_errors.append(f"{device}: {output.splitlines()[-1]}")

        active_connections = {}
        if active_rc == 0:
            for line in active.splitlines():
                fields = split_nmcli_terse(line)
                if len(fields) == 3 and fields[2] in ("802-11-wireless", "wifi"):
                    active_connections[fields[1]] = fields[0]
        connected_devices = [
            device for device in wifi_devices
            if device_states.get(device, "").lower() == "connected"
        ]
        active_name = active_connections.get(connected_devices[0], "") if connected_devices else ""
        snapshot = None
        if active_name:
            snapshot = self.connection_snapshot(connected_devices[0])

        access_points = []
        list_rc = 0
        for device in wifi_devices:
            device_rc, networks = self.nmcli(
                "-t", "--escape", "yes", "-f", "IN-USE,BSSID,SSID,SIGNAL,SECURITY,DEVICE",
                "device", "wifi", "list", "ifname", device,
                "--rescan", "yes" if scan else "no",
                timeout=30 if scan else 15,
            )
            if device_rc != 0:
                list_rc = device_rc
                if networks:
                    scan_errors.append(f"{device}: {networks.splitlines()[-1]}")
                continue
            parsed = parse_nmcli_wifi(networks)
            for item in parsed:
                item["device"] = item.get("device") or device
            access_points.extend(parsed)
        if not wifi_devices:
            list_rc, networks = self.nmcli(
                "-t", "--escape", "yes", "-f", "IN-USE,BSSID,SSID,SIGNAL,SECURITY,DEVICE",
                "device", "wifi", "list", "--rescan", "yes" if scan else "no",
                timeout=30 if scan else 15,
            )
            access_points = parse_nmcli_wifi(networks) if list_rc == 0 else []
        unique_access_points = {}
        for item in access_points:
            key = (item.get("device"), item.get("bssid"), item.get("ssid"), item.get("security"))
            previous = unique_access_points.get(key)
            if previous is None or item.get("signal", 0) > previous.get("signal", 0):
                unique_access_points[key] = item
        access_points = list(unique_access_points.values())
        if not access_points:
            for device in wifi_devices:
                iw_rc, iw_output = run(["iw", "dev", device, "scan"], admin=True, timeout=30)
                if iw_rc == 0:
                    access_points.extend(parse_iw_wifi(iw_output, device))
                elif iw_output:
                    scan_errors.append(f"{device}: {iw_output.splitlines()[-1]}")
        grouped = group_wifi_access_points(access_points)
        return {
            "dbus_ok": dbus_ok,
            "daemon_ok": daemon_rc == 0,
            "supplicant_ok": supplicant_rc == 0,
            "radio": radio,
            "wifi_devices": wifi_devices,
            "ready_wifi_devices": ready_wifi_devices,
            "device_states": device_states,
            "active_name": active_name,
            "connected_device": connected_devices[0] if connected_devices else "",
            "snapshot": snapshot,
            "access_points": access_points,
            "grouped": grouped,
            "scan_errors": scan_errors,
            "list_rc": list_rc,
        }

    def apply_refresh_data(self, data):
        self.wifi_devices = data["wifi_devices"]
        self.ready_wifi_devices = data["ready_wifi_devices"]
        self.device_states = data["device_states"]
        self.access_points = data["access_points"]
        services_ready = data["dbus_ok"] and data["daemon_ok"] and data["supplicant_ok"]
        if services_ready:
            service_text = "Services: D-Bus + NetworkManager + supplicant"
        elif not data["dbus_ok"]:
            service_text = "Services: system D-Bus stopped"
        elif data["daemon_ok"]:
            service_text = "Services: supplicant stopped"
        else:
            service_text = "Services: NetworkManager stopped"
        self.set_state(self.service_label, service_text, "good" if services_ready else "bad")
        if self.wifi_devices:
            adapter_text = ", ".join(
                f"{name} ({self.device_states.get(name, 'unknown')})"
                for name in self.wifi_devices
            )
        else:
            adapter_text = "not detected"
        radio = data["radio"]
        self.set_state(
            self.radio_label,
            f"Radio: {radio or 'unknown'} | Adapter: {adapter_text}",
            "good" if radio == "enabled" and self.ready_wifi_devices else "warn",
        )
        snapshot = data["snapshot"]
        active_name = data["active_name"]
        if active_name and snapshot:
            addresses = snapshot["addresses"]
            connectivity = snapshot["connectivity"]
            verified = snapshot["state"] == 100 and bool(addresses)
            connection_text = f"Connection: {active_name} | {connectivity}"
            connection_state = "good" if verified and connectivity == "full" else "warn"
        elif any(self.device_states.get(device, "").lower() in ("connecting", "config", "ip-config") for device in self.wifi_devices):
            connection_text = "Connection: activating"
            connection_state = "warn"
        else:
            connection_text = "Connection: offline"
            connection_state = "warn"
        self.set_state(self.active_label, connection_text, connection_state)
        self.radio_button.set_label("Wi-Fi off" if radio == "enabled" else "Wi-Fi on")

        grouped = data["grouped"]
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
        scan_errors = data["scan_errors"]
        if not self.wifi_devices:
            self.detail.set_text("Wi-Fi adapter not detected. Repair reloads firmware, clears RFKill, retriggers udev, then restarts NetworkManager.")
        elif not self.ready_wifi_devices:
            detail = "Wi-Fi adapter detected but unavailable to NetworkManager. Repair restarts wpa_supplicant and NetworkManager."
            if scan_errors:
                detail += " " + " | ".join(dict.fromkeys(scan_errors))
            self.detail.set_text(detail)
        elif not grouped:
            detail = "No networks found after NetworkManager and direct hardware scans."
            if scan_errors:
                detail += " " + " | ".join(dict.fromkeys(scan_errors))
            self.detail.set_text(detail)
        else:
            self.detail.set_text(f"{len(grouped)} network name(s), {len(self.access_points)} access point(s). Duplicate SSIDs are grouped.")

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
        live_devices = self.current_wifi_devices()
        known_devices = self.wifi_devices if live_devices is None else live_devices
        device_candidates = []
        for candidate in [network.get("device"), *known_devices]:
            if live_devices is not None and candidate not in live_devices:
                continue
            if candidate and candidate not in device_candidates:
                device_candidates.append(candidate)
        if not device_candidates:
            return 1, "No Wi-Fi adapter is available."

        preparation_errors = []
        fresh_access_points = []
        device = ""
        fallback_device = ""
        for candidate in device_candidates:
            try:
                candidate_access_points = self.prepare_device(
                    candidate,
                    ssid,
                    network.get("hidden", False),
                )
                if not network.get("hidden", False) and not candidate_access_points:
                    preparation_errors.append(
                        f"{candidate}: {ssid!r} was not visible in NetworkManager's latest cache; trying activation anyway."
                    )
                    if not fallback_device:
                        fallback_device = candidate
                    continue
                fresh_access_points = candidate_access_points
                device = candidate
                break
            except RuntimeError as exc:
                preparation_errors.append(f"{candidate}: {exc}")
        if not device and fallback_device:
            device = fallback_device
        if not device:
            return 1, (
                f"No ready Wi-Fi adapter can see {ssid!r}.\n"
                + "\n".join(preparation_errors)
                + "\nUse Repair service once, then Scan. Use Other network only for hidden SSIDs."
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
            return self.connect_owe(network, credentials, device)
        return self.connect_standard(network, credentials, device)

    @staticmethod
    def current_wifi_devices():
        rc, output = run(
            ["nmcli", "-t", "--escape", "yes", "-f", "DEVICE,TYPE", "device", "status"],
            admin=True,
            timeout=8,
        )
        if rc != 0:
            return None
        devices = []
        for line in output.splitlines():
            fields = split_nmcli_terse(line)
            if len(fields) == 2 and fields[1] == "wifi" and fields[0] not in devices:
                devices.append(fields[0])
        return devices

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
        access_points = parse_nmcli_wifi(output) if rc == 0 else []
        for item in access_points:
            item["device"] = item.get("device") or device
        return access_points

    @staticmethod
    def prepare_device(device, ssid, hidden=False):
        run(["nmcli", "networking", "on"], admin=True, timeout=8)
        run(["nmcli", "radio", "wifi", "on"], admin=True, timeout=8)
        if not device:
            return []
        run(["iw", "dev", device, "set", "power_save", "off"], admin=True, timeout=8)
        ready_rc, ready_output = WifiWindow.wait_for_device_ready(device)
        if ready_rc != 0:
            raise RuntimeError(ready_output)
        if hidden:
            run(
                ["nmcli", "device", "wifi", "rescan", "ifname", device],
                admin=True,
                timeout=WIFI_SCAN_SETTLE_TIMEOUT,
            )
            return []

        # Rescans are asynchronous. Campus access points may need several
        # rounds before NetworkManager has a usable BSSID.
        deadline = time.monotonic() + WIFI_SCAN_SETTLE_TIMEOUT
        next_rescan = 0
        direct_scan_done = False
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
            if not direct_scan_done:
                direct_scan_done = True
                iw_rc, iw_output = run(
                    ["iw", "dev", device, "scan"],
                    admin=True,
                    timeout=30,
                )
                if iw_rc == 0:
                    direct_matches = [
                        item for item in parse_iw_wifi(iw_output, device)
                        if item.get("ssid") == ssid
                    ]
                    if direct_matches:
                        return direct_matches
            time.sleep(2)
        return []

    @staticmethod
    def wait_for_device_ready(device, timeout=WIFI_DEVICE_READY_TIMEOUT):
        deadline = time.monotonic() + timeout
        last_output = ""
        while time.monotonic() < deadline:
            rc, output = run(
                [
                    "nmcli", "-g",
                    "GENERAL.TYPE,GENERAL.NM-MANAGED,GENERAL.STATE,GENERAL.REASON",
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
            f"Wi-Fi adapter {device} stayed unavailable for {timeout} seconds.\n"
            f"{last_output}\nNetworkManager or wpa_supplicant is not ready."
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
    def delete_wifi_profiles(profile):
        rc, output = run(
            [
                "nmcli", "-t", "--escape", "yes", "-f", "NAME,UUID,TYPE",
                "connection", "show",
            ],
            admin=True,
            timeout=12,
        )
        if rc != 0:
            return rc, output
        errors = []
        for line in output.splitlines():
            fields = split_nmcli_terse(line)
            if len(fields) != 3 or fields[0] != profile:
                continue
            if fields[2] not in ("802-11-wireless", "wifi"):
                continue
            delete_rc, delete_output = run(
                ["nmcli", "connection", "delete", "uuid", fields[1]],
                admin=True,
                timeout=12,
            )
            if delete_rc != 0:
                errors.append(delete_output or f"Could not remove stale profile {fields[1]}")
        return (1, "\n".join(errors)) if errors else (0, "")

    @staticmethod
    def add_wifi_profile(profile, ssid, device, hidden=False, credentials=None):
        credentials = credentials or {}
        rc, output = WifiWindow.delete_wifi_profiles(profile)
        if rc != 0:
            return rc, output
        command = [
            "nmcli", "connection", "add", "type", "wifi",
            "con-name", profile, "ssid", ssid,
        ]
        rc, output = run(command, admin=True, timeout=20)
        if rc != 0:
            return rc, output
        ipv4_mode = credentials.get("ipv4_mode", "auto")
        proxy_mode = credentials.get("proxy_mode", "none")
        properties = [
            "connection.autoconnect", "yes",
            "connection.permissions", "",
            "connection.metered", credentials.get("metered", "unknown"),
            "ipv4.method", ipv4_mode,
            "ipv4.may-fail", "no",
            "ipv6.method", credentials.get("ipv6_mode", "auto"),
            "ipv6.may-fail", "yes",
            "proxy.method", proxy_mode,
            "802-11-wireless.mode", "infrastructure",
            # Scan results shown by this UI are visible networks. Marking every
            # profile hidden makes roaming campus APs fail with SSID_NOT_FOUND.
            "802-11-wireless.hidden", "yes" if hidden else "no",
            "802-11-wireless.powersave", "2",
            "802-11-wireless.cloned-mac-address", credentials.get("mac_policy", "stable"),
        ]
        if ipv4_mode == "manual":
            properties.extend(["ipv4.addresses", credentials.get("ipv4_address", "")])
            if credentials.get("ipv4_gateway"):
                properties.extend(["ipv4.gateway", credentials["ipv4_gateway"]])
            if credentials.get("ipv4_dns"):
                dns_servers = " ".join(credentials["ipv4_dns"].replace(",", " ").split())
                properties.extend(["ipv4.dns", dns_servers])
        if proxy_mode == "auto":
            properties.extend(["proxy.pac-url", credentials.get("proxy_url", "")])
        return run(
            ["nmcli", "connection", "modify", profile, *properties],
            admin=True,
            timeout=20,
        )

    def connect_standard(self, network, credentials, device):
        profile = self.profile_name(network["ssid"])
        rc, output = self.add_wifi_profile(
            profile, network["ssid"], device, network.get("hidden", False), credentials,
        )
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
                "802-11-wireless-security.psk-flags", "0",
            ]
        elif network["security_kind"] == "wep":
            is_hex = len(password) in (10, 26) and all(char in "0123456789abcdefABCDEF" for char in password)
            key_type = "1" if len(password) in (5, 13) or is_hex else "2"
            properties = [
                "802-11-wireless-security.key-mgmt", "none",
                "802-11-wireless-security.wep-key0", password,
                "802-11-wireless-security.wep-key-type", key_type,
                "802-11-wireless-security.wep-key-flags", "0",
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

    def connect_owe(self, network, credentials, device):
        profile = self.profile_name(network["ssid"])
        rc, output = self.add_wifi_profile(
            profile, network["ssid"], device, network.get("hidden", False), credentials,
        )
        if rc != 0:
            return rc, output
        rc, output = run(
            [
                "nmcli", "connection", "modify", profile,
                "connection.autoconnect", "yes",
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
        candidates = candidates[:3]

        # Let NetworkManager choose the strongest matching BSSID first. This is
        # required for roaming networks where one SSID is advertised by many APs.
        up = ["nmcli", "--wait", str(WIFI_ACTIVATION_TIMEOUT), "connection", "up", *identifier]
        if device:
            up.extend(["ifname", device])
        rc, output = run(up, admin=True, timeout=WIFI_ACTIVATION_TIMEOUT + 10)
        if rc == 0:
            verify_rc, verify_output = self.verify_profile_connected(profile, device)
            if verify_rc == 0:
                return 0, "\n".join(item for item in (output, verify_output) if item)
            rc = verify_rc
            errors.append(verify_output)
            run(["nmcli", "connection", "down", *identifier], admin=True, timeout=12)
        elif output:
            errors.append(output)
        unavailable, state_output = self.device_is_unavailable(device)
        if unavailable:
            errors.append(state_output)
            errors.append(self.connection_diagnostics(device))
            return rc, "\n".join(item for item in errors if item)

        # BSSID retries remain useful for stale scan caches and mixed AP fleets.
        for access_point in candidates:
            up = ["nmcli", "--wait", str(WIFI_ACTIVATION_TIMEOUT), "connection", "up", *identifier]
            if device:
                up.extend(["ifname", device])
            up.extend(["ap", access_point["bssid"]])
            rc, output = run(up, admin=True, timeout=WIFI_ACTIVATION_TIMEOUT + 10)
            if rc == 0:
                verify_rc, verify_output = self.verify_profile_connected(profile, device)
                if verify_rc == 0:
                    return 0, "\n".join(item for item in (output, verify_output) if item)
                rc = verify_rc
                output = verify_output
                run(["nmcli", "connection", "down", *identifier], admin=True, timeout=12)
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
    def connection_snapshot(device):
        state_rc, state_output = run(
            ["nmcli", "-g", "GENERAL.STATE,GENERAL.CONNECTION", "device", "show", device],
            admin=True,
            timeout=8,
        )
        state_lines = state_output.splitlines()
        try:
            state = int(state_lines[0].strip().split()[0]) if state_rc == 0 and state_lines else 0
        except (ValueError, IndexError):
            state = 0
        connection = state_lines[1].strip() if len(state_lines) > 1 else ""
        address_rc, address_output = run(
            ["nmcli", "-g", "IP4.ADDRESS,IP6.ADDRESS", "device", "show", device],
            admin=True,
            timeout=8,
        )
        addresses = []
        if address_rc == 0:
            addresses = [
                value.strip() for value in address_output.splitlines()
                if value.strip()
                and not value.strip().lower().startswith("fe80:")
                and not value.strip().startswith("169.254.")
            ]
        connectivity_rc, connectivity_output = run(
            ["nmcli", "-t", "-f", "CONNECTIVITY", "general"],
            admin=True,
            timeout=8,
        )
        connectivity = connectivity_output.splitlines()[0].strip().lower() if connectivity_rc == 0 and connectivity_output.strip() else "unknown"
        return {
            "state": state,
            "connection": connection,
            "addresses": addresses,
            "connectivity": connectivity,
            "detail": state_output,
        }

    @staticmethod
    def verify_profile_connected(profile, device, timeout=20):
        deadline = time.monotonic() + timeout
        last = {}
        while True:
            last = WifiWindow.connection_snapshot(device)
            matches = not profile or last["connection"] == profile
            if last["state"] == 100 and matches and last["addresses"]:
                connectivity = last["connectivity"]
                return 0, (
                    f"Verified {profile} on {device}: {', '.join(last['addresses'])}; "
                    f"connectivity {connectivity}."
                )
            if time.monotonic() >= deadline:
                break
            time.sleep(1)
        return 1, (
            f"NetworkManager did not confirm a usable IP connection for {profile} on {device}.\n"
            f"State: {last.get('state', 0)}  Active: {last.get('connection') or 'none'}  "
            f"Addresses: {', '.join(last.get('addresses', [])) or 'none'}  "
            f"Connectivity: {last.get('connectivity', 'unknown')}\n"
            f"{last.get('detail', '')}"
        ).strip()

    @staticmethod
    def device_is_unavailable(device):
        if not device:
            return True, "No Wi-Fi device selected."
        rc, output = run(
            ["nmcli", "-g", "GENERAL.STATE,GENERAL.REASON", "device", "show", device],
            admin=True,
            timeout=8,
        )
        fields = output.splitlines()
        try:
            state = int(fields[0].strip().split()[0]) if rc == 0 and fields else 0
        except (ValueError, IndexError):
            state = 0
        return state < 30, f"Device state after activation:\n{output}"

    @staticmethod
    def connection_diagnostics(device):
        if not device:
            return "No Wi-Fi device selected."
        rc, output = run(
            [
                "nmcli", "-f",
                "GENERAL.DEVICE,GENERAL.TYPE,GENERAL.NM-MANAGED,GENERAL.STATE,GENERAL.REASON,GENERAL.FIRMWARE-MISSING",
                "device", "show", device,
            ],
            admin=True,
            timeout=12,
        )
        sections = ["Device state:\n" + output if rc == 0 else f"Device diagnostics failed: {output}"]
        for title, command in (
            ("NetworkManager", ["nmcli", "-f", "STATE,CONNECTIVITY,WIFI-HW,WIFI", "general"]),
            ("RFKill", ["rfkill", "list"]),
            ("Wireless interface", ["iw", "dev", device, "info"]),
            ("NetworkManager log", ["tail", "-n", "80", "/var/log/NetworkManager.log"]),
        ):
            detail_rc, detail = run(command, admin=True, timeout=10)
            if detail_rc == 0 and detail:
                sections.append(f"{title}:\n{detail}")
        return "\n\n".join(sections)

    def connect_enterprise(self, network, credentials, device):
        profile = self.profile_name(network["ssid"])
        rc, output = self.add_wifi_profile(
            profile, network["ssid"], device, network.get("hidden", False), credentials,
        )
        if rc != 0:
            return rc, output

        properties = [
            "connection.autoconnect", "yes",
            "802-11-wireless-security.key-mgmt", "wpa-eap",
            "802-1x.eap", credentials["eap"],
            "802-1x.identity", credentials["identity"],
            "802-1x.password-flags", "0",
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
                properties.extend([
                    "802-1x.private-key-password", credentials["private_key_password"],
                    "802-1x.private-key-password-flags", "0",
                ])
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
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text="Choose Wi-Fi 3D mode",
        )
        dialog.format_secondary_text(
            "RuView uses Ooonana sensing-server. wifi-3d-fusion needs compatible CSI hardware and drivers. "
            "Normal laptop Wi-Fi provides only coarse RSSI mapping."
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.add_button("RuView", 1)
        dialog.add_button("wifi-3d-fusion", 2)
        response = dialog.run()
        dialog.destroy()
        if response == 1:
            self.launch_ruview_runtime()
        elif response == 2:
            self.launch_wifi_3d_fusion()

    def launch_wifi_3d_fusion(self):
        for command_name in ("wifi-3d-fusion", "wifi3d-fusion"):
            if command_exists(command_name):
                if not launch([command_name]):
                    message(self, "Wi-Fi 3D failed", f"Could not start {command_name}.", Gtk.MessageType.ERROR)
                return
        launch(["xdg-open", "https://github.com/MaliosDark/wifi-3d-fusion"])

    def launch_ruview_runtime(self):
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
            text="RuView runtime is not installed",
        )
        dialog.format_secondary_text(
            "Install sensing-server for RuView. Full pose tracking needs supported CSI hardware."
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

        run_async(
            ["ooonana-service-repair", "force-wifi"],
            done,
            admin=True,
            timeout=SERVICE_REPAIR_TIMEOUT,
        )

    def reset_hardware(self, _widget):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text="Reset Wi-Fi adapter?",
        )
        dialog.format_secondary_text(
            "Use only when normal service repair fails. Adapter disappears briefly while its kernel driver resets."
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Reset adapter", Gtk.ResponseType.OK)
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        self.set_busy(True, "Resetting Wi-Fi adapter")

        def done(rc, output):
            self.set_busy(False)
            if rc != 0:
                message(self, "Wi-Fi reset failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh(scan=True)

        run_async(
            ["ooonana-service-repair", "deep-wifi"],
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
