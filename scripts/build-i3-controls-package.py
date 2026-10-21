#!/usr/bin/env python3
"""Repack verified i3 4.24 payload with locally built opt-in native controls."""
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
spec = importlib.util.spec_from_file_location("release_repo", ROOT / "scripts/check-release-repo.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(base, binary, out):
    base, binary, out = map(lambda p: p.resolve(strict=True), (base, binary, out))
    if (out / "CURRENT").exists() or "generations" in out.parts or base == out:
        raise ValueError("Separate unpublished output required")
    package = release.metadata(base / "i3wm.pkg")
    if (package["VERSION"], package.get("BASE"), package.get("SHA256")) != (
            "4.24-r0", "alpine-v3.24", "852c0e3f6e47cac9e73ab17bcdc4a8c135550945c430a0710652afbde4aa2e86"):
        raise ValueError("Pinned upstream i3wm payload changed; review before repackaging")
    archive = release.safe_file(base, package["ARCHIVE"])
    if sha(archive) != package["SHA256"]:
        raise ValueError("Upstream payload checksum mismatch")
    manifest = json.loads((binary.parent / "build-manifest.json").read_text())
    pins = json.loads((ROOT / "packages/i3wm/source-pins.json").read_text())
    if manifest.get("source") != pins or manifest.get("control_api") != 1 or manifest.get("binary_sha256") != sha(binary):
        raise ValueError("Build provenance/binary mismatch")
    for name in ("scripts/patch-i3-controls.py", "packages/i3wm/ooonana_controls.h"):
        if manifest.get("inputs", {}).get(name) != sha(ROOT / name):
            raise ValueError("Build inputs changed; rebuild candidate")
    elf = subprocess.check_output(["readelf", "-lW", str(binary)], text=True)
    if "Requesting program interpreter: /lib/ld-musl-x86_64.so.1" not in elf:
        raise ValueError("Expected native x86_64 musl binary")
    version = "4.24-r0.ooonana1"
    relative = f"archives/i3wm-{version}.tar.gz"
    target = out / relative
    if target.exists() or target.is_symlink() or (out / "i3wm.pkg").exists():
        raise ValueError("Refusing existing package output")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".i3wm-", dir=target.parent)
    try:
        count = 0
        with os.fdopen(fd, "wb") as stream, gzip.GzipFile(fileobj=stream, mode="wb", mtime=0, filename="") as compressed, \
                tarfile.open(fileobj=compressed, mode="w") as destination, tarfile.open(archive) as source:
            for member in source:
                name = PurePosixPath(member.name.removeprefix("./"))
                if name.is_absolute() or ".." in name.parts:
                    raise ValueError("Unsafe upstream archive path")
                item = copy.copy(member)
                item.uid = item.gid = item.mtime = 0
                item.uname = item.gname = "root"
                if name.as_posix() == "usr/bin/i3":
                    if not item.isfile():
                        raise ValueError("Upstream i3 must be regular file")
                    data = binary.read_bytes()
                    item.size, item.mode = len(data), 0o755
                    destination.addfile(item, io.BytesIO(data))
                    count += 1
                else:
                    destination.addfile(item, source.extractfile(member) if member.isfile() else None)
            if count != 1:
                raise ValueError("Expected exactly one upstream i3 executable")
            for name, data in (
                    ("build-manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"),
                    ("source-pins.json", (ROOT / "packages/i3wm/source-pins.json").read_bytes()),
                    ("patch-i3-controls.py", (ROOT / "scripts/patch-i3-controls.py").read_bytes()),
                    ("ooonana_controls.h", (ROOT / "packages/i3wm/ooonana_controls.h").read_bytes())):
                item = tarfile.TarInfo("usr/share/doc/i3/ooonana-controls/" + name)
                item.mode, item.size = 0o644, len(data)
                destination.addfile(item, io.BytesIO(data))
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    package.update(VERSION=version, SHA256=sha(target), ARCHIVE=relative,
                   COMPONENTS="apk-import alpine x86_64 native-controls-v1",
                   NOTES="Pinned i3 4.24 payload; locally rebuilt opt-in native-sized titlebar controls")
    (out / "i3wm.pkg").write_text("".join(f"OOONANA_PKG_{key}={json.dumps(value)}\n" for key, value in package.items()))
    print("I3_CONTROLS_PACKAGE_OK", version, package["SHA256"], "; GUI/release gates still required")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    build(args.base, args.binary, args.out_dir)
