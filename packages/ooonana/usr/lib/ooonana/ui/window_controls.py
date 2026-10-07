"""Opaque, focus-neutral titlebar buttons for i3-decorated third-party windows."""
import ctypes
import cairo
import fcntl
import hashlib
import math
import os
from pathlib import Path
import threading
import time
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import i3_events
from common import Gdk, GLib, Gtk, window_control_icon, run_async

WIDTH = 66


def decoration_targets(tree, visible):
    result = {}

    def fullscreen(node, global_only=False):
        # i3 workspaces themselves report fullscreen_mode=1 even in normal layout.
        if node.get("fullscreen_mode") and node.get("type") != "workspace" and (not global_only or node["fullscreen_mode"] == 2):
            return node
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            found = fullscreen(child, global_only)
            if found:
                return found
        return None

    global_exclusive = fullscreen(tree, global_only=True)

    def overlaps(rectangle, x, y, height):
        return (rectangle.get("x", 0) < x + WIDTH and x < rectangle.get("x", 0) + rectangle.get("width", 0)
                and rectangle.get("y", 0) < y + height and y < rectangle.get("y", 0) + rectangle.get("height", 0))

    def visit(node, workspace=None, exclusive=None, occluders=()):
        if node.get("type") == "workspace":
            workspace = node.get("name")
            exclusive = global_exclusive or fullscreen(node)
        properties = node.get("window_properties") or {}
        klass = str(properties.get("class", "")).lower()
        deco, rect = node.get("deco_rect") or {}, node.get("rect") or {}
        if node.get("window") and workspace in visible and not node.get("fullscreen_mode") and exclusive is None and not klass.startswith(("ooonana", "oonana", "polybar")):
            height, width = deco.get("height", 0), deco.get("width", 0)
            if 16 <= height <= 64 and width >= WIDTH:
                x = rect.get("x", 0) + deco.get("x", 0) + width - WIDTH
                y = rect.get("y", 0) + deco.get("y", 0)
                if not any(overlaps(front, x, y, height) for front in occluders):
                    result[node["id"]] = (x, y, height)
        children = node.get("nodes", [])
        if node.get("layout") in ("tabbed", "stacked") and children:
            order = node.get("focus", [])
            selected = next((child for identifier in order for child in children if child.get("id") == identifier), children[0])
            # Hidden tabs must never expose controls targeting invisible clients.
            children = [selected]
        floating = node.get("floating_nodes", [])
        order = node.get("focus", [])
        floating = sorted(floating, key=lambda child: order.index(child["id"]) if child.get("id") in order else len(order))
        fronts = list(occluders)
        for child in floating:
            visit(child, workspace, exclusive, fronts)
            fronts.append(child.get("rect", {}))
        for child in children:
            visit(child, workspace, exclusive, fronts)
    visit(tree)
    return result


CSS = b"""
.third-party-controls { background: #1b1f26; border: none; box-shadow: none; }
.third-party-controls.inactive { background: #101317; }
.third-party-controls button { min-width: 14px; min-height: 14px; padding: 0; margin: 0; border-radius: 99px; border: 1px solid #242830; color: #101317; box-shadow: none; }
.third-party-controls .close { background: #ff736b; }
.third-party-controls .minimize { background: #ffd16c; }
.third-party-controls .fullscreen { background: #7fd6a0; }
.third-party-controls button:hover { border-color: #ffffff; }
"""


class Controls(Gtk.Window):
    def __init__(self, identifier, owner):
        super().__init__(type=Gtk.WindowType.POPUP)
        # Compositor must not round/clip this tiny titlebar overlay again.
        self.set_wmclass("ooonana-window-controls", "OoonanaWindowControls")
        self.identifier = identifier
        self.last_position = None
        self.connect("realize", self.register, owner)
        self.connect("destroy", self.unregister, owner)
        self.xid = None
        self.control_region = cairo.Region()
        self.connect_after("size-allocate", self.clip_controls)
        self.connect("map", self.clip_controls)
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
        row.connect_after("size-allocate", self.clip_controls)
        for action, title, glyph in (("close", "Close window", "window-close-symbolic"), ("minimize", "Minimize window", "window-minimize-symbolic"), ("fullscreen", "Toggle fullscreen", "view-fullscreen-symbolic")):
            control = Gtk.Button()
            image = window_control_icon(glyph)
            image.set_pixel_size(10)
            control.set_image(image)
            control.set_can_focus(False)
            control.get_style_context().add_class(action)
            control.set_tooltip_text(title)
            control.get_accessible().set_name(title)
            control.connect("clicked", lambda _widget, operation=action: self.activate(operation))
            row.pack_start(control, False, False, 0)
        self.add(row)

    def clip_controls(self, *_args):
        if not self.get_realized():
            return
        # Cut out the popup's background/gaps, not translucent button surfaces.
        # Both paint and input regions follow circles; exposed titlebar stays
        # draggable even without a compositor.
        shape = cairo.Region()
        for button in self.get_child().get_children():
            origin = button.translate_coordinates(self, 0, 0)
            if origin is None:
                continue
            size = button.get_allocation()
            rx, ry = size.width / 2, size.height / 2
            if not rx or not ry:
                continue
            for y in range(size.height):
                half = rx * math.sqrt(max(0, 1 - ((y + 0.5 - ry) / ry) ** 2))
                inset = math.ceil(rx - half)
                width = size.width - 2 * inset
                if width > 0:
                    shape.union(cairo.RectangleInt(origin[0] + inset, origin[1] + y, width, 1))
        self.control_region = shape
        self.get_window().shape_combine_region(shape, 0, 0)
        self.get_window().input_shape_combine_region(shape, 0, 0)

    def register(self, _widget, owner):
        from gi.repository import GdkX11
        owner.own_windows.add(GdkX11.X11Window.get_xid(self.get_window()))
        self.xid = GdkX11.X11Window.get_xid(self.get_window())

    def unregister(self, _widget, owner):
        owner.own_windows.discard(self.xid)

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
        self.xlib.XFlush.argtypes = [ctypes.c_void_p]
        self.xlib.XFlush.restype = ctypes.c_int
        self.xlib.XPending.argtypes = [ctypes.c_void_p]
        self.xlib.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.display = self.xlib.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("X11 display unavailable")
        self.xlib.XSelectInput(self.display, self.xlib.XDefaultRootWindow(self.display), (1 << 19))
        # Xlib buffers this request. No i3 event is emitted for every drag step;
        # without flushing, root ConfigureNotify never reaches our idle socket.
        self.xlib.XFlush(self.display)
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
            # Coalesce configure events within one frame, not a visible 60ms lag.
            GLib.timeout_add(16, self.refresh)
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
            focused = set()
            def visit(node):
                if node.get("window") and node.get("focused"):
                    focused.add(node["id"])
                for child in node.get("nodes", []) + node.get("floating_nodes", []):
                    visit(child)
            visit(tree)
        except (OSError, ValueError, EOFError):
            return self.clear()
        for identifier in set(self.controls) - set(targets):
            self.controls.pop(identifier).destroy()
        for identifier, target in targets.items():
            if identifier not in self.controls:
                self.controls[identifier] = Controls(identifier, self)
            style = self.controls[identifier].get_style_context()
            (style.remove_class if identifier in focused else style.add_class)("inactive")
            self.controls[identifier].position(target)
            self.controls[identifier].get_window().raise_()
        return False


def main():
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))) / "ooonana"
    runtime.mkdir(parents=True, exist_ok=True)
    display = hashlib.sha256(os.environ.get("DISPLAY", "default").encode()).hexdigest()[:16]
    with (runtime / f"window-controls-{display}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        manager = Manager()
        Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
