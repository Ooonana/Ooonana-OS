#!/usr/bin/env python3
"""Actual metric helpers and API state guards; no GTK, model loading or signals."""
import ast
import io
import json
from pathlib import Path
import signal
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/openvino-chat/source/src'))
from openvino_chat import api, perf

source = (ROOT / 'packages/ooonana/usr/lib/ooonana/ui/task_manager_app.py').read_text()
names = {'read_text', 'read_number', 'cpu_totals', 'network_bytes'}
functions = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in names]
helpers = {'Path': Path}
exec(compile(ast.Module(body=functions, type_ignores=[]), 'actual-task-manager-helpers', 'exec'), helpers)
cpu, network = helpers['cpu_totals'], helpers['network_bytes']
assert cpu('cpu 100 0 0 100 0 0 0 0 100 0\n') == (200, 100)
assert cpu('cpu 100 20 10 100 5 2 3 4 50 10\n') == (244, 105)
assert cpu('cpu 1 2 3 4 5 6\n') == (21, 9)
for text in ('', 'cpu 1 2', 'cpu nope 2 3 4 5', 'cpu -1 2 3 4 5'):
    assert cpu(text) is None
with patch.object(perf, '_CPU_SAMPLE', None), patch.object(perf.Path, 'read_text', return_value='cpu 100 0 0 100 0 0 0 0 100 0\n'):
    assert perf._get_linux_cpu_usage() == 'cpu=50.0%'
for text in ('', 'other 1 2 3 4 5', 'cpu -1 2 3 4 5', 'cpu nope 2 3 4 5'):
    with patch.object(perf.Path, 'read_text', return_value=text):
        assert perf._get_linux_cpu_usage() == 'cpu=unknown'

with tempfile.TemporaryDirectory(prefix='ooonana-metrics-api-test-') as temporary:
    work = Path(temporary)
    net = work / 'net'
    net.mkdir()

    def device(name, state, rx=10, tx=20, carrier=None, wifi=False):
        folder = net / name
        (folder / 'statistics').mkdir(parents=True, exist_ok=True)
        (folder / 'operstate').write_text(state)
        for key, value in (('rx_bytes', rx), ('tx_bytes', tx)):
            (folder / 'statistics' / key).write_text(str(value))
        if carrier is not None:
            (folder / 'carrier').write_text(str(carrier))
        if wifi:
            (folder / 'wireless').mkdir(exist_ok=True)
        return folder

    device('lo', 'up', 9999, 9999, 1)
    wlan = device('wlan0', 'down', carrier=0, wifi=True)
    eth = device('eth0', 'up', 100, 200, 1)
    assert network(net) == ('eth0', 100, 200)
    (wlan / 'operstate').write_text('up')
    (wlan / 'carrier').write_text('1')
    assert network(net) == ('wlan0', 10, 20)
    (wlan / 'operstate').write_text('unknown')
    (wlan / 'carrier').unlink()
    assert network(net) == ('eth0', 100, 200)
    (eth / 'operstate').write_text('lowerlayerdown')
    assert network(net) == ('wlan0', 10, 20)  # Missing metadata: cautious fallback.
    (wlan / 'statistics/rx_bytes').write_text('-1')
    assert network(net) is None
    (wlan / 'statistics/rx_bytes').write_text('bad')
    assert network(net) is None
    (wlan / 'statistics/rx_bytes').write_text('10')
    (wlan / 'operstate').write_text('down')
    vpn = device('tun0', 'unknown', 300, 400, 1)
    assert network(net) == ('tun0', 300, 400)
    (vpn / 'carrier').write_text('0')
    assert network(net) is None
    device('dormant0', 'dormant', carrier=1)
    assert network(net) is None
    device('gone0', 'notpresent', carrier=1)
    assert network(net) is None
    refresh = next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name == 'refresh')
    assert 'self.previous_network = None' in ast.unparse(refresh)

    state = work / 'api.json'
    good = {'pid': 1234, 'host': '127.0.0.1', 'port': 11435, 'instance_id': 'owned'}
    body = json.dumps({'instance_id': 'owned', 'loaded': False, 'model': 'fixture'}).encode()
    with patch.object(api, 'API_STATE_PATH', state), patch.object(api.os, 'kill') as kill, \
            patch.object(api.urllib.request, 'urlopen', side_effect=lambda *_args, **_kwargs: io.BytesIO(body)) as request:
        for field, values in (
            ('port', [[], [11435], {}, True, 1.5, None, '', 'bad', -1, 0, 65536]),
            ('pid', [[], {}, True, 1.5, None, '', 'bad', -1, 0, 2**31]),
            ('host', [[], {}, [1], {'host': 'bad'}, False, True, 0, 12, None]),
            ('instance_id', [[], {}, True, 12, None, '']),
        ):
            for value in values:
                request.reset_mock()
                state.write_text(json.dumps({**good, field: value}))
                assert not api.api_status()['running'], (field, value)
                assert api.stop_api_process() is False
                request.assert_not_called()
                kill.assert_not_called()
        for data in (b'{broken', b'[]', b'null', b'\xff', b' ' * 65537):
            state.write_bytes(data)
            assert api.api_status() == {'running': False}
            assert api.stop_api_process() is False
            api._remove_owned_state('owned')
            kill.assert_not_called()
        state.write_text(json.dumps(good))
        assert api.api_status()['running']
        assert request.call_args.kwargs['timeout'] == 0.35
        assert request.call_args.args[0] == 'http://127.0.0.1:11435/health'
        request.side_effect = lambda *_args, **_kwargs: io.BytesIO(b'{"instance_id":"other"}')
        assert not api.api_status()['running']
        request.side_effect = lambda *_args, **_kwargs: io.BytesIO(b' ' * 65537)
        assert not api.api_status()['running']
        request.side_effect = TimeoutError('fixture timeout')
        assert not api.api_status()['running']
        for invalid in (0, -1, [], True):
            with patch.object(api, 'api_status', return_value={**good, 'running': True, 'pid': invalid}):
                try:
                    api.stop_api_process()
                except RuntimeError:
                    pass
                else:
                    raise AssertionError('unsafe mocked PID accepted')
                kill.assert_not_called()
        # Stop may encounter newer state from a replacement instance. Keep it.
        state.write_text(json.dumps(good))
        replacement = {**good, 'instance_id': 'replacement'}
        kill.side_effect = lambda *_args: state.write_text(json.dumps(replacement))
        with patch.object(api, 'api_status', return_value={**good, 'running': True}), \
                patch.object(api, '_health_matches', return_value=False):
            assert api.stop_api_process()
        kill.assert_called_once_with(1234, signal.SIGTERM)
        assert json.loads(state.read_text()) == replacement
        api._remove_owned_state('owned')
        assert state.exists()
        api._remove_owned_state('replacement')
        assert not state.exists()

print('ok backend-metrics-api: guest counters, active links, malformed/bounded state, safe mocked signals')
