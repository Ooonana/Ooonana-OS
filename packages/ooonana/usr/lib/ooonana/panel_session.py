"""Display-scoped panel supervisor; restart only subprocesses owned here."""
import fcntl
import hashlib
import os
from pathlib import Path
import select
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time

PANEL_COMMAND = ["polybar", "-c", "/etc/ooonana/polybar.ini", "ooonana"]
DOCK_COMMAND = [*PANEL_COMMAND[:-1], "ooonana-dock"]
GEOMETRY_KEYS = {
    "OOONANA_DOCK_WIDTH", "OOONANA_DOCK_OFFSET", "OOONANA_PANEL_LEFT",
    "OOONANA_PANEL_RIGHT", "OOONANA_PANEL_GAP", "OOONANA_MEDIA_MAX_CHARS",
}


def geometry_environment():
    environment = dict(os.environ)
    for option in ("--dock-geometry", "--panel-geometry"):
        try:
            output = subprocess.check_output(["ooonana-window-list", option], text=True, timeout=3)
            for assignment in shlex.split(output):
                key, separator, value = assignment.partition("=")
                if separator and key in GEOMETRY_KEYS:
                    environment[key] = value
        except (OSError, ValueError, subprocess.SubprocessError):
            pass  # Polybar's bounded defaults remain available.
    return environment


def stop_child(child):
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=3)


def native_dock_available():
    if not shutil.which("ooonana-dock"):
        return False
    try:
        return subprocess.run([sys.executable, "-c", "import gi, cairo"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=3, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def main():
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))) / "ooonana"
    runtime.mkdir(parents=True, exist_ok=True)
    display = hashlib.sha256(os.environ.get("DISPLAY", "default").encode()).hexdigest()[:16]
    endpoint = runtime / f"panel-{display}.sock"
    panel_only = "--panel-only" in sys.argv[1:]
    with (runtime / f"panel-{display}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Startup may still be binding its socket. Never trust a saved PID.
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
                deadline = time.monotonic() + 3
                while True:
                    try:
                        client.sendto(b"panel" if panel_only else b"all", str(endpoint))
                        return 0
                    except (FileNotFoundError, ConnectionRefusedError):
                        if time.monotonic() >= deadline:
                            return 1
                        time.sleep(0.05)
        panel = dock = None
        running = True

        def stopped(_signal, _frame):
            nonlocal running
            running = False

        def restart(include_dock):
            nonlocal panel, dock
            environment = geometry_environment()
            stop_child(panel)
            panel = subprocess.Popen(PANEL_COMMAND, env=environment)
            if dock is not None and not native:
                stop_child(dock)
                dock = None
            if include_dock and (dock is None or dock.poll() is not None):
                dock = subprocess.Popen(["ooonana-dock"] if native else DOCK_COMMAND, env=environment)

        native = native_dock_available()
        signal.signal(signal.SIGTERM, stopped)
        signal.signal(signal.SIGINT, stopped)
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
            # Only this lock holder owns the socket and its child handles.
            endpoint.unlink(missing_ok=True)
            try:
                server.bind(str(endpoint))
                endpoint.chmod(0o600)
                restart(not panel_only)
                while running:
                    if select.select([server], [], [], 0.5)[0]:
                        request = server.recv(16)
                        if request in (b"panel", b"all"):
                            restart(request == b"all" or dock is not None)
                    if panel.poll() is not None:
                        return panel.returncode or 1
            finally:
                stop_child(dock)
                stop_child(panel)
                endpoint.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
