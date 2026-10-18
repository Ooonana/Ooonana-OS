#!/usr/bin/env python3
"""Owned X11 device/application-coordinate checks; no physical display changes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme
from gi.repository import GdkX11
from dock_app import Dock, fullscreen_on_monitor, windows
from window_controls import Manager, WIDTH
import i3_events

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
apply_theme()
os.environ["PATH"] = str(ROOT / "packages/ooonana/usr/bin") + ":" + os.environ["PATH"]
findings = []


def settle(seconds=0.15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


def wait(predicate, message):
    end = time.monotonic() + 10
    while not predicate():
        assert time.monotonic() < end, message
        settle(0.03)


def check(condition, message):
    if not condition:
        findings.append(message)
        print("DEVICE_SCALE_FINDING", message, flush=True)


def capture(name):
    settle()
    root = Gdk.get_default_root_window()
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
        str(output / (name + ".png")), "png", [], [])


def geometry(window):
    xid = GdkX11.X11Window.get_xid(window.get_window())
    result = subprocess.check_output(["xdotool", "getwindowgeometry", "--shell", str(xid)], text=True)
    values = dict(line.split("=", 1) for line in result.splitlines())
    return tuple(int(values[key]) for key in ("X", "Y", "WIDTH", "HEIGHT"))


with tempfile.TemporaryDirectory(prefix="ooonana-device-scale-") as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                               if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    terminal = dock = manager = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0,
             "Owned window manager unavailable")
        socket = i3_events.socket_path()
        terminal = subprocess.Popen(["xterm", "-title", "Device-scale fixture", "-bg", "#173a55", "-e", "sleep", "90"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait(lambda: bool(windows.windows(i3_events.request(socket, 4))), "Owned terminal unavailable")
        selected = next(item for item in windows.windows(i3_events.request(socket, 4)) if item[1] == "Device-scale fixture")
        manager = Manager()
        manager.refresh()
        wait(lambda: selected[0] in manager.controls, "Third-party controls unavailable")
        control = manager.controls[selected[0]]
        wait(lambda: control.get_realized(), "Control popup not mapped")
        settle()
        scale = control.get_scale_factor()
        actual = geometry(control)
        target = control.last_position
        print("DEVICE_SCALE_CONTROLS", scale, "i3", target, "X11", actual, flush=True)
        check(abs(actual[0] - target[0]) < scale and abs(actual[1] - target[1]) < scale,
              "Third-party controls use device coordinates as application coordinates")
        check(actual[2] <= WIDTH + scale and actual[3] <= target[2] + scale,
              "Third-party controls grow beyond native titlebar")
        capture("controls")
        dock = Dock(subscribe=False)
        dock.snapshot = i3_events.request(socket, 4)
        dock.refresh()
        settle()
        area = dock.monitor_geometry()
        outputs = i3_events.request(socket, 3)
        physical = next(item["rect"] for item in outputs if item.get("active"))
        print("DEVICE_SCALE_MONITOR", dock.get_scale_factor(), "Gdk", area.x, area.y, area.width, area.height,
              "i3", physical, flush=True)
        check(physical["width"] == area.width * scale, "Fixture did not establish device/application ratio")
        # Shift the measured output geometry to reproduce a nonzero-origin
        # monitor. This is a coordinate guard, not physical multi-monitor proof.
        shifted = SimpleNamespace(x=area.width, y=0, width=area.width, height=area.height)
        sample = {"type": "con", "fullscreen_mode": 1,
                  "rect": {"x": physical["width"], "y": 0, **{key: physical[key] for key in ("width", "height")}}}
        overlaps = fullscreen_on_monitor(sample, shifted, scale=scale)
        check(overlaps, "Fullscreen hit test mixes logical/device coordinates on offset output")
        def click(action):
            popup = manager.controls[selected[0]]
            button = next(item for item in popup.get_child().get_children()
                          if item.get_accessible().get_name() == action)
            point = button.translate_coordinates(popup, 0, 0)
            raw = geometry(popup)
            x = raw[0] + (point[0] + button.get_allocated_width() // 2) * scale
            y = raw[1] + (point[1] + button.get_allocated_height() // 2) * scale
            subprocess.run(["xdotool", "mousemove", "--sync", str(x), str(y), "click", "1"], check=True)

        click("Minimize window")
        wait(lambda: next(item for item in windows.windows(i3_events.request(socket, 4)) if item[0] == selected[0])[3],
             "Actual scaled Minimize click missed titlebar control")
        hidden = next(item for item in windows.windows(i3_events.request(socket, 4)) if item[0] == selected[0])
        windows.focus(hidden)
        wait(lambda: selected[0] in manager.controls and manager.controls[selected[0]].get_visible(), "Scaled controls did not restore")
        settle()
        windows.window_action(selected, "fullscreen")
        settle()
        dock.snapshot = i3_events.request(socket, 4)
        dock.refresh()
        check(not dock.get_visible(), "Dock covers fullscreen content")
        capture("fullscreen")
        windows.window_action(selected, "fullscreen")
        settle()
        dock.snapshot = i3_events.request(socket, 4)
        dock.refresh()
        check(dock.get_visible(), "Dock failed to return after fullscreen")
        manager.refresh()
        settle()
        click("Close window")
        wait(lambda: terminal.poll() is not None, "Actual scaled Close click missed titlebar control")
        print("DEVICE_SCALE_RESULTS", json.dumps(findings), flush=True)
        assert not findings, "; ".join(findings)
        print("DEVICE_SCALE_UI_OK real Gdk/device ratio, native titlebar bounds and fullscreen restoration", flush=True)
    finally:
        if dock is not None:
            dock.destroy()
        if manager is not None:
            manager.clear()
        if terminal is not None and terminal.poll() is None:
            terminal.terminate()
            terminal.wait(timeout=4)
        wm.terminate()
        wm.wait(timeout=4)
