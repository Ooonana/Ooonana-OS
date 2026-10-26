#!/usr/bin/env python3
"""Source wrapper fallbacks in private PATH; never executes a browser/editor/shell UI."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
with tempfile.TemporaryDirectory(prefix="ooonana-launch-fallback-") as temporary:
    work = Path(temporary)
    log = work / "arguments.json"
    for name in ("ooonana-browser", "ooonana-files", "ooonana-editor"):
        script = builder.split(f'"$ROOTFS/usr/bin/{name}" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
        (work / name).write_text(script); (work / name).chmod(0o755)
    theme = work / "ooonana-theme-env"
    theme.write_text('#!/bin/sh\nif [ "${1:-}" = client-env ]; then exit 0; fi\nexec "$@"\n')
    theme.chmod(0o755)
    terminal = work / "xterm"
    terminal.write_text('#!/usr/bin/python3\nimport json,os,sys\nopen(os.environ["QA_ARGS"],"w").write(json.dumps(sys.argv[1:]))\n')
    terminal.chmod(0o755)
    env = {**os.environ, "PATH": str(work), "QA_ARGS": str(log), "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent/owned-qa"}
    for name, diagnostic in (("ooonana-browser", "chromium missing"), ("ooonana-files", "nemo missing"), ("ooonana-editor", "editor missing")):
        result = subprocess.run([str(work / name)], env=env, capture_output=True, text=True)
        assert result.returncode == 0, (name, result.stderr)
        args = json.loads(log.read_text())
        assert args[:3] == ["-e", "sh", "-lc"] and diagnostic in args[3], (name, args)
    (work / "vim").write_text('#!/bin/sh\nexit 0\n'); (work / "vim").chmod(0o755)
    target = str(work / 'notes ; never-execute.txt')
    result = subprocess.run([str(work / "ooonana-editor"), target], env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(log.read_text()) == ["-e", "vim", target], "Editor fallback must preserve literal filename argv"
print("LAUNCHER_FALLBACKS_OK browser/files/editor diagnostics and literal editor filename; no real app launched")
