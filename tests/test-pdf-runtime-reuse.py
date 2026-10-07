#!/usr/bin/env python3
"""Verified native reuse: applet-only refresh, originals preserved, tamper refused."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
kernel_config = (root / "configs/kernel/ooonana-pdf-riscv64.fragment").read_bytes()
with tempfile.TemporaryDirectory() as temporary:
    source, work = Path(temporary) / "original", Path(temporary) / "work"
    files = {"kernel-riscv64.bin": b"kernel fixture", "kernel.config": kernel_config,
             "busybox.config": b"CONFIG_STATIC=y\nCONFIG_FEATURE_SH_STANDALONE=y\nCONFIG_FEATURE_SH_NOFORK=y\n",
             "rootfs/bin/busybox": b"busybox fixture"}
    for name, value in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    (source / "rootfs/bin/busybox").chmod(0o755)
    (source / "rootfs/bin/sh").symlink_to("busybox")
    (source / "rootfs/private-data").write_text("Must not enter new payload")
    manifest = dict(architecture="riscv64", kernel="6.18.37", busybox="1.37.0",
                    files={name: hashlib.sha256(value).hexdigest() for name, value in files.items()})
    (source / "RUNTIME-MANIFEST.json").write_text(json.dumps(manifest))
    command = ["bash", str(root / "scripts/build-native-pdf-runtime.sh"),
               "--reuse-runtime", str(source), "--work-dir", str(work)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    rebuilt = next(work.glob("runtime.*/rootfs"))
    assert (rebuilt / "bin/sh").is_symlink()
    assert (rebuilt / "bin/busybox").read_bytes() == files["rootfs/bin/busybox"]
    assert not (rebuilt / "private-data").exists()
    assert not (rebuilt / "usr/lib/ooonana/ui").exists()
    assert (source / "rootfs/private-data").read_text() == "Must not enter new payload"
    # A valid checksum is not enough: required features must match current policy.
    for config, expected in (
        (kernel_config.replace(b"CONFIG_TMPFS=y", b"# CONFIG_TMPFS is not set"), "CONFIG_TMPFS=y"),
        (kernel_config.replace(b"CONFIG_MODULES=n", b"CONFIG_MODULES=y"), "CONFIG_MODULES=n"),
        (kernel_config + b"CONFIG_TMPFS=y\n", "Duplicate native kernel option"),
    ):
        (source / "kernel.config").write_bytes(config)
        manifest["files"]["kernel.config"] = hashlib.sha256(config).hexdigest()
        (source / "RUNTIME-MANIFEST.json").write_text(json.dumps(manifest))
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode != 0 and expected in result.stderr, result.stderr
        assert (source / "rootfs/private-data").read_text() == "Must not enter new payload"
    (source / "kernel.config").write_bytes(kernel_config)
    manifest["files"]["kernel.config"] = hashlib.sha256(kernel_config).hexdigest()
    (source / "RUNTIME-MANIFEST.json").write_text(json.dumps(manifest))
    (source / "kernel-riscv64.bin").write_bytes(b"tampered")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0 and "Runtime checksum mismatch" in result.stderr
print("ok pdf-runtime-reuse: verified binaries/config, applet-only refresh, originals preserved, tamper/missing features refused")
