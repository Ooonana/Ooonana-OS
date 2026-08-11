#!/usr/bin/env python3
import re
import unicodedata
"""Pure parsing helpers shared by the native wireless applications."""


def clean_display_name(value):
    text = unicodedata.normalize("NFC", str(value or ""))
    return "".join(char for char in text if char >= " " and char != "\x7f").strip()


def split_nmcli_terse(line):
    fields = []
    value = []
    escaped = False
    for char in line.rstrip("\n"):
        if escaped:
            value.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(value))
            value = []
        else:
            value.append(char)
    if escaped:
        value.append("\\")
    fields.append("".join(value))
    return fields


def signal_percent(dbm):
    try:
        value = float(dbm)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, int(2 * (value + 100))))


def security_kind(raw):
    value = " ".join((raw or "").upper().split())
    if value in ("--", "NONE", "OPEN"):
        return "open"
    if not value:
        return "unknown"
    if "802.1X" in value or "EAP" in value or "SUITE-B" in value:
        return "enterprise"
    if "OWE" in value:
        return "owe"
    if "WEP" in value:
        return "wep"
    if any(token in value for token in ("WPA", "RSN", "SAE", "PSK")):
        return "personal"
    return "unknown"


def security_label(raw):
    kind = security_kind(raw)
    if kind == "open":
        return "Open"
    if kind == "unknown":
        return "Unknown"
    if kind == "enterprise":
        return (raw or "WPA Enterprise").replace("802.1X", "Enterprise")
    if kind == "owe":
        return "Enhanced Open (OWE)"
    return raw or kind.title()


def parse_nmcli_wifi(output):
    access_points = []
    for line in output.splitlines():
        fields = split_nmcli_terse(line)
        if len(fields) != 6:
            continue
        in_use, bssid, ssid, signal, security, device = fields
        ssid = clean_display_name(ssid)
        if not ssid:
            continue
        try:
            strength = max(0, min(100, int(signal)))
        except ValueError:
            strength = 0
        access_points.append(
            {
                "connected": in_use == "*",
                "bssid": bssid.upper(),
                "ssid": ssid,
                "signal": strength,
                "security": security,
                "security_kind": security_kind(security),
                "device": device,
            }
        )
    return access_points


def parse_iw_wifi(output, device=""):
    access_points = []
    current = None

    def finish():
        if not current or not current.get("ssid"):
            return
        security = current.get("security") or (
            "WEP" if current.get("privacy") else "--"
        )
        access_points.append(
            {
                "connected": False,
                "bssid": current.get("bssid", "").upper(),
                "ssid": current["ssid"],
                "signal": signal_percent(current.get("signal", -100)),
                "security": security,
                "security_kind": security_kind(security),
                "device": device,
            }
        )

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("BSS "):
            finish()
            bssid = line.split()[1].split("(", 1)[0]
            current = {"bssid": bssid}
        elif current is None:
            continue
        elif line.startswith("SSID:"):
            current["ssid"] = clean_display_name(line.split(":", 1)[1])
        elif line.startswith("signal:"):
            current["signal"] = line.split(":", 1)[1].strip().split()[0]
        elif line.startswith("capability:") and "Privacy" in line:
            current["privacy"] = True
        elif line in ("RSN:", "WPA:"):
            current["security"] = "WPA"
        elif "Authentication suites:" in line:
            suite = line.split(":", 1)[1].strip()
            if "802.1X" in suite:
                current["security"] = "WPA2 802.1X"
            elif "SAE" in suite:
                current["security"] = "WPA3 SAE"
            elif "OWE" in suite:
                current["security"] = "OWE"
            elif "PSK" in suite and current.get("security") == "WPA":
                current["security"] = "WPA2 PSK"
    finish()
    return access_points


def group_wifi_access_points(access_points):
    groups = {}
    for ap in access_points:
        ssid = ap.get("ssid", "")
        if not ssid:
            continue
        groups.setdefault(ssid, []).append(ap)

    result = []
    preference = {"enterprise": 5, "personal": 4, "owe": 3, "wep": 2, "open": 1, "unknown": 0}
    for ssid, members in groups.items():
        ordered = sorted(
            members,
            key=lambda item: (
                bool(item.get("connected")),
                preference.get(item.get("security_kind"), 0),
                item.get("signal", 0),
            ),
            reverse=True,
        )
        selected = dict(ordered[0])
        labels = []
        kinds = set()
        for member in ordered:
            label = security_label(member.get("security"))
            if label not in labels:
                labels.append(label)
            kinds.add(member.get("security_kind", "unknown"))
        selected["access_points"] = ordered
        selected["ap_count"] = len(ordered)
        selected["connected"] = any(item.get("connected") for item in ordered)
        selected["signal"] = max(item.get("signal", 0) for item in ordered)
        selected["mixed_security"] = len(kinds) > 1
        selected["security_label"] = (
            "Mixed: " + " / ".join(labels) if len(kinds) > 1 else labels[0]
        )
        result.append(selected)
    return sorted(result, key=lambda item: (item["connected"], item["signal"]), reverse=True)


def parse_bluetooth_info(output):
    values = {
        "paired": False,
        "trusted": False,
        "connected": False,
        "services_resolved": False,
        "rssi": None,
        "name": "",
        "alias": "",
        "icon": "",
    }
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        lowered = value.lower()
        if key in ("Paired", "Trusted", "Connected", "ServicesResolved"):
            normalized = "services_resolved" if key == "ServicesResolved" else key.lower()
            values[normalized] = lowered == "yes"
        elif key == "RSSI":
            try:
                values["rssi"] = int(value)
            except ValueError:
                pass
        elif key.lower() in ("name", "alias", "icon"):
            values[key.lower()] = clean_display_name(value)
    values["signal"] = signal_percent(values["rssi"]) if values["rssi"] is not None else 0
    return values


def parse_bluetooth_scan(output):
    """Parse bluetoothctl discovery events, including transient RSSI values."""
    devices = {}
    ansi = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
    event = re.compile(
        r"^\[(?:NEW|CHG)\]\s+Device\s+([0-9A-Fa-f:]{17})(?:\s+(.*))?$"
    )
    for raw_line in output.splitlines():
        line = ansi.sub("", raw_line).strip()
        match = event.match(line)
        if not match:
            continue
        address = match.group(1).upper()
        detail = (match.group(2) or "").strip()
        values = devices.setdefault(
            address,
            {"address": address, "name": address, "rssi": None, "signal": 0},
        )
        if detail.startswith("RSSI:"):
            try:
                values["rssi"] = int(detail.split(":", 1)[1].strip())
                values["signal"] = signal_percent(values["rssi"])
            except ValueError:
                pass
        elif detail.startswith(("Name:", "Alias:")):
            values["name"] = clean_display_name(detail.split(":", 1)[1]) or address
        elif detail and ":" not in detail:
            values["name"] = clean_display_name(detail)
    return devices


def parse_ip_neighbors(output):
    """Return usable LAN peers from `ip neigh show` output."""
    neighbors = []
    seen = set()
    ignored_states = {"FAILED", "INCOMPLETE", "NOARP"}
    for raw_line in output.splitlines():
        fields = raw_line.split()
        if len(fields) < 5 or "lladdr" not in fields:
            continue
        state = fields[-1].upper()
        if state in ignored_states:
            continue
        mac_index = fields.index("lladdr") + 1
        if mac_index >= len(fields):
            continue
        address = fields[mac_index].upper()
        if address in seen:
            continue
        seen.add(address)
        interface = fields[fields.index("dev") + 1] if "dev" in fields else ""
        neighbors.append(
            {
                "address": address,
                "name": f"{fields[0]} ({interface})" if interface else fields[0],
                "state": state,
            }
        )
    return neighbors
