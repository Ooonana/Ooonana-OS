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
from common import Gdk, GLib, Gtk, WINDOW_CONTROL_CSS, window_control_icon, run_async

WIDTH = 66


def native_control_scale(version):
    """Negotiate with the running WM, never an upgraded binary on disk."""
    if not isinstance(version, dict) or type(version.get("ooonana_control_api")) is not int:
        return 0
    scale = version.get("ooonana_control_scale")
    return scale if version["ooonana_control_api"] == 1 and type(scale) is int and 1 <= scale <= 4 else 0


def initial_app_targets(tree, visible):
    """Fit new editor/files frames; preserve fitting defaults and later user moves."""
    result = {}
    def visit(node, output=None, workspace=None):
        if node.get("type") == "output":
            output = node.get("rect")
        if node.get("type") == "workspace":
            workspace = node.get("name")
        properties = node.get("window_properties") or {}
        if (output and node.get("window") and workspace in visible
                and str(properties.get("class", "")).casefold() in ("geany", "nemo")
                and node.get("window_type") == "normal"
                and node.get("floating") in ("auto_on", "user_on")
                and not node.get("fullscreen_mode")):
            rect = node.get("rect") or {}
            x, y, width, height = (rect.get(key, 0) for key in ("x", "y", "width", "height"))
            # Same usable clearances as shipped i3 gaps: panel/dock stay usable.
            available_width, available_height = output.get("width", 0) - 24, output.get("height", 0) - 142
            if min(width, height, available_width, available_height) > 0:
                new_width, new_height = min(width, available_width), min(height, available_height)
                left, top = output.get("x", 0) + 12, output.get("y", 0) + 58
                new_x = max(left, min(x, left + available_width - new_width))
                new_y = max(top, min(y, top + available_height - new_height))
                if (new_x, new_y, new_width, new_height) != (x, y, width, height):
                    # i3 floating resize sets the complete frame, not just client.
                    result[node["id"]] = ((new_x, new_y, new_width, new_height),
                                         (x, y, width, height), node["window"])
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            visit(child, output, workspace)
    visit(tree)
    return result


def initial_dialog_targets(tree, visible):
    """Only the observed Qt settings placement fault; never resize native UI."""
    result = {}

    def visit(node, output=None, workspace=None):
        if node.get("type") == "output":
            output = node.get("rect")
        if node.get("type") == "workspace":
            workspace = node.get("name")
        properties = node.get("window_properties") or {}
        if (output and node.get("window") and workspace in visible
                and str(properties.get("class", "")).lower() == "qterminal"
                and node.get("window_type") == "dialog"
                and node.get("floating") in ("auto_on", "user_on")
                and not node.get("fullscreen_mode")):
            rect = node.get("rect") or {}
            x, y, width, height = (rect.get(key, 0) for key in ("x", "y", "width", "height"))
            if 0 < width <= output.get("width", 0) and 0 < height <= output.get("height", 0):
                left, top = output.get("x", 0), output.get("y", 0)
                target = (max(left, min(x, left + output["width"] - width)),
                          max(top, min(y, top + output["height"] - height)))
                if target != (x, y):
                    result[node["id"]] = (target, (x, y, width, height))
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            visit(child, output, workspace)
    visit(tree)
    return result


def decoration_targets(tree, visible, native_scale=0):
    result = {}
    row_width = 82 * native_scale if native_scale else WIDTH
    inset = 14 * native_scale

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
        return (rectangle.get("x", 0) < x + row_width and x < rectangle.get("x", 0) + rectangle.get("width", 0)
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
            minimum_height = 32 * native_scale if native_scale else 16
            if minimum_height <= height <= max(64, minimum_height) and width >= row_width + inset:
                offset = inset if native_scale else width - WIDTH
                x = rect.get("x", 0) + deco.get("x", 0) + offset
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
""" + WINDOW_CONTROL_CSS


class Controls(Gtk.Window):
    def __init__(self, identifier, owner):
        super().__init__(type=Gtk.WindowType.POPUP)
        # Compositor must not round/clip this tiny titlebar overlay again.
        self.set_wmclass("ooonana-window-controls", "OoonanaWindowControls")
        visual = self.get_screen().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.identifier = identifier
        self.last_position = None
        self.last_scale = None
        self.last_control_scale = 0
        self.target_xid = None
        self.scale_provider = Gtk.CssProvider()
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
            control.get_style_context().add_class("window-control")
            control.get_style_context().add_class(action + "-control")
            control.get_style_context().add_provider(self.scale_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
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
        changed = not self.control_region.equal(shape)
        self.control_region = shape
        self.get_window().shape_combine_region(shape, 0, 0)
        self.get_window().input_shape_combine_region(shape, 0, 0)
        if changed:
            # Initial/map allocation can change the X11 bounding shape after
            # GTK has painted. Damage the newly visible pixels explicitly;
            # otherwise a compositor can retain black, unpainted button fills.
            self.queue_draw()
            for button in self.get_child().get_children():
                button.queue_draw()

    def register(self, _widget, owner):
        from gi.repository import GdkX11
        owner.own_windows.add(GdkX11.X11Window.get_xid(self.get_window()))
        self.xid = GdkX11.X11Window.get_xid(self.get_window())

    def unregister(self, _widget, owner):
        owner.own_windows.discard(self.xid)

    def activate(self, action):
        if self.target_xid:
            run_async(["ooonana-window-list", "--window-action", action, str(self.identifier),
                       "--expect-xid", str(self.target_xid)], lambda *_: None)

    def position(self, target, native_scale=0):
        scale = max(1, self.get_scale_factor())
        if self.last_position != target or self.last_scale != scale or self.last_control_scale != native_scale:
            x, y, height = target
            # i3 targets are X11 device pixels; GTK placement and CSS use
            # application pixels. Match the native titlebar, not GDK_SCALE.
            # GTK quantizes CSS borders to whole application pixels. Budget
            # their actual width, or three buttons exceed the 66-device-pixel row.
            border = math.ceil(1 / scale)
            size = 24 * native_scale if native_scale else 16
            width = 82 * native_scale if native_scale else WIDTH
            minimum = max(1, size / scale - 2 * border)
            self.scale_provider.load_from_data((
                "button { min-width: %gpx; min-height: %gpx; border-width: %gpx; padding: 0; }"
                % (minimum, minimum, border)).encode())
            row = self.get_child()
            row.set_spacing(max(1, 5 * max(1, native_scale) // scale))
            row.set_margin_left(0 if native_scale else max(1, 4 // scale))
            row.set_margin_right(0 if native_scale else max(1, 4 // scale))
            for button in row.get_children():
                button.get_image().set_pixel_size(max(1, (12 * native_scale if native_scale else 10) // scale))
            self.set_size_request(math.ceil(width / scale), math.ceil(height / scale))
            self.move(x // scale, y // scale)
            self.last_position = target
            self.last_scale = scale
            self.last_control_scale = native_scale
        self.show_all()


class Manager:
    def __init__(self):
        self.controls = {}
        self.own_windows = set()
        self.placement_seen = None
        self.control_scale = 0
        self.capability_path = None
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
                GLib.idle_add(self.clear)
            except (OSError, ValueError, EOFError):
                GLib.idle_add(self.clear)
                time.sleep(2)

    def clear(self):
        for window in self.controls.values():
            window.destroy()
        self.controls.clear()
        self.placement_seen = None
        self.control_scale = 0
        self.capability_path = None
        return False

    def place_initial_dialog(self, identifier, original):
        # Qt can reposition after i3's map rule. One deferred correction only;
        # changed geometry, closed windows and later user moves are left alone.
        if self.placement_seen is None or identifier not in self.placement_seen:
            return False
        try:
            path = i3_events.socket_path()
            tree = i3_events.request(path, 4)
            visible = {item["name"] for item in i3_events.request(path, 1) if item.get("visible")}
            candidate = initial_dialog_targets(tree, visible).get(identifier)
            if candidate and candidate[1] == original:
                x, y = candidate[0]
                run_async(["i3-msg", f"[con_id={int(identifier)}] move absolute position {int(x)} px {int(y)} px"],
                          lambda *_: None)
        except (OSError, ValueError, EOFError):
            pass
        return False

    def fit_initial_app(self, identifier, original, xid):
        if self.placement_seen is None or identifier not in self.placement_seen:
            return False
        try:
            path = i3_events.socket_path()
            tree = i3_events.request(path, 4)
            visible = {item["name"] for item in i3_events.request(path, 1) if item.get("visible")}
            candidate = initial_app_targets(tree, visible).get(identifier)
            if candidate and candidate[1:] == (original, xid):
                x, y, width, height = candidate[0]
                criterion = f"[con_id={int(identifier)} id={int(xid)}]"
                run_async(["i3-msg", f"{criterion} resize set {width} px {height} px; "
                           f"{criterion} move absolute position {x} px {y} px"], lambda *_: None)
        except (OSError, ValueError, EOFError):
            pass
        return False

    def refresh(self):
        self.pending = False
        try:
            path = i3_events.socket_path()
            if path != self.capability_path:
                self.control_scale = native_control_scale(i3_events.request(path, 7))
                self.capability_path = path
            tree = i3_events.request(path, 4)
            visible = {workspace["name"] for workspace in i3_events.request(path, 1) if workspace.get("visible")}
            targets = decoration_targets(tree, visible, self.control_scale)
            focused = set()
            live = set()
            live_xids = {}
            def visit(node):
                if node.get("window"):
                    live.add(node["id"])
                    live_xids[node["id"]] = node["window"]
                if node.get("window") and node.get("focused"):
                    focused.add(node["id"])
                for child in node.get("nodes", []) + node.get("floating_nodes", []):
                    visit(child)
            visit(tree)
            if self.placement_seen is not None:
                for identifier, (_position, original) in initial_dialog_targets(tree, visible).items():
                    if identifier not in self.placement_seen:
                        GLib.timeout_add(120, self.place_initial_dialog, identifier, original)
                for identifier, (_position, original, xid) in initial_app_targets(tree, visible).items():
                    if identifier not in self.placement_seen:
                        GLib.timeout_add(120, self.fit_initial_app, identifier, original, xid)
            self.placement_seen = live
        except (OSError, ValueError, EOFError):
            return self.clear()
        for identifier in set(self.controls) - set(targets):
            self.controls.pop(identifier).destroy()
        for identifier, target in targets.items():
            if identifier not in self.controls:
                self.controls[identifier] = Controls(identifier, self)
            self.controls[identifier].target_xid = live_xids[identifier]
            style = self.controls[identifier].get_style_context()
            (style.remove_class if identifier in focused else style.add_class)("inactive")
            self.controls[identifier].position(target, self.control_scale)
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
