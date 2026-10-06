#!/usr/bin/env python3
"""Knowledge/checkpoint/benchmark faults; disposable files, no models or network."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/openvino-chat/source/src'))
sys.path.insert(0, str(ROOT / 'packages/ooonana/usr/lib/ooonana'))
from openvino_chat import benchmarks, knowledge, state_io
from openvino_chat.engine import GenerationMetrics
from storage_health import storage_health


def rejected(operation, exceptions=(ValueError, OSError)):
    try:
        operation()
    except exceptions:
        return
    raise AssertionError('unsafe operation accepted')


with tempfile.TemporaryDirectory(prefix='ooonana-ai-store-test-') as temporary:
    root = Path(temporary)
    document = root / 'first.txt'
    document.write_text('fixture knowledge with useful backend facts')
    next_document = root / 'second.txt'
    next_document.write_text('new fixture source')
    index = root / 'index.json'
    good = {'version': 1, 'chunks': []}
    bad_chunk = {'chunk_id': 'fixture', 'source': [], 'text': 'fixture'}
    bad = (b'{broken', b'\xff', b'[]', b'null',
           json.dumps({'version': 1, 'chunks': [bad_chunk]}).encode(),
           json.dumps({'version': 1, 'chunks': [{**bad_chunk, 'source': ''}]}).encode(),
           json.dumps({'version': True, 'chunks': []}).encode(),
           json.dumps({'version': 1, 'chunks': [{**bad_chunk, 'source': 'x', 'text': None}]}).encode(),
           json.dumps({'version': 1, 'chunks': [{**bad_chunk, 'source': 'x', 'embedding': [float('nan')]}]}).encode())
    for raw in bad:
        index.write_bytes(raw)
        store = knowledge.KnowledgeStore(index, root / 'absent-models')
        assert store.list_sources() == [] and store.search('fixture') == [] and store.load_error
        rejected(lambda: store.add(document))
        rejected(store.reindex)
        assert index.read_bytes() == raw
    index.write_text(json.dumps(good))
    assert store.chunk_count == 0 and store.load_error is None  # Same instance retries repaired state.
    store.add(document)
    assert store.chunk_count and store.search('backend')
    original = index.read_bytes()
    sources = store.list_sources()
    checkpoint = store.checkpoint()
    rejected(lambda: store.restore_checkpoint('unknown-checkpoint'))
    assert index.read_bytes() == original
    fresh = knowledge.KnowledgeStore(index, root / 'absent-models')
    with patch.object(knowledge, 'read_bytes', side_effect=PermissionError('fixture unreadable checkpoint')):
        rejected(fresh.checkpoint, (PermissionError,))
    assert not fresh._checkpoints and index.read_bytes() == original
    missing = knowledge.KnowledgeStore(root / 'missing-index.json', root / 'absent-models')
    absent = missing.checkpoint()
    missing.add(document)
    missing.restore_checkpoint(absent)
    assert not missing.index_path.exists()  # Only a recorded absence may remove it.

    for hook in ('openvino_chat.state_io.os.fsync', 'openvino_chat.state_io.os.replace'):
        with patch(hook, side_effect=OSError('fixture failed write')):
            rejected(lambda: store.add(next_document), (OSError,))
        assert store.list_sources() == sources and index.read_bytes() == original
        assert not list(root.glob('.index-*.tmp'))
    with patch.object(knowledge, '_read_document', return_value=None):
        rejected(store.reindex)
    assert store.list_sources() == sources and index.read_bytes() == original
    with patch.object(Path, 'stat', side_effect=PermissionError('fixture source cannot be inspected')):
        rejected(store.reindex, (PermissionError,))
    with patch.object(knowledge.os, 'walk', side_effect=PermissionError('fixture scan denied')):
        rejected(lambda: store.add(root), (PermissionError,))
    with patch.object(knowledge, 'MAX_FILE_BYTES', 4):
        rejected(store.reindex)
        rejected(lambda: store.add(root))
    assert store.list_sources() == sources and index.read_bytes() == original
    with patch.object(Path, 'unlink', side_effect=OSError('fixture failed clear')):
        rejected(store.clear, (OSError,))
    assert store.list_sources() == sources and index.read_bytes() == original
    store.add(next_document)
    changed = index.read_bytes()
    for hook in ('openvino_chat.state_io.os.fsync', 'openvino_chat.state_io.os.replace'):
        with patch(hook, side_effect=OSError('fixture failed restore')):
            rejected(lambda: store.restore_checkpoint(checkpoint), (OSError,))
        assert index.read_bytes() == changed and len(store.list_sources()) == 2
        assert not list(root.glob('.index-*.tmp'))
    store.restore_checkpoint(checkpoint)
    assert index.read_bytes() == original and store.list_sources() == sources
    assert index.stat().st_mode & 0o777 == 0o600
    with patch.object(knowledge, 'MAX_INDEX_BYTES', 32):
        rejected(store.checkpoint)
        # Cached checkpoints skip disk reads, so use a new instance for the bound.
        bounded = knowledge.KnowledgeStore(index, root / 'absent-models')
        rejected(bounded.checkpoint)
        assert bounded.chunk_count == 0 and bounded.load_error
    assert index.read_bytes() == original

    path = root / 'benchmarks.json'
    metrics = GenerationMetrics(2, 4, 1.0, 0.1, 4.0)
    model = root / 'model'
    key = benchmarks._profile_key(model, 'CPU', 'auto', 4096)
    store = benchmarks.BenchmarkStore(path)
    malformed = (b'{broken', b'\xff', b'[]', b'null',
                 json.dumps({'version': 2, 'profiles': {}}).encode(),
                 json.dumps({'profiles': {key: []}}).encode(),
                 json.dumps({'profiles': {key: {'samples': True}}}).encode(),
                 json.dumps({'profiles': {key: {'elapsed_seconds': float('inf')}}}).encode())
    for raw in malformed:
        path.write_bytes(raw)
        assert store.get(model, 'CPU', 'auto', 4096) is None and store.last_error
        rejected(lambda: store.record(model, 'CPU', 'auto', 4096, metrics))
        assert path.read_bytes() == raw
    # Valid older profiles missing counters can be extended without losing data.
    path.write_text(json.dumps({'version': 1, 'profiles': {key: {'model': 'model'}}}))
    result = store.record(model, 'CPU', 'auto', 4096, metrics)
    assert result['samples'] == 1 and not store.last_error
    original = path.read_bytes()
    for hook in ('openvino_chat.state_io.os.fsync', 'openvino_chat.state_io.os.replace'):
        with patch(hook, side_effect=OSError('fixture benchmark failure')):
            rejected(lambda: store.record(model, 'CPU', 'auto', 4096, metrics), (OSError,))
        assert path.read_bytes() == original and not list(root.glob('.benchmarks-*.tmp'))
    assert store.record(model, 'CPU', 'auto', 4096, metrics)['samples'] == 2
    assert path.stat().st_mode & 0o777 == 0o600
    original = path.read_bytes()
    with patch.object(benchmarks, 'MAX_BENCHMARK_BYTES', 32):
        rejected(lambda: store.record(model, 'CPU', 'auto', 4096, metrics))
    assert path.read_bytes() == original
    with patch('json.loads', side_effect=RecursionError('fixture state nesting')):
        assert store.get(model, 'CPU', 'auto', 4096) is None
        rejected(lambda: store.record(model, 'CPU', 'auto', 4096, metrics))
    assert path.read_bytes() == original

    metadata = root / 'live-metadata'
    metadata.mkdir()
    mode = metadata / 'persistence-mode'
    assert storage_health(metadata)['mode'] == 'installed'
    for raw in (b'\xff', b'usb' + b' ' * 100, b'invalid'):
        mode.write_bytes(raw)
        assert storage_health(metadata)['level'] == 'critical'
        assert mode.read_bytes() == raw
    with patch.object(Path, 'open', side_effect=PermissionError('fixture unreadable live state')):
        status = storage_health(metadata)
        assert status['mode'] == 'unknown' and status['level'] == 'critical'
    mode.write_text('usb\n')
    assert storage_health(metadata)['mode'] == 'usb'

print('ok ai-store-safety: corrupt state/schema, checkpoint ownership/read refusal, atomic retry/cache, bounded private writes, live health')
