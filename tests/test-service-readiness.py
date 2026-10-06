#!/usr/bin/env python3
"""Bounded real endpoint probes; no host service activation or audio playback."""
from pathlib import Path
import re
import subprocess
import sys
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'packages/ooonana/usr/lib/ooonana'))
import service_status

for mode, expected in (('ready', 'ready'), ('frozen', 'unresponsive'),
                       ('missing', 'not-ready'), ('invalid-owner', 'not-ready')):
    calls = []

    def probe(command):
        calls.append(command)
        if command[0] == 'pactl':
            return 0, 'server reply'
        if command[-1] == 'string:org.freedesktop.DBus':
            return 0, 'boolean true'
        if command[-1] == 'org.freedesktop.DBus.Peer.Ping':
            assert '--dest=:1.42' in command
            return (124, '') if mode == 'frozen' else (0, 'method return')
        if mode == 'missing':
            return 1, ''
        return 0, 'string "org.bluez"' if mode == 'invalid-owner' else 'string ":1.42"'

    result = service_status.check_services(probe, lambda _: True, lambda: True)
    for key in ('network', 'bluetooth', 'wifi-auth'):
        assert result[key]['state'] == expected, (mode, key, result)
    if mode in ('missing', 'invalid-owner'):
        assert not any(command[-1] == 'org.freedesktop.DBus.Peer.Ping' for command in calls)
    assert all('play' not in part for command in calls for part in command)

def unavailable_bus(command):
    return 124, ''

result = service_status.check_services(unavailable_bus, lambda _: True, lambda: True)
assert result['dbus']['state'] == 'unreachable'
assert all(result[key]['state'] == 'waiting-for-dbus' for key in ('network', 'bluetooth', 'wifi-auth'))

with patch.object(service_status.subprocess, 'run', side_effect=subprocess.TimeoutExpired('probe', 2)):
    assert service_status.execute(['dbus-send']) == (124, '')
with patch.object(service_status.subprocess, 'run') as mocked:
    mocked.return_value.returncode, mocked.return_value.stdout = 0, 'reply'
    service_status.execute(['pactl', 'info'])
    assert mocked.call_args.kwargs['timeout'] == 2
    assert mocked.call_args.args[0][1].startswith('--server=')

# Exercise both actual shell readiness functions with fixture commands only.
source = (root / 'scripts/build-full-i3-rootfs.sh').read_text()
functions = re.findall(r'^bluez_ready\(\) \{\n.*?^\}', source, re.M | re.S)
assert len(functions) == 2
for function in functions:
    for owner_rc, endpoint_rc, expected in ((0, 0, 0), (0, 1, 1), (0, 124, 1), (1, 0, 1)):
        fixture = '''
process_running() { return 0; }
running() { return 0; }
dbus_ready() { return 0; }
run_limited() { shift; "$@"; }
fixture_send() {
  case "$*" in
    *GetNameOwner*) printf 'string ":1.42"\\n'; return OWNER_RC ;;
    *Peer.Ping*) case "$*" in *--dest=:1.42*) return ENDPOINT_RC ;; *) return 99 ;; esac ;;
  esac
}
'''.replace('OWNER_RC', str(owner_rc)).replace('ENDPOINT_RC', str(endpoint_rc))
        completed = subprocess.run(['sh', '-c', fixture + function.replace('dbus-send', 'fixture_send') + '\nbluez_ready\n'],
                                   capture_output=True, text=True, timeout=3)
        assert (completed.returncode == 0) == (expected == 0), (owner_rc, endpoint_rc, completed.stderr)
print('ok service-readiness: ready/frozen/missing owners, both shell probes, bounds/no activation')
