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
        header=lambda *_args, **_kwargs: None,
        label=lambda *_args, **_kwargs: None,
        launch=lambda *_args, **_kwargs: False,
        message=lambda *_args, **_kwargs: None,
        page_intro=lambda *_args, **_kwargs: None,
        read_file=lambda *_args, **_kwargs: "",
        run=lambda *_args, **_kwargs: (0, ""),
        run_async=lambda *_args, **_kwargs: None,
        run_async_task=lambda *_args, **_kwargs: None,
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
        "add_wifi_profile",
        "connection_diagnostics",
        "wait_for_device_ready",
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


def fake_run(command, **_kwargs):
    commands.append(command)
    if command[1:4] == ["-g", "GENERAL.NM-MANAGED", "device"]:
        return 0, "yes"
    if command[1:3] == ["-g", "GENERAL.TYPE,GENERAL.NM-MANAGED,GENERAL.STATE,GENERAL.REASON"]:
        return 0, "wifi\nyes\n30 (disconnected)\n0 (No reason given)"
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
    check(len(deletes) == 1, "stale profile removed before profile creation")
    check("ap" not in connects[0], "generic activation has no BSSID lock")
    check(connects[1][-2:] == ["ap", "AA:BB:CC:DD:EE:01"], "first BSSID retry")
    check(connects[2][-2:] == ["ap", "AA:BB:CC:DD:EE:02"], "second BSSID retry")
    check(all("AA:BB:CC:DD:EE:03" not in command for command in connects), "other adapter BSSID excluded")
    check(all("device" not in command or "connect" not in command for command in commands), "SSID shortcut removed")
    add = next(command for command in commands if command[1:4] == ["connection", "add", "type"])
    check("School WiFi" in add and "wlan0" not in add, "profile stays available to compatible adapters")
    check(
        not any(command[1:4] == ["device", "set", "wlan0"] for command in commands),
        "already-managed adapter is not reset",
    )
    modify = [command for command in commands if command[1:3] == ["connection", "modify"]]
    check(any("802-11-wireless.hidden" in command and "no" in command for command in modify), "visible profile enabled")
    check(any("connection.metered" in command and "unknown" in command for command in modify), "automatic metered detection")
    check(any("proxy.method" in command and "none" in command for command in modify), "no proxy default")
    check(any("802-11-wireless.cloned-mac-address" in command and "stable" in command for command in modify), "stable randomized MAC")
    check(any("wpa-psk" in command and "school-secret" in command for command in modify), "personal security profile")
    check(all("uuid" in command for command in connects), "profile activated by UUID")

    commands.clear()
    rc, _output = target.add_wifi_profile("Hidden profile", "Hidden WiFi", "wlan0", True)
    check(rc == 0, "hidden profile creation")
    modify = [command for command in commands if command[1:3] == ["connection", "modify"]]
    check(any("802-11-wireless.hidden" in command and "yes" in command for command in modify), "hidden profile enabled")

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
        "ca_policy": "system",
        "ca_cert": "",
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

    commands.clear()
    wpa3_enterprise = network("enterprise")
    wpa3_enterprise["security"] = "WPA3 802.1X"
    rc, _output = target.connect_enterprise(wpa3_enterprise, credentials, "wlan0")
    check(rc == 0, "WPA3 enterprise connection")
    modify = next(command for command in commands if command[1:3] == ["connection", "modify"] and "wpa-eap" in command)
    check("802-11-wireless-security.pmf" in modify and "3" in modify, "WPA3 enterprise requires PMF")

    commands.clear()
    custom_ca = dict(credentials)
    custom_ca.update({"ca_policy": "custom", "ca_cert": "/etc/ssl/certs/school.pem"})
    rc, _output = target.connect_enterprise(network("enterprise"), custom_ca, "wlan0")
    check(rc == 0, "enterprise custom CA connection")
    modify = next(command for command in commands if command[1:3] == ["connection", "modify"] and "wpa-eap" in command)
    check("/etc/ssl/certs/school.pem" in modify, "enterprise custom CA path")
    check(modify[modify.index("802-1x.system-ca-certs") + 1] == "no", "custom CA disables system CA")

    commands.clear()
    insecure = dict(credentials)
    insecure.update({"ca_policy": "insecure", "domain": ""})
    rc, _output = target.connect_enterprise(network("enterprise"), insecure, "wlan0")
    check(rc == 0, "enterprise explicit no-validation connection")
    modify = next(command for command in commands if command[1:3] == ["connection", "modify"] and "wpa-eap" in command)
    check("802-1x.domain-suffix-match" not in modify, "unsafe mode omits ineffective domain match")
    check(modify[modify.index("802-1x.system-ca-certs") + 1] == "no", "unsafe mode disables CA validation")

    commands.clear()
    pwd_credentials = dict(credentials)
    pwd_credentials["eap"] = "pwd"
    rc, _output = target.connect_enterprise(network("enterprise"), pwd_credentials, "wlan0")
    check(rc == 0, "EAP-PWD connection")
    modify = next(command for command in commands if command[1:3] == ["connection", "modify"] and "wpa-eap" in command)
    check("802-1x.password" in modify, "EAP-PWD password")
    check("802-1x.phase2-auth" not in modify, "EAP-PWD omits invalid phase2")

    commands.clear()
    rc, _output = target.connect_owe(network("owe"), "wlan0")
    check(rc == 0, "OWE connection")
    modify = next(command for command in commands if command[1:3] == ["connection", "modify"] and "owe" in command)
    check(modify[-2:] == ["802-11-wireless-security.key-mgmt", "owe"], "OWE key management")
finally:
    wifi_app.run = real_run
    wifi_app.time.sleep = real_sleep


fallback_target = harness()
fallback_target.wifi_devices = ["wlan1"]
fallback_attempts = []


def prepare_fallback(device, _ssid, _hidden=False):
    fallback_attempts.append(device)
    if device == "wlan0":
        raise RuntimeError("wlan0 unavailable")
    return [{"ssid": "School WiFi", "device": "wlan1", "bssid": "AA:BB:CC:DD:EE:04"}]


fallback_target.prepare_device = prepare_fallback
fallback_target.connect_standard = lambda _network, _credentials, device: (0, device)
rc, selected_device = fallback_target.connect_task(network("personal"), {"password": "school-secret"})
check(rc == 0 and selected_device == "wlan1", "connection falls back to usable Wi-Fi adapter")
check(fallback_attempts == ["wlan0", "wlan1"], "unavailable adapter fallback order")

missing_target = harness()
missing_target.wifi_devices = ["wlan0", "wlan1"]
missing_target.prepare_device = lambda *_args: []
rc, output = missing_target.connect_task(network("personal"), {"password": "school-secret"})
check(rc != 0, "connection rejects adapters that cannot see selected SSID")
check("wlan0" in output and "wlan1" in output, "missing SSID reports every adapter")
check("Other network" in output, "missing SSID explains hidden-network path")


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
            connected = "yes" if self.connect_attempts >= 3 else "no"
            return 0, f"Paired: yes\nTrusted: yes\nConnected: {connected}"
        return 0, "ok"


bluetooth_target = BluetoothHarness()
bluetooth_target.connect_with_retry = MethodType(
    bluetooth_app.BluetoothWindow.connect_with_retry,
    bluetooth_target,
)
bluetooth_system_calls = []
real_bluetooth_run = bluetooth_app.run
bluetooth_app.run = lambda command, **_kwargs: (bluetooth_system_calls.append(command) or (0, "ok"))
try:
    rc, output = bluetooth_target.connect_with_retry("AA:BB:CC:DD:EE:FF")
    check(rc == 0, "Bluetooth retry reaches confirmed connection")
    check(bluetooth_target.connect_attempts == 3, "Bluetooth retries unconfirmed connection")
    check(any(call[0] == "power" for call in bluetooth_target.calls), "Bluetooth powers controller before connect")
    check(any("scan" in call for call in bluetooth_target.calls), "Bluetooth rescans before retry")
    check(any("rfkill" in call for call in bluetooth_system_calls), "Bluetooth clears RFKill before connect")
    check("Connection successful" in output, "Bluetooth returns successful output")
finally:
    bluetooth_app.run = real_bluetooth_run

print("ok wireless-actions")
