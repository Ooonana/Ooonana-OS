#!/usr/bin/env python3
"""Legacy factory adoption: real CLI config preservation, failure and crash recovery."""
import hashlib
import io
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "packages/ooonana/usr/bin/ooonana"
with tempfile.TemporaryDirectory(prefix="ooonana-core-adoption-") as temporary:
    work = Path(temporary); root = work / "root"; repo = work / "repo"; state = root / "var/lib/ooonana/packages"
    for path in (root / "etc/ooonana", root / "usr/share/fixture", repo / "hooks", state / "installed", state / "files"):
        path.mkdir(parents=True, exist_ok=True)
    config = root / "etc/ooonana/fixture.conf"; config.write_text("custom=yes\n"); config.chmod(0o640)
    payload = root / "usr/share/fixture/version"; payload.write_text("legacy")
    legacy = state / "installed/ooonana-core.pkg"
    legacy.write_text('OOONANA_PKG_ID="ooonana-core"\nOOONANA_PKG_VERSION="0.10.0"\nOOONANA_PKG_KIND="archive"\nOOONANA_PKG_SUMMARY="Legacy factory core"\nOOONANA_PKG_DEPS=""\n')
    legacy_manifest = state / "files/ooonana-core.list"; legacy_manifest.write_text("etc/ooonana/fixture.conf\nusr/share/fixture/version\n")
    original_legacy = legacy.read_bytes(); original_manifest = legacy_manifest.read_bytes()
    archive = repo / "runtime.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for name, data in (("etc/ooonana/fixture.conf", b"default=yes\n"), ("usr/share/fixture/version", b"runtime"),
                           ("var/lib/ooonana/packages/files/ooonana-core.list", b"")):
            item = tarfile.TarInfo(name); item.size, item.mode = len(data), 0o644; bundle.addfile(item, io.BytesIO(data))
    (repo / "ooonana-core-runtime.pkg").write_text('OOONANA_PKG_ID="ooonana-core-runtime"\nOOONANA_PKG_VERSION="0.10.0"\nOOONANA_PKG_KIND="archive"\nOOONANA_PKG_SUMMARY="QA runtime adoption"\nOOONANA_PKG_DEPS=""\nOOONANA_PKG_ARCHIVE="runtime.tar.gz"\nOOONANA_PKG_SHA256="' + hashlib.sha256(archive.read_bytes()).hexdigest() + '"\n')
    env = {**os.environ, "OOONANA_ROOT": str(root), "OOONANA_REPO_DIR": str(repo),
           "OOONANA_SOURCES_DIR": str(work / "sources"), "OOONANA_CACHE_DIR": str(work / "cache")}
    def run(*args, success=True):
        result = subprocess.run(["sh", str(CLI), *args], env=env, capture_output=True, text=True, timeout=30)
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return result.stdout + result.stderr
    def restored():
        assert config.read_text() == "custom=yes\n" and config.stat().st_mode & 0o777 == 0o640
        assert payload.read_text() == "legacy"
        assert legacy.read_bytes() == original_legacy and legacy_manifest.read_bytes() == original_manifest
        assert not (state / "installed/ooonana-core-runtime.pkg").exists()
        assert not (state / "files/ooonana-core-runtime.list").exists()
        assert not config.with_suffix(".conf.ooonana-new").exists()
    hook = repo / "hooks/ooonana-core-runtime.healthcheck"
    hook.write_text("#!/bin/sh\nexit 17\n"); hook.chmod(0o755)
    run("repo", "index", str(repo)); run("get", "ooonana-core-runtime", success=False); restored()
    ready = root / "ready"
    hook.write_text('#!/bin/sh\nprintf ready > "$OOONANA_ROOT/ready"\nwhile :; do sleep 1; done\n')
    run("repo", "index", str(repo))
    with (work / "crash.log").open("w") as log:
        child = subprocess.Popen(["sh", str(CLI), "get", "ooonana-core-runtime"], env=env, stdout=log, stderr=log, start_new_session=True)
        try:
            deadline = time.monotonic() + 30
            while not ready.exists():
                assert child.poll() is None, (work / "crash.log").read_text()
                assert time.monotonic() < deadline; time.sleep(.03)
            assert config.read_text() == "custom=yes\n" and payload.read_text() == "runtime"
            os.killpg(child.pid, signal.SIGKILL); child.wait(timeout=10)
        finally:
            if child.poll() is None: os.killpg(child.pid, signal.SIGKILL); child.wait(timeout=10)
    checkpoint, = state.glob(".replace-*")
    marker = checkpoint / "installed.absent"; original_marker = marker.read_bytes(); marker.write_text("damaged")
    run("recover", success=False); assert payload.read_text() == "runtime"
    marker.write_bytes(original_marker); run("recover"); restored()
    # First runtime adoption is still an OS replacement when legacy core is
    # older: changing package IDs must not bypass the existing major policy.
    legacy.write_bytes(original_legacy.replace(b'VERSION="0.10.0"', b'VERSION="0.9.0"'))
    dependency = state / "installed/adoption-dependency.pkg"
    (repo / "adoption-dependency.pkg").write_text('OOONANA_PKG_ID="adoption-dependency"\nOOONANA_PKG_VERSION="1"\nOOONANA_PKG_KIND="bundle"\nOOONANA_PKG_SUMMARY="QA dependency mutation marker"\nOOONANA_PKG_DEPS=""\n')
    metadata = repo / "ooonana-core-runtime.pkg"
    metadata.write_text(metadata.read_text().replace('OOONANA_PKG_DEPS=""', 'OOONANA_PKG_DEPS="adoption-dependency"'))
    hook.write_text("#!/bin/sh\nexit 0\n"); run("repo", "index", str(repo))
    denied = run("get", "ooonana-core-runtime", success=False)
    assert "major OS update requires explicit --allow-major" in denied
    assert "major update needs --allow-major" in run("get", "--dry-run", "ooonana-core-runtime")
    assert payload.read_text() == "legacy" and not (state / "installed/ooonana-core-runtime.pkg").exists()
    assert not dependency.exists(), "Major refusal must precede dependency installation"
    run("reinstall", "ooonana-core-runtime", "--allow-major")
    assert dependency.exists(), "Explicit major adoption must install its dependency"
    assert config.read_text() == "custom=yes\n" and config.stat().st_mode & 0o777 == 0o640
    assert config.with_suffix(".conf.ooonana-new").read_text() == "default=yes\n"
    assert payload.read_text() == "runtime" and legacy_manifest.read_bytes() == b""
    assert (state / "installed/ooonana-core-runtime.pkg").is_file()
    run("reinstall", "ooonana-core-runtime"); assert config.read_text() == "custom=yes\n"
print("CORE_ADOPTION_OK configs/modes, legacy state, failed-health rollback, crash/marker recovery, major policy and reinstall")
