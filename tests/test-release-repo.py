#!/usr/bin/env python3
"""Regression gate: stale bundles, missing closure, tampered metadata/index."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gate", root / "scripts/check-release-repo.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
with tempfile.TemporaryDirectory() as temporary:
    repo = Path(temporary) / "repo"
    repo.mkdir()
    profile = Path(temporary) / "profile"
    profile.write_text("openssl\n")
    def package(name, deps="", version="1.0"):
        (repo / f"{name}.pkg").write_text(
            f'OOONANA_PKG_ID="{name}"\nOOONANA_PKG_VERSION="{version}"\n'
            f'OOONANA_PKG_KIND="bundle"\nOOONANA_PKG_SUMMARY="Fixture"\nOOONANA_PKG_DEPS="{deps}"\n')
    for name in ("base", "branding", "openssl", "openvino-chat"):
        package(name)
    package("i3", "openssl")
    package("full-i3", "base branding i3 openvino-chat")
    package("ooonana-core", "ooonana-core-runtime")
    package("ooonana-core-runtime", "openssl", "0.9.8")
    def index():
        subprocess.run([sys.executable, str(root / "scripts/index-repo-fast.py"), "--repo", str(repo)], check=True, capture_output=True)
    def reject(needle, key=None):
        try:
            gate.validate(repo, profile, key=key, expected_core="0.9.8")
        except ValueError as error:
            assert needle in str(error), str(error)
        else:
            raise AssertionError("Invalid repository accepted")
    index()
    assert gate.validate(repo, profile, expected_core="0.9.8")[1] == 8
    reject("Trusted-key validation requires signed manifest",
           key=root / "packages/ooonana/etc/ooonana/trusted-keys/repository-20261002.pub")
    package("full-i3", "base branding")
    index()
    reject("Full-i3 install closure missing: i3")
    package("full-i3", "base i3 openvino-chat")
    index()
    reject("Full-i3 install closure missing: branding")
    package("full-i3", "base branding i3 openvino-chat")
    index()
    package("i3")
    index()
    reject("stale i3.pkg dependency bundle: openssl")
    package("i3", "openssl")
    package("openvino-chat", "missing-runtime")
    index()
    reject("Dependency closure missing: missing-runtime")
    package("openvino-chat")
    index()
    package("openssl", version="tampered")
    reject("Stale index/checksum entry")
    package("openssl")
    index()
    (repo / "index.tsv").write_text((repo / "index.tsv").read_text() + "\n")
    reject("Invalid/duplicate package index row")
    (repo / "CURRENT").write_text("../escape\n")
    reject("Invalid generation pointer")
print("ok release-repo: bundle/install closure, metadata/index, generation/signature guards")
