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
from dock_model import PinStore, app_groups, click_target, stable_key, visible_groups
from ui_preferences import config_path
import window_menu
import gi
gi.require_version("GdkX11", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkX11, GdkPixbuf, Gio

loader = SourceFileLoader("dock_windows", str(Path(__file__).resolve().parents[3] / "bin/ooonana-window-list"))
windows = module_from_spec(spec_from_loader(loader.name, loader))
loader.exec_module(windows)
NAMES = windows.PIN_NAMES
ICONS = {"apps": "ooonana-apps", "terminal": "ooonana-terminal", "browser": "ooonana-browser",
         "files": "ooonana-files", "editor": "ooonana-editor", "music": "ooonana-music",
         "openvino": "ooonana-openvino", "tasks": "ooonana-task-manager", "other": "view-more-symbolic"}
DOCK_RADIUS = 16
CSS = b"""
.ooonana-dock { background: #1b1f26; background-image: none; box-shadow: none; border: 1px solid #343b46; border-radius: 16px; }
.ooonana-dock button { padding: 1px 8px; border: none; border-radius: 10px; background: #1b1f26; color: #f5f5f7; background-image: none; box-shadow: none; text-shadow: none; min-width: 28px; min-height: 48px; transition: background-color 140ms ease-out; }
.ooonana-dock button.active { background-color: #1b1f26; }
.ooonana-dock button:hover, .ooonana-dock button.active:hover { background-color: #303640; }
.ooonana-dock button:active, .ooonana-dock button.active:active { background-color: #22272f; }
.ooonana-dock button.active label { color: #ffb21a; }
.ooonana-dock button.drop-target { background-color: #303640; outline: 1px solid #ffb21a; outline-offset: -2px; }
.ooonana-dock label { font-size: 9px; color: #b4bdc8; }
.ooonana-dock separator { background: #414957; min-width: 1px; min-height: 24px; margin: 0 2px; }
tooltip { background: #1b1f26; color: #f5f5f7; border: 1px solid #414957; border-radius: 12px; padding: 4px; }
.dock-preview-title { font-size: 10.5pt; font-weight: 700; color: #f5f5f7; }
.dock-preview-caption { font-size: 9.5pt; color: #b4bdc8; }
"""


def fullscreen_on_monitor(tree, area, scale=1):
    """Visible i3 fullscreen clients only; workspace mode=1 is not a client."""
    scale = max(1, int(scale))
    left, top = area.x * scale, area.y * scale
    width, height = area.width * scale, area.height * scale
    def visit(node):
        if node.get("name") in ("__i3", "__i3_scratch"):
            return False
        mode = node.get("fullscreen_mode", 0)
        if mode and node.get("type") in ("con", "floating_con"):
            rect = node.get("rect") or {}
            if mode == 2 or (rect.get("x", 0) < left + width
                    and left < rect.get("x", 0) + rect.get("width", 0)
                    and rect.get("y", 0) < top + height
                    and top < rect.get("y", 0) + rect.get("height", 0)):
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
        self.groups, self.names, self.catalog = {}, dict(NAMES), {}
        self.overflow, self.recent, self.app_order = [], [], []
        self.pins = PinStore(config_path().with_name("dock.json"),
                             [{"key": key} for key, *_ in windows.available_pins() if key != "apps"])
        self.app_order = list(self.pins.order)
        self.app_ids = {}
        self.drag_key, self.click_suppressed_until = None, 0
        self.layout_pending, self.problem = False, ""
        self.menu, self.button_state = None, None
        self.app_monitor = Gio.AppInfoMonitor.get()
        self.app_monitor_handler = self.app_monitor.connect("changed", self.catalog_changed)
        self.catalog_changed()
        self.connect("size-allocate", self.position)
        self.connect("destroy", self.closed)
        self.get_screen().connect("size-changed", lambda *_: self.queue())
        self.get_screen().connect("monitors-changed", lambda *_: self.queue())
        if subscribe:
            threading.Thread(target=self.listen, daemon=True).start()

    def closed(self, *_):
        self.stopped = True
        if self.pending:
            GLib.source_remove(self.pending)
        self.pending = 0
        self.app_monitor.disconnect(self.app_monitor_handler)
        if self.menu:
            self.menu.destroy()
            self.menu = None
        if Gtk.main_level():
            Gtk.main_quit()

    def catalog_changed(self, *_):
        self.catalog = {}
        self.app_ids = {}
        for app in Gio.AppInfo.get_all():
            if not app.should_show():
                continue
            if app.get_id():
                self.app_ids[app.get_id()] = app
            names = [(app.get_id() or "").removesuffix(".desktop")]
            wm_class = getattr(app, "get_startup_wm_class", lambda: None)()
            if wm_class:
                names.append(wm_class)
            executable = Path(app.get_executable() or "").name
            if executable not in ("", "sh", "bash", "env", "python", "python3"):
                names.append(executable)
            for name in names:
                if name:
                    self.catalog.setdefault(name.casefold(), app)
        self.button_state = None
        self.queue()

    def app_info(self, key):
        saved = next((record.get("desktop") for record in self.pins.records if record["key"] == key), None)
        if saved:
            return self.app_ids.get(saved)
        identity = {"terminal": "xterm", "browser": "chromium", "files": "nemo", "editor": "geany",
                    "tasks": "ooonana-task-manager", "music": "ooonana-music", "apps": "ooonana-apps"}.get(key, key.removeprefix("class:"))
        return self.catalog.get(identity)

    def app_image(self, key, size):
        icon_name = ICONS.get(key, "ooonana-controls" if key in ("ooonana-sound", "ooonana-brightness", "ooonana-power") else key if key.startswith("ooonana-") else None)
        if icon_name:
            asset = Path(__file__).resolve().parents[3] / "share/icons/hicolor/scalable/apps" / (icon_name + ".svg")
            image = (Gtk.Image.new_from_gicon(Gio.FileIcon.new(Gio.File.new_for_path(str(asset))), Gtk.IconSize.DIALOG)
                     if asset.is_file() else Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG))
        elif (app := self.app_info(key)) and app.get_icon():
            image = Gtk.Image.new_from_gicon(app.get_icon(), Gtk.IconSize.DIALOG)
        else:
            fallback = "ooonana-controls" if key in ("ooonana-sound", "ooonana-brightness", "ooonana-power") else "application-x-executable"
            image = Gtk.Image.new_from_icon_name(fallback, Gtk.IconSize.DIALOG)
        image.set_pixel_size(size)
        return image

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
            self.pending = GLib.timeout_add(60, self.flush)
        return False

    def flush(self):
        self.pending = 0
        return self.refresh()

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
        if self.pending:
            GLib.source_remove(self.pending)
        self.pending = 0
        if self.stopped:
            return False
        snapshot = self.snapshot
        self.items = windows.windows(snapshot)
        self.nodes = {node["id"]: node for node, _hidden in windows.leaves(snapshot)}
        area = self.monitor_geometry()
        geometry = (area.x, area.y, area.width, area.height)
        if self.geometry_state is not None and geometry != self.geometry_state:
            run_async(["ooonana-panel-start", "--panel-only"], lambda *_: None)
        self.geometry_state = geometry
        groups, hints = app_groups(self.items, self.nodes, windows.pin_for)
        priority = [key for key in self.pins.order if key in groups]
        self.app_order = priority + [key for key in self.app_order if key in groups and key not in priority] + [key for key in groups if key not in self.app_order and key not in priority]
        self.groups = {key: groups[key] for key in self.app_order}
        pin_keys = [record["key"] for record in self.pins.records]
        self.names = dict(NAMES)
        self.names["other"] = "More apps"
        for key in set(self.groups) | set(pin_keys):
            if key not in NAMES:
                app = self.app_info(key)
                self.names[key] = " ".join((app.get_display_name() if app else hints.get(key, key.removeprefix("class:"))).split())
        focused = next((item[0] for item in self.items if item[2]), None)
        identifiers = {item[0] for item in self.items}
        self.recent = ([focused] if focused else []) + [identifier for identifier in self.recent if identifier != focused and identifier in identifiers]
        self.recent = self.recent[:256]
        keys, self.overflow = visible_groups(self.groups, ["apps", *pin_keys], area.width)
        icon_size = 24 if area.width < 520 else 32
        state = (tuple(keys), icon_size, tuple(pin_keys))
        if self.button_state != state:
            if self.menu:
                self.menu.destroy()
                self.menu = None
            for widget in self.row.get_children():
                widget.destroy()
            self.buttons = {}
            previous_section = None
            for key in keys:
                section = "pinned" if key in pin_keys else "running"
                if key != "apps" and previous_section == "pinned" and section == "running":
                    divider = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
                    divider.set_valign(Gtk.Align.CENTER)
                    self.row.pack_start(divider, False, False, 0)
                control = Gtk.Button()
                control.set_can_focus(False)
                control.get_accessible().set_name(self.names.get(key, "Other windows"))
                content = Gtk.Overlay()
                image = self.app_image(key, icon_size)
                image.set_halign(Gtk.Align.CENTER)
                image.set_valign(Gtk.Align.CENTER)
                content.add(image)
                dot = Gtk.Label(label=" ")
                dot.set_halign(Gtk.Align.CENTER)
                dot.set_valign(Gtk.Align.END)
                # Running state must not move the icon away from tile center.
                content.add_overlay(dot)
                content.set_overlay_pass_through(dot, True)
                control.add(content)
                control.connect("clicked", self.clicked, key)
                control.connect("button-press-event", self.press, key)
                control.set_has_tooltip(True)
                control.connect("query-tooltip", self.tooltip, key)
                self.row.pack_start(control, False, False, 0)
                self.buttons[key] = (control, dot, image)
                if key not in ("apps", "other") and stable_key(key):
                    target = Gtk.TargetEntry.new("application/x-ooonana-dock-app", Gtk.TargetFlags.SAME_APP, 0)
                    control.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [target], Gdk.DragAction.MOVE)
                    control.drag_dest_set(Gtk.DestDefaults.ALL, [target], Gdk.DragAction.MOVE)
                    control.connect("drag-begin", self.drag_begin, key)
                    control.connect("drag-data-get", self.drag_data_get, key)
                    control.connect("drag-data-received", self.drag_received, key)
                    control.connect("drag-end", self.drag_end)
                    control.connect("drag-leave", lambda widget, *_: widget.get_style_context().remove_class("drop-target"))
                    control.connect("drag-motion", lambda widget, *_: (widget.get_style_context().add_class("drop-target"), False)[1])
                if key == "apps":
                    divider = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
                    divider.set_valign(Gtk.Align.CENTER)
                    self.row.pack_start(divider, False, False, 0)
                else:
                    previous_section = section
            self.button_state = state
        for key, (control, dot, _image) in self.buttons.items():
            matches = self.matches(key)
            style = control.get_style_context()
            (style.add_class if any(item[2] for item in matches) else style.remove_class)("active")
            dot.set_text(str(len(matches)) if len(matches) > 1 else "○" if matches and matches[0][3] else "•" if matches else " ")
            hidden_count = sum(bool(item[3]) for item in matches)
            status = f"{len(matches)} window" + ("s" if len(matches) != 1 else "") if matches else "Not running"
            if hidden_count:
                status += f" · {hidden_count} minimized"
            if any(item[2] for item in matches):
                status += " · Focused"
            if key == "other":
                status = f"{len(self.overflow)} apps · {len(matches)} windows"
            control.get_accessible().set_description(status)
        if fullscreen_on_monitor(snapshot, area, self.get_scale_factor()):
            self.hide()
        else:
            self.show_all()
            self.position()
        return False

    def matches(self, key):
        return [item for group in self.overflow for item in self.groups.get(group, [])] if key == "other" else self.groups.get(key, [])

    def tooltip_content(self, key):
        budget = min(300, max(160, self.monitor_geometry().width - 24))
        def bounded(label, width):
            char_width = max(1, label.create_pango_layout("M").get_pixel_size()[0])
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_max_width_chars(max(3, int(width) // char_width))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(6)
        matches = sorted(self.matches(key), key=lambda item: (not item[2], item[3]))
        heading = Gtk.Box(spacing=12)
        title = Gtk.Label(label=self.names.get(key, "Other windows"), xalign=0)
        title.get_style_context().add_class("dock-preview-title")
        heading.pack_start(title, True, True, 0)
        if len(matches) > 1:
            count = Gtk.Label(label=f"{len(matches)} windows")
            count.get_style_context().add_class("dock-preview-caption")
            heading.pack_end(count, False, False, 0)
            title_width = budget - 24 - count.create_pango_layout(count.get_text()).get_pixel_size()[0]
        else:
            title_width = budget - 12
        bounded(title, title_width)
        box.pack_start(heading, False, False, 0)
        if matches:
            item = matches[0]
            picture = preview_image(self.nodes.get(item[0]), item[3])
            if picture:
                box.pack_start(Gtk.Image.new_from_pixbuf(picture), False, False, 0)
            for entry in matches[:3]:
                caption = Gtk.Label(label=entry[1] + (" · Minimized" if entry[3] else ""), xalign=0)
                caption.get_style_context().add_class("dock-preview-caption")
                bounded(caption, budget - 12)
                box.pack_start(caption, False, False, 0)
            if len(matches) > 3:
                remaining = Gtk.Label(label=f"+{len(matches) - 3} windows", xalign=0)
                remaining.get_style_context().add_class("dock-preview-caption")
                box.pack_start(remaining, False, False, 0)
        else:
            available = key in NAMES or self.app_info(key)
            hint = Gtk.Label(label="Click for pinned apps and windows" if key == "other" else "Click to open" if available else "App unavailable · reinstall or unpin", xalign=0)
            hint.get_style_context().add_class("dock-preview-caption")
            bounded(hint, budget - 12)
            box.pack_start(hint, False, False, 0)
        box.show_all()
        return box

    def tooltip(self, _widget, _x, _y, _keyboard, tooltip, key):
        tooltip.set_custom(self.tooltip_content(key))
        return True

    def open(self, key):
        self.problem = ""
        if key == "other":
            self.show_menu(key)
            return
        target = click_target(self.matches(key), self.recent)
        if target:
            self.perform(target, "show", self.nodes.get(target[0], {}).get("window"))
        elif key in NAMES:
            self.action("--dock-open", key)
        elif (app := self.app_info(key)):
            try:
                app.launch([], self.get_display().get_app_launch_context())
            except GLib.Error as exc:
                self.problem = str(exc)
                self.show_menu(key)
        else:
            self.problem = "App launcher unavailable. Reinstall app or unpin."
            self.show_menu(key)

    def clicked(self, _button, key):
        if not self.drag_key and GLib.get_monotonic_time() >= self.click_suppressed_until:
            self.open(key)

    def save_layout(self, records, order=None):
        if not self.pins.save(records, order):
            return False
        self.app_order = list(self.pins.order) + [key for key in self.app_order if key not in self.pins.order]
        if self.drag_key:
            self.layout_pending = True
        else:
            self.refresh()
        return True

    def toggle_pin(self, key):
        records = [record for record in self.pins.records if record["key"] != key]
        if len(records) == len(self.pins.records):
            app = self.app_info(key)
            desktop = app.get_id() if app and app.get_id() in self.app_ids else None
            if key not in NAMES and not desktop:
                return
            records.append({"key": key, **({"desktop": desktop} if desktop and key not in NAMES else {})})
        if not self.save_layout(records):
            GLib.idle_add(lambda: (self.show_menu(key), False)[1] if key in self.buttons or "other" in self.buttons else False)

    def reorder(self, source, target):
        pinned = [record["key"] for record in self.pins.records]
        if source == target or source in ("apps", "other") or target in ("apps", "other"):
            return False
        if (source in pinned) != (target in pinned):
            return False  # Pin/Unpin is explicit; dragging never changes app lifetime.
        if source in pinned:
            records = list(self.pins.records)
            moving = records.pop(pinned.index(source))
            records.insert(pinned.index(target), moving)
            return self.save_layout(records)
        order = [key for key in self.app_order if key not in pinned and stable_key(key)]
        if source not in order or target not in order:
            return False
        original = order.index(target)
        order.remove(source)
        order.insert(original, source)
        return self.save_layout(list(self.pins.records), order)

    def drag_begin(self, _button, context, key):
        self.drag_key = key
        gicon = self.buttons[key][2].get_gicon()[0]
        if not gicon and (name := self.buttons[key][2].get_icon_name()[0]):
            gicon = Gio.ThemedIcon.new(name)
        if gicon:
            Gtk.drag_set_icon_gicon(context, gicon, 16, 16)

    def drag_data_get(self, _button, _context, selection, _info, _time, key):
        selection.set(selection.get_target(), 8, key.encode("utf-8"))

    def drag_received(self, _button, context, _x, _y, selection, _info, timestamp, target):
        data = selection.get_data()
        try:
            source = data.decode("utf-8") if data and len(data) <= 1024 else ""
        except UnicodeError:
            source = ""
        success = source == self.drag_key and source in self.buttons and self.reorder(source, target)
        Gtk.drag_finish(context, bool(success), False, timestamp)

    def drag_end(self, *_):
        self.drag_key = None
        self.click_suppressed_until = GLib.get_monotonic_time() + 200_000
        for control, *_ in self.buttons.values():
            control.get_style_context().remove_class("drop-target")
        if self.layout_pending:
            self.layout_pending = False
            GLib.idle_add(self.refresh)

    def action(self, action, key):
        command = ["ooonana-window-list", action, key]
        run_async(command, lambda *_: None)

    def perform(self, item, action, xid):
        if isinstance(xid, int) and xid > 0:
            run_async(["ooonana-window-list", "--window-action", action, str(item[0]), "--expect-xid", str(xid)], lambda *_: None)

    def menu_label(self, text):
        label = Gtk.Label(label=text, xalign=0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        char_width = max(1, label.create_pango_layout("M").get_pixel_size()[0])
        label.set_max_width_chars(max(4, min(34, (self.monitor_geometry().width - 96) // char_width)))
        label.set_tooltip_text(text)
        return label

    def context_menu(self, key):
        menu = Gtk.Menu()
        menu.get_accessible().set_name(self.names.get(key, "Other windows") + " dock options")
        self.menu_heading(menu, self.names.get(key, "Other windows"))
        matches = sorted(self.matches(key), key=lambda item: (not item[2], item[3]))
        idle = [group for group in self.overflow if not self.groups.get(group)] if key == "other" else []
        if idle:
            menu.append(Gtk.SeparatorMenuItem())
            for group in idle:
                row = Gtk.MenuItem()
                row.add(self.menu_label(self.names.get(group, group) + " · Open"))
                row.get_accessible().set_name(self.names.get(group, group) + " · Open")
                row.ooonana_app = group
                row.connect("activate", lambda _row, group=group: self.open(group))
                row.connect("button-press-event", self.app_row_actions, group)
                menu.append(row)
        if matches and (len(matches) > 1 or key == "other"):
            menu.append(Gtk.SeparatorMenuItem())
            for item in matches:
                text = item[1] + (" · Minimized" if item[3] else "")
                row = Gtk.MenuItem()
                box = Gtk.Box(spacing=10)
                glyph = "emblem-default-symbolic" if item[2] else "view-restore-symbolic" if item[3] else "window-new-symbolic"
                box.pack_start(Gtk.Image.new_from_icon_name(glyph, Gtk.IconSize.MENU), False, False, 0)
                box.pack_start(self.menu_label(text), True, True, 0)
                row.add(box)
                xid = self.nodes.get(item[0], {}).get("window")
                row.connect("activate", lambda _row, item=item, xid=xid: self.perform(item, "show", xid))
                row.connect("button-press-event", self.row_actions, key, item, xid)
                row.connect("key-press-event", self.row_keys, key, item, xid)
                row.ooonana_window = (item, xid)
                row.set_tooltip_text(text + "\nClick to show; right-click or Shift+F10 for this window's actions.")
                row.get_accessible().set_name(text + (" · Focused" if item[2] else ""))
                menu.append(row)
            menu.append(Gtk.SeparatorMenuItem())
        menu.connect("key-press-event", self.menu_keys, key)
        if matches:
            item = click_target(matches, self.recent)
            if len(matches) > 1 or key == "other":
                self.menu_heading(menu, "Actions: " + item[1])
            else:
                menu.append(Gtk.SeparatorMenuItem())
            xid = self.nodes.get(item[0], {}).get("window")
            window_menu.append_actions(menu, item[3], lambda action: self.perform(item, action, xid),
                                       bool(self.nodes.get(item[0], {}).get("fullscreen_mode")))
        app = self.app_info(key)
        if app and "new-window" in getattr(app, "list_actions", lambda: [])():
            menu.append(Gtk.SeparatorMenuItem())
            new_window = Gtk.MenuItem.new_with_label("New window")
            new_window.connect("activate", lambda *_: app.launch_action("new-window", self.get_display().get_app_launch_context()))
            menu.append(new_window)
        if not matches and key != "other":
            menu.append(Gtk.SeparatorMenuItem())
            launch = Gtk.MenuItem.new_with_label("Open " + self.names[key])
            launch.set_sensitive(bool(key in NAMES or app))
            launch.connect("activate", lambda *_: self.open(key))
            menu.append(launch)
        self.pin_actions(menu, key)
        return menu

    def pin_actions(self, menu, key):
        if key in ("apps", "other"):
            return
        if self.pins.error or self.problem:
            warning = self.menu_heading(menu, "Dock changes not saved" if self.pins.error else "App could not open", "status-bad")
            detail = (self.pins.error + "\nCheck dock.json permissions/contents and retry." if self.pins.error else self.problem)
            warning.set_tooltip_text(detail)
            warning.get_accessible().set_description(detail)
        pinned = [record["key"] for record in self.pins.records]
        app = self.app_info(key)
        can_pin = key in NAMES or app and app.get_id() in self.app_ids
        menu.append(Gtk.SeparatorMenuItem())
        pin = Gtk.MenuItem.new_with_label("Unpin from dock" if key in pinned else "Pin to dock")
        pin.set_sensitive(bool(key in pinned or can_pin))
        pin.set_tooltip_text("Keeps running windows open" if key in pinned else "Requires an installed application launcher" if not can_pin else "Keep this app available after its windows close")
        pin.connect("activate", lambda *_: self.toggle_pin(key))
        menu.append(pin)
        order = pinned if key in pinned else [item for item in self.app_order if item not in pinned and stable_key(item)]
        if key in order and len(order) > 1:
            for offset, text in ((-1, "Move left"), (1, "Move right")):
                index = order.index(key) + offset
                row = Gtk.MenuItem.new_with_label(text)
                row.set_sensitive(0 <= index < len(order))
                if 0 <= index < len(order):
                    row.connect("activate", lambda _row, target=order[index]: self.reorder(key, target))
                menu.append(row)

    def menu_heading(self, menu, text, style="muted"):
        heading = Gtk.MenuItem()
        label = self.menu_label(text)
        label.get_style_context().add_class(style)
        heading.add(label)
        heading.set_sensitive(False)
        menu.append(heading)
        return heading

    def row_actions(self, _row, event, key, item, xid):
        if event.button != 3:
            return False
        self.window_actions(key, item, xid, event)
        return True

    def row_keys(self, _row, event, key, item, xid):
        if event.keyval == Gdk.KEY_Menu or (event.keyval == Gdk.KEY_F10 and event.state & Gdk.ModifierType.SHIFT_MASK):
            self.window_actions(key, item, xid, event, keyboard=True)
            return True
        return False

    def menu_keys(self, menu, event, key):
        row = menu.get_selected_item()
        target = getattr(row, "ooonana_window", None)
        if target:
            return self.row_keys(row, event, key, *target)
        app = getattr(row, "ooonana_app", None)
        if app and (event.keyval == Gdk.KEY_Menu or event.keyval == Gdk.KEY_F10 and event.state & Gdk.ModifierType.SHIFT_MASK):
            self.app_options(app, event, keyboard=True)
            return True
        return False

    def app_row_actions(self, _row, event, key):
        if event.button != 3:
            return False
        self.app_options(key, event)
        return True

    def app_options(self, key, event, keyboard=False):
        event = event.copy()
        event.window = Gdk.get_default_root_window()
        if self.menu:
            self.menu.popdown()
        GLib.idle_add(lambda: (self.show_menu(key, event, keyboard), False)[1] if not self.stopped else False)

    def window_actions(self, key, item, xid, event=None, keyboard=False):
        # Release the app menu's grab before showing one flat per-window menu.
        if event is not None:
            event = event.copy()
            event.window = Gdk.get_default_root_window()
        if self.menu:
            self.menu.popdown()
        def show():
            if self.stopped:
                return False
            self.menu = Gtk.Menu()
            self.menu_heading(self.menu, item[1])
            window_menu.append_actions(self.menu, item[3], lambda action: self.perform(item, action, xid),
                                       bool(self.nodes.get(item[0], {}).get("fullscreen_mode")))
            group = next((group for group, entries in self.groups.items() if any(entry[0] == item[0] for entry in entries)), None)
            if group:
                self.pin_actions(self.menu, group)
            self.menu.connect("deactivate", lambda menu: GLib.idle_add(self.menu_closed, menu))
            control = self.buttons.get(key, (None,))[0]
            window_menu.popup(self.menu, widget=control, event=event, keyboard=keyboard)
            return False
        GLib.idle_add(show)

    def show_menu(self, key, event=None, keyboard=False):
        if self.menu:
            self.menu.destroy()
        self.menu = self.context_menu(key)
        self.menu.connect("deactivate", lambda menu: GLib.idle_add(self.menu_closed, menu))
        anchor = self.buttons.get(key, self.buttons.get("other", (None,)))[0]
        window_menu.popup(self.menu, widget=anchor, event=event or Gtk.get_current_event(), keyboard=keyboard)

    def menu_closed(self, menu):
        if self.menu is menu:
            self.menu = None
        menu.destroy()
        return False

    def press(self, _button, event, key):
        if event.button == 3:
            self.show_menu(key, event)
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
