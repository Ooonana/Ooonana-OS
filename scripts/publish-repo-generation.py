#!/usr/bin/env python3
"""Publish a verified immutable repo snapshot; replace CURRENT only at completion."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile


@contextmanager
def publication_lock(path):
    with path.open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            lock.write(b"\0")
            lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def verify(source, public_key=None):
    source = source.resolve()
    if not (source / "index.tsv").is_file() or not (source / "SHA256SUMS").is_file():
        raise ValueError("Repository requires index.tsv and SHA256SUMS")
    entries = {}
    for line in (source / "SHA256SUMS").read_text().splitlines():
        checksum, relative = line.split("  ", 1)
        path = PurePosixPath(relative)
        if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum) or path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Invalid manifest entry: {relative}")
        target = source / relative
        if not target.resolve().is_relative_to(source) or not target.is_file() or digest(target) != checksum:
            raise ValueError(f"Checksum mismatch: {relative}")
        if relative in entries:
            raise ValueError(f"Duplicate manifest entry: {relative}")
        entries[relative] = checksum
    if entries.get("index.tsv") != digest(source / "index.tsv"):
        raise ValueError("Index must be covered by manifest")
    for line in (source / "index.tsv").read_text().splitlines():
        values = line.split("\t")
        if len(values) < 7 or not re.fullmatch(r"[A-Za-z0-9_.+-]+", values[0]) or entries.get(values[0] + ".pkg") != values[6]:
            raise ValueError("Index and package metadata disagree")
        if values[5] != "-" and values[5] not in entries:
            raise ValueError(f"Unlisted archive: {values[5]}")
    for hook in (source / "hooks").glob("*"):
        if hook.is_file() and hook.relative_to(source).as_posix() not in entries:
            raise ValueError(f"Unindexed hook: {hook.name}")
    signature = source / "SHA256SUMS.sig"
    if public_key and not signature.is_file():
        raise ValueError("Trusted-key publication requires signed manifest")
    if signature.exists():
        key = public_key or source / "repo.pub"
        if not key.is_file():
            raise ValueError("Signed repository requires public key")
        subprocess.run([os.environ.get("OOONANA_OPENSSL", "openssl"), "dgst", "-sha256", "-verify", str(key), "-signature", str(signature), str(source / "SHA256SUMS")], check=True, capture_output=True)
    return entries


def publish(source, target, public_key=None):
    source, target = source.resolve(), target.resolve()
    if target == source or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError("Source and publication tree must be separate")
    entries = verify(source, public_key)
    identity = hashlib.sha256(b"".join((source / name).read_bytes() if (source / name).is_file() else b"" for name in ("SHA256SUMS", "index.tsv", "SHA256SUMS.sig", "repo.pub"))).hexdigest()
    target.mkdir(parents=True, exist_ok=True)
    with publication_lock(target / ".publication.lock"):
        generations = target / "generations"
        generations.mkdir(exist_ok=True)
        previous = None
        previous_sums = {}
        if (target / "CURRENT").is_file():
            prior_id = (target / "CURRENT").read_text().strip()
            if re.fullmatch(r"[0-9a-f]{64}", prior_id):
                previous = generations / prior_id
                if (previous / "SHA256SUMS").is_file():
                    previous_sums = {relative: checksum for checksum, relative in (line.split("  ", 1) for line in (previous / "SHA256SUMS").read_text().splitlines())}
        final = generations / identity
        if not final.exists():
            stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=generations))
            try:
                # Only manifest-owned files and detached trust material enter
                # publication. Never copy unrelated files or private keys.
                for relative in set(entries) | {"SHA256SUMS", "SHA256SUMS.sig", "repo.pub"}:
                    original = source / relative
                    if original.is_file():
                        with original.open("rb") as stream:
                            prefix = stream.read(100)
                        if b"PRIVATE KEY" in prefix:
                            raise ValueError(f"Private key cannot be published: {relative}")
                        destination = stage / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shared = previous / relative if previous and relative.startswith("archives/") else None
                        if shared and shared.is_file() and shared.resolve().is_relative_to(previous.resolve()) and previous_sums.get(relative) == entries.get(relative):
                            try:
                                # Share only an immutable published archive,
                                # never mutable staging or legacy-root files.
                                os.link(shared, destination)
                            except OSError:
                                shutil.copy2(original, destination)
                        else:
                            shutil.copy2(original, destination)
                        destination.chmod(0o755 if relative.startswith("hooks/") else 0o644)
                verify(stage, public_key)
                stage.chmod(0o755)
                os.replace(stage, final)
            finally:
                if stage.exists():
                    if not stage.resolve().is_relative_to(generations.resolve()):
                        raise ValueError("Unsafe staging cleanup path")
                    shutil.rmtree(stage)
        else:
            verify(final, public_key)
        descriptor, temporary = tempfile.mkstemp(prefix=".CURRENT-", dir=target)
        try:
            with os.fdopen(descriptor, "w", newline="\n") as pointer:
                pointer.write(identity + "\n")
                pointer.flush()
                os.fsync(pointer.fileno())
            Path(temporary).chmod(0o644)
            os.replace(temporary, target / "CURRENT")
        finally:
            Path(temporary).unlink(missing_ok=True)
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--public-key", type=Path)
    arguments = parser.parse_args()
    print(publish(arguments.source, arguments.target, arguments.public_key))
