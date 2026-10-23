#!/usr/bin/env python3
"""Unpublished native locker repack; vendor PAM policy/dependencies retained."""
import argparse
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release", ROOT / "scripts/check-release-repo.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
UPSTREAM_SHA = "a2ad4209c819bd7f416a4938a4990513ac667d6af9610803d2344f77113ab7c0"
INPUTS = ("scripts/patch-i3lock-visuals.py", "packages/i3lock/ooonana_lock_visuals.h")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(base, binary, out):
    base, binary, out = (path.resolve(strict=True) for path in (base, binary, out))
    if base == out or (out / "CURRENT").exists() or "generations" in out.parts:
        raise ValueError("Separate unpublished output required")
    package = release.metadata(base / "i3lock.pkg")
    if (package["VERSION"], package.get("BASE"), package.get("SHA256")) != ("2.16-r0", "alpine-v3.24", UPSTREAM_SHA):
        raise ValueError("Pinned vendor locker changed; review before repackaging")
    archive = release.safe_file(base, package["ARCHIVE"])
    if sha(archive) != UPSTREAM_SHA:
        raise ValueError("Vendor locker checksum mismatch")
    manifest = json.loads((binary.parent / "build-manifest.json").read_text())
    release.validate_lock_manifest(manifest, binary.read_bytes())
    elf = subprocess.check_output(["readelf", "-lW", str(binary)], text=True)
    if "Requesting program interpreter: /lib/ld-musl-x86_64.so.1" not in elf:
        raise ValueError("Expected native x86_64 musl locker")
    version = "2.16-r0.ooonana1"
    relative = f"archives/i3lock-{version}.tar.gz"
    target = out / relative
    if target.exists() or target.is_symlink() or (out / "i3lock.pkg").exists():
        raise ValueError("Refusing existing package output")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".i3lock-", dir=target.parent)
    try:
        count = 0
        with os.fdopen(descriptor, "wb") as stream, gzip.GzipFile(fileobj=stream, mode="wb", mtime=0, filename="") as compressed, \
                tarfile.open(fileobj=compressed, mode="w") as destination, tarfile.open(archive) as source:
            for member in source:
                name = PurePosixPath(member.name.removeprefix("./"))
                if name.is_absolute() or ".." in name.parts:
                    raise ValueError("Unsafe vendor archive path")
                item = copy.copy(member)
                item.uid = item.gid = item.mtime = 0
                item.uname = item.gname = "root"
                if name.as_posix() == "usr/bin/i3lock":
                    if not item.isfile():
                        raise ValueError("Vendor locker must be regular file")
                    data = binary.read_bytes()
                    item.size, item.mode = len(data), 0o755
                    destination.addfile(item, io.BytesIO(data))
                    count += 1
                else:
                    destination.addfile(item, source.extractfile(member) if member.isfile() else None)
            if count != 1:
                raise ValueError("Expected exactly one vendor locker")
            for name, data in (
                    ("build-manifest.json", json.dumps(manifest, sort_keys=True, indent=2).encode() + b"\n"),
                    ("source-pins.json", (ROOT / "packages/i3lock/source-pins.json").read_bytes()),
                    ("patch-i3lock-visuals.py", (ROOT / INPUTS[0]).read_bytes()),
                    ("ooonana_lock_visuals.h", (ROOT / INPUTS[1]).read_bytes())):
                item = tarfile.TarInfo("usr/share/doc/i3lock/ooonana-visuals/" + name)
                item.mode, item.size = 0o644, len(data)
                destination.addfile(item, io.BytesIO(data))
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    package.update(VERSION=version, SHA256=sha(target), ARCHIVE=relative,
                   COMPONENTS="apk-import alpine x86_64 native-lock-visuals-v1",
                   NOTES="Pinned i3lock 2.16; opt-in compact clock/feedback; vendor PAM authentication retained")
    (out / "i3lock.pkg").write_text("".join(f"OOONANA_PKG_{key}={json.dumps(value)}\n" for key, value in package.items()))
    release.validate_native_lock(out, package)
    print("LOCK_PACKAGE_OK", version, package["SHA256"], "; unpublished; integration/auth gates still required")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    build(args.base, args.binary, args.out_dir)
