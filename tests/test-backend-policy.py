#!/usr/bin/env python3
"""Fixture-only checks: immutable publication, memory estimates, bounded IPC."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/openvino-chat/source/src"))
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana"))
import i3_events
from openvino_chat.memory_guard import MIB, estimate_memory, is_memory_error

loader = importlib.util.spec_from_file_location("repo_publication", root / "scripts/publish-repo-generation.py")
publication = importlib.util.module_from_spec(loader)
loader.loader.exec_module(publication)
cli = root / "packages/ooonana/usr/bin/ooonana"
workflow = (root / ".github/workflows/build-ooonana-packages.yml").read_text()
assert 'default: "candidate-core-0.10.0"' in workflow
assert 'case "$RELEASE_TAG" in candidate-*)' in workflow
assert '[ "$PUBLISH_PAGES" = true ]' in workflow and '[ "$PUBLISH_R2" = true ]' in workflow
assert '$OOONANA_ALLOW_MAJOR_PUBLISH == "1"' in (root / ".gitlab-ci.yml").read_text()
profile = (root / "configs/packages/full-i3.list").read_text().splitlines()
assert "glycin-image-rs" in profile and "glycin-svg" in profile

with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    source = work / "repo"
    source.mkdir()
    (source / "archives").mkdir()
    (source / "archives/fixture.tar.gz").write_bytes(b"Fixture archive")
    import hashlib
    archive_sha = hashlib.sha256(b"Fixture archive").hexdigest()
    metadata = f'OOONANA_PKG_ID="fixture"\nOOONANA_PKG_VERSION="1.0"\nOOONANA_PKG_KIND="archive"\nOOONANA_PKG_SUMMARY="Fixture"\nOOONANA_PKG_DEPS=""\nOOONANA_PKG_ARCHIVE="archives/fixture.tar.gz"\nOOONANA_PKG_SHA256="{archive_sha}"\n'
    (source / "fixture.pkg").write_text(metadata)
    subprocess.run(["sh", str(cli), "repo", "index", str(source)], check=True, capture_output=True)
    target = work / "published"
    first = publication.publish(source, target)
    pointer = (target / "CURRENT").read_text()
    assert first.is_dir() and (first / "index.tsv").is_file()
    (source / "fixture.pkg").write_text(metadata.replace('"1.0"', '"1.1"'))
    try:
        publication.publish(source, target)
        raise AssertionError("Corrupt source promoted")
    except ValueError:
        pass
    assert (target / "CURRENT").read_text() == pointer
    subprocess.run(["sh", str(cli), "repo", "index", str(source)], check=True, capture_output=True)
    second = publication.publish(source, target)
    assert second != first and first.is_dir()
    assert first.stat().st_mode & 0o777 == 0o755
    assert (target / "CURRENT").stat().st_mode & 0o777 == 0o644
    assert (first / "archives/fixture.tar.gz").stat().st_ino == (second / "archives/fixture.tar.gz").stat().st_ino
    assert (source / "archives/fixture.tar.gz").stat().st_ino != (first / "archives/fixture.tar.gz").stat().st_ino
    index_before = (source / "index.tsv").read_bytes()
    sums_before = (source / "SHA256SUMS").read_bytes()
    subprocess.run([sys.executable, str(root / "scripts/index-repo-fast.py"), "--repo", str(source)], check=True, capture_output=True)
    assert (source / "index.tsv").read_bytes() == index_before
    assert (source / "SHA256SUMS").read_bytes() == sums_before
    (target / "CURRENT").write_bytes((target / "CURRENT").read_bytes().replace(b"\n", b"\r\n"))
    result = subprocess.run(["sh", str(cli), "show", "fixture"], env={**os.environ, "OOONANA_REPO_DIR": str(target), "OOONANA_SOURCES_DIR": str(work / "no-sources"), "OOONANA_ROOT": str(work / "root")}, text=True, capture_output=True)
    assert result.returncode == 0 and "1.1" in result.stdout, result.stderr
    publication.publish(source, target)
    assert b"\r" not in (target / "CURRENT").read_bytes()
    model = work / "model"
    model.mkdir()
    with (model / "openvino_model.bin").open("wb") as stream:
        stream.truncate(512 * MIB)
    (model / "config.json").write_text(json.dumps(dict(num_hidden_layers=32, num_attention_heads=32, num_key_value_heads=8, hidden_size=4096)))
    full = estimate_memory(model, 4096, "f16", (8 * 1024 * MIB, 2 * 1024 * MIB, 1024 * MIB))
    reduced = estimate_memory(model, 4096, "u8", (8 * 1024 * MIB, 2 * 1024 * MIB, 1024 * MIB))
    assert full.weights == 512 * MIB and reduced.estimated_kv * 2 == full.estimated_kv
    assert not full.report()["swap_is_physical_ram"]
    assert is_memory_error(RuntimeError("std::bad_alloc"))
    assert not is_memory_error(RuntimeError("GPU not available"))

left, right = socket.socketpair()
right.sendall(i3_events.HEADER.pack(i3_events.MAGIC, 2, 4) + b"{}")
assert i3_events.receive(left) == (4, {})
right.sendall(i3_events.HEADER.pack(i3_events.MAGIC, i3_events.MAX_MESSAGE + 1, 4))
try:
    i3_events.receive(left)
    raise AssertionError("Unbounded IPC accepted")
except ValueError:
    pass
left.close(); right.close()
print("ok backend-policy")
