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
from ui_preferences import transition_ms
import gi
gi.require_version("GdkX11", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkX11, GdkPixbuf

loader = SourceFileLoader("dock_windows", str(Path(__file__).resolve().parents[3] / "bin/ooonana-window-list"))
windows = module_from_spec(spec_from_loader(loader.name, loader))
loader.exec_module(windows)
NAMES = windows.PIN_NAMES
ICONS = {"apps": "ooonana-apps", "terminal": "ooonana-terminal", "browser": "ooonana-browser",
         "files": "ooonana-files", "editor": "ooonana-editor", "music": "ooonana-music",
         "openvino": "ooonana-openvino", "tasks": "ooonana-task-manager", "other": "application-x-executable"}
HOVER_MARGIN = 2
DOCK_RADIUS = 16
CSS = b"""
.ooonana-dock { background: #1b1f26; border: 1px solid #343b46; border-radius: 16px; }
.ooonana-dock button { padding: 1px 8px; border: none; border-radius: 11px; background: #1b1f26; box-shadow: none; min-width: 28px; min-height: 48px; transition: background-color 140ms ease-out; }
.ooonana-dock button:hover { background: #303640; }
.ooonana-dock button.active { background: #303640; }
.ooonana-dock button.active:hover { background: #39414b; }
.ooonana-dock button:active, .ooonana-dock button.active:active { background: #22272f; }
.ooonana-dock button.active label { color: #ffb21a; }
.ooonana-dock label { font-size: 9px; color: #b4bdc8; }
.ooonana-dock separator { background: #414957; min-width: 1px; min-height: 24px; margin: 0 2px; }
tooltip { background: #1b1f26; color: #f5f5f7; border: 1px solid #414957; border-radius: 12px; padding: 4px; }
.dock-preview-title { font-size: 10.5pt; font-weight: 700; color: #f5f5f7; }
.dock-preview-caption { font-size: 9.5pt; color: #b4bdc8; }
"""


def fullscreen_on_monitor(tree, area):
    """Visible i3 fullscreen clients only; workspace mode=1 is not a client."""
    def visit(node):
        if node.get("name") in ("__i3", "__i3_scratch"):
            return False
        mode = node.get("fullscreen_mode", 0)
        if mode and node.get("type") in ("con", "floating_con"):
            rect = node.get("rect") or {}
            if mode == 2 or (rect.get("x", 0) < area.x + area.width
                    and area.x < rect.get("x", 0) + rect.get("width", 0)
                    and rect.get("y", 0) < area.y + area.height
                    and area.y < rect.get("y", 0) + rect.get("height", 0)):
                return True
        tiled, floating = node.get("nodes", []), node.get("floating_nodes", [])
        workspaces = [child for child in tiled if child.get("type") == "workspace"]
        if node.get("name") == "content" and workspaces:
            # Each output's content focus order identifies its visible workspace,
            # including an output which does not currently own keyboard focus.
            selected = next((child for identifier in node.get("focus", []) for child in workspaces
                             if child.get("id") == identifier), None)
            tiled = [selected] if selected else []
        elif node.get("layout") in ("tabbed", "stacked") and tiled:
            selected = next((child for identifier in node.get("focus", []) for child in tiled
                             if child.get("id") == identifier), tiled[0])
            tiled = [selected]
        return any(visit(child) for child in tiled + floating)
    return visit(tree)


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
        self.set_resizable(False)
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
        self.row.set_border_width(5)
        self.add(self.row)
        self.snapshot, self.items, self.nodes, self.buttons = {}, [], {}, {}
        self.pending, self.stopped, self.geometry_state = 0, False, None
        self.hover_states, self.motion_source = {}, 0
        self.connect("size-allocate", self.position)
        self.connect("destroy", self.closed)
        self.get_screen().connect("size-changed", lambda *_: self.queue())
        self.get_screen().connect("monitors-changed", lambda *_: self.queue())
        if subscribe:
            threading.Thread(target=self.listen, daemon=True).start()

    def closed(self, *_):
        self.stopped = True
        for source in (self.pending, self.motion_source):
            if source:
                GLib.source_remove(source)
        self.pending = self.motion_source = 0
        if Gtk.main_level():
            Gtk.main_quit()

    def hover(self, _control, _event, key, entered):
        image = self.buttons[key][2]
        duration = transition_ms()
        settings = Gtk.Settings.get_default()
        if settings:
            settings.set_property('gtk-enable-animations', bool(duration))
        target = 0 if entered and duration else HOVER_MARGIN
        self.hover_states[key] = (image, image.get_margin_top(), target,
                                  GLib.get_monotonic_time(), duration * 1000)
        if not self.motion_source:
            self.motion_source = GLib.timeout_add(16, self.animate_hover)
        return False

    def animate_hover(self):
        now = GLib.get_monotonic_time()
        for key, (image, initial, target, start, duration) in list(self.hover_states.items()):
            progress = min(1, (now - start) / duration) if duration else 1
            eased = 1 - (1 - progress) ** 3
            margin = round(initial + (target - initial) * eased)
            # Constant total margins: no dock resize, focus stealing or jitter.
            image.set_margin_top(margin)
            image.set_margin_bottom(2 * HOVER_MARGIN - margin)
            if progress == 1:
                del self.hover_states[key]
        if not self.hover_states or self.stopped:
            self.motion_source = 0
            return False
        return True

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
        radius = min(DOCK_RADIUS, height // 2, width // 2)
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
        if area.width < 380:
            pins = [pin for pin in pins if pin[0] not in ("openvino", "tasks")]
        keys = [pin[0] for pin in pins]
        other = [item for item in self.items if windows.pin_for(item) not in keys]
        if other:
            keys.append("other")
        if list(self.buttons) != keys:
            for widget in self.row.get_children():
                widget.destroy()
            self.hover_states.clear()
            self.buttons = {}
            for key in keys:
                control = Gtk.Button()
                control.set_can_focus(False)
                control.get_accessible().set_name(NAMES.get(key, "Other windows"))
                content = Gtk.Overlay()
                image = Gtk.Image.new_from_icon_name(ICONS[key], Gtk.IconSize.DIALOG)
                image.set_pixel_size(24 if area.width < 520 else 32)
                image.set_halign(Gtk.Align.CENTER)
                image.set_valign(Gtk.Align.CENTER)
                image.set_margin_top(HOVER_MARGIN)
                image.set_margin_bottom(HOVER_MARGIN)
                content.add(image)
                dot = Gtk.Label(label=" ")
                dot.set_halign(Gtk.Align.CENTER)
                dot.set_valign(Gtk.Align.END)
                # Running state must not move the icon away from tile center.
                content.add_overlay(dot)
                content.set_overlay_pass_through(dot, True)
                control.add(content)
                control.connect("clicked", lambda _button, pin=key: self.open(pin))
                control.connect("button-press-event", self.press, key)
                control.set_has_tooltip(True)
                control.connect("query-tooltip", self.tooltip, key)
                control.connect("enter-notify-event", self.hover, key, True)
                control.connect("leave-notify-event", self.hover, key, False)
                self.row.pack_start(control, False, False, 0)
                self.buttons[key] = (control, dot, image)
                if key == "apps":
                    divider = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
                    divider.set_valign(Gtk.Align.CENTER)
                    self.row.pack_start(divider, False, False, 0)
        for key, (control, dot, _image) in self.buttons.items():
            matches = other if key == "other" else [item for item in self.items if windows.pin_for(item) == key]
            style = control.get_style_context()
            (style.add_class if any(item[2] for item in matches) else style.remove_class)("active")
            dot.set_text(str(len(matches)) if len(matches) > 1 else "○" if matches and matches[0][3] else "•" if matches else " ")
            hidden_count = sum(bool(item[3]) for item in matches)
            status = f"{len(matches)} window" + ("s" if len(matches) != 1 else "") if matches else "Not running"
            if hidden_count:
                status += f" · {hidden_count} minimized"
            if any(item[2] for item in matches):
                status += " · Focused"
            control.get_accessible().set_description(status)
        if fullscreen_on_monitor(self.snapshot, area):
            self.hide()
        else:
            self.show_all()
            self.position()
        return False

    def matches(self, key):
        visible_keys = set(self.buttons) - {"other"}
        return [item for item in self.items if (windows.pin_for(item) not in visible_keys if key == "other" else windows.pin_for(item) == key)]

    def tooltip_content(self, key):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(6)
        matches = sorted(self.matches(key), key=lambda item: (not item[2], item[3]))
        heading = Gtk.Box(spacing=12)
        title = Gtk.Label(label=NAMES.get(key, "Other windows"), xalign=0)
        title.get_style_context().add_class("dock-preview-title")
        heading.pack_start(title, True, True, 0)
        if len(matches) > 1:
            count = Gtk.Label(label=f"{len(matches)} windows")
            count.get_style_context().add_class("dock-preview-caption")
            heading.pack_end(count, False, False, 0)
        box.pack_start(heading, False, False, 0)
        if matches:
            item = matches[0]
            picture = preview_image(self.nodes.get(item[0]), item[3])
            if picture:
                box.pack_start(Gtk.Image.new_from_pixbuf(picture), False, False, 0)
            for entry in matches[:3]:
                caption = Gtk.Label(label=entry[1] + (" · Minimized" if entry[3] else ""), xalign=0)
                caption.get_style_context().add_class("dock-preview-caption")
                caption.set_ellipsize(Pango.EllipsizeMode.END)
                caption.set_max_width_chars(36)
                box.pack_start(caption, False, False, 0)
            if len(matches) > 3:
                remaining = Gtk.Label(label=f"+{len(matches) - 3} windows", xalign=0)
                remaining.get_style_context().add_class("dock-preview-caption")
                box.pack_start(remaining, False, False, 0)
        else:
            hint = Gtk.Label(label="Click to open", xalign=0)
            hint.get_style_context().add_class("dock-preview-caption")
            box.pack_start(hint, False, False, 0)
        box.show_all()
        return box

    def tooltip(self, _widget, _x, _y, _keyboard, tooltip, key):
        tooltip.set_custom(self.tooltip_content(key))
        return True

    def open(self, key):
        self.action("--dock-open", key)

    def action(self, action, key):
        command = ["ooonana-window-list", action, key]
        if key == "other":
            command.extend(["--visible-pins", ",".join(pin for pin in self.buttons if pin != "other")])
        run_async(command, lambda *_: None)

    def press(self, _button, event, key):
        if event.button == 3:
            self.action("--dock-actions", key)
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
