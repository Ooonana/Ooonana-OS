#!/usr/bin/env python3
"""Offline mode-only repair of pinned imported PAM; no authentication code change."""
import argparse
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release", ROOT / "scripts/check-release-repo.py")
release = importlib.util.module_from_spec(spec); spec.loader.exec_module(release)
UPSTREAM_SHA = "66b733a03aef6750f95fb1ad75d4060ef8ba63460a24c6bd13442df236071302"
HELPER = "usr/sbin/unix_chkpwd"


def build(base, out):
    base, out = base.resolve(strict=True), out.resolve(strict=True)
    if base == out or "generations" in out.parts or (out / "CURRENT").exists():
        raise ValueError("Separate unpublished output required")
    package = release.metadata(base / "linux-pam.pkg")
    if (package["VERSION"], package.get("BASE"), package.get("SHA256")) != ("1.7.1-r2", "alpine-v3.24", UPSTREAM_SHA):
        raise ValueError("Pinned imported PAM changed")
    archive = release.safe_file(base, package["ARCHIVE"])
    if hashlib.sha256(archive.read_bytes()).hexdigest() != UPSTREAM_SHA:
        raise ValueError("Imported PAM checksum differs")
    version = "1.7.1-r2.ooonana1"; relative = f"archives/linux-pam-{version}.tar.gz"
    target = out / relative
    if target.exists() or target.is_symlink() or (out / "linux-pam.pkg").exists():
        raise ValueError("Refusing existing package output")
    # Preflight complete archive before creating output. Ownership and every byte
    # remain vendor-imported; only known broken SGID-root mode becomes SUID-root.
    names = set(); helper_sha = None
    with tarfile.open(archive) as bundle:
        for item in bundle:
            name = PurePosixPath(item.name.removeprefix("./"))
            if name.is_absolute() or ".." in name.parts or str(name) in names:
                raise ValueError("Unsafe/duplicate PAM member")
            names.add(str(name))
            if str(name) == HELPER:
                if not item.isfile() or (item.uid, item.gid, item.mode) != (0, 0, 0o2755):
                    raise ValueError("Expected known root-owned SGID helper layout")
                helper_sha = hashlib.sha256(bundle.extractfile(item).read()).hexdigest()
    if helper_sha is None: raise ValueError("PAM password helper missing")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".pam-helper-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream, gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as compressed, \
                tarfile.open(fileobj=compressed, mode="w") as destination, tarfile.open(archive) as original:
            for member in original:
                item = copy.copy(member)
                if item.name.removeprefix("./") == HELPER: item.mode = 0o4755
                destination.addfile(item, original.extractfile(member) if member.isfile() else None)
            data = json.dumps({"upstream_sha256": UPSTREAM_SHA, "helper_sha256": helper_sha,
                "mode": "4755", "authentication_code_unchanged": True,
                "packager_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, sort_keys=True).encode() + b"\n"
            item = tarfile.TarInfo("usr/share/doc/linux-pam/ooonana-helper.json"); item.mode, item.size = 0o644, len(data)
            destination.addfile(item, io.BytesIO(data))
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    package.update(VERSION=version, ARCHIVE=relative, SHA256=hashlib.sha256(target.read_bytes()).hexdigest(),
                   COMPONENTS=package.get("COMPONENTS", "") + " pam-helper-root-v1",
                   NOTES="Pinned vendor PAM bytes/policy retained; normalized root-owned helper mode repaired")
    (out / "linux-pam.pkg").write_text("".join(f"OOONANA_PKG_{k}={json.dumps(v)}\n" for k, v in package.items()))
    print("PAM_HELPER_PACKAGE_OK", version, package["SHA256"], "; unpublished; vendor authentication unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(); build(args.base, args.out_dir)
