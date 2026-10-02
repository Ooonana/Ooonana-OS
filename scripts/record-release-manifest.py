#!/usr/bin/env python3
"""Record build inputs and package versions without credentials or host paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--repo", required=True, type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
packages = {}
for path in args.repo.glob("*.pkg"):
    version = re.search(r'^OOONANA_PKG_VERSION="([^"]+)"', path.read_text(), re.MULTILINE)
    if version:
        packages[path.stem] = version.group(1)
inputs = hashlib.sha256()
for directory in (root / "scripts", root / "configs", root / "packages/ooonana", root / "packages/openvino-chat"):
    for path in sorted(directory.rglob("*")):
        if (path.is_file() and "__pycache__" not in path.parts
                and not any(part.endswith(".egg-info") for part in path.parts)
                and path.suffix not in (".pyc", ".pyo", ".log")):
            inputs.update(path.relative_to(root).as_posix().encode())
            inputs.update(hashlib.sha256(path.read_bytes()).digest())
revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True).stdout.strip()
dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True).stdout.strip())
manifest = {"format": 1, "revision": revision, "dirty": dirty, "source_digest": inputs.hexdigest(),
            "source_date_epoch": int(os.environ.get("SOURCE_DATE_EPOCH", "0")), "packages": dict(sorted(packages.items())),
            "architecture": "x86_64", "models_bundled": False}
(args.repo / "BUILD-MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
