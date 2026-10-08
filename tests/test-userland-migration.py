#!/usr/bin/env python3
"""Offline disposable roots: cross-base guards, same-version ABI, resumability."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

project = Path(__file__).resolve().parents[1]
cli = project / "packages/ooonana/usr/bin/ooonana"

with tempfile.TemporaryDirectory(prefix="ooonana-userland-") as temporary:
    work = Path(temporary)
    repo, root = work / "repo", work / "root"
    (repo / "hooks").mkdir(parents=True)
    env = dict(os.environ, OOONANA_ROOT=str(root), OOONANA_REPO_DIR=str(repo),
               OOONANA_STATE_DIR=str(work / "state"), OOONANA_CACHE_DIR=str(work / "cache"),
               OOONANA_SOURCES_DIR=str(work / "sources"))

    def run(*args, success=True, overrides=None):
        result = subprocess.run(["sh", str(cli), *args], env=env | (overrides or {}),
                                text=True, capture_output=True, timeout=30)
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return result.stdout + result.stderr

    def package(name, version, kind="apk", base="", files=None, deps=""):
        fields = dict(ID=name, VERSION=version, KIND=kind, SUMMARY="Disposable fixture", DEPS=deps)
        if base:
            fields["BASE"] = base
        if files:
            archive = repo / f"{name}.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                for path, data in files.items():
                    entry = tarfile.TarInfo(path)
                    content = data.encode()
                    entry.size, entry.mode = len(content), 0o644
                    stream.addfile(entry, io.BytesIO(content))
            fields.update(ARCHIVE=archive.name, SHA256=hashlib.sha256(archive.read_bytes()).hexdigest())
        (repo / f"{name}.pkg").write_text("".join(f'OOONANA_PKG_{key}="{value}"\n' for key, value in fields.items()))

    def index():
        run("repo", "index", str(repo))

    package("same", "1", base="alpine-v3.20", files={"usr/share/same": "old"})
    package("lower", "2", base="alpine-v3.20", files={"usr/share/lower": "old"})
    package("ooonana-core-runtime", "0.9.9", kind="archive", deps="same lower",
            files={"etc/os-release": 'OOONANA_USERLAND_BASE="alpine-v3.20"\n'})
    package("ooonana-core", "0.9.9", kind="bundle", deps="ooonana-core-runtime")
    index()
    run("get", "ooonana-core")
    package("same", "1", base="alpine-v3.24", files={"usr/share/same": "new"})
    package("lower", "1", base="alpine-v3.24", files={"usr/share/lower": "new"})
    package("ooonana-core-runtime", "0.10.0", kind="archive", deps="same lower",
            files={"etc/os-release": 'OOONANA_USERLAND_BASE="alpine-v3.24"\n'})
    package("ooonana-core", "0.10.0", kind="bundle", deps="ooonana-core-runtime")

    # Major preflight must refuse before alphabetically earlier libraries change.
    index()
    assert "before any package changes" in run("upgrade", success=False)
    assert (root / "usr/share/same").read_text() == "old"
    assert "cross-base package refused" in run("upgrade", "lower", success=False)
    assert "cross-base package refused" in run("reinstall", "lower", success=False)
    package("new", "1", base="alpine-v3.24", files={"usr/share/new": "new"})
    index()
    assert "cross-base package refused" in run("get", "new", success=False)
    assert not (root / "usr/share/new").exists()
    manifest = repo / "BUILD-MANIFEST.json"
    manifest.write_text(json.dumps({"userland_base": "alpine-v3.24"}, indent=2) + "\n")
    index()
    assert "whole-world" in run("reinstall", "same", success=False)
    assert "whole-world" in run("upgrade", "same", "--allow-major", success=False)
    assert "whole-world" in run("upgrade", "--security-only", "--allow-major", success=False)
    assert "explicit --allow-major" in run("upgrade", success=False)
    assert "offline target" in run("upgrade", "--allow-major", success=False,
                                   overrides={"OOONANA_ROOT": "/"})
    assert not (work / "state/.userland-migration").exists()
    plan = run("upgrade", "--dry-run", "--allow-major")
    assert "would upgrade same 1 -> 1" in plan and "would upgrade lower 2 -> 1" in plan

    # Unsupported retirement refuses before any target payload changes.
    package("same", "1", kind="bundle")
    index()
    assert "retirement/replacement" in run("upgrade", "--allow-major", success=False)
    assert (root / "usr/share/same").read_text() == "old"
    package("same", "1", base="alpine-v3.24", files={"usr/share/same": "new"})
    hook = repo / "hooks/ooonana-core-runtime.healthcheck"
    failed = work / "readiness-failed"
    failed.touch()
    hook_source = f"#!/bin/sh\n[ ! -f '{failed}' ]\n"
    hook.write_text(hook_source)
    hook.chmod(0o755)
    index()
    run("upgrade", "--allow-major", success=False)
    journal = work / "state/.userland-migration"
    assert journal.is_file()
    assert (root / "usr/share/same").read_text() == "new"
    assert (root / "usr/share/lower").read_text() == "new"
    assert "incomplete" in run("verify", success=False)
    run("recover")
    assert journal.is_file()

    # A premature core marker must not bypass remaining whole-world guard.
    (root / "etc/os-release").write_text('OOONANA_USERLAND_BASE="alpine-v3.24"\n')
    assert "whole-world" in run("remove", "same", success=False)
    original = manifest.read_bytes()
    manifest.write_text(json.dumps({"userland_base": "alpine-v3.24", "changed": True}, indent=2) + "\n")
    index()
    assert "identical repository" in run("upgrade", "--allow-major", success=False)
    manifest.write_bytes(original)
    # Simulates readiness recovering without changing the original repository.
    hook.write_text("#!/bin/sh\nexit 0\n")
    index()
    # Journal must pin ALL checksums, not merely manifest content.
    assert "identical repository" in run("upgrade", "--allow-major", success=False)
    hook.write_text(hook_source)
    index()
    failed.unlink()
    output = run("upgrade", "--allow-major")
    assert "migration complete" in output
    assert not journal.exists()
    assert list((work / "state/backups").glob("userland-completed.*/journal"))
    run("verify", "same")
    run("verify", "lower")

print("ok offline userland migration guards, ABI replacements, retained interruption journal")
