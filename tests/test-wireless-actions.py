#!/usr/bin/env python3
import sys
from pathlib import Path
from types import MethodType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))

try:
    import gi  # noqa: F401
except ImportError:
    class DummyWidget:
        pass

    common = SimpleNamespace(
        GLib=SimpleNamespace(),
        Gtk=SimpleNamespace(Dialog=DummyWidget, Window=DummyWidget),
        apply_theme=lambda: None,
        button=lambda *_args, **_kwargs: None,
        command_exists=lambda _name: False,
        flow_row=lambda *_args, **_kwargs: None,
        header=lambda *_args, **_kwargs: None,
        label=lambda *_args, **_kwargs: None,
        launch=lambda *_args, **_kwargs: False,
        message=lambda *_args, **_kwargs: None,
        page_intro=lambda *_args, **_kwargs: None,
        read_file=lambda *_args, **_kwargs: "",
        run=lambda *_args, **_kwargs: (0, ""),
        run_async=lambda *_args, **_kwargs: None,
        run_async_task=lambda *_args, **_kwargs: None,
        system_dbus_ready=lambda: True,
    )
    sys.modules["common"] = common
    sys.modules["signal_map"] = SimpleNamespace(SignalMapWindow=DummyWidget)

import wifi_app  # noqa: E402
import bluetooth_app  # noqa: E402


def check(condition, detail):
    if not condition:
        raise AssertionError(detail)


def harness():
    value = SimpleNamespace(wifi_devices=["wlan0"])
    for name in (
        "connect_task",
        "connect_standard",
        "connect_owe",
        "connect_enterprise",
        "activate_profile",
    ):
        setattr(value, name, MethodType(getattr(wifi_app.WifiWindow, name), value))
    for name in (
        "prepare_device",
        "scan_access_points",
        "profile_uuid",
        "delete_wifi_profiles",
        "add_wifi_profile",
        "connection_diagnostics",
        "device_is_unavailable",
        "verify_profile_connected",
        "current_wifi_devices",
    ):
        setattr(value, name, getattr(wifi_app.WifiWindow, name))
    value.profile_name = wifi_app.WifiWindow.profile_name
    return value


def network(kind):
    return {
        "ssid": "School WiFi",
        "security": "WPA2 PSK" if kind == "personal" else "WPA2 802.1X",
        "security_kind": kind,
        "device": "wlan0",
        "hidden": False,
        "access_points": [
            {"bssid": "AA:BB:CC:DD:EE:01", "security_kind": kind, "device": "wlan0", "signal": 80},
            {"bssid": "AA:BB:CC:DD:EE:02", "security_kind": kind, "device": "wlan0", "signal": 70},
            {"bssid": "AA:BB:CC:DD:EE:03", "security_kind": kind, "device": "wlan1", "signal": 100},
        ],
    }


commands = []
secret_payloads = []


def fake_run(command, **_kwargs):
    commands.append(command)
    if "passwd-file" in command:
        path = Path(command[command.index("passwd-file") + 1])
        secret_payloads.append((path, path.read_text(encoding="utf-8")))
    if "DEVICE,TYPE" in command and "status" in command:
        return 0, "wlan0:wifi"
    if "NAME,UUID,TYPE" in command:
        return 0, (
            "Ooonana Wi-Fi - School WiFi:aaaaaaaa-1111-2222-3333-444444444444:802-11-wireless\n"
            "Ooonana Wi-Fi - School WiFi:bbbbbbbb-1111-2222-3333-444444444444:802-11-wireless\n"
        )
    if "GENERAL.TYPE,GENERAL.NM-MANAGED,GENERAL.STATE,GENERAL.REASON" in command:
        return 0, "wifi\nyes\n30 (disconnected)\n42 (supplicant available)"
    if "GENERAL.STATE,GENERAL.CONNECTION" in command:
        return 0, "100 (connected)\nOoonana Wi-Fi - School WiFi"
    if "IP4.ADDRESS,IP6.ADDRESS" in command:
        return 0, "192.0.2.20/24"
    if "CONNECTIVITY" in command and "general" in command:
        return 0, "full"
    if "GENERAL.NM-MANAGED" in command:
        return 0, "yes"
    if any(str(field).startswith("GENERAL.STATE") for field in command):
        return 0, "30 (disconnected)\n42 (supplicant available)"
    if "wifi" in command and "list" in command:
        return 0, (
            ":AA\\:BB\\:CC\\:DD\\:EE\\:01:School WiFi:80:WPA2 PSK:wlan0\n"
            ":AA\\:BB\\:CC\\:DD\\:EE\\:02:School WiFi:70:WPA2 PSK:wlan0"
        )
    if command[1:4] == ["-g", "connection.uuid", "connection"]:
        return 0, "11111111-2222-3333-4444-555555555555"
    if "up" in command and "AA:BB:CC:DD:EE:01" in command:
        return 10, "SSID not found"
    if "up" in command and "ap" not in command:
        return 10, "initial roaming activation failed"
    return 0, "ok"


real_run = wifi_app.run
real_sleep = wifi_app.time.sleep
wifi_app.run = fake_run
wifi_app.time.sleep = lambda _seconds: None
try:
    target = harness()
    rc, _output = target.connect_task(network("personal"), {"password": "school-secret"})
    check(rc == 0, "personal connection retries next access point")
    connects = [command for command in commands if "connection" in command and "up" in command]
    deletes = [command for command in commands if command[1:3] == ["connection", "delete"]]
    check(len(connects) == 3, "generic activation plus two BSSID retries")
    check(len(deletes) == 2, "all stale profile UUIDs removed before profile creation")
    check(all(command[3] == "uuid" for command in deletes), "stale profiles removed without ambiguous names")
    check("ap" not in connects[0], "generic activation has no BSSID lock")
    check(connects[1][-2:] == ["ap", "AA:BB:CC:DD:EE:01"], "first BSSID retry")
    check(connects[2][-2:] == ["ap", "AA:BB:CC:DD:EE:02"], "second BSSID retry")
    check(all("AA:BB:CC:DD:EE:03" not in command for command in connects), "other adapter BSSID excluded")
    check(all("device" not in command or "connect" not in command for command in commands), "SSID shortcut removed")
    check(not any(command[1:3] == ["device", "set"] for command in commands), "managed adapter is not reset")
    add = next(command for command in commands if command[1:4] == ["connection", "add", "type"])
    check("School WiFi" in add and "ifname" not in add, "profile allows compatible adapters")
    modify = [command for command in commands if command[1:3] == ["connection", "modify"]]
    check(any("802-11-wireless.hidden" in command and "no" in command for command in modify), "visible profile enabled")
    check(any("connection.interface-name" in command and "802-11-wireless.bssid" in command for command in modify), "stale hardware binding cleared")
    check(any("wpa-psk" in command and "school-secret" in command for command in modify), "personal security profile")
    check(any("802-11-wireless-security.psk-flags" in command and "0" in command for command in modify), "personal secret saved")
    check(all("uuid" in command for command in connects), "profile activated by UUID")

    commands.clear()
    renamed = network("personal")
    renamed["device"] = "wlan-old"
    renamed["access_points"][0]["device"] = "wlan-old"
    rc, _output = target.connect_task(renamed, {"password": "school-secret"})
    check(rc == 0, "renamed adapter connection")
    connects = [command for command in commands if "connection" in command and "up" in command]
    check(connects and all("wlan-old" not in command for command in connects), "stale adapter name excluded")

    selected_devices = []
    multi_adapter = harness()
    multi_adapter.wifi_devices = ["wlan0", "wlan1"]
    multi_adapter.current_wifi_devices = lambda: ["wlan0", "wlan1"]
    multi_adapter.prepare_device = lambda device, *_args: (
        [] if device == "wlan0" else [{
            "ssid": "School WiFi",
            "bssid": "AA:BB:CC:DD:EE:10",
            "security_kind": "personal",
            "device": "wlan1",
            "signal": 90,
        }]
    )

    def record_standard(_network, _credentials, device):
        selected_devices.append(device)
        return 0, "ok"

    multi_adapter.connect_standard = record_standard
    rc, _output = multi_adapter.connect_task(network("personal"), {"password": "school-secret"})
    check(rc == 0 and selected_devices == ["wlan1"], "visible SSID selects adapter that can see it")

    commands.clear()
    rc, _output = target.add_wifi_profile("Hidden profile", "Hidden WiFi", "wlan0", True)
    check(rc == 0, "hidden profile creation")
    modify = [command for command in commands if command[1:3] == ["connection", "modify"]]
    check(any("802-11-wireless.hidden" in command and "yes" in command for command in modify), "hidden profile enabled")

    commands.clear()
    advanced = {
        "mac_policy": "random",
        "ipv4_mode": "manual",
        "ipv4_address": "192.168.50.20/24",
        "ipv4_gateway": "192.168.50.1",
        "ipv4_dns": "1.1.1.1, 8.8.8.8",
        "ipv6_mode": "disabled",
        "metered": "yes",
        "proxy_mode": "auto",
        "proxy_url": "https://proxy.example.org/proxy.pac",
    }
    rc, _output = target.add_wifi_profile("Advanced profile", "Advanced WiFi", "wlan0", False, advanced)
    check(rc == 0, "advanced profile creation")
    modify = next(command for command in commands if command[1:3] == ["connection", "modify"])
    for value in (
        "random", "manual", "192.168.50.20/24", "192.168.50.1",
        "1.1.1.1 8.8.8.8", "disabled", "yes", "auto",
        "https://proxy.example.org/proxy.pac",
    ):
        check(value in modify, f"advanced profile value: {value}")

    commands.clear()
    transition = network("personal")
    transition["security"] = "WPA2 WPA3 SAE PSK"
    rc, _output = target.connect_standard(transition, {"password": "transition-secret"}, "wlan0")
    check(rc == 0, "WPA2/WPA3 transition connection")
    modify = [command for command in commands if command[1:3] == ["connection", "modify"]]
    check(any("wpa-psk" in command for command in modify), "transition network prefers compatible PSK")

    commands.clear()
    wpa3 = network("personal")
    wpa3["security"] = "WPA3 SAE"
    rc, _output = target.connect_standard(wpa3, {"password": "wpa3-secret"}, "wlan0")
    check(rc == 0, "WPA3-only connection")
    modify = [command for command in commands if command[1:3] == ["connection", "modify"]]
    check(any("sae" in command for command in modify), "WPA3-only network uses SAE")

    commands.clear()
    credentials = {
        "eap": "peap",
        "identity": "student@example.org",
        "anonymous_identity": "anonymous@example.org",
        "domain": "radius.example.org",
        "ca_cert": "",
        "ca_policy": "system",
        "system_ca": True,
        "client_cert": "",
        "private_key": "",
        "private_key_password": "",
        "phase2": "mschapv2",
        "password": "enterprise-secret",
    }
    rc, _output = target.connect_enterprise(network("enterprise"), credentials, "wlan0")
    check(rc == 0, "enterprise connection")
    modify = next(command for command in commands if command[1:3] == ["connection", "modify"] and "wpa-eap" in command)
    check("wpa-eap" in modify and "802-1x.domain-suffix-match" in modify, "enterprise security properties")
    check("802-1x.system-ca-certs" in modify and "yes" in modify, "enterprise system CA")
    check("802-1x.password-flags" in modify and "0" in modify, "enterprise password saved")
    enterprise_up = [command for command in commands if "connection" in command and "up" in command]
    check(enterprise_up and all("passwd-file" in command for command in enterprise_up), "enterprise activation uses protected secret file")
    check(secret_payloads and "802-1x.identity:student@example.org" in secret_payloads[-1][1], "enterprise identity supplied")
    check("802-1x.password:enterprise-secret" in secret_payloads[-1][1], "enterprise password supplied")
    check(not secret_payloads[-1][0].exists(), "enterprise secret file removed")

    commands.clear()
    enterprise_advanced = dict(credentials)
    enterprise_advanced.update(advanced)
    rc, _output = target.connect_enterprise(network("enterprise"), enterprise_advanced, "wlan0")
    check(rc == 0, "enterprise advanced connection")
    advanced_modify = next(
        command for command in commands
        if command[1:3] == ["connection", "modify"] and "ipv4.addresses" in command
    )
    check("manual" in advanced_modify and "disabled" in advanced_modify, "enterprise preserves IP options")
    security_modify = next(
        command for command in commands
        if command[1:3] == ["connection", "modify"] and "wpa-eap" in command
    )
    check("ipv4.method" not in security_modify and "ipv6.method" not in security_modify, "enterprise security does not reset IP options")

    commands.clear()
    unsafe_credentials = dict(credentials)
    unsafe_credentials.update({"ca_policy": "insecure", "system_ca": False, "domain": ""})
    rc, _output = target.connect_enterprise(network("enterprise"), unsafe_credentials, "wlan0")
    check(rc == 0, "enterprise connection without CA validation")
    modify = next(command for command in commands if command[1:3] == ["connection", "modify"] and "wpa-eap" in command)
    check("802-1x.system-ca-certs" in modify and "no" in modify, "enterprise no-CA policy")
    check("802-1x.ca-cert" not in modify, "enterprise no-CA policy leaves certificate unset")

    commands.clear()
    pwd_credentials = dict(credentials)
    pwd_credentials["eap"] = "pwd"
    rc, _output = target.connect_enterprise(network("enterprise"), pwd_credentials, "wlan0")
    check(rc == 0, "EAP-PWD connection")
    modify = next(command for command in commands if command[1:3] == ["connection", "modify"] and "wpa-eap" in command)
    check("802-1x.password" in modify, "EAP-PWD password")
    check("802-1x.phase2-auth" not in modify, "EAP-PWD omits invalid phase2")

    commands.clear()
    rc, _output = target.connect_owe(network("owe"), {}, "wlan0")
    check(rc == 0, "OWE connection")
    modify = next(command for command in commands if command[1:3] == ["connection", "modify"] and "owe" in command)
    check(modify[-2:] == ["802-11-wireless-security.key-mgmt", "owe"], "OWE key management")

    commands.clear()
    rc, _output = target.connect_owe(network("owe"), advanced, "wlan0")
    check(rc == 0, "OWE advanced connection")
    security_modify = next(
        command for command in commands
        if command[1:3] == ["connection", "modify"] and "owe" in command
    )
    check("ipv4.method" not in security_modify and "ipv6.method" not in security_modify, "OWE security does not reset IP options")

    commands.clear()
    blocked = harness()
    blocked.prepare_device = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        RuntimeError("Wi-Fi adapter wlan0 stayed unavailable")
    )
    rc, output = blocked.connect_task(network("personal"), {"password": "school-secret"})
    check(rc != 0 and "stayed unavailable" in output, "unavailable adapter blocks connection")
    check(not any(command[1:3] == ["connection", "add"] for command in commands), "no profile made at state 20")

    commands.clear()
    direct_scan_calls = []

    def direct_scan_run(command, **_kwargs):
        direct_scan_calls.append(command)
        if "GENERAL.TYPE,GENERAL.NM-MANAGED,GENERAL.STATE,GENERAL.REASON" in command:
            return 0, "wifi\nyes\n30 (disconnected)\n0 (none)"
        if "wifi" in command and "list" in command:
            return 0, ""
        if command[:3] == ["iw", "dev", "wlan0"] and "scan" in command:
            return 0, (
                "BSS aa:bb:cc:dd:ee:10(on wlan0)\n"
                " signal: -45.00 dBm\n"
                " capability: ESS Privacy (0x0011)\n"
                " SSID: School WiFi\n"
                " RSN:\n"
                " Authentication suites: IEEE 802.1X\n"
            )
        return 0, "ok"

    wifi_app.run = direct_scan_run
    matches = wifi_app.WifiWindow.prepare_device("wlan0", "School WiFi")
    check(matches and matches[0]["device"] == "wlan0", "direct iw scan bridges stale NetworkManager cache")

    wifi_app.run = lambda _command, **_kwargs: (
        0,
        ":AA\\:BB\\:CC\\:DD\\:EE\\:44:Device Test:77:WPA2 PSK:",
    )
    device_results = wifi_app.WifiWindow.scan_access_points("wlp0s20f3")
    check(
        device_results and device_results[0]["device"] == "wlp0s20f3",
        "per-adapter scan fills missing NetworkManager device field",
    )

    wifi_app.run = lambda command, **_kwargs: (
        (0, "100 (connected)\nOoonana Wi-Fi - School WiFi")
        if "GENERAL.STATE,GENERAL.CONNECTION" in command else
        ((0, "") if "IP4.ADDRESS,IP6.ADDRESS" in command else (0, "none"))
    )
    rc, output = wifi_app.WifiWindow.verify_profile_connected(
        "Ooonana Wi-Fi - School WiFi", "wlan0", timeout=0,
    )
    check(rc != 0 and "usable IP connection" in output, "nmcli exit success without IP is rejected")

    wifi_app.run = lambda command, **_kwargs: (
        (0, "100 (connected)\nOoonana Wi-Fi - School WiFi")
        if "GENERAL.STATE,GENERAL.CONNECTION" in command else
        ((0, "169.254.22.5/16\nfe80::1/64") if "IP4.ADDRESS,IP6.ADDRESS" in command else (0, "none"))
    )
    rc, output = wifi_app.WifiWindow.verify_profile_connected(
        "Ooonana Wi-Fi - School WiFi", "wlan0", timeout=0,
    )
    check(rc != 0 and "Addresses: none" in output, "link-local-only Wi-Fi is rejected")
finally:
    wifi_app.run = real_run
    wifi_app.time.sleep = real_sleep


class BluetoothHarness:
    def __init__(self):
        self.calls = []
        self.connect_attempts = 0

    def btctl(self, *args, **_kwargs):
        self.calls.append(args)
        if "connect" in args:
            self.connect_attempts += 1
            return 0, "Connection successful"
        if args and args[0] == "info":
            connected = "yes" if self.connect_attempts >= 2 else "no"
            return 0, f"Paired: yes\nTrusted: yes\nConnected: {connected}"
        return 0, "ok"


bluetooth_target = BluetoothHarness()
bluetooth_target.connect_with_retry = MethodType(
    bluetooth_app.BluetoothWindow.connect_with_retry,
    bluetooth_target,
)
bluetooth_target.wait_for_connection_state = MethodType(
    bluetooth_app.BluetoothWindow.wait_for_connection_state,
    bluetooth_target,
)
real_bluetooth_sleep = bluetooth_app.time.sleep
bluetooth_app.time.sleep = lambda _seconds: None
try:
    rc, output = bluetooth_target.connect_with_retry("AA:BB:CC:DD:EE:FF")
finally:
    bluetooth_app.time.sleep = real_bluetooth_sleep
check(rc == 0, "Bluetooth retry reaches confirmed connection")
check(bluetooth_target.connect_attempts == 2, "Bluetooth retries unconfirmed connection")
check(any("scan" in call for call in bluetooth_target.calls), "Bluetooth rescans before retry")
check("Connection successful" in output, "Bluetooth returns successful output")

print("ok wireless-actions")
