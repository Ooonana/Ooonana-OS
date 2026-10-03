"""Opaque event-driven dock. Hover previews stay in RAM and never focus windows."""
import cairo
import fcntl
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import math
import os
from pathlib import Path
import re
import threading
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import i3_events
from common import Gdk, GLib, Gtk, Pango, apply_theme, run_async
import gi
gi.require_version("GdkX11", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkX11, GdkPixbuf

loader = SourceFileLoader("dock_windows", str(Path(__file__).resolve().parents[3] / "bin/ooonana-window-list"))
windows = module_from_spec(spec_from_loader(loader.name, loader))
loader.exec_module(windows)
NAMES = {"apps": "Applications", "terminal": "Terminal", "browser": "Browser",
         "files": "Files", "editor": "Editor", "music": "Music",
         "openvino": "Offline AI", "tasks": "Task Manager"}
ICONS = {"apps": "ooonana-apps", "terminal": "ooonana-terminal", "browser": "web-browser",
         "files": "ooonana-files", "editor": "ooonana-editor", "music": "ooonana-music",
         "openvino": "ooonana-openvino", "tasks": "ooonana-task-manager", "other": "application-x-executable"}
CSS = b"""
.ooonana-dock { background: #1b1f26; border: 1px solid #414957; border-radius: 20px; }
.ooonana-dock button { padding: 5px 8px; border: 1px solid transparent; border-radius: 13px; background: #1b1f26; box-shadow: none; min-width: 0; min-height: 0; }
.ooonana-dock button:hover { background: #303640; border-color: #596574; }
.ooonana-dock button.active { background: #303640; border-color: #ffb21a; }
.ooonana-dock label { font-size: 9px; color: #b4bdc8; }
tooltip { background: #1b1f26; color: #f5f5f7; border: 1px solid #414957; }
"""


def preview_image(node, hidden=False):
    """Mapped X11 windows only; bounded capture, no disk cache or unminimizing."""
    if hidden or not node or not node.get("window"):
        return None
    display = Gdk.Display.get_default()
    foreign = GdkX11.X11Window.foreign_new_for_display(display, int(node["window"]))
    if not foreign or not foreign.is_visible():
        return None
    width, height = foreign.get_width(), foreign.get_height()
    if width <= 0 or height <= 0 or width * height > 4_000_000:
        return None
    display.error_trap_push()
    try:
        picture = Gdk.pixbuf_get_from_window(foreign, 0, 0, width, height)
    finally:
        error = display.error_trap_pop()
    if error or picture is None:
        return None
    scale = min(240 / width, 150 / height, 1)
    return picture.scale_simple(max(1, int(width * scale)), max(1, int(height * scale)),
                                GdkPixbuf.InterpType.BILINEAR)


class Dock(Gtk.Window):
    def __init__(self, subscribe=True):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_title("Ooonana Dock")
        self.set_wmclass("ooonana-dock", "OoonanaDock")
        self.set_decorated(False)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.get_style_context().add_class("ooonana-dock")
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        self.row = Gtk.Box(spacing=4)
        self.row.set_border_width(8)
        self.add(self.row)
        self.snapshot, self.items, self.nodes, self.buttons = {}, [], {}, {}
        self.pending, self.stopped, self.geometry_state = 0, False, None
        self.connect("size-allocate", self.position)
        self.connect("destroy", self.closed)
        self.get_screen().connect("size-changed", lambda *_: self.queue())
        self.get_screen().connect("monitors-changed", lambda *_: self.queue())
        if subscribe:
            threading.Thread(target=self.listen, daemon=True).start()

    def closed(self, *_):
        self.stopped = True
        if Gtk.main_level():
            Gtk.main_quit()

    def listen(self):
        while not self.stopped:
            try:
                for snapshot in i3_events.trees():
                    if self.stopped:
                        return
                    self.snapshot = snapshot
                    GLib.idle_add(self.queue)
            except (OSError, ValueError, EOFError):
                pass
            time.sleep(2)

    def queue(self):
        if not self.pending and not self.stopped:
            self.pending = GLib.timeout_add(60, self.refresh)
        return False

    def monitor_geometry(self):
        display = self.get_display()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        return monitor.get_geometry()

    def position(self, _widget=None, allocation=None):
        if not self.get_realized():
            return
        area = self.monitor_geometry()
        width, height = self.get_size()
        self.move(area.x + max(0, (area.width - width) // 2), area.y + area.height - height - 12)
        # Clip corners without translucent surfaces or compositor dependence.
        radius = min(20, height // 2, width // 2)
        shape = cairo.Region()
        for y in range(height):
            distance = radius - y - 0.5 if y < radius else y - (height - radius) + 0.5 if y >= height - radius else 0
            inset = math.ceil(radius - math.sqrt(max(0, radius * radius - distance * distance))) if distance else 0
            shape.union(cairo.RectangleInt(inset, y, max(1, width - 2 * inset), 1))
        self.get_window().shape_combine_region(shape, 0, 0)

    def refresh(self):
        self.pending = 0
        self.items = windows.windows(self.snapshot)
        self.nodes = {node["id"]: node for node, _hidden in windows.leaves(self.snapshot)}
        area = self.monitor_geometry()
        geometry = (area.x, area.y, area.width, area.height)
        if self.geometry_state is not None and geometry != self.geometry_state:
            run_async(["ooonana-panel-start", "--panel-only"], lambda *_: None)
        self.geometry_state = geometry
        pins = windows.available_pins()
        if area.width < 520:
            pins = [pin for pin in pins if pin[0] not in ("editor", "music")]
        keys = [pin[0] for pin in pins]
        other = [item for item in self.items if windows.pin_for(item) not in keys]
        if other:
            keys.append("other")
        if list(self.buttons) != keys:
            for widget in self.row.get_children():
                widget.destroy()
            self.buttons = {}
            for key in keys:
                control = Gtk.Button()
                control.set_can_focus(False)
                control.get_accessible().set_name(NAMES.get(key, "Other windows"))
                content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
                image = Gtk.Image.new_from_icon_name(ICONS[key], Gtk.IconSize.DIALOG)
                image.set_pixel_size(24 if area.width < 520 else 32)
                content.pack_start(image, False, False, 0)
                dot = Gtk.Label(label=" ")
                content.pack_start(dot, False, False, 0)
                control.add(content)
                control.connect("clicked", lambda _button, pin=key: self.open(pin))
                control.connect("button-press-event", self.press, key)
                control.set_has_tooltip(True)
                control.connect("query-tooltip", self.tooltip, key)
                self.row.pack_start(control, False, False, 0)
                self.buttons[key] = (control, dot)
        for key, (control, dot) in self.buttons.items():
            matches = other if key == "other" else [item for item in self.items if windows.pin_for(item) == key]
            style = control.get_style_context()
            (style.add_class if any(item[2] for item in matches) else style.remove_class)("active")
            dot.set_text(str(len(matches)) if len(matches) > 1 else "○" if matches and matches[0][3] else "•" if matches else " ")
        self.show_all()
        self.position()
        return False

    def matches(self, key):
        visible_keys = set(self.buttons) - {"other"}
        return [item for item in self.items if (windows.pin_for(item) not in visible_keys if key == "other" else windows.pin_for(item) == key)]

    def tooltip_content(self, key):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(8)
        matches = sorted(self.matches(key), key=lambda item: (not item[2], item[3]))
        title = Gtk.Label(label=NAMES.get(key, "Other windows"))
        box.pack_start(title, False, False, 0)
        if matches:
            item = matches[0]
            picture = preview_image(self.nodes.get(item[0]), item[3])
            if picture:
                box.pack_start(Gtk.Image.new_from_pixbuf(picture), False, False, 0)
            for entry in matches[:3]:
                caption = Gtk.Label(label=entry[1] + (" · Minimized" if entry[3] else ""))
                caption.set_ellipsize(Pango.EllipsizeMode.END)
                caption.set_max_width_chars(36)
                box.pack_start(caption, False, False, 0)
            if len(matches) > 3:
                box.pack_start(Gtk.Label(label=f"+{len(matches) - 3} windows"), False, False, 0)
        else:
            box.pack_start(Gtk.Label(label="Click to open"), False, False, 0)
        box.show_all()
        return box

    def tooltip(self, _widget, _x, _y, _keyboard, tooltip, key):
        tooltip.set_custom(self.tooltip_content(key))
        return True

    def open(self, key):
        args = ["--menu"] if key == "other" else ["--dock-open", key]
        run_async(["ooonana-window-list", *args], lambda *_: None)

    def press(self, _button, event, key):
        if event.button == 3:
            args = ["--actions"] if key == "other" else ["--dock-actions", key]
            run_async(["ooonana-window-list", *args], lambda *_: None)
            return True
        return False


def main():
    state = Path(os.environ.get("XDG_RUNTIME_DIR", str(Path.home() / ".local/state"))) / "ooonana"
    state.mkdir(parents=True, exist_ok=True)
    display = re.sub(r"[^A-Za-z0-9_-]", "_", os.environ.get("DISPLAY", "default"))
    with (state / f"dock-{display}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        apply_theme()
        window = Dock()
        window.queue()
        Gtk.main()


if __name__ == "__main__":
    main()
