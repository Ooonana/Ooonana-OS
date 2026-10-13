#!/usr/bin/env python3
"""Firmware audit must match target kernel, not host loader capabilities."""
import importlib.util
from pathlib import Path
import tempfile

source = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("audit", source / "tests/audit-full-i3-runtime.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
base = {"CONFIG_FW_LOADER=y", "CONFIG_FW_LOADER_COMPRESS=y"}
name = "/lib/firmware/i915/adlp_dmc.bin"
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / "root"
    blob = root / name.lstrip("/")
    blob.parent.mkdir(parents=True)
    assert not audit.firmware_exists(root, name, base)
    blob.write_bytes(b"raw firmware")
    assert audit.firmware_exists(root, name, set())
    blob.write_bytes(b"")
    assert not audit.firmware_exists(root, name, base)
    blob.unlink()
    for suffix, option in ((".zst", "CONFIG_FW_LOADER_COMPRESS_ZSTD=y"),
                           (".xz", "CONFIG_FW_LOADER_COMPRESS_XZ=y")):
        compressed = blob.with_name(blob.name + suffix)
        compressed.write_bytes(b"fixture")
        assert not audit.firmware_exists(root, name, base)
        assert not audit.firmware_exists(root, name, {option})
        assert audit.firmware_exists(root, name, base | {option})
        compressed.unlink()
    target = blob.with_name("versioned.bin.zst")
    target.write_bytes(b"fixture")
    compressed = blob.with_name(blob.name + ".zst")
    compressed.symlink_to(target.name)
    assert audit.firmware_exists(root, name, base | {"CONFIG_FW_LOADER_COMPRESS_ZSTD=y"})
    target.unlink()
    assert not audit.firmware_exists(root, name, base | {"CONFIG_FW_LOADER_COMPRESS_ZSTD=y"})
    compressed.unlink()
    outside = Path(temporary) / "host-firmware"
    outside.write_bytes(b"not target firmware")
    blob.symlink_to(outside)
    assert not audit.firmware_exists(root, name, base)

for profile in ("full-i3.list", "both.list"):
    names = {line.split("#", 1)[0].strip() for line in
             (source / "configs/packages" / profile).read_text().splitlines()}
    assert {"rofi", "rofi-x11-wayland"} <= names, profile
release = (source / "scripts/rebuild-full-i3-release.sh").read_text()
assert 'audit-full-i3-runtime.py" "$ROOTFS" --kernel-config "$KERNEL_CONFIG"' in release
print("ok runtime-firmware: raw, target-supported compression, missing/empty/unsafe blobs, rofi split")
