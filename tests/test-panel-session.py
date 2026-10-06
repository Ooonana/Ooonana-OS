#!/usr/bin/env python3
"""Disposable child processes only: panel reload and multi-display ownership."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR = ROOT / "packages/ooonana/usr/lib/ooonana/panel_session.py"


def wait(predicate, message, seconds=8):
    until = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < until, message
        time.sleep(0.03)


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        process.wait(timeout=8)


with tempfile.TemporaryDirectory(prefix="ooonana-panel-") as temporary:
    fixture = Path(temporary)
    binary = fixture / "bin"
    binary.mkdir()
    events = fixture / "events.jsonl"
    stub = binary / "polybar"
    stub.write_text(f"#!{sys.executable}\n" + '''
import json, os, signal, sys, time
def record(event):
    with open(os.environ["FIXTURE_EVENTS"], "a") as stream:
        stream.write(json.dumps(dict(event=event, pid=os.getpid(), display=os.environ["DISPLAY"],
                                    bar=sys.argv[-1], left=os.environ.get("OOONANA_PANEL_LEFT"))) + "\\n")
def stop(*_):
    record("stop")
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
record("start")
while True:
    time.sleep(0.1)
''')
    stub.chmod(0o755)
    geometry = binary / "ooonana-window-list"
    geometry.write_text(f"#!{sys.executable}\n" + '''
import sys
print("OOONANA_DOCK_WIDTH=524\\nOOONANA_DOCK_OFFSET=378" if sys.argv[-1] == "--dock-geometry"
      else "OOONANA_PANEL_LEFT='workspaces media'\\nOOONANA_PANEL_RIGHT='memory power'\\nOOONANA_PANEL_GAP=0\\nOOONANA_MEDIA_MAX_CHARS=10")
''')
    geometry.chmod(0o755)
    environment = {**os.environ, "PATH": str(binary), "FIXTURE_EVENTS": str(events),
                   "XDG_RUNTIME_DIR": str(fixture / "runtime")}
    # PATH excludes the real native dock; fallback exercises two owned bars.
    first_env = {**environment, "DISPLAY": ":qa-first"}
    second_env = {**environment, "DISPLAY": ":qa-second"}
    first = second = unrelated = None

    def records():
        if not events.exists():
            return []
        return [json.loads(line) for line in events.read_text().splitlines() if line]

    def started(display, bar):
        return [row for row in records() if row["event"] == "start" and row["display"] == display and row["bar"] == bar]

    try:
        unrelated = subprocess.Popen([str(stub), "unrelated"], env=first_env)
        first = subprocess.Popen([sys.executable, "-B", str(SUPERVISOR)], env=first_env)
        second = subprocess.Popen([sys.executable, "-B", str(SUPERVISOR)], env=second_env)
        wait(lambda: len(started(":qa-first", "ooonana-dock")) == 1 and len(started(":qa-second", "ooonana-dock")) == 1,
             "Initial display-scoped bars missing")
        subprocess.run([sys.executable, "-B", str(SUPERVISOR), "--panel-only"], env=first_env, check=True, timeout=5)
        wait(lambda: len(started(":qa-first", "ooonana-dock")) == 2, "Reload failed")
        assert unrelated.poll() is None
        assert len(started(":qa-second", "ooonana")) == 1
        assert len(started(":qa-second", "ooonana-dock")) == 1
        assert all(row["left"] == "workspaces media" for row in started(":qa-first", "ooonana"))
        first_starts = started(":qa-first", "ooonana") + started(":qa-first", "ooonana-dock")
        assert all(any(row["event"] == "stop" and row["pid"] == start["pid"] for row in records())
                   for start in first_starts[:1])
        stop(first)
        assert unrelated.poll() is None and second.poll() is None
        digest = hashlib.sha256(b":qa-first").hexdigest()[:16]
        endpoint = fixture / "runtime/ooonana" / f"panel-{digest}.sock"
        assert not endpoint.exists()
        stop(second)
        owned = [row for row in records() if row["event"] == "start" and row["bar"] != "unrelated"]
        stopped = {row["pid"] for row in records() if row["event"] == "stop"}
        assert all(row["pid"] in stopped for row in owned), (owned, stopped)
        # Stale endpoint has no PID authority; lock owner replaces only its socket.
        endpoint.write_text("stale socket fixture")
        first = subprocess.Popen([sys.executable, "-B", str(SUPERVISOR), "--panel-only"], env=first_env)
        wait(lambda: len(started(":qa-first", "ooonana")) == 3, "Stale socket recovery failed")
        assert len(started(":qa-first", "ooonana-dock")) == 2
        stop(first)
    finally:
        for process in (first, second, unrelated):
            stop(process)

    # Exercise actual control-lock main with inert GTK/Manager replacements.
    control_source = ROOT / "packages/ooonana/usr/lib/ooonana/ui/window_controls.py"
    lock_probe = '''
import ast, fcntl, hashlib, os, signal, sys
from pathlib import Path
from types import SimpleNamespace
source, proof = map(Path, sys.argv[1:])
function = next(node for node in ast.parse(source.read_text()).body if isinstance(node, ast.FunctionDef) and node.name == "main")
namespace = dict(fcntl=fcntl, hashlib=hashlib, os=os, Path=Path,
                 Manager=lambda: proof.write_text("ready"), Gtk=SimpleNamespace(main=signal.pause))
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
raise SystemExit(namespace["main"]())
'''
    first = second = None
    try:
        first = subprocess.Popen([sys.executable, "-B", "-c", lock_probe, str(control_source), str(fixture / "first")], env=first_env)
        second = subprocess.Popen([sys.executable, "-B", "-c", lock_probe, str(control_source), str(fixture / "second")], env=second_env)
        wait(lambda: (fixture / "first").exists() and (fixture / "second").exists(), "Controls blocked across displays")
        subprocess.run([sys.executable, "-B", "-c", lock_probe, str(control_source), str(fixture / "duplicate")], env=first_env, check=True, timeout=5)
        assert not (fixture / "duplicate").exists()
    finally:
        stop(first)
        stop(second)

    # Native GTK dock stays alive through both panel-only and i3 reloads.
    native_stub = binary / "ooonana-dock"
    native_stub.write_text(stub.read_text().replace("bar=sys.argv[-1]", 'bar="native-dock"'))
    native_stub.chmod(0o755)
    native_env = {**environment, "DISPLAY": ":qa-native"}
    native_runner = '''
import importlib.util, sys
spec = importlib.util.spec_from_file_location("panel_fixture", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.native_dock_available = lambda: True
sys.argv = [sys.argv[1]]
raise SystemExit(module.main())
'''
    first = None
    try:
        first = subprocess.Popen([sys.executable, "-B", "-c", native_runner, str(SUPERVISOR)], env=native_env)
        wait(lambda: len(started(":qa-native", "native-dock")) == 1, "Native dock missing")
        for index, arguments in enumerate((["--panel-only"], []), 2):
            subprocess.run([sys.executable, "-B", str(SUPERVISOR), *arguments], env=native_env, check=True, timeout=5)
            wait(lambda: len(started(":qa-native", "ooonana")) == index, "Native panel reload failed")
        assert len(started(":qa-native", "native-dock")) == 1
        stop(first)
        native_pid = started(":qa-native", "native-dock")[0]["pid"]
        assert any(row["event"] == "stop" and row["pid"] == native_pid for row in records())
    finally:
        stop(first)

    # Actual generated Wi-Fi status must not publish executable Polybar tags.
    builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
    status = builder.split('"$ROOTFS/usr/bin/ooonana-wifi-status" <<\'EOF\'\n', 1)[1].split('\nEOF', 1)[0]
    status = status.replace("PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n", "")
    status_script = fixture / "wifi-status"
    status_script.write_text(status)
    nmcli = binary / "nmcli"
    nmcli.write_text(f"#!{sys.executable}\n" + '''
import sys
print("enabled" if sys.argv[-1] == "radio" else "802-11-wireless:network%{F#ff0000}tag\\x01name")
''')
    nmcli.chmod(0o755)
    wifi_env = {**environment, "PATH": str(binary) + ":" + os.environ["PATH"]}
    wifi_env.pop("WSL_DISTRO_NAME", None)
    output = subprocess.check_output(["sh", str(status_script)], env=wifi_env, text=True, timeout=5)
    assert "%" not in output and "\x01" not in output and "network" in output, output

    # Track truncation must count Unicode characters, not slice UTF-8 bytes.
    mpc = binary / "mpc"
    title = "한글%노래🎵" * 10
    mpc.write_text(f"#!{sys.executable}\nimport sys\nprint('[playing]' if sys.argv[-1] == 'status' else {title!r})\n")
    mpc.chmod(0o755)
    output = subprocess.check_output(["sh", str(ROOT / "packages/ooonana/usr/bin/ooonana-media-status"), "--once"],
                                     env={**wifi_env, "OOONANA_MEDIA_MAX_CHARS": "14"}, text=True, timeout=5)
    assert output.partition(" ")[2].strip() == title.replace("%", "")[:14], output

print("ok panel session: reload scoped, unrelated bars preserved, children stopped, controls per display")
