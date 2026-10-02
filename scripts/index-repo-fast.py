#!/usr/bin/env python3
"""Index literal factory metadata without executing it; native Windows/WSL fast path."""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import tempfile


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def index(repo, key=None, openssl="openssl"):
    repo = repo.resolve()
    if (repo / "CURRENT").exists():
        raise ValueError("Published generations immutable; index staging only")
    rows, sums = [], {}
    for path in sorted(repo.glob("*.pkg")):
        values = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"OOONANA_PKG_([A-Z0-9_]+)=(.*)", line)
            if not match:
                raise ValueError(f"Only literal factory metadata supported: {path.name}")
            tokens = shlex.split(match[2], comments=True)
            if len(tokens) != 1 or "$" in match[2] or "`" in match[2]:
                raise ValueError(f"Dynamic metadata requires shell indexer: {path.name}")
            values[match[1]] = tokens[0]
        ident = values.get("ID", "")
        if not re.fullmatch(r"[A-Za-z0-9_.+-]+", ident) or ident != path.stem or not values.get("VERSION") or not values.get("SUMMARY"):
            raise ValueError(f"Invalid metadata: {path.name}")
        digest = checksum(path)
        sums[path.name] = digest
        archive = values.get("ARCHIVE", "")
        if archive:
            relative = PurePosixPath(archive)
            target = repo / archive
            if relative.is_absolute() or ".." in relative.parts or not target.resolve().is_relative_to(repo):
                raise ValueError(f"Unsafe archive: {archive}")
            digest_archive = sums.get(archive) or checksum(target)
            if values.get("SHA256") and digest_archive != values["SHA256"]:
                raise ValueError(f"Archive checksum mismatch: {ident}")
            sums[archive] = digest_archive
        row = (ident, values["VERSION"], values.get("KIND", "bundle"), values["SUMMARY"], values.get("DEPS") or "-", archive or "-", digest)
        if any(any(char in field for char in "\t\r\n") for field in row):
            raise ValueError(f"Invalid index field: {ident}")
        rows.append("\t".join(row))
    content = ("\n".join(sorted(set(rows))) + "\n").encode()
    sums["index.tsv"] = hashlib.sha256(content).hexdigest()
    for path in (repo / "hooks").glob("*"):
        if path.is_file():
            sums[path.relative_to(repo).as_posix()] = checksum(path)
    if (repo / "BUILD-MANIFEST.json").is_file():
        sums["BUILD-MANIFEST.json"] = checksum(repo / "BUILD-MANIFEST.json")
    outputs = {"index.tsv": content, "SHA256SUMS": ("\n".join(sorted(f"{digest}  {name}" for name, digest in sums.items())) + "\n").encode()}
    staged = {}
    try:
        for name, data in outputs.items():
            descriptor, temporary = tempfile.mkstemp(prefix=f".{name}.", dir=repo)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            staged[name] = Path(temporary)
        if key:
            for name in ("SHA256SUMS.sig", "repo.pub"):
                descriptor, temporary = tempfile.mkstemp(prefix=f".{name}.", dir=repo)
                os.close(descriptor)
                staged[name] = Path(temporary)
            subprocess.run([openssl, "dgst", "-sha256", "-sign", str(key), "-out", str(staged["SHA256SUMS.sig"]), str(staged["SHA256SUMS"])], check=True)
            subprocess.run([openssl, "pkey", "-in", str(key), "-pubout", "-out", str(staged["repo.pub"])], check=True)
        elif (repo / "SHA256SUMS.sig").exists():
            raise ValueError("Signed staging repo requires signing key for reindex")
        for name, temporary in staged.items():
            os.replace(temporary, repo / name)
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--sign-key", type=Path)
    parser.add_argument("--openssl", default="openssl")
    args = parser.parse_args()
    print(f"Indexed {index(args.repo, args.sign_key, args.openssl)} packages")
