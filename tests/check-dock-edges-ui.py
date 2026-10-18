#!/usr/bin/env python3
"""Owned display/tooltips/menus; fixture terminals only, no host input or sound."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme
from dock_app import Dock, windows
import i3_events
import window_menu

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", int(96 * 1024 * float(os.environ["OOONANA_GUI_TEXT_SCALE"])))
apply_theme()
os.environ["PATH"] = str(ROOT / "packages/ooonana/usr/bin") + ":" + os.environ["PATH"]
findings = []


def settle(seconds=0.1):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


def wait(predicate, message):
    end = time.monotonic() + 8
    while not predicate():
        assert time.monotonic() < end, message
        settle(0.03)


def check(condition, message):
    if not condition:
        findings.append(message)
        print("DOCK_EDGE_FINDING", message, flush=True)


def capture(name):
    settle()
    root = Gdk.get_default_root_window()
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
        str(output / (name + ".png")), "png", [], [])


def bounded(native, name):
    rect = native.get_frame_extents()
    root = Gdk.get_default_root_window()
    check(0 <= rect.x and rect.x + rect.width <= root.get_width() and
          0 <= rect.y and rect.y + rect.height <= root.get_height(), name + ": outside display")
    print("DOCK_EDGE_FRAME", name, rect.x, rect.y, rect.width, rect.height, flush=True)


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


with tempfile.TemporaryDirectory(prefix="ooonana-dock-edges-") as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                               if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    clients = []
    dock = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0,
             "Private window manager unavailable")
        socket = i3_events.socket_path()

        def current():
            return windows.windows(i3_events.request(socket, 4))

        # ASCII XTerm WM titles avoid conflating its locale/title encoding with
        # dock layout. CJK text rendering is covered by separate native probes.
        for title in ("First long terminal title - window " * 5, "Second terminal title - window " * 5):
            clients.append(subprocess.Popen(["xterm", "-title", title, "-bg", "#173a55", "-e", "sleep", "100"],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        wait(lambda: len(current()) == 2, "Owned terminal clients unavailable")
        selected = next(item for item in current() if item[2])
        dock = Dock(subscribe=False)
        dock.snapshot = i3_events.request(socket, 4)
        dock.refresh()
        settle()
        bounded(dock.get_window(), "dock")
        area = dock.monitor_geometry()
        x, y = dock.get_position()
        width, height = dock.get_size()
        check(abs(x + width / 2 - (area.x + area.width / 2)) <= 1, "Dock not centered on real output")
        check(area.y + area.height - y - height == 12, "Dock bottom clearance changed")
        check(all(control.get_allocated_width() >= 44 and control.get_allocated_height() >= 44
                  for control, _marker, _image in dock.buttons.values()), "Compact dock targets too small")
        capture("dock")
        pointer = dock.get_display().get_default_seat().get_pointer()

        def tooltips():
            return [native for native in dock.get_screen().get_toplevel_windows()
                    if native.is_visible() and native.get_type_hint() == Gdk.WindowTypeHint.TOOLTIP]

        for key in ("apps", "terminal", list(dock.buttons)[-1]):
            pointer.warp(dock.get_screen(), 1, 1)
            settle(0.6)
            button = dock.buttons[key][0]
            point = button.translate_coordinates(dock, 0, 0)
            origin = dock.get_position()
            pointer.warp(dock.get_screen(), origin[0] + point[0] + button.get_allocated_width() // 2,
                         origin[1] + point[1] + button.get_allocated_height() // 2)
            settle(0.6)
            Gtk.Tooltip.trigger_tooltip_query(dock.get_display())
            wait(lambda: bool(tooltips()), "Real tooltip did not appear: " + key)
            bounded(tooltips()[0], "tooltip-" + key)
            check(next(item[0] for item in current() if item[2]) == selected[0], "Tooltip changed focused client")
            capture("tooltip-" + key)
        pointer.warp(dock.get_screen(), 1, 1)
        settle(0.6)
        canvas = Gdk.get_default_root_window()
        corners = ((1, 1), (canvas.get_width() - 2, 1),
                   (1, canvas.get_height() - 2), (canvas.get_width() - 2, canvas.get_height() - 2))
        for number, (x, y) in enumerate(corners):
            pointer.warp(dock.get_screen(), x, y)

            def inspect_menu():
                try:
                    menus = [item for window in Gtk.Window.list_toplevels() for item in descendants(window)
                             if isinstance(item, Gtk.Menu) and item.get_visible()]
                    menu = menus[0] if menus else Gtk.grab_get_current()
                    assert isinstance(menu, Gtk.Menu), "Owned menu not found"
                    bounded(menu.get_toplevel().get_window(), "menu-" + str(number))
                    capture("menu-" + str(number))
                except Exception as exc:
                    check(False, "Menu driver: " + type(exc).__name__)
                finally:
                    subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"], check=True)
                return False

            GLib.timeout_add(300, inspect_menu)
            previous = sys.argv
            sys.argv = ["window_menu.py", "--window", str(selected[0]), "--title", selected[1]]
            try:
                assert window_menu.main() == 0
            finally:
                sys.argv = previous
        windows.window_action(selected, "fullscreen")
        settle()
        dock.snapshot = i3_events.request(socket, 4)
        dock.refresh()
        capture("fullscreen")
        check(not dock.get_visible(), "Dock covers active fullscreen content")
        subprocess.run(["i3-msg", 'workspace "99:dock-edge"'], capture_output=True, check=True)
        settle()
        dock.snapshot = i3_events.request(socket, 4)
        dock.refresh()
        check(dock.get_visible(), "Inactive fullscreen workspace hid dock")
        windows.focus(next(item for item in current() if item[0] == selected[0]))
        settle()
        dock.snapshot = i3_events.request(socket, 4)
        dock.refresh()
        check(not dock.get_visible(), "Returning to fullscreen did not hide dock")
        windows.window_action(selected, "fullscreen")
        settle()
        dock.snapshot = i3_events.request(socket, 4)
        dock.refresh()
        check(dock.get_visible(), "Fullscreen restore left dock hidden")
        check(next(item[0] for item in current() if item[2]) == selected[0], "Dock restore stole client focus")
        bounded(dock.get_window(), "restored-dock")
        print("DOCK_EDGE_RESULTS", findings, flush=True)
        assert not findings, "; ".join(findings)
        print("DOCK_EDGES_UI_OK real monitor, native tooltips, four-corner menus, hover focus and fullscreen restore", flush=True)
    finally:
        if dock is not None:
            dock.destroy()
        for process in clients:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=4)
        wm.terminate()
        wm.wait(timeout=4)
