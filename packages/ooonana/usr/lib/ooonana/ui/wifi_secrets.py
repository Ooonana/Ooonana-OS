#!/usr/bin/env python3
"""Save secrets on a freshly created Wi-Fi profile; input travels over stdin."""
import json
import sys
import uuid

ALLOWED = {
    "802-11-wireless-security": {"psk", "wep-key0"},
    "802-1x": {"password", "private-key-password"},
}


def validate(payload):
    if not isinstance(payload, dict) or not payload:
        raise ValueError("missing Wi-Fi secrets")
    for section, values in payload.items():
        if section not in ALLOWED or not isinstance(values, dict) or not values:
            raise ValueError("invalid Wi-Fi secret section")
        for key, value in values.items():
            if key not in ALLOWED[section] or not isinstance(value, str) or "\x00" in value:
                raise ValueError("invalid Wi-Fi secret value")
    return payload


def variant_settings(value):
    # unpack() loses integer/byte-array signatures needed when sending Update.
    settings = {}
    for index in range(value.n_children()):
        entry = value.get_child_value(index)
        properties = entry.get_child_value(1)
        fields = {}
        for prop_index in range(properties.n_children()):
            prop = properties.get_child_value(prop_index)
            fields[prop.get_child_value(0).get_string()] = prop.get_child_value(1).get_variant()
        settings[entry.get_child_value(0).get_string()] = fields
    return settings


def save(connection_uuid, payload, bus, GLib, Gio):
    connection_uuid = str(uuid.UUID(connection_uuid))
    payload = validate(payload)
    service = "org.freedesktop.NetworkManager"
    interface = service + ".Settings.Connection"

    def call(path, iface, method, parameters=None):
        return bus.call_sync(service, path, iface, method, parameters, None,
                             Gio.DBusCallFlags.NONE, 10000, None)

    path = call("/org/freedesktop/NetworkManager/Settings", service + ".Settings",
                "GetConnectionByUuid", GLib.Variant("(s)", (connection_uuid,))).unpack()[0]
    settings = variant_settings(call(path, interface, "GetSettings").get_child_value(0))
    if settings["connection"]["type"].unpack() != "802-11-wireless":
        raise ValueError("profile is not Wi-Fi")
    for section, values in payload.items():
        if section not in settings:
            raise ValueError("missing Wi-Fi security configuration")
        # Caller recreated this profile and supplies its complete secret set.
        # Do not ask a secret agent for credentials before saving the first set.
        for key, value in values.items():
            settings[section][key] = GLib.Variant("s", value)
    call(path, interface, "Update", GLib.Variant("(a{sa{sv}})", (settings,)))


def main():
    try:
        from gi.repository import Gio, GLib
        if len(sys.argv) != 2:
            raise ValueError("UUID required")
        raw = sys.stdin.read(65537)
        if len(raw) > 65536:
            raise ValueError("input too large")
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        save(sys.argv[1], json.loads(raw), bus, GLib, Gio)
        return 0
    except Exception:
        # D-Bus errors can echo settings; never print exception payloads or input.
        print("Could not save Wi-Fi credentials through NetworkManager.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
