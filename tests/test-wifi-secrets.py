#!/usr/bin/env python3
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'packages/ooonana/usr/lib/ooonana/ui'))
import wifi_secrets

from gi.repository import GLib, Gio

identifier = '11111111-2222-3333-4444-555555555555'
settings = {
    'connection': {'uuid': GLib.Variant('s', identifier), 'type': GLib.Variant('s', '802-11-wireless')},
    '802-11-wireless': {'ssid': GLib.Variant('ay', list(' Café '.encode()))},
    '802-11-wireless-security': {'key-mgmt': GLib.Variant('s', 'wpa-psk'), 'psk-flags': GLib.Variant('u', 0)},
    'ipv4': {'method': GLib.Variant('s', 'manual'), 'dns': GLib.Variant('au', [16843009])},
}
updates = []

def call(service, path, interface, method, params, *_):
    if method == 'GetConnectionByUuid':
        assert params.unpack() == (identifier,)
        return GLib.Variant('(o)', ('/org/freedesktop/NetworkManager/Settings/7',))
    if method == 'GetSettings':
        return GLib.Variant('(a{sa{sv}})', (settings,))
    if method == 'GetSecrets':
        return GLib.Variant('(a{sa{sv}})', ({'802-11-wireless-security': {'psk': GLib.Variant('s', 'old')}},))
    assert method == 'Update'
    updates.append(wifi_secrets.variant_settings(params.get_child_value(0)))
    return GLib.Variant('()', ())

wifi_secrets.save(identifier, {'802-11-wireless-security': {'psk': 'new-secret'}},
                  SimpleNamespace(call_sync=call), GLib, Gio)
updated = updates[0]
assert updated['802-11-wireless-security']['psk'].unpack() == 'new-secret'
assert updated['802-11-wireless-security']['psk-flags'].get_type_string() == 'u'
assert updated['ipv4']['dns'].get_type_string() == 'au'
assert updated['802-11-wireless']['ssid'].unpack() == list(' Café '.encode())
assert updated['ipv4']['method'].unpack() == 'manual'
for value in [{'bad': {'password': 'x'}}, {'802-1x': {'password': 42}}, {'802-1x': {'password': '\0'}}]:
    try:
        wifi_secrets.validate(value)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid secrets accepted')
print('ok wifi-secrets D-Bus variants and persistence request')
