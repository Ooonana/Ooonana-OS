#!/usr/bin/env python3
"""Browser cache compatibility never disables sandbox or loses user flags/URL."""
import os
import ast
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
builder = (root / "scripts/build-full-i3-rootfs.sh").read_text()
helper = builder.split('"$ROOTFS/usr/bin/ooonana-browser" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
config = root / "packages/ooonana/etc/chromium/zz-ooonana.conf"
assert "--no-sandbox" not in helper + config.read_text()
assert "--disable-setuid-sandbox" not in helper + config.read_text()
assert "--disable-seccomp-filter-sandbox" not in helper + config.read_text()
assert "--password-store=basic" not in helper + config.read_text(), "Fixture password policy entered production"
assert "--disable-gpu" not in config.read_text().replace("--disable-gpu-shader-disk-cache", "")
assert 'etc/chromium/zz-ooonana.conf' in builder.split("install_current_backend_checks()", 1)[1]

with tempfile.TemporaryDirectory(prefix="ooonana-browser-") as temporary:
    work = Path(temporary)
    launcher, mock, trace = work / "browser", work / "chromium", work / "trace"
    launcher.write_text(helper)
    mock.write_text('''#!/bin/sh
printf '%s\\0' "$@" >>"$PROBE_TRACE"
printf '\\0' >>"$PROBE_TRACE"
if [ "${PROBE_FAIL_FIRST:-0}" = 1 ]; then
  for argument in "$@"; do [ "$argument" != --disable-gpu ] || exit 0; done
  exit 1
fi
''')
    mock.chmod(0o755)
    env = dict(os.environ, PATH=str(work) + ":" + os.environ["PATH"],
               OOONANA_BROWSER_DBUS="1", DBUS_SESSION_BUS_ADDRESS="invalid-fixture",
               XDG_STATE_HOME=str(work / "state"), PROBE_TRACE=str(trace))
    url = "https://example.invalid/?label=two words"
    for fallback in (False, True):
        trace.unlink(missing_ok=True)
        env["PROBE_FAIL_FIRST"] = str(int(fallback))
        subprocess.run(["sh", str(launcher), url], env=env, check=True)
        commands = [chunk.split(b"\0") for chunk in trace.read_bytes().split(b"\0\0") if chunk]
        assert len(commands) == (2 if fallback else 1), commands
        for command in commands:
            assert b"--disable-gpu-shader-disk-cache" in command and command[-1] == url.encode(), command
        assert b"--disable-gpu" not in commands[0], "Normal path disabled acceleration"
    result = subprocess.run(["sh", "-c", '. "$1"; printf "%s" "$CHROMIUM_FLAGS"', "sh", str(config)],
                            env=dict(env, CHROMIUM_FLAGS="--existing-option"), capture_output=True, text=True, check=True)
    assert result.stdout == "--existing-option --disable-gpu-shader-disk-cache"

    # Parse actual QA helpers without importing GTK or launching a browser.
    # Forked children must finish sandbox initialization before the assertion.
    module = ast.parse((root / "tests/check-third-party-frames.py").read_text())
    helpers = ast.Module(body=[node for node in module.body if isinstance(node, ast.FunctionDef)
                              and node.name in {"browser_sandboxes", "browser_process_diagnostics", "ready_browser_sandboxes"}],
                         type_ignores=[])
    proc = work / "proc"
    namespace = {"Path": lambda path: proc if path == "/proc" else Path(path)}
    exec(compile(helpers, "browser-sandbox-helpers", "exec"), namespace)
    for pid, kind in ((11, ""), (12, "renderer"), (13, "gpu-process")):
        directory = proc / str(pid)
        directory.mkdir(parents=True)
        directory.joinpath("status").write_text("Name:\tchromium\nPPid:\t11\nSeccomp:\t0\nNoNewPrivs:\t0\n")
        directory.joinpath("cmdline").write_bytes(b"chromium\0" + (f"--type={kind}\0".encode() if kind else b""))
    assert namespace["ready_browser_sandboxes"]() is None, "Uninitialized children accepted"
    for pid in (12, 13):
        proc.joinpath(str(pid), "status").write_text("Name:\tchromium\nPPid:\t11\nSeccomp:\t2\nNoNewPrivs:\t1\n")
    assert set(namespace["ready_browser_sandboxes"]()) == {"renderer", "gpu-process"}
    proc.joinpath("13/status").write_text("Name:\tchromium\nPPid:\t11\nSeccomp:\t2\nNoNewPrivs:\t0\n")
    assert namespace["ready_browser_sandboxes"]() is None, "Unlocked privilege state accepted"
    proc.joinpath("13/cmdline").write_bytes(b"chromium\0--type=utility\0")
    assert namespace["ready_browser_sandboxes"]() is None, "Missing GPU snapshot accepted"

print("ok browser-policy: sandbox retained, normal GPU path, software fallback, URL/user flags preserved")
