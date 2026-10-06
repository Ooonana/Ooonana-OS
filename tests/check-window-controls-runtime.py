#!/usr/bin/env python3
"""Exercise shared native controls against nested i3, including unfocused windows."""

import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme, header, i3_window_action, message_dialog  # noqa: E402
from gi.repository import GdkX11  # noqa: E402


def windows():
    tree = json.loads(subprocess.check_output(["i3-msg", "-t", "get_tree"], text=True))
    result = {}

    def visit(node, hidden=False):
        hidden = hidden or node.get("name") == "__i3_scratch"
        if node.get("window"):
            result[node["window"]] = (node, hidden)
        for key in ("nodes", "floating_nodes"):
            for child in node.get(key, []):
                visit(child, hidden)

    visit(tree)
    return result


def wait_for(predicate):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        Gdk.Display.get_default().sync()
        if predicate(windows()):
            return
        time.sleep(0.05)
    raise AssertionError("Window state did not settle")


def control(window, name):
    def descendants(widget):
        yield widget
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                yield from descendants(child)
    return next(widget for widget in descendants(window.get_titlebar()) if widget.get_name() == name)


apply_theme()
a = Gtk.Window(title="Ooonana QA A")
b = Gtk.Window(title="Ooonana QA B")
for window in (a, b):
    window.set_default_size(360, 180)
    header(window, window.get_title())
    window.add(Gtk.Label(label="Window control regression check"))
    window.show_all()
passed = False
dialogs = []


def verify():
    global passed
    try:
        aid = GdkX11.X11Window.get_xid(a.get_window())
        bid = GdkX11.X11Window.get_xid(b.get_window())
        assert i3_window_action(b, "focus")
        control(a, "ooonana-window-minimize").emit("clicked")
        wait_for(lambda state: state[aid][1] and not state[bid][1])
        assert i3_window_action(a, "scratchpad show")
        assert i3_window_action(a, "focus")
        control(b, "ooonana-window-fullscreen").emit("clicked")
        wait_for(lambda state: state[bid][0].get("fullscreen_mode") == 1 and not state[aid][0].get("fullscreen_mode"))
        control(b, "ooonana-window-fullscreen").emit("clicked")
        wait_for(lambda state: not state[bid][0].get("fullscreen_mode"))
        control(b, "ooonana-window-close").emit("clicked")
        wait_for(lambda state: bid not in state and aid in state)
        native_dialog = message_dialog(a, "Diagnostic fixture", "Fixture detail\n" * 50)
        third_party_dialog = Gtk.Dialog(title="Third-party dialog fixture", transient_for=a)
        third_party_dialog.set_wmclass("fixture-dialog", "ThirdPartyDialog")
        third_party_dialog.get_content_area().add(Gtk.Label(label="Default third-party titlebar retained"))
        dialogs.extend((native_dialog, third_party_dialog))
        for dialog in dialogs:
            dialog.show_all()
        native_id = GdkX11.X11Window.get_xid(native_dialog.get_window())
        third_id = GdkX11.X11Window.get_xid(third_party_dialog.get_window())
        wait_for(lambda state: native_id in state and third_id in state)
        state = windows()
        assert state[native_id][0]["deco_rect"]["height"] == 0, "Duplicate native dialog titlebar"
        assert state[third_id][0]["deco_rect"]["height"] > 0, "Third-party dialog lost controls"
        control(native_dialog, "ooonana-window-close").emit("clicked")
        wait_for(lambda state: native_id not in state)
        passed = True
        print("NATIVE_WINDOW_CONTROLS_OK", flush=True)
    except Exception:
        traceback.print_exc()
    finally:
        for dialog in dialogs:
            dialog.destroy()
        a.destroy()
        b.destroy()
        Gtk.main_quit()
    return False


GLib.timeout_add(1000, verify)
Gtk.main()
raise SystemExit(0 if passed else 1)
