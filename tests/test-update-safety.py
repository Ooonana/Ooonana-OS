#!/usr/bin/env python3
import hashlib
import io
import os
from pathlib import Path
import subprocess
import stat
import tarfile
import tempfile

project = Path(__file__).resolve().parents[1]
cli = project / "packages/ooonana/usr/bin/ooonana"
os.umask(0o077)  # Package and rollback modes must not inherit caller restrictions.

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

    def package(version, healthy=True, security=False, kind="archive"):
        ident = "ooonana-kernel" if kind == "kernel" else "ooonana-core-runtime"
        files = (("boot/vmlinuz", version),) if kind == "kernel" else (
            ("etc/fixture.conf", f"default={version}\n"), ("usr/share/fixture/version", version),
        )
        archive = repo / f"{ident}-{version}.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            for name, data in files:
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                entry.mode = 0o644
                stream.addfile(entry, io.BytesIO(data.encode()))
        metadata = dict(ID=ident, VERSION=version, KIND=kind, SUMMARY="Fixture", DEPS="", ARCHIVE=archive.name, SHA256=hashlib.sha256(archive.read_bytes()).hexdigest(), REBOOT="1", SECURITY="1" if security else "0")
        (repo / f"{ident}.pkg").write_text("".join(f'OOONANA_PKG_{key}="{value}"\n' for key, value in metadata.items()))
        hook = repo / f"hooks/{ident}.healthcheck"
        hook.write_text(f"#!/bin/sh\nexit {0 if healthy else 1}\n")
        hook.chmod(0o755)
        command("repo", "index", str(repo))

    package("0.9.4")
    command("get", "ooonana-core-runtime")
    config = root / "etc/fixture.conf"
    assert stat.S_IMODE(config.stat().st_mode) == 0o644
    config.write_text("custom=yes\n")
    config.chmod(0o640)
    package("0.9.5", security=True)
    output = command("upgrade", "--security-only")
    assert "healthcheck" in output and "checkpoint" in output
    assert config.read_text() == "custom=yes\n"
    assert stat.S_IMODE(config.stat().st_mode) == 0o640
    assert config.with_name("fixture.conf.ooonana-new").read_text() == "default=0.9.5\n"
    assert (root / "run/ooonana/reboot-required").is_file()
    baseline = (work / "state/config-baselines/ooonana-core-runtime.sha256").read_bytes()
    package("0.9.6", healthy=False)
    command("upgrade", success=False)
    assert (root / "usr/share/fixture/version").read_text() == "0.9.5"
    assert config.read_text() == "custom=yes\n"
    assert stat.S_IMODE(config.stat().st_mode) == 0o640
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

    marker = root / "mnt/ooonana-live/persistence-mode"
    marker.parent.mkdir(parents=True)
    kernel_path = root / "boot/vmlinuz"
    reboot_marker = root / "run/ooonana/reboot-required"
    package("1.0.0", kind="kernel")
    marker.write_text("ram\n")
    assert "needs a fresh USB image" in command("get", "ooonana-kernel", success=False)
    assert not kernel_path.exists()
    marker.unlink()
    command("get", "ooonana-kernel")
    package("1.0.1", kind="kernel", security=True)
    for mode, version in (("ram", "0.11.1"), ("usb-temporary", "0.11.2"), ("usb", "0.11.3")):
        marker.write_text(f"{mode}\n")
        package(version, security=True)
        reboot_marker.unlink(missing_ok=True)
        status = command("update-status")
        storage_hint = "survive reboot" if mode == "usb" else "disappear on reboot"
        assert storage_hint in status
        assert "ooonana-kernel 1.0.0 -> 1.0.1 [security,fresh-USB-image]" in status
        assert "needs a fresh USB image" in command(
            "upgrade", "ooonana-core-runtime", "ooonana-kernel", success=False
        )
        assert (root / "usr/share/fixture/version").read_text() != version
        preview = command("upgrade", "--dry-run", "--security-only")
        assert "would upgrade ooonana-core-runtime" in preview
        assert "Fresh USB image required: ooonana-kernel" in preview
        output = command("upgrade", "--security-only")
        assert storage_hint in output
        assert f"-> {version}" in output and "upgraded ooonana-kernel" not in output
        assert (root / "usr/share/fixture/version").read_text() == version
        assert kernel_path.read_text() == "1.0.0"
        assert config.read_text() == "custom=yes\n"
        assert reboot_marker.exists() == (mode == "usb")
    assert "needs a fresh USB image" in command("reinstall", "ooonana-kernel", success=False)
    assert "Fresh USB image required" in command("fix", "--reinstall", "--dry-run")
    marker.write_text("invalid\n")
    assert "could not be verified" in command("update-status")
    assert "needs a fresh USB image" in command("upgrade", "ooonana-kernel", success=False)
    marker.unlink()
    command("upgrade", "ooonana-kernel")
    assert kernel_path.read_text() == "1.0.1"
print("ok update-safety")
