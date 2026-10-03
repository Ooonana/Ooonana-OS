#!/usr/bin/env python3
"""Read-only ISO repository gate. Never execute package metadata."""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
IDENTIFIER = re.compile(r"[A-Za-z0-9_.+-]+")


def metadata(path):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"OOONANA_PKG_([A-Z0-9_]+)=(.*)", line)
        if not match or "$" in match[2] or chr(96) in match[2]:
            raise ValueError(f"Nonliteral package metadata: {path.name}")
        tokens = shlex.split(match[2], comments=True)
        if len(tokens) != 1 or match[1] in values:
            raise ValueError(f"Invalid package metadata: {path.name}")
        values[match[1]] = tokens[0]
    if values.get("ID") != path.stem or not IDENTIFIER.fullmatch(path.stem):
        raise ValueError(f"Package ID mismatch: {path.name}")
    if not values.get("VERSION") or not values.get("SUMMARY"):
        raise ValueError(f"Incomplete package metadata: {path.name}")
    return values


def safe_file(repo, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError(f"Unsafe repository path: {relative}")
    target = repo / relative
    if not target.resolve().is_relative_to(repo.resolve()) or not target.is_file():
        raise ValueError(f"Repository file missing/outside root: {relative}")
    return target


def validate(repo, profile, key=None, expected_core=None):
    if (repo / "CURRENT").is_file():
        generation = (repo / "CURRENT").read_text().strip()
        if not re.fullmatch(r"[0-9a-f]{64}", generation):
            raise ValueError("Invalid generation pointer")
        repo = repo / "generations" / generation
    sums = {}
    for line in (repo / "SHA256SUMS").read_text().splitlines():
        digest, relative = line.split("  ", 1)
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or relative in sums:
            raise ValueError("Invalid checksum manifest")
        safe_file(repo, relative)
        sums[relative] = digest
    signature = repo / "SHA256SUMS.sig"
    if signature.is_file():
        if key is None or not key.is_file():
            raise ValueError("Signed repository needs explicit trusted public key")
        subprocess.run([os.environ.get("OOONANA_OPENSSL", "openssl"), "dgst", "-sha256",
                        "-verify", str(key), "-signature", str(signature),
                        str(repo / "SHA256SUMS")], check=True, stdout=subprocess.DEVNULL)
    packages = {path.stem: metadata(path) for path in repo.glob("*.pkg")}
    index = {}
    for line in (repo / "index.tsv").read_text().splitlines():
        fields = line.split("\t")
        if len(fields) != 7 or fields[0] in index:
            raise ValueError("Invalid/duplicate package index row")
        index[fields[0]] = fields
    if set(index) != set(packages):
        raise ValueError("Package index/metadata inventory differs")
    for name, values in packages.items():
        row = index[name]
        digest = hashlib.sha256((repo / f"{name}.pkg").read_bytes()).hexdigest()
        wanted = [name, values["VERSION"], values.get("KIND", "bundle"), values["SUMMARY"],
                  values.get("DEPS") or "-", values.get("ARCHIVE") or "-", digest]
        if row != wanted or sums.get(f"{name}.pkg") != digest:
            raise ValueError(f"Stale index/checksum entry: {name}")
        archive = values.get("ARCHIVE")
        if archive:
            safe_file(repo, archive)
            if not values.get("SHA256") or sums.get(archive) != values["SHA256"]:
                raise ValueError(f"Archive checksum metadata differs: {name}")
    index_digest = hashlib.sha256((repo / "index.tsv").read_bytes()).hexdigest()
    if sums.get("index.tsv") != index_digest:
        raise ValueError("Index checksum mismatch")
    required = [line.split("#", 1)[0].strip() for line in profile.read_text().splitlines()]
    required = [name for name in required if name]
    for name in ("base", "branding", "i3", "full-i3", "ooonana-core", "ooonana-core-runtime", "openvino-chat"):
        if name not in packages:
            raise ValueError(f"Full-i3 repository missing: {name}")
    bundled = set(packages["i3"].get("DEPS", "").split())
    for name in required:
        if name not in packages:
            raise ValueError(f"Profile package missing: {name}")
        if name not in {"base", "branding", "i3", "full-i3"} and name not in bundled:
            raise ValueError(f"stale i3.pkg dependency bundle: {name}; refresh metadata-only staging")
    if expected_core and packages["ooonana-core-runtime"]["VERSION"] != expected_core:
        raise ValueError("Cached core version differs from source")
    visited = set()
    def closure(name):
        if name in visited:
            return
        if name not in packages:
            raise ValueError(f"Dependency closure missing: {name}")
        visited.add(name)
        for dependency in packages[name].get("DEPS", "").split():
            if not IDENTIFIER.fullmatch(dependency):
                raise ValueError(f"Invalid dependency: {name}")
            closure(dependency)
    for target in ("full-i3", "ooonana-core", "openvino-chat"):
        closure(target)
    return repo, len(packages), len(visited)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--profile", type=Path, default=ROOT / "configs/packages/full-i3.list")
    parser.add_argument("--public-key", type=Path)
    parser.add_argument("--core-version")
    args = parser.parse_args()
    try:
        repo, count, closure_count = validate(args.repo, args.profile, args.public_key, args.core_version)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"FAIL: release repository: {error}\n")
    print(f"OOONANA_RELEASE_REPO_OK {count} packages; {closure_count} dependency nodes; {repo}")
