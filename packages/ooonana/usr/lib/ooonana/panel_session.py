"""Display-scoped panel supervisor; restart only subprocesses owned here."""
import fcntl
from collections import deque
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

sys.path.insert(0, str(Path(__file__).parent / "ui"))
from ui_preferences import DEFAULT_THEME, config_path, resolved_theme
from theme_watch import AppearanceWatch

PANEL_COMMAND = ["polybar", "-c", "/etc/ooonana/polybar.ini", "ooonana"]
DOCK_COMMAND = [*PANEL_COMMAND[:-1], "ooonana-dock"]
GEOMETRY_KEYS = {
    "OOONANA_DOCK_WIDTH", "OOONANA_DOCK_OFFSET", "OOONANA_PANEL_LEFT",
    "OOONANA_PANEL_RIGHT", "OOONANA_PANEL_GAP", "OOONANA_MEDIA_MAX_CHARS",
    "OOONANA_WIFI_MAX_CHARS",
}


def palette_environment(composited=False):
    # Owned roles only. Never reuse stale automatic session color exports.
    roles = ("BACKGROUND", "FOREGROUND", "ACCENT", "MUTED", "URGENT", "COOL", "BORDER")
    theme = resolved_theme() or DEFAULT_THEME
    if theme == "glass":
        values = ("#a40d1015" if composited else "#282e40", "#f6f7fb", "#ffe9c4",
                  "#e9edf4", "#442a39", "#e8f2ff", "#b8e8edf6" if composited else "#6e7993")
    elif theme == "light":
        values = ("#ffffff", "#1b1f26", "#805600", "#55616e", "#fae9e7", "#0065a8", "#adb7c2")
    else:
        values = ("#1b1f26", "#f5f5f7", "#ffb21a", "#b4bdc8", "#3b2324", "#9ec3ff", "#46505c")
    environment = {"OOONANA_BAR_" + role: value for role, value in zip(roles, values)}
    active = theme == "glass" and composited
    environment.update(
        OOONANA_PANEL_WINDOW="ooonana-glass-panel" if active else "polybar-ooonana",
        OOONANA_DOCK_WINDOW="ooonana-glass-dock" if active else "polybar-ooonana-dock",
    )
    return environment


def compositor_screen():
    try:
        import gi
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk
        if Gdk.init_check([])[0]:
            screen = Gdk.Screen.get_default()
            if screen and screen.get_rgba_visual():
                return screen
    except (ImportError, ValueError):
        pass
    return None


def watch_appearance(changed):
    try:
        from gi.repository import Gio, GLib
    except ImportError:
        return None, None  # Minimal fallback retains explicit panel reload.
    watch = AppearanceWatch(Gio, GLib, (config_path().with_name("theme"), Path("/etc/ooonana/theme")),
                            lambda: resolved_theme() or DEFAULT_THEME, changed)
    return watch, GLib.MainContext.default()


def geometry_environment(composited=False):
    environment = dict(os.environ)
    environment.update(palette_environment(composited))
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
        appearance_watch = context = None
        screen = compositor_screen()
        compositor_handler = None
        running = True
        failures = {"panel": deque(), "dock": deque()}
        cooling = set()

        def allow_recovery(name):
            now = time.monotonic()
            recent = failures[name]
            while recent and now - recent[0] >= 30:
                recent.popleft()
            if len(recent) >= 3:
                if name not in cooling:
                    print(f"ooonana panel: {name} keeps exiting; cooling retries, keeping healthy sibling", file=sys.stderr)
                    cooling.add(name)
                return False
            cooling.discard(name)
            recent.append(now)
            return True

        def stopped(_signal, _frame):
            nonlocal running
            running = False

        def panel_environment():
            return geometry_environment(bool(screen and screen.is_composited()))

        def restart(include_dock):
            nonlocal panel, dock
            environment = panel_environment()
            stop_child(panel)
            panel = subprocess.Popen(PANEL_COMMAND, env=environment)
            if dock is not None and not native:
                stop_child(dock)
                dock = None
            if include_dock and (dock is None or dock.poll() is not None):
                dock = subprocess.Popen(["ooonana-dock"] if native else DOCK_COMMAND, env=environment)

        def appearance_changed():
            if not running:
                return
            try:
                restart(dock is not None)
            except OSError as error:
                print(f"ooonana panel: appearance refresh failed: {error}", file=sys.stderr)

        native = native_dock_available()
        signal.signal(signal.SIGTERM, stopped)
        signal.signal(signal.SIGINT, stopped)
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
            # Only this lock holder owns the socket and its child handles.
            endpoint.unlink(missing_ok=True)
            try:
                server.bind(str(endpoint))
                endpoint.chmod(0o600)
                appearance_watch, context = watch_appearance(appearance_changed)
                if screen:
                    compositor_handler = screen.connect(
                        "composited-changed",
                        lambda *_: appearance_changed() if (resolved_theme() or DEFAULT_THEME) == "glass" else None,
                    )
                restart(not panel_only)
                while running:
                    if select.select([server], [], [], 0.5)[0]:
                        request = server.recv(16)
                        if request in (b"panel", b"all"):
                            restart(request == b"all" or dock is not None)
                    if context is not None:
                        for _ in range(8):  # Bound event bursts; keep IPC/recovery responsive.
                            if not context.pending():
                                break
                            context.iteration(False)
                    if not running:
                        break
                    if panel.poll() is not None:
                        if allow_recovery("panel"):
                            try:
                                panel = subprocess.Popen(PANEL_COMMAND, env=panel_environment())
                            except OSError as error:
                                print(f"ooonana panel: panel recovery failed: {error}", file=sys.stderr)
                    if dock is not None and dock.poll() is not None:
                        if allow_recovery("dock"):
                            try:
                                dock = subprocess.Popen(["ooonana-dock"] if native else DOCK_COMMAND,
                                                        env=panel_environment())
                            except OSError as error:
                                print(f"ooonana panel: dock recovery failed: {error}", file=sys.stderr)
            finally:
                if compositor_handler is not None:
                    screen.disconnect(compositor_handler)
                if appearance_watch is not None:
                    appearance_watch.close()
                stop_child(dock)
                stop_child(panel)
                endpoint.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
