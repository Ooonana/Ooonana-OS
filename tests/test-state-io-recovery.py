#!/usr/bin/env python3
"""Damaged state and failed writes: private disposable files, history never reset."""
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'packages/openvino-chat/source/src'),
                str(ROOT / 'packages/ooonana/usr/lib/ooonana/ui')]
from openvino_chat.sessions import CrashRecoveryStore, ChatSessionStore
from openvino_chat import api, sessions as session_module
from openvino_chat import perf, memory_guard
from chat_store import ChatStore
from notification_utils import parse_history
from ui_preferences import read_json, write_json

deep = ('[' * 6000 + '0' + ']' * 6000).encode()
with tempfile.TemporaryDirectory(prefix='ooonana-state-io-test-') as temporary:
    root = Path(temporary)
    target = root / 'state.json'
    corrupt = (b'\xff', b'{broken', deep, b'null', b'[]')
    for raw in corrupt:
        target.write_bytes(raw)
        recovery = CrashRecoveryStore(target)
        assert recovery.load() == {} and recovery.last_error
        assert target.read_bytes() == raw
        store = ChatStore(target)
        assert not store.threads and store.load_error
        store.append(store.new(), 'user', 'must not overwrite damaged history')
        assert target.read_bytes() == raw
        with patch.object(api, 'API_STATE_PATH', target), patch.object(api.urllib.request, 'urlopen') as request:
            assert not api.api_status()['running']
            request.assert_not_called()
        if raw in (b'\xff', b'{broken'):
            assert read_json(target, {'fallback': True}) == {'fallback': True}
    assert parse_history(deep.decode()) == []
    # Parser recursion thresholds vary by Python version; inject this failure
    # explicitly rather than treating a valid JSON array as a syntax error.
    target.write_text('{}')
    with patch('json.loads', side_effect=RecursionError('fixture parser nesting')):
        assert read_json(target, {'fallback': True}) == {'fallback': True}
        assert recovery.load() == {} and recovery.last_error
        store = ChatStore(target)
        assert store.load_error
        store.append(store.new(), 'user', 'preserve failed parse')
        assert target.read_text() == '{}'
        assert parse_history('[]') == []
        with patch.object(api, 'API_STATE_PATH', target), patch.object(api.urllib.request, 'urlopen') as request:
            assert not api.api_status()['running']
            request.assert_not_called()
    # Recovery re-reads a repaired record, with no silent file rewrite on load.
    target.write_text('{"draft":"kept","session":"owned"}')
    assert recovery.load()['draft'] == 'kept' and recovery.last_error is None
    target.write_text(' ' * (1024 * 1024 + 1))
    assert recovery.load() == {} and 'size limit' in recovery.last_error
    assert read_json(target, {}, limit=4096) == {}
    target.unlink()
    assert recovery.load() == {} and recovery.last_error is None

    recovery = CrashRecoveryStore(root / 'recovery.json', debounce_seconds=5)
    recovery.schedule('owned', 'obsolete')
    recovery.save_now('owned', 'newer', pending=True)
    recovery.flush()
    assert recovery.load()['draft'] == 'newer'
    recovery.schedule('owned', 'pending obsolete')
    recovery.clear()
    recovery.flush()
    assert not recovery.path.exists()
    recovery.save_now('owned', 'within limit')
    old = recovery.path.read_bytes()
    with patch.object(session_module, 'MAX_RECOVERY_CHARS', 4096):
        recovery.save_now('owned', 'x' * 5000)
        assert 'size limit' in recovery.last_error and recovery.path.read_bytes() == old
        recovery.flush()
        assert recovery.path.read_bytes() == old
    recovery.clear()
    recovery.save_now('owned', 'saved draft')
    old = recovery.path.read_bytes()
    for hook in ('openvino_chat.sessions.os.fsync', 'openvino_chat.sessions.Path.replace'):
        with patch(hook, side_effect=OSError('fixture recovery storage unavailable')):
            recovery.save_now('owned', 'retry draft')
        assert recovery.last_error and recovery.path.read_bytes() == old
        assert not list(root.glob('.recovery-*.tmp'))
        recovery.flush()
        assert recovery.last_error is None and recovery.load()['draft'] == 'retry draft'
        old = recovery.path.read_bytes()
    # A failed older commit must not replace a newer pending revision.
    def supersede(_descriptor):
        recovery.schedule('owned', 'newest draft')
        raise OSError('fixture older write failed')
    with patch('openvino_chat.sessions.os.fsync', side_effect=supersede):
        recovery.save_now('owned', 'obsolete failed draft')
    recovery.flush()
    assert recovery.load()['draft'] == 'newest draft'
    recovery.clear()
    recovery.flush()
    assert not recovery.path.exists()

    sessions = ChatSessionStore(root / 'sessions')
    path = sessions.save('owned', [('user', 'old history')])
    old = path.read_bytes()
    with patch.object(session_module, 'MAX_SESSION_CHARS', 4096):
        try:
            sessions.save('owned', [('user', 'x' * 5000)])
        except ValueError as error:
            assert 'size limit' in str(error)
        else:
            raise AssertionError('saved session would exceed reader limit')
        assert path.read_bytes() == old and not list(sessions.root.glob('.*.tmp'))
    for failure in ('flush', 'replace'):
        hook = 'openvino_chat.sessions.os.fsync' if failure == 'flush' else 'openvino_chat.sessions.Path.replace'
        with patch(hook, side_effect=OSError('fixture disk full')):
            try:
                sessions.save('owned', [('user', 'new history')])
            except OSError:
                pass
            else:
                raise AssertionError('failed session write accepted')
        assert path.read_bytes() == old
        assert not list(sessions.root.glob('.*.tmp'))
    for raw in corrupt:
        path.write_bytes(raw)
        for operation in (sessions.load, sessions.metadata, sessions.load_state):
            try:
                operation('owned')
            except (ValueError, OSError):
                pass
            assert path.read_bytes() == raw
    path.write_text('{}')
    with patch('json.loads', side_effect=RecursionError('fixture parser nesting')):
        for operation in (sessions.load, sessions.metadata, sessions.load_state):
            try:
                operation('owned')
            except ValueError as error:
                assert 'nesting' in str(error)
            else:
                raise AssertionError('session parser failure accepted')
            assert path.read_text() == '{}'

    chat = root / 'chat.json'
    store = ChatStore(chat)
    thread = store.new()
    store.append(thread, 'user', 'saved')
    old = chat.read_bytes()
    for hook in ('chat_store.os.fsync', 'chat_store.os.replace'):
        with patch(hook, side_effect=OSError('fixture storage unavailable')):
            store.append(thread, 'assistant', 'unsaved during failure')
        assert chat.read_bytes() == old and store.load_error
        assert not list(root.glob('.chat-*'))
        store.append(thread, 'user', 'space restored')
        assert not store.load_error and chat.read_bytes() != old
        assert ChatStore(chat).threads[0]['messages'] == thread['messages']
        assert chat.stat().st_mode & 0o777 == 0o600
        old = chat.read_bytes()

    preferences = root / 'ui.json'
    write_json(preferences, {'reduce_motion': False})
    old = preferences.read_bytes()
    with patch('ui_preferences.os.replace', side_effect=OSError('fixture full')):
        try:
            write_json(preferences, {'reduce_motion': True})
        except OSError:
            pass
    assert preferences.read_bytes() == old and not list(root.glob('ui.json.*'))
    write_json(preferences, {'reduce_motion': True})
    assert read_json(preferences, {}) == {'reduce_motion': True}

    good = {'pid': 1234, 'host': '127.0.0.1', 'port': 11435, 'instance_id': 'owned'}
    target.write_text(json.dumps(good))
    with patch.object(api, 'API_STATE_PATH', target), \
            patch.object(api.urllib.request, 'urlopen', return_value=io.BytesIO(deep)):
        assert not api.api_status()['running']
    with patch.object(api, '_read_api_state', return_value=good), \
            patch.object(api.urllib.request, 'urlopen', return_value=io.BytesIO(b'{}')), \
            patch('json.loads', side_effect=RecursionError('fixture health nesting')):
        assert not api.api_status()['running']

    model = root / 'model'
    model.mkdir()
    config = model / 'config.json'
    baseline = perf.estimate_model_memory(model, 4096).kv_cache_bytes
    assert baseline > 0
    for data in ([1], None, {'num_key_value_heads': 'broken'},
                 {'num_key_value_heads': -4}, {'num_hidden_layers': []},
                 {'num_attention_heads': True}, {'head_dim': 1.5}):
        config.write_text(json.dumps(data))
        assert perf.estimate_model_memory(model, 4096).kv_cache_bytes == baseline
        guarded = memory_guard.estimate_memory(model, 4096, snapshot=(8 << 30, 4 << 30, 0))
        assert guarded.estimated_kv == baseline
    for raw in (b'\xff', b'{broken', deep, b' ' * (1024 * 1024 + 1)):
        config.write_bytes(raw)
        assert perf.estimate_model_memory(model, 4096).kv_cache_bytes == baseline
    dimensions = dict(num_hidden_layers=32, num_attention_heads=32,
                      num_key_value_heads=8, hidden_size=4096)
    config.write_text(json.dumps(dimensions))
    for precision, width in (('f16', 2), ('u8', 1), ('u4', 0.5)):
        expected = int(4096 * 32 * 8 * 128 * 2 * width)
        assert perf.estimate_model_memory(model, 4096, precision).kv_cache_bytes == expected
        assert memory_guard.estimate_memory(model, 4096, precision, (8 << 30, 4 << 30, 0)).estimated_kv == expected
    per_token = perf.estimate_model_memory(model, 1).kv_cache_bytes
    constrained = memory_guard.estimate_memory(model, 2, snapshot=(8 << 30, per_token, 0))
    assert constrained.recommended_context == 0 and constrained.estimated_required > constrained.available_ram
    dimensions['layer_types'] = ['full_attention', 'linear_attention'] * 16
    config.write_text(json.dumps({'text_config': dimensions}))
    expected = 4096 * 16 * 8 * 128 * 2 * 2
    assert perf.estimate_model_memory(model, 4096).kv_cache_bytes == expected
    assert memory_guard.estimate_memory(model, 4096, snapshot=(8 << 30, 4 << 30, 0)).estimated_kv == expected

print('ok state-io-recovery: corrupt/deep state, draft ordering/retry, failed writes, history preservation, safe model dimensions')
