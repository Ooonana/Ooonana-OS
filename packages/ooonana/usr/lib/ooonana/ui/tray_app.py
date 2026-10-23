#!/usr/bin/env python3
"""Compact indicator overflow. App-owned actions stay on their original bus peer."""
import hashlib
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import Gdk, GLib, Gtk, Pango, apply_theme, button, header, icon, label
from gi.repository import Gio, GdkPixbuf
from tray_model import MAX_ITEMS, menu_nodes, text
from tray_service import TrayService, WATCHER


class TrayWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Ooonana Background Apps")
        self.app, self.rows, self.menu, self.menu_signals = app, {}, None, []
        self.loading, self.activating = set(), set()
        self.menu_epoch, self.menu_item, self.menu_path = 0, None, ""
        self.set_wmclass("ooonana-tray", "OoonanaTray")
        self.set_default_size(380, -1)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.set_skip_taskbar_hint(True)
        bar = header(self, "Background apps", "", "")
        # Transient overflow has Close/Escape, not hidden minimized sessions.
        def compact_controls(container):
            for child in container.get_children():
                if child.get_name() in ("ooonana-window-minimize", "ooonana-window-fullscreen"):
                    child.set_no_show_all(True); child.hide()
                elif isinstance(child, Gtk.Container): compact_controls(child)
        compact_controls(bar)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_border_width(12); self.add(root)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        scroll = self.scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_propagate_natural_height(True)
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        area = monitor.get_workarea()
        self.set_default_size(min(380, max(200, area.width - 24)), -1)
        scroll.set_max_content_height(max(120, min(320, area.height - 160)))
        self.list_limit = max(120, min(320, area.height - 160))
        scroll.set_min_content_height(72)
        scroll.add(self.list); root.pack_start(scroll, True, True, 0)
        self.empty = label("No background apps registered.", "muted")
        self.empty.set_margin_top(16); self.empty.set_margin_bottom(16)
        self.list.pack_start(self.empty, False, False, 0)
        self.status = label("App menus stay available here.", "muted")
        self.status.set_lines(3); self.status.set_ellipsize(Pango.EllipsizeMode.END)
        root.pack_start(self.status, False, False, 0)
        self.connect("delete-event", self.hidden)
        self.connect("key-press-event", self.key)
        self.connect("unmap", lambda *_: self.close_menu())
        self.connect("map-event", lambda *_: (GLib.timeout_add(80, self.position), False)[1])

    def position(self):
        if not self.get_visible(): return False
        point = self.get_display().get_default_seat().get_pointer().get_position()
        monitor = self.get_display().get_monitor_at_point(point.x, point.y)
        area = monitor.get_workarea(); width, height = self.get_size()
        self.move(max(area.x + 8, min(point.x - width + 24, area.x + area.width - width - 8)),
                  max(area.y + 8, min(56, area.y + area.height - height - 8)))
        return False

    def hidden(self, *_args):
        self.close_menu(); self.hide()
        return True

    def key(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            return self.hidden()
        return False

    def refresh(self):
        service = self.app.service
        if service is None or service.closed: return
        if self.menu_item is not None and (not service.current(self.menu_item) or self.menu_item.props.get("Menu") != self.menu_path):
            self.close_menu(); self.feedback("App no longer available.")
        for identifier in list(self.rows):
            if identifier not in service.items:
                row = self.rows.pop(identifier)
                focused = self.get_focus()
                needs_focus = focused is not None and (focused == row[0] or focused.is_ancestor(row[0]))
                row[0].destroy()
                if needs_focus and self.get_visible() and self.rows:
                    next(iter(self.rows.values()))[1].grab_focus()
        for identifier, item in service.items.items():
            if identifier not in self.rows:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                main = Gtk.Button(); main.set_hexpand(True)
                content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                image = Gtk.Image(); image.set_pixel_size(24); image.set_size_request(24, 24)
                title = label("Loading…", wrap=False); title.set_ellipsize(Pango.EllipsizeMode.END); title.set_max_width_chars(32)
                title.set_hexpand(True)
                content.pack_start(image, False, False, 0); content.pack_start(title, True, True, 0)
                main.add(content)
                more = button("", "view-more-symbolic", lambda widget, item=item: self.open_menu(item, widget))
                more.set_tooltip_text("App menu"); more.get_accessible().set_name("App menu")
                main.connect("clicked", lambda widget, item=item: self.activate(item, widget))
                row.pack_start(main, True, True, 0); row.pack_start(more, False, False, 0)
                self.list.pack_start(row, False, False, 0)
                self.rows[identifier] = row, main, more, image, title
                row.show_all()
            row, main, more, image, title = self.rows[identifier]
            name = item.props.get("Title") or item.props.get("Id") or item.bus
            title.set_text(name)
            main.get_accessible().set_name(name)
            more.get_accessible().set_name(name + " menu")
            main.set_tooltip_text(item.props.get("ToolTip") or name)
            more.set_sensitive(item not in self.loading)
            if item.image:
                width, height, data = item.image
                pixels = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(data), GdkPixbuf.Colorspace.RGB, True, 8, width, height, width * 4)
                factor = 24 / max(width, height)
                image.set_from_pixbuf(pixels.scale_simple(max(1, round(width * factor)), max(1, round(height * factor)), GdkPixbuf.InterpType.BILINEAR))
            else:
                name = item.props.get("AttentionIconName") if item.props.get("Status") == "NeedsAttention" else item.props.get("IconName")
                image.set_from_icon_name(name if name and "/" not in name else "application-x-executable-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
            row.get_style_context().remove_class("status-warn")
            if item.props.get("Status") == "NeedsAttention": row.get_style_context().add_class("status-warn")
        self.empty.set_visible(not self.rows)
        row_height = max((row[0].get_preferred_height()[1] for row in self.rows.values()), default=32)
        self.scroll.set_min_content_height(min(self.list_limit, max(72, min(6, len(self.rows)) * (row_height + 4))))

    def feedback(self, value):
        self.status.set_text(text(value, 384))

    def activate(self, item, widget):
        if not self.app.service.current(item) or item in self.activating: return
        if item.props.get("ItemIsMenu"):
            return self.open_menu(item, widget)
        widget.set_sensitive(False)
        self.activating.add(item)
        def done(_value, error):
            self.activating.discard(item)
            if not self.app.service.current(item): return
            widget.set_sensitive(True)
            self.feedback("App unavailable. Open menu to retry." if error else "App activated.")
        pointer = self.get_display().get_default_seat().get_pointer().get_position()
        self.app.service.action(item, "Activate", pointer.x, pointer.y, done)

    def close_menu(self):
        self.menu_epoch += 1
        self.menu_item = None
        self.menu_path = ""
        for subscription in self.menu_signals: self.app.service.bus.signal_unsubscribe(subscription)
        self.menu_signals.clear()
        if self.menu is not None:
            menu, self.menu = self.menu, None
            menu.popdown(); menu.destroy()

    def open_menu(self, item, anchor):
        service = self.app.service
        if not service.current(item) or item in self.loading: return
        self.close_menu()
        epoch = self.menu_epoch
        # Get current input now, not in asynchronous D-Bus reply callback.
        trigger = Gtk.get_current_event()
        if trigger is None:
            trigger = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
            trigger.window = anchor.get_window()
            trigger.time, trigger.button = Gtk.get_current_event_time(), 1
            trigger.set_device(self.get_display().get_default_seat().get_pointer())
        path = item.props.get("Menu")
        if not path:
            point = self.get_display().get_default_seat().get_pointer().get_position()
            service.action(item, "ContextMenu", point.x, point.y, lambda _value, error: self.feedback("No app menu available." if error else "App menu requested."))
            return
        anchor.set_sensitive(False)
        self.loading.add(item)
        self.feedback("Loading app menu…")
        def valid():
            return self.menu_epoch == epoch and service.current(item) and item.props.get("Menu") == path and self.get_visible()
        def layout(value, error):
            self.loading.discard(item)
            if service.current(item): anchor.set_sensitive(True)
            if not valid(): return
            node = menu_nodes(value[1]) if not error and value and len(value) == 2 else None
            if node is None or not node["children"]:
                self.feedback("Menu unavailable. Try again."); return
            self.menu = self.build_menu(item, path, node["children"])
            self.menu_item = item
            self.menu_path = path
            def changed(*_args):
                self.close_menu(); self.feedback("App menu changed. Open it again.")
            for signal in ("LayoutUpdated", "ItemsPropertiesUpdated"):
                self.menu_signals.append(service.bus.signal_subscribe(item.owner, "com.canonical.dbusmenu", signal, path,
                    None, Gio.DBusSignalFlags.NONE, changed))
            self.menu.connect("deactivate", lambda menu: GLib.idle_add(self.menu_finished, menu))
            self.menu.show_all()
            self.menu.popup_at_widget(anchor, Gdk.Gravity.SOUTH_EAST, Gdk.Gravity.NORTH_EAST, trigger)
            self.feedback("App menu ready.")
        def get_layout(*_args):
            if not valid():
                self.loading.discard(item)
                if service.current(item): anchor.set_sensitive(True)
                return
            service.call(item.owner, path, "com.canonical.dbusmenu", "GetLayout",
                GLib.Variant("(iias)", (0, 3, ["label", "enabled", "visible", "type", "toggle-type", "toggle-state", "children-display"])), layout, item.cancel)
        service.call(item.owner, path, "com.canonical.dbusmenu", "AboutToShow", GLib.Variant("(i)", (0,)), get_layout, item.cancel)

    def menu_finished(self, menu):
        if self.menu is menu: self.close_menu()
        return False

    def build_menu(self, item, path, nodes):
        menu = Gtk.Menu()
        for node in nodes:
            if node["separator"]:
                widget = Gtk.SeparatorMenuItem()
            elif node["toggle"]:
                widget = Gtk.CheckMenuItem.new_with_mnemonic(node["label"])
                widget.set_draw_as_radio(node["toggle"] == "radio"); widget.set_active(node["checked"])
            else:
                widget = Gtk.MenuItem.new_with_mnemonic(node["label"])
            widget.set_sensitive(node["enabled"])
            child = widget.get_child()
            if isinstance(child, Gtk.Label):
                child.set_max_width_chars(40); child.set_ellipsize(Pango.EllipsizeMode.END)
            if node["children"]:
                widget.set_submenu(self.build_menu(item, path, node["children"]))
            elif not node["separator"]:
                def activate(_widget, identifier=node["id"]):
                    service = self.app.service
                    if not service.current(item) or item.props.get("Menu") != path: return
                    service.call(item.owner, path, "com.canonical.dbusmenu", "Event",
                        GLib.Variant("(isvu)", (identifier, "clicked", GLib.Variant("s", ""), Gtk.get_current_event_time())),
                        lambda _value, error: self.feedback("App action failed. Reopen menu to retry." if error else "App action requested."), item.cancel)
                widget.connect("activate", activate)
            menu.append(widget)
        return menu


class TrayApplication(Gtk.Application):
    def __init__(self):
        display = hashlib.sha256(os.environ.get("DISPLAY", "default").encode()).hexdigest()[:16]
        super().__init__(application_id="org.ooonana.Tray.x" + display, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window, self.service, self.error_text = None, None, ""

    def do_startup(self):
        Gtk.Application.do_startup(self)
        apply_theme()
        self.service = TrayService(self.changed, self.failed)
        self.hold()

    def changed(self):
        if self.window is not None: self.window.refresh()

    def failed(self, value):
        self.error_text = text(value, 384)
        if self.window is not None: self.window.feedback(self.error_text)

    def do_activate(self):
        if self.window is None:
            self.window = TrayWindow(self)
        if self.window.get_visible():
            self.window.hidden(); return
        self.window.refresh(); self.window.show_all(); self.window.empty.set_visible(not self.window.rows)
        if self.error_text: self.window.feedback(self.error_text)
        self.window.present()
        if self.window.rows: next(iter(self.window.rows.values()))[1].grab_focus()

    def do_command_line(self, command):
        args = command.get_arguments()[1:]
        if args not in ([], ["--toggle"], ["--background"]): return 2
        if args != ["--background"]: self.activate()
        return 0

    def do_shutdown(self):
        if self.window is not None: self.window.close_menu()
        if self.service is not None:
            try: self.service.close()
            except GLib.Error: pass  # Session bus may already be gone at logout.
        Gtk.Application.do_shutdown(self)


def main():
    if sys.argv[1:] not in ([], ["--toggle"], ["--background"], ["--wait-ready"], ["--dry-run"]):
        print("usage: ooonana-tray [--toggle|--background|--wait-ready|--dry-run]", file=sys.stderr)
        return 2
    if sys.argv[1:] == ["--dry-run"]:
        print("native GTK indicator overflow; session bus only; real app-owned menus")
        print("OOONANA_TRAY_NATIVE_OK")
        return 0
    if sys.argv[1:] == ["--wait-ready"]:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        loop = GLib.MainLoop(); ready = [False]
        watch = Gio.bus_watch_name_on_connection(bus, WATCHER, Gio.BusNameWatcherFlags.NONE,
            lambda *_: (ready.__setitem__(0, True), loop.quit()), None)
        timer = GLib.timeout_add_seconds(5, lambda: (loop.quit(), False)[1])
        loop.run(); Gio.bus_unwatch_name(watch)
        if ready[0]: GLib.source_remove(timer)
        return 0 if ready[0] else 1
    return TrayApplication().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
