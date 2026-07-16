#!/usr/bin/env python3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))

from wireless_utils import (  # noqa: E402
    group_wifi_access_points,
    parse_bluetooth_info,
    parse_iw_wifi,
    parse_nmcli_wifi,
    security_kind,
    split_nmcli_terse,
)


def check(condition, detail):
    if not condition:
        raise AssertionError(detail)


fields = split_nmcli_terse(r"*:AA\:BB\:CC\:DD\:EE\:01:School\:Main:82:WPA2 802.1X:wlan0")
check(fields[1] == "AA:BB:CC:DD:EE:01", "escaped BSSID")
check(fields[2] == "School:Main", "escaped SSID")

raw = "\n".join(
    (
        r"*:AA\:BB\:CC\:DD\:EE\:01:School WiFi:82:WPA2 802.1X:wlan0",
        r":AA\:BB\:CC\:DD\:EE\:02:School WiFi:63:WPA2 802.1X:wlan0",
        r":AA\:BB\:CC\:DD\:EE\:03:Cafe:70:--:wlan0",
    )
)
access_points = parse_nmcli_wifi(raw)
check(len(access_points) == 3, "nmcli access-point parsing")
grouped = group_wifi_access_points(access_points)
check(len(grouped) == 2, "duplicate SSIDs grouped")
school = next(item for item in grouped if item["ssid"] == "School WiFi")
check(school["ap_count"] == 2, "access-point count")
check(school["security_kind"] == "enterprise", "enterprise classification")
check(school["bssid"] == "AA:BB:CC:DD:EE:01", "strongest connected BSSID")

mixed = group_wifi_access_points(
    parse_nmcli_wifi(
        r":00\:00\:00\:00\:00\:01:Mixed:90:--:wlan0" + "\n" +
        r":00\:00\:00\:00\:00\:02:Mixed:55:WPA2 PSK:wlan0"
    )
)[0]
check(mixed["mixed_security"], "mixed security warning")
check(mixed["security_kind"] == "personal", "secured BSSID preferred")
check(security_kind("") == "unknown", "missing security must not become open")

iw_output = """
BSS aa:bb:cc:dd:ee:10(on wlan0)
        signal: -48.00 dBm
        capability: ESS Privacy (0x0011)
        SSID: Campus
        RSN:
                Authentication suites: IEEE 802.1X
"""
iw = parse_iw_wifi(iw_output, "wlan0")
check(iw[0]["security_kind"] == "enterprise", "iw enterprise parsing")
check(iw[0]["bssid"] == "AA:BB:CC:DD:EE:10", "iw BSSID parsing")

bluetooth = parse_bluetooth_info(
    "Alias: Headphones\nPaired: yes\nTrusted: yes\nConnected: no\nRSSI: -45\n"
)
check(bluetooth["paired"] and bluetooth["trusted"], "Bluetooth state parsing")
check(not bluetooth["connected"] and bluetooth["signal"] > 0, "Bluetooth RSSI parsing")

print("ok wireless-utils")
