#!/usr/bin/env python3
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

project = Path(__file__).resolve().parents[1]
cli = project / "packages/ooonana/usr/bin/ooonana"

with tempfile.TemporaryDirectory() as temporary:
    work = Path(temporary)
    repo = work / "repo"
    repo.mkdir()
    (repo / "hooks").mkdir()
    root = work / "root"
    env = dict(os.environ, OOONANA_ROOT=str(root), OOONANA_REPO_DIR=str(repo), OOONANA_STATE_DIR=str(work / "state"), OOONANA_CACHE_DIR=str(work / "cache"), OOONANA_SOURCES_DIR=str(work / "sources"), OOONANA_KEEP_UPDATE_BACKUPS="all")

    def command(*args, success=True):
        result = subprocess.run(["sh", str(cli), *args], env=env, text=True, capture_output=True)
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return result.stdout + result.stderr

    def package(version, healthy=True, security=False):
        archive = repo / f"core-{version}.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            for name, data in (("etc/fixture.conf", f"default={version}\n"), ("usr/share/fixture/version", version)):
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                entry.mode = 0o644
                stream.addfile(entry, io.BytesIO(data.encode()))
        metadata = dict(ID="ooonana-core-runtime", VERSION=version, KIND="archive", SUMMARY="Fixture", DEPS="", ARCHIVE=archive.name, SHA256=hashlib.sha256(archive.read_bytes()).hexdigest(), REBOOT="1", SECURITY="1" if security else "0")
        (repo / "ooonana-core-runtime.pkg").write_text("".join(f'OOONANA_PKG_{key}="{value}"\n' for key, value in metadata.items()))
        hook = repo / "hooks/ooonana-core-runtime.healthcheck"
        hook.write_text(f"#!/bin/sh\nexit {0 if healthy else 1}\n")
        hook.chmod(0o755)
        command("repo", "index", str(repo))

    package("0.9.4")
    command("get", "ooonana-core-runtime")
    config = root / "etc/fixture.conf"
    config.write_text("custom=yes\n")
    package("0.9.5", security=True)
    output = command("upgrade", "--security-only")
    assert "healthcheck" in output and "checkpoint" in output
    assert config.read_text() == "custom=yes\n"
    assert config.with_name("fixture.conf.ooonana-new").read_text() == "default=0.9.5\n"
    assert (root / "run/ooonana/reboot-required").is_file()
    baseline = (work / "state/config-baselines/ooonana-core-runtime.sha256").read_bytes()
    package("0.9.6", healthy=False)
    command("upgrade", success=False)
    assert (root / "usr/share/fixture/version").read_text() == "0.9.5"
    assert config.read_text() == "custom=yes\n"
    assert (work / "state/config-baselines/ooonana-core-runtime.sha256").read_bytes() == baseline
    package("0.10.0")
    assert "major" in command("update-status")
    assert "explicit --allow-major" in command("upgrade", success=False)
    assert "major update needs" in command("upgrade", "--dry-run")
    command("upgrade", "--allow-major")
    assert (root / "usr/share/fixture/version").read_text() == "0.10.0"
    package("0.11.0", security=True)
    assert '[major,security]' in command("update-status")
    assert 'explicit --allow-major' in command('upgrade', '--security-only', success=False)
    assert 'major update needs' in command('upgrade', '--security-only', '--dry-run')
    assert (root / 'usr/share/fixture/version').read_text() == '0.10.0'
    assert 'explicit --allow-major' in command('reinstall', 'ooonana-core-runtime', success=False)
    assert (root / 'usr/share/fixture/version').read_text() == '0.10.0'
    assert 'major update needs' in command('fix', 'ooonana-core-runtime', '--reinstall', '--dry-run')
    assert (root / 'usr/share/fixture/version').read_text() == '0.10.0'
    (root / 'usr/share/fixture/version').unlink()  # Broken-package repair must obey the same policy.
    assert 'explicit --allow-major' in command('fix', 'ooonana-core-runtime', success=False)
    assert '0.10.0' in (work / 'state/installed/ooonana-core-runtime.pkg').read_text()
    command('reinstall', 'ooonana-core-runtime', '--allow-major')
    assert (root / 'usr/share/fixture/version').read_text() == '0.11.0'
print("ok update-safety")
