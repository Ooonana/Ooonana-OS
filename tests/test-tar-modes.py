#!/usr/bin/env python3
"""Real CLI: GNU extraction, root BusyBox, unsupported nonroot refusal."""
import hashlib
import io
import os
from pathlib import Path
import shutil
import shlex
import stat
import subprocess
import tarfile
import tempfile

cli = Path(__file__).resolve().parents[1] / "packages/ooonana/usr/bin/ooonana"
busybox = os.environ.get("OOONANA_TEST_BUSYBOX") or shutil.which("busybox")
loader = os.environ.get("OOONANA_TEST_BUSYBOX_LOADER")

with tempfile.TemporaryDirectory(prefix="ooonana-tar-modes-") as temporary:
    work = Path(temporary)
    repo, root, bindir = work / "repo", work / "root", work / "bin"
    (repo / "hooks").mkdir(parents=True)
    bindir.mkdir()
    env = dict(os.environ, OOONANA_ROOT=str(root), OOONANA_REPO_DIR=str(repo),
               OOONANA_STATE_DIR=str(work / "state"), OOONANA_CACHE_DIR=str(work / "cache"),
               OOONANA_SOURCES_DIR=str(work / "sources"))

    def run(*args, success=True, portable=False):
        selected = env | ({"PATH": str(bindir) + ":" + env["PATH"]} if portable else {})
        result = subprocess.run(["sh", str(cli), *args], env=selected, umask=0o077,
                                text=True, capture_output=True, timeout=30)
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return result.stdout + result.stderr

    def package(version, healthy=True):
        archive = repo / "fixture.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            for name, mode in (("var/", 0o755), ("var/tmp/", 0o1777),
                               ("etc/", 0o755), ("usr/", 0o755), ("usr/share/", 0o755)):
                entry = tarfile.TarInfo(name)
                entry.type, entry.mode = tarfile.DIRTYPE, mode
                stream.addfile(entry)
            for name, value in (("etc/fixture.conf", "default=" + version),
                                ("usr/share/version", version)):
                entry = tarfile.TarInfo(name)
                data = value.encode()
                entry.size, entry.mode = len(data), 0o644
                stream.addfile(entry, io.BytesIO(data))
        fields = dict(ID="fixture", VERSION=version, KIND="archive", SUMMARY="Mode fixture",
                      DEPS="", ARCHIVE=archive.name,
                      SHA256=hashlib.sha256(archive.read_bytes()).hexdigest())
        (repo / "fixture.pkg").write_text("".join(
            f'OOONANA_PKG_{key}="{value}"\n' for key, value in fields.items()))
        hook = repo / "hooks/fixture.healthcheck"
        hook.write_text(f"#!/bin/sh\nexit {0 if healthy else 1}\n")
        hook.chmod(0o755)
        run("repo", "index", str(repo))

    package("1")
    if busybox:
        portable_command = ([loader] if loader else []) + [busybox, "tar"]
        wrapper = bindir / "tar"
        wrapper.write_text('#!/bin/sh\nexec ' + shlex.join(portable_command) + ' "$@"\n')
        wrapper.chmod(0o755)
    run("get", "fixture", portable=bool(busybox and not os.geteuid()))
    config = root / "etc/fixture.conf"
    assert stat.S_IMODE(config.stat().st_mode) == 0o644
    assert stat.S_IMODE((root / "var/tmp").stat().st_mode) == 0o1777
    config.write_text("custom=yes")
    config.chmod(0o640)
    if busybox:
        package("2")
        if os.geteuid():
            refusal = run("upgrade", "fixture", portable=True, success=False)
            assert "requires GNU tar" in refusal, refusal
            assert (root / "usr/share/version").read_text() == "1"
            assert not list((work / "state").glob(".replace-*"))
            print("ok nonroot BusyBox refused before payload changes")
        else:
            help_text = subprocess.run(portable_command + ["--help"], text=True,
                                       capture_output=True, timeout=5)
            if "-T FILE" not in help_text.stdout + help_text.stderr:
                print("SKIP root BusyBox upgrade: host build lacks file-list feature; install modes passed")
            else:
                run("upgrade", "fixture", portable=True)
                assert (root / "usr/share/version").read_text() == "2"
                package("3", healthy=False)
                run("upgrade", "fixture", portable=True, success=False)
                assert (root / "usr/share/version").read_text() == "2"
                assert not list((work / "state").glob(".replace-*"))
                print("ok root BusyBox upgrade and rollback")
        assert config.read_text() == "custom=yes"
        assert stat.S_IMODE(config.stat().st_mode) == 0o640
        assert stat.S_IMODE((root / "var/tmp").stat().st_mode) == 0o1777
    else:
        print("SKIP BusyBox mode probe: executable absent")
print("ok archive modes under umask 077")
