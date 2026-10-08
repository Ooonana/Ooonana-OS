#!/usr/bin/env python3
"""Guarded source sync: disposable target and CLI only, no installed WSL mutation."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/update-installed-wsl.sh"

with tempfile.TemporaryDirectory(prefix="ooonana-wsl-update-") as temporary:
    work = Path(temporary)
    target, repo = work / "root", work / "repo"
    state = target / "var/lib/ooonana/packages"
    for folder in (target / "etc/i3", target / "usr/bin", state / "installed", repo / "archives", work / "tmp"):
        folder.mkdir(parents=True)
    (target / "etc/os-release").write_text('ID=ooonana\n')
    custom = target / "etc/i3/config"
    custom.write_bytes(b"# custom user configuration\n")
    log = work / "calls.jsonl"
    cli = target / "usr/bin/ooonana"
    cli.write_text(f"#!{sys.executable}\n" + '''
import json,os,sys
from pathlib import Path
record=dict(args=sys.argv[1:], signed=os.environ.get("OOONANA_REQUIRE_SIGNED_REPOS"),
            backups=os.environ.get("OOONANA_KEEP_UPDATE_BACKUPS"),
            repo=os.environ["OOONANA_REPO_DIR"],
            sources=list(Path(os.environ["OOONANA_SOURCES_DIR"]).iterdir()))
with open(os.environ["FIXTURE_LOG"],"a") as stream: stream.write(json.dumps(record)+"\\n")
if os.environ.get("FIXTURE_FAIL") and "--dry-run" not in sys.argv: raise SystemExit(17)
''')
    cli.chmod(0o755)
    env = {**os.environ, "OOONANA_ROOT": str(target), "WSL_DISTRO_NAME": "Ooonana",
           "FIXTURE_LOG": str(log), "TMPDIR": str(work / "tmp"), "OOONANA_REQUIRE_SIGNED_REPOS": "1"}
    for key in ("OOONANA_STATE_DIR", "OOONANA_PERSONAL_CURSOR_DIR", "OOONANA_KEEP_UPDATE_BACKUPS"):
        env.pop(key, None)

    def package(name, version="0.9.9", archive=True):
        relative = f"archives/{name}.tar.gz" if archive else ""
        digest = ""
        if archive:
            payload = repo / relative
            payload.write_bytes(b"disposable archive fixture")
            digest = hashlib.sha256(payload.read_bytes()).hexdigest()
        text = (f'OOONANA_PKG_VERSION="{version}"\nOOONANA_PKG_ARCHIVE="{relative}"\n'
                f'OOONANA_PKG_SHA256="{digest}"\n')
        (repo / f"{name}.pkg").write_text(text)
        (state / "installed" / f"{name}.pkg").write_text(text)

    package("ooonana-core-runtime")
    package("ooonana-core", archive=False)
    hooks = repo / "hooks"
    hooks.mkdir()
    for name in ("ooonana-core-runtime", "ooonana-core"):
        hook = hooks / f"{name}.healthcheck"
        hook.write_text("#!/bin/sh\nexit 0\n")
        hook.chmod(0o755)

    def run(*args, expected=0, **overrides):
        log.unlink(missing_ok=True)
        result = subprocess.run(["sh", str(SCRIPT), *args], env={**env, **overrides},
                                capture_output=True, text=True, timeout=8)
        assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
        assert custom.read_bytes() == b"# custom user configuration\n"
        assert not list((work / "tmp").iterdir()), "Private scratch directory leaked"
        return [json.loads(row) for row in log.read_text().splitlines()] if log.exists() else []

    assert not run(expected=2)  # Raw source overlay is retired.
    assert not run("--repo", str(repo), WSL_DISTRO_NAME="Ubuntu", expected=2)
    (target / "etc/os-release").write_text('ID=ubuntu\n')
    assert not run("--repo", str(repo), expected=2)
    (target / "etc/os-release").write_text('ID=ooonana\n')
    core_hook = hooks / "ooonana-core.healthcheck"
    saved_hook = core_hook.read_bytes()
    core_hook.unlink()
    assert not run("--repo", str(repo), expected=2)
    core_hook.write_bytes(saved_hook)
    core_hook.chmod(0o644)
    assert not run("--repo", str(repo), expected=2)
    core_hook.chmod(0o755)
    rows = run("--repo", str(repo), "--dry-run")
    assert [row["args"] for row in rows] == [["reinstall", "ooonana-core-runtime", "ooonana-core", "--dry-run"]]
    rows = run("--repo", str(repo))
    assert len(rows) == 4 and rows[1]["args"] == ["reinstall", "ooonana-core-runtime", "ooonana-core"]
    assert all(row["signed"] == "1" and row["backups"] == "all" and not row["sources"] for row in rows)

    payload = repo / "archives/ooonana-core-runtime.tar.gz"
    payload.write_bytes(b"bad archive")
    assert not run("--repo", str(repo), expected=2)
    package("ooonana-core-runtime")
    (repo / "ooonana-core-runtime.pkg").write_text((repo / "ooonana-core-runtime.pkg").read_text().replace('"0.9.9"', '"0.10.0"'))
    assert not run("--repo", str(repo), expected=2)
    package("ooonana-core-runtime")
    assert not run("--repo", str(repo), OOONANA_PERSONAL_CURSOR_DIR="unreviewed cursor", expected=2)
    (state / "installed/openvino-chat.pkg").write_text('OOONANA_PKG_VERSION="0.2.1"\n')
    assert not run("--repo", str(repo), expected=2)
    package("openvino-chat", "0.2.1")
    rows = run("--repo", str(repo))
    assert len(rows) == 5 and "openvino-chat" in rows[1]["args"]
    rows = run("--repo", str(repo), FIXTURE_FAIL="1", expected=17)
    assert len(rows) == 2 and not any(row["args"][0] == "verify" for row in rows)
    (repo / "current").write_text("../escape\n")
    assert not run("--repo", str(repo), expected=2)
    (repo / "current").unlink()
    generation = repo / "generations" / ("a" * 64)
    generation.mkdir(parents=True)
    for item in list(repo.iterdir()):
        if item.name != "generations":
            shutil.move(str(item), generation / item.name)
    (repo / "CURRENT").write_text("a" * 64 + "\n")
    assert not run("--repo", str(repo), expected=2)
    (generation / "index.tsv").write_text("fixture index\n")
    (generation / "SHA256SUMS").write_text("fixture sums\n")
    rows = run("--repo", str(repo))
    assert len(rows) == 5 and all(row["repo"] == str(generation) for row in rows)

print("ok installed-wsl-update: no raw overlays, version/archive/hook guards, pinned generation, config/trust retention, native transactions")
