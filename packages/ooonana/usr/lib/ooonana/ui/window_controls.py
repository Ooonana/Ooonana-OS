"""Opaque, focus-neutral titlebar buttons for i3-decorated third-party windows."""
import ctypes
import fcntl
import os
from pathlib import Path
import socket
import threading
import time
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import i3_events
from common import Gdk, GLib, Gtk, icon, run_async

WIDTH = 76


def decoration_targets(tree, visible):
    result = {}

    def visit(node, workspace=None):
        if node.get("type") == "workspace":
            workspace = node.get("name")
        properties = node.get("window_properties") or {}
        klass = str(properties.get("class", "")).lower()
        deco, rect = node.get("deco_rect") or {}, node.get("rect") or {}
        if node.get("window") and workspace in visible and not node.get("fullscreen_mode") and not klass.startswith(("ooonana", "oonana", "polybar")):
            height, width = deco.get("height", 0), deco.get("width", 0)
            if 16 <= height <= 64 and width >= WIDTH:
                result[node["id"]] = (rect.get("x", 0) + deco.get("x", 0) + width - WIDTH,
                                       rect.get("y", 0) + deco.get("y", 0), height)
        for key in ("nodes", "floating_nodes"):
            for child in node.get(key, []):
                visit(child, workspace)
    visit(tree)
    return result


CSS = b"""
.third-party-controls { background: #1b1f26; border: none; box-shadow: none; }
.third-party-controls button { min-width: 16px; min-height: 16px; padding: 0; border-radius: 99px; border: 1px solid #242830; color: #101317; box-shadow: none; }
.third-party-controls .close { background: #ff736b; }
.third-party-controls .minimize { background: #ffd16c; }
.third-party-controls .fullscreen { background: #7fd6a0; }
.third-party-controls button:hover { border-color: #ffffff; }
"""


class Controls(Gtk.Window):
    def __init__(self, identifier, owner):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.identifier = identifier
        self.last_position = None
        self.connect("realize", self.register, owner)
        self.set_decorated(False)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.get_style_context().add_class("third-party-controls")
        row = Gtk.Box(spacing=5)
        row.set_margin_left(4)
        row.set_margin_right(4)
        row.set_valign(Gtk.Align.CENTER)
        for action, title, glyph in (("close", "Close window", "window-close-symbolic"), ("minimize", "Minimize window", "window-minimize-symbolic"), ("fullscreen", "Toggle fullscreen", "view-fullscreen-symbolic")):
            control = Gtk.Button()
            control.set_image(icon(glyph))
            control.set_can_focus(False)
            control.get_style_context().add_class(action)
            control.set_tooltip_text(title)
            control.get_accessible().set_name(title)
            control.connect("clicked", lambda _widget, operation=action: self.activate(operation))
            row.pack_start(control, False, False, 0)
        self.add(row)

    def register(self, _widget, owner):
        from gi.repository import GdkX11
        owner.own_windows.add(GdkX11.X11Window.get_xid(self.get_window()))

    def activate(self, action):
        run_async(["ooonana-window-list", "--window-action", action, str(self.identifier)], lambda *_: None)

    def position(self, target):
        if self.last_position != target:
            x, y, height = target
            self.set_size_request(WIDTH, height)
            self.move(x, y)
            self.last_position = target
        self.show_all()


class Manager:
    def __init__(self):
        self.controls = {}
        self.own_windows = set()
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        self.pending = False
        self.xlib = ctypes.CDLL("libX11.so.6")
        self.xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.xlib.XOpenDisplay.restype = ctypes.c_void_p
        self.xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.xlib.XDefaultRootWindow.restype = ctypes.c_ulong
        self.xlib.XConnectionNumber.argtypes = [ctypes.c_void_p]
        self.xlib.XConnectionNumber.restype = ctypes.c_int
        self.xlib.XSelectInput.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_long]
        self.xlib.XPending.argtypes = [ctypes.c_void_p]
        self.xlib.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.display = self.xlib.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("X11 display unavailable")
        self.xlib.XSelectInput(self.display, self.xlib.XDefaultRootWindow(self.display), (1 << 19))
        GLib.io_add_watch(self.xlib.XConnectionNumber(self.display), GLib.IO_IN, self.configured)
        threading.Thread(target=self.watch, daemon=True).start()

    def configured(self, _source, _condition):
        event = ctypes.create_string_buffer(192)
        changed = False
        while self.xlib.XPending(self.display):
            self.xlib.XNextEvent(self.display, event)
            # Root SubstructureNotify carries affected window after parent.
            identifier = ctypes.c_ulong.from_buffer(event, 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 20).value
            if identifier not in self.own_windows:
                changed = True
        if changed:
            self.schedule()
        return True

    def schedule(self):
        if not self.pending:
            self.pending = True
            GLib.timeout_add(60, self.refresh)
        return False

    def watch(self):
        while True:
            try:
                for _tree in i3_events.trees():
                    GLib.idle_add(self.schedule)
            except (OSError, ValueError, EOFError):
                GLib.idle_add(self.clear)
                time.sleep(2)

    def clear(self):
        for window in self.controls.values():
            window.destroy()
        self.controls.clear()
        return False

    def refresh(self):
        self.pending = False
        try:
            path = i3_events.socket_path()
            tree = i3_events.request(path, 4)
            visible = {workspace["name"] for workspace in i3_events.request(path, 1) if workspace.get("visible")}
            targets = decoration_targets(tree, visible)
        except (OSError, ValueError, EOFError):
            return self.clear()
        for identifier in set(self.controls) - set(targets):
            self.controls.pop(identifier).destroy()
        for identifier, target in targets.items():
            if identifier not in self.controls:
                self.controls[identifier] = Controls(identifier, self)
            self.controls[identifier].position(target)
            self.controls[identifier].get_window().raise_()
        return False


def main():
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))) / "ooonana"
    runtime.mkdir(parents=True, exist_ok=True)
    with (runtime / "window-controls.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        manager = Manager()
        Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
