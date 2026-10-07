#!/usr/bin/env python3
"""Real CLI, private installation roots; signals never target host services."""
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import os
from pathlib import Path
import signal
import socket
import subprocess
import tarfile
import tempfile
import threading
import time

PROJECT = Path(__file__).resolve().parents[1]
CLI = PROJECT / "packages/ooonana/usr/bin/ooonana"


def run(env, *args, success=True):
    child = subprocess.Popen(["sh", str(CLI), *args], env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True)
    try:
        output, errors = child.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        output, errors = child.communicate(timeout=10)
        raise AssertionError("CLI timeout: " + output + errors) from None
    assert (child.returncode == 0) == success, output + errors
    return output + errors


with tempfile.TemporaryDirectory(prefix="ooonana-interrupted-update-") as temporary:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        work = Path(temporary) / sig.name
        repo = work / "repo"
        (repo / "hooks").mkdir(parents=True)
        root = work / "root"
        env = dict(os.environ, OOONANA_ROOT=str(root), OOONANA_REPO_DIR=str(repo),
                   OOONANA_STATE_DIR=str(work / "state"),
                   OOONANA_CACHE_DIR=str(work / "cache"),
                   OOONANA_SOURCES_DIR=str(work / "sources"),
                   OOONANA_KEEP_UPDATE_BACKUPS="all")

        def package(version):
            archive = repo / "fixture.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                files = {"etc/fixture.conf": "default=" + version,
                         "usr/share/fixture/version": version}
                if version == "2":
                    files["usr/share/fixture/new-file"] = "new"
                for name, value in files.items():
                    entry = tarfile.TarInfo(name)
                    data = value.encode()
                    entry.size, entry.mode = len(data), 0o644
                    stream.addfile(entry, io.BytesIO(data))
            fields = dict(ID="fixture", VERSION=version, KIND="archive",
                          SUMMARY="Private interruption fixture", DEPS="",
                          ARCHIVE=archive.name,
                          SHA256=hashlib.sha256(archive.read_bytes()).hexdigest())
            (repo / "fixture.pkg").write_text("".join(
                f'OOONANA_PKG_{key}="{value}"\n' for key, value in fields.items()))
            run(env, "repo", "index", str(repo))

        package("1")
        run(env, "get", "fixture")
        config = root / "etc/fixture.conf"
        config.write_text("custom=yes")
        installed = (work / "state/installed/fixture.pkg").read_bytes()
        baseline = (work / "state/config-baselines/fixture.sha256").read_bytes()
        manifest = (work / "state/files/fixture.list").read_bytes()
        package("2")
        hook = repo / "hooks/fixture.healthcheck"
        hook.write_text('#!/bin/sh\nprintf ready > "$OOONANA_ROOT/ready"\n'
                        'while :; do sleep 1; done\n')
        hook.chmod(0o755)
        run(env, "repo", "index", str(repo))
        with (work / "interruption.log").open("w") as log:
            child = subprocess.Popen(["sh", str(CLI), "upgrade", "fixture"],
                                     env=env, stdout=log, stderr=log,
                                     start_new_session=True)
            try:
                deadline = time.monotonic() + 30
                while not (root / "ready").exists():
                    assert child.poll() is None, (work / "interruption.log").read_text()
                    assert time.monotonic() < deadline, "health hook never reached"
                    time.sleep(0.03)
                assert (root / "usr/share/fixture/version").read_text() == "2"
                # Concurrent writers must not snapshot an in-progress update.
                output = run(env, "remove", "fixture", success=False)
                assert "busy" in output, output
                os.killpg(child.pid, sig)
                child.wait(timeout=15)
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=15)
        if sig == signal.SIGKILL:
            checkpoint, = (work / "state").glob(".replace-*")
            output = run(env, "fix", "fixture", success=False)
            assert "recover" in output, output
            output = run(dict(env, OOONANA_ROOT=str(work / "other-root")), "recover", success=False)
            assert "another installation" in output, output
            assert (root / "usr/share/fixture/version").read_text() == "2"
            payload = checkpoint / "payload.tar"
            original = payload.read_bytes()
            payload.write_bytes(b"corrupted snapshot")
            output = run(env, "recover", success=False)
            assert "checkpoint retained" in output, output
            assert config.read_text() == "custom=yes"
            assert (root / "usr/share/fixture/version").read_text() == "2"
            payload.write_bytes(original)
            # A failed restore must keep its journal and remain retryable.
            bindir = work / "bin"
            bindir.mkdir()
            failing_tar = bindir / "tar"
            failing_tar.write_text('#!/bin/sh\n[ "$1" != -xf ] || exit 9\nexec /bin/tar "$@"\n')
            failing_tar.chmod(0o755)
            output = run(dict(env, PATH=str(bindir) + ":" + env["PATH"]), "recover", success=False)
            assert "checkpoint retained" in output and checkpoint.is_dir(), output
            output = run(env, "recover")
            assert "restored previous package" in output, output
            assert "no interrupted" in run(env, "recover")
        assert (root / "usr/share/fixture/version").read_text() == "1"
        assert not (root / "usr/share/fixture/new-file").exists()
        assert config.read_text() == "custom=yes"
        assert not config.with_name("fixture.conf.ooonana-new").exists()
        assert (work / "state/installed/fixture.pkg").read_bytes() == installed
        assert (work / "state/config-baselines/fixture.sha256").read_bytes() == baseline
        assert (work / "state/files/fixture.list").read_bytes() == manifest
        assert not list((work / "state").glob(".replace-*"))
        print("ok update-interruption", sig.name)

    # Interrupt a real localhost archive transfer, not a mocked downloader.
    hook.unlink()
    package("2")

    class CutTransfer(SimpleHTTPRequestHandler):
        broken = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(repo), **kwargs)

        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.broken and self.path.endswith("/fixture.tar.gz"):
                data = (repo / "fixture.tar.gz").read_bytes()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data[:len(data) // 2])
                self.wfile.flush()
                self.connection.shutdown(socket.SHUT_RDWR)
                self.close_connection = True
            else:
                super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", 0), CutTransfer)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        empty_repo, sources = work / "empty-repo", work / "sources"
        empty_repo.mkdir()
        sources.mkdir()
        (sources / "cloud.repo").write_text(
            'OOONANA_REPO_NAME="cloud"\n'
            f'OOONANA_REPO_URI="http://127.0.0.1:{server.server_port}"\n')
        remote_env = dict(env, OOONANA_REPO_DIR=str(empty_repo),
                          OOONANA_DOWNLOAD_RETRIES="0", OOONANA_DOWNLOAD_MAX_TIME="5",
                          OOONANA_DOWNLOAD_CONNECT_TIMEOUT="1")
        run(remote_env, "update")
        run(remote_env, "upgrade", "fixture", success=False)
        assert (root / "usr/share/fixture/version").read_text() == "1"
        assert config.read_text() == "custom=yes"
        assert (work / "state/installed/fixture.pkg").read_bytes() == installed
        assert not list((work / "state").glob(".replace-*"))
        assert not list((work / "cache").rglob(".fetch.*"))
        CutTransfer.broken = False
        run(remote_env, "upgrade", "fixture")
        assert (root / "usr/share/fixture/version").read_text() == "2"
        assert config.read_text() == "custom=yes"
        print("ok update-interruption truncated-download and successful retry")
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
print("ok update-interruption")
