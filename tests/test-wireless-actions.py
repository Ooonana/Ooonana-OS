#!/usr/bin/env python3
import sys
from pathlib import Path
from types import MethodType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))

import wifi_app  # noqa: E402


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
    for name in ("prepare_device", "profile_uuid", "add_wifi_profile", "connection_diagnostics"):
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
            {"bssid": "AA:BB:CC:DD:EE:01", "security_kind": kind},
            {"bssid": "AA:BB:CC:DD:EE:02", "security_kind": kind},
        ],
    }


commands = []


def fake_run(command, **_kwargs):
    commands.append(command)
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
    check(all("device" not in command or "connect" not in command for command in commands), "SSID shortcut removed")
    add = next(command for command in commands if command[1:4] == ["connection", "add", "type"])
    check("School WiFi" in add and "wlan0" in add, "profile binds SSID and adapter")
    modify = [command for command in commands if command[1:3] == ["connection", "modify"]]
    check(any("802-11-wireless.hidden" in command and "no" in command for command in modify), "visible profile enabled")
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
        "ca_cert": "",
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

    commands.clear()
    rc, _output = target.connect_owe(network("owe"), "wlan0")
    check(rc == 0, "OWE connection")
    modify = next(command for command in commands if command[1:3] == ["connection", "modify"] and "owe" in command)
    check(modify[-2:] == ["802-11-wireless-security.key-mgmt", "owe"], "OWE key management")
finally:
    wifi_app.run = real_run
    wifi_app.time.sleep = real_sleep

print("ok wireless-actions")
