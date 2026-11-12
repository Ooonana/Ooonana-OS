#!/usr/bin/env python3
"""Repack only pinned Qt X11 portal plugin; separate unpublished output required."""
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
release = importlib.util.module_from_spec(spec); spec.loader.exec_module(release)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def build(base, binary, source, out):
    base, binary, source, out = (path.resolve(strict=True) for path in (base, binary, source, out))
    if base == out or "generations" in out.parts or (out / "CURRENT").exists():
        raise ValueError("Separate unpublished output required")
    package = release.metadata(base / "qt6-qtbase-x11.pkg")
    if (package["VERSION"], package.get("BASE"), package.get("SHA256")) != ("6.11.1-r0", "alpine-v3.24", release.QT_UPSTREAM_SHA):
        raise ValueError("Pinned upstream Qt X11 package changed")
    archive = release.safe_file(base, package["ARCHIVE"])
    if sha(archive) != release.QT_UPSTREAM_SHA: raise ValueError("Upstream Qt archive checksum mismatch")
    manifest = json.loads((binary.parent / "build-manifest.json").read_text())
    data = binary.read_bytes(); release.validate_qt_manifest(manifest, data)
    dynamic = subprocess.check_output(["readelf", "-d", str(binary)], text=True)
    if "libQt6Gui.so.6" not in dynamic or "libQt6DBus.so.6" not in dynamic or "/opt/" in dynamic:
        raise ValueError("Qt plugin ABI/dependency or build-path mismatch")
    sources = {}
    for name, digest in manifest["source"]["files"].items():
        path = source / name
        if path.is_symlink() or sha(path) != digest: raise ValueError("Qt vendor source differs: " + name)
        sources[release.QT_DOC + "vendor/" + name] = path.read_bytes()
    for name in release.QT_INPUTS: sources[release.QT_DOC + name] = (ROOT / name).read_bytes()
    sources[release.QT_DOC + "source-pins.json"] = (ROOT / "packages/qt-portal/source-pins.json").read_bytes()
    sources[release.QT_DOC + "build-manifest.json"] = json.dumps(manifest, sort_keys=True, indent=2).encode() + b"\n"
    sources[release.QT_DOC + "package-provenance.json"] = json.dumps({
        "upstream_sha256": release.QT_UPSTREAM_SHA, "packager_sha256": sha(Path(__file__)),
        "unchanged_vendor_dialog": True, "unpublished": True}, sort_keys=True, indent=2).encode() + b"\n"
    version = "6.11.1-r0.ooonana1"
    relative = f"archives/qt6-qtbase-x11-{version}.tar.gz"
    target = out / relative
    if target.exists() or target.is_symlink() or (out / "qt6-qtbase-x11.pkg").exists():
        raise ValueError("Refusing existing package output")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".qt-portal-", dir=target.parent)
    try:
        count, names = 0, set()
        with os.fdopen(descriptor, "wb") as stream, gzip.GzipFile(fileobj=stream, mode="wb", mtime=0, filename="") as compressed, \
                tarfile.open(fileobj=compressed, mode="w") as destination, tarfile.open(archive) as original:
            for member in original:
                name = PurePosixPath(member.name.removeprefix("./"))
                if name.is_absolute() or ".." in name.parts or str(name) in names or str(name).startswith(release.QT_DOC):
                    raise ValueError("Unsafe/duplicate upstream Qt member")
                names.add(str(name)); item = copy.copy(member)
                item.uid = item.gid = item.mtime = 0; item.uname = item.gname = "root"
                if str(name) == release.QT_PLUGIN:
                    if not item.isfile() or hashlib.sha256(original.extractfile(member).read()).hexdigest() != manifest["source"]["original_plugin_sha256"]:
                        raise ValueError("Original Qt plugin differs")
                    item.size, item.mode = len(data), 0o755
                    destination.addfile(item, io.BytesIO(data)); count += 1
                else:
                    destination.addfile(item, original.extractfile(member) if item.isfile() else None)
            if count != 1: raise ValueError("Exactly one original Qt portal plugin required")
            for name, content in sources.items():
                item = tarfile.TarInfo(name); item.mode, item.size = 0o644, len(content)
                destination.addfile(item, io.BytesIO(content))
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    package.update(VERSION=version, SHA256=sha(target), ARCHIVE=relative,
                   COMPONENTS=package.get("COMPONENTS", "") + " native-portal-palette-v1",
                   NOTES="Pinned Qt6.11.1 X11 payload; one portal cache invalidation; vendor dialogs retained")
    (out / "qt6-qtbase-x11.pkg").write_text("".join(f"OOONANA_PKG_{key}={json.dumps(value)}\n" for key, value in package.items()))
    release.validate_native_qt(out, package)
    print("QT_PORTAL_PACKAGE_OK", version, package["SHA256"], "; unpublished; no release pointer changed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    build(args.base, args.binary, args.source, args.out_dir)
