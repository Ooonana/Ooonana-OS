#!/usr/bin/env python3
"""Actual idle/PAM lock, Settings persistence, and isolated login1 protocol QA."""
import ctypes as C
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana"))
from common import Gdk, Gtk, apply_theme
from settings_app import SettingsWindow
from session_control import IdleDisplay
from ui_preferences import load_preferences

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode
output = Path(sys.argv[1])
assert output == Path("/qa/session-control")
output.mkdir()
os.environ["XDG_CONFIG_HOME"] = str(output / "config")
config = output / "i3.conf"
config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                           if not line.startswith("exec")) + "\n")
wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", round(96 * 1024 * float(os.environ["OOONANA_GUI_TEXT_SCALE"])))
apply_theme()
window = display = provider = None
bus_pid = None


def settle():
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    time.sleep(.02)


def wait(predicate, detail, seconds=15):
    deadline = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < deadline, detail
        settle()


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=6)


def capture(name):
    for _ in range(10):
        settle()
    root = Gdk.get_default_root_window()
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(output / (name + ".png")), "png", [], [])


def grabbed():
    x = display.x
    x.XGrabKeyboard.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_int, C.c_int, C.c_ulong]
    x.XUngrabKeyboard.argtypes = [C.c_void_p, C.c_ulong]
    x.XSync.argtypes = [C.c_void_p, C.c_int]
    result = x.XGrabKeyboard(display.display, display.root, False, 1, 1, 0)
    if result == 0:
        x.XUngrabKeyboard(display.display, 0)
        x.XSync(display.display, False)
    return result == 1


def unlock():
    command("xdotool", "key", "ctrl+u")
    subprocess.run(["xdotool", "type", "--clearmodifiers", "--file", "-"],
        input="Ooonana-private-lock-QA-20261023", text=True, check=True)
    command("xdotool", "key", "Return")
    wait(lambda: not grabbed(), "Public disposable credential did not unlock")


def child(command_line, success):
    process = subprocess.Popen(command_line, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        wait(lambda: process.poll() is not None, "Session command stalled", 20)
        text = process.communicate(timeout=2)[0]
        assert (process.returncode == 0) == success, text
        return text
    finally:
        if process.poll() is None:
            process.terminate(); process.wait(timeout=3)


def guards():
    result = []
    for path in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            args = path.read_bytes().split(b"\0")
            if b"/usr/lib/ooonana/session_control.py" in args and b"--watch" in args and b"--background" not in args:
                result.append(int(path.parent.name))
        except OSError:
            pass
    return result


try:
    wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0, "Private i3 unavailable")
    display = IdleDisplay()
    assert display.has_window_manager() and not grabbed()
    window = SettingsWindow(); window.show_all()
    window.sidebar.select_row(window.sidebar.get_row_at_index(3))
    child(["ooonana-session-guard", "--background"], True)
    assert not guards(), "Disabled idle locking leaves a resident daemon"
    window.idle_lock_combo.grab_focus()
    window.idle_lock_combo.set_active_id("1")
    wait(lambda: not window.lock_pending, "Guard start did not settle")
    assert "enabled" in window.lock_status.get_text().lower(), window.lock_status.get_text()
    assert load_preferences()["idle_lock_minutes"] == 1
    capture("settings-lock-enabled")
    child(["ooonana-session-guard", "--background"], True)
    wait(lambda: len(guards()) == 1, "Display-scoped guard singleton failed")
    if "--layout-only" in sys.argv:
        window.idle_lock_combo.set_active_id("0")
        assert load_preferences()["idle_lock_minutes"] == 0
        capture("settings-lock-off")
        print("SESSION_LAYOUT_OK actual saved preference and service start; no idle wait", flush=True)
    else:
        pid = guards()[0]
        status = Path(f"/proc/{pid}/status").read_text()
        rss = next(line for line in status.splitlines() if line.startswith("VmRSS:"))
        print("SESSION_GUARD_MEMORY", rss, flush=True)
        ticks_before = sum(map(int, Path(f"/proc/{pid}/stat").read_text().split()[13:15]))
        command("xdotool", "mousemove", "100", "100")
        wait(lambda: display.idle_ms() < 2000, "Idle counter did not reset")
        start = time.monotonic()
        wait(grabbed, "Real one-minute idle timeout did not lock", 78)
        assert time.monotonic() - start >= 55, "Idle lock fired too early"
        ticks_after = sum(map(int, Path(f"/proc/{pid}/stat").read_text().split()[13:15]))
        print("SESSION_GUARD_CPU_SECONDS", (ticks_after - ticks_before) / os.sysconf("SC_CLK_TCK"), flush=True)
        capture("automatic-lock")
        window.idle_lock_combo.set_active_id("0")
        assert grabbed(), "Disabling idle policy unlocked active locker"
        unlock()
        wait(lambda: not guards(), "Disabled idle guard remained resident", 12)
        print("SESSION_IDLE_REAL_OK one-minute Xss idle, real PAM lock/unlock, singleton, disabling does not unlock and releases daemon", flush=True)

        directory = output / "provider"; directory.mkdir()
        (directory / "config.json").write_text('{"states":["yes"]}')
        bus = command("dbus-daemon", "--session", "--fork", "--print-address=1", "--print-pid=1",
                      "--address=unix:path=" + str(output / "system-bus")).stdout.splitlines()
        address, bus_pid = bus[0], int(bus[1])
        assert address.startswith("unix:path=/qa/session-control/") and bus_pid > 1
        os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = address
        log = (directory / "provider.log").open("w")
        provider = subprocess.Popen([sys.executable, str(ROOT / "tests/fixtures/login1-provider.py"), str(directory), address], stdout=log, stderr=log)
        wait(lambda: (directory / "ready").exists(), "Private login1 provider unavailable")

        def calls():
            path = directory / "calls.jsonl"
            return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

        for state in ("no", "na", "challenge", "inhibited"):
            before = len(calls())
            (directory / "config.json").write_text(json.dumps({"states": [state]}))
            child(["ooonana-session", "--suspend"], False)
            assert not grabbed() and not any(item["method"] == "Suspend" for item in calls()[before:])
        (directory / "config.json").write_text('{"states":["yes","no"]}')
        before = len(calls())
        text = child(["ooonana-session", "--suspend"], False)
        assert grabbed() and "stays locked" in text, (text, calls())
        assert not any(item["method"] == "Suspend" for item in calls()[before:])
        duplicate = subprocess.run(["ooonana-lock"], capture_output=True, text=True, timeout=5)
        assert duplicate.returncode == 75 and grabbed(), "Background locker lost launch ownership across vendor fork"
        unlock()
        (directory / "config.json").write_text('{"states":["yes"]}')
        child(["ooonana-session", "--suspend"], True)
        record = calls()[-1]
        assert record == {"method": "Suspend", "interactive": False, "locked": True}, record
        assert grabbed()
        capture("suspend-protocol-locked")
        unlock()
        provider.terminate(); provider.wait(timeout=4); provider = None
        child(["ooonana-session", "--suspend"], False)
        assert not grabbed(), "Missing provider unexpectedly locked session"
        print("SESSION_SUSPEND_PROTOCOL_OK real private DBus; denied/challenge/inhibited refuse before lock; permission change stays locked; only locked noninteractive request; missing provider refusal", flush=True)
        print("SESSION_CONTROL_UI_OK no host suspend/logout/wake operation performed", flush=True)
finally:
    if window is not None:
        window.destroy()
    if provider is not None and provider.poll() is None:
        provider.terminate(); provider.wait(timeout=4)
    if bus_pid:
        os.kill(bus_pid, signal.SIGTERM)
    if display is not None:
        display.close()
    wm.terminate(); wm.wait(timeout=5)
