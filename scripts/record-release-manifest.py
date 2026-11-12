#!/usr/bin/env python3
"""Source-only release inputs; no generated caches, secrets or host paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

SOURCE_PATHS = ("scripts", "configs", "branding", "packages", ".gitlab-ci.yml",
                ".github/workflows", ".gitattributes", ".gitignore")


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root)


def generated(path):
    return (any(part in {"__pycache__", "node_modules", ".venv"}
                or part.endswith(".egg-info") for part in path.parts)
            or path.suffix in {".pyc", ".pyo", ".log"})


def source_state(root):
    tracked = set(git(root, "ls-files", "-z", "--", *SOURCE_PATHS).split(b"\0"))
    new = set(git(root, "ls-files", "--others", "--exclude-standard", "-z", "--", *SOURCE_PATHS).split(b"\0"))
    digest = hashlib.sha256()
    count = 0
    for name in sorted(tracked | new):
        if not name:
            continue
        relative = Path(os.fsdecode(name))
        if generated(relative):
            continue
        path = root / relative
        if not path.is_file() and not path.is_symlink():
            continue
        # Never follow source links into unrelated user data.
        data = os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
        digest.update(relative.as_posix().encode())
        digest.update(hashlib.sha256(data).digest())
        count += 1
    changed = bool(git(root, "diff", "HEAD", "--name-only", "--", *SOURCE_PATHS).strip())
    dirty = changed or any(name and not generated(Path(os.fsdecode(name))) for name in new)
    return digest.hexdigest(), count, dirty


def build_manifest(root, repo):
    packages = {}
    bases = set()
    unknown_base = False
    for path in repo.glob("*.pkg"):
        version = re.search(r'^OOONANA_PKG_VERSION="([^"]+)"', path.read_text(), re.MULTILINE)
        if version:
            packages[path.stem] = version.group(1)
        text = path.read_text()
        if re.search(r'^OOONANA_PKG_KIND="apk"$', text, re.MULTILINE):
            base = re.search(r'^OOONANA_PKG_BASE="(alpine-v[0-9]+\.[0-9]+)"$', text, re.MULTILINE)
            if base:
                bases.add(base.group(1))
            else:
                unknown_base = True
    if len(bases) > 1:
        raise ValueError("Mixed userland branches cannot be released")
    userland_base = "unverified" if unknown_base else next(iter(bases), "none")
    digest, count, dirty = source_state(root)
    return {"format": 2, "revision": git(root, "rev-parse", "HEAD").decode().strip(),
            "dirty": dirty, "source_digest": digest, "source_files": count,
            "source_inputs": "git-tracked plus nonignored source files; generated caches excluded",
            "source_date_epoch": int(os.environ.get("SOURCE_DATE_EPOCH", "0")),
            "packages": dict(sorted(packages.items())), "architecture": "x86_64",
            "models_bundled": False, "userland_base": userland_base}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    args = parser.parse_args()
    manifest = build_manifest(Path(__file__).resolve().parents[1], args.repo)
    (args.repo / "BUILD-MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
