"""Single-instance, opaque desktop flyouts. Full applications keep normal frames."""
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import i3_events
from shell_client import application_id
from common import Gdk, Gio, GLib, Gtk, Pango, apply_theme, button, flow_row, header, icon, label, launch, run

SPECS = {
    "apps": ("Applications", 560, 520, "bottom"),
    "notifications": ("Notifications", 440, 520, "right"),
    "controls": ("Control center", 440, 460, "right"),
    "audio": ("Sound", 460, 360, "right"),
    "brightness": ("Brightness", 420, 260, "right"),
    "wifi": ("Wi-Fi", 560, 520, "right"),
    "bluetooth": ("Bluetooth", 520, 500, "right"),
    "power": ("Power", 420, 360, "right"),
}


def anchor_geometry(area, size, anchor):
    x, y, width, height = area
    margin, top, bottom = min(12, width // 4), min(56, height // 4), min(84, height // 4)
    w = max(1, min(size[0], width - 2 * margin))
    h = max(1, min(size[1], height - top - bottom))
    left = x + margin if anchor == "left" else x + (width - w) // 2 if anchor == "bottom" else x + width - margin - w
    return left, y + height - bottom - h if anchor == "bottom" else y + top, w, h


def focused_client(tree):
    if tree.get("focused") and tree.get("window") and str((tree.get("window_properties") or {}).get("class", "")).casefold() != "ooonanaflyout":
        return tree["id"], tree["window"]
    for child in tree.get("nodes", []) + tree.get("floating_nodes", []):
        found = focused_client(child)
        if found:
            return found
    return None


def visible_client(tree, target, visible, workspace=None):
    if tree.get("type") == "workspace":
        workspace = tree.get("name")
    if (tree.get("id"), tree.get("window")) == target:
        return workspace in visible
    return any(visible_client(child, target, visible, workspace)
               for child in tree.get("nodes", []) + tree.get("floating_nodes", []))


def operation_group(kind):
    return "controls" if kind in ("controls", "audio", "brightness") else kind


def external_child(tree, owner, workspace=None):
    if tree.get("type") == "workspace":
        workspace = tree.get("name")
    if workspace == "__i3_scratch":
        return False
    if (tree.get("window_properties") or {}).get("transient_for") == owner:
        return True
    return any(external_child(child, owner, workspace)
               for child in tree.get("nodes", []) + tree.get("floating_nodes", []))


class Flyout:
    def __init__(self, app, window, kind, anchor):
        self.app, self.window, self.kind, self.anchor = app, window, kind, anchor
        self.focus_timer = self.place_timer = self.outside_timer = 0
        self.pointer_watch = None
        self.closing = False
        self.child_focus_until = 0
        display = window.get_display()
        pointer = display.get_default_seat().get_pointer().get_position()
        self.monitor = display.get_monitor_at_point(pointer.x, pointer.y)
        area = self.monitor.get_workarea()
        width, height = SPECS[kind][1:3]
        if kind == "notifications":
            height = 260
        geometry = anchor_geometry((area.x, area.y, area.width, area.height), (width, height), anchor)
        window.set_size_request(-1, -1)
        window.set_default_size(*geometry[2:])
        window.set_resizable(False)
        old_header = window.get_titlebar()
        actions = [getattr(window, name) for name in ("clear_button", "refresh_button") if hasattr(window, name)]
        root = window.get_child()
        window.remove(root)
        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        heading = Gtk.Box(spacing=8)
        heading.set_border_width(12)
        title = label(SPECS[kind][0], "card-title", wrap=False)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        heading.pack_start(title, True, True, 0)
        if kind == "apps" and old_header is not None:
            count = label(old_header.get_subtitle() or "", "muted", wrap=False)
            count.set_ellipsize(Pango.EllipsizeMode.END)
            count.set_max_width_chars(18)
            old_header.connect("notify::subtitle", lambda bar, _prop: count.set_text(bar.get_subtitle() or ""))
            heading.pack_start(count, False, False, 0)
        close = button("", "window-close-symbolic", lambda *_: app.dismiss(True))
        close.get_accessible().set_name("Close " + SPECS[kind][0])
        close.set_tooltip_text("Close · Escape")
        close.get_style_context().add_class("shell-icon")
        close.get_image().set_margin_end(0)
        heading.pack_end(close, False, False, 0)
        for action in actions:
            action.get_parent().remove(action)
            name = action.get_label()
            action.set_tooltip_text(name)
            action.get_accessible().set_name(name)
            action.set_label("")
            action.get_image().set_margin_end(0)
            action.get_style_context().add_class("shell-icon")
            heading.pack_end(action, False, False, 0)
        frame.pack_start(heading, False, False, 0)
        frame.pack_start(root, True, True, 0)
        window.set_titlebar(None)
        window.set_decorated(False)
        window.add(frame)
        window.get_style_context().add_class("shell-flyout")
        window.set_wmclass("ooonana-flyout", "OoonanaFlyout")
        window.set_role("ooonana-flyout")
        window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        window.set_skip_taskbar_hint(True)
        window.set_skip_pager_hint(True)
        window.set_keep_above(True)
        window._shell_dismiss = lambda: app.dismiss(True)
        if kind == "notifications" and hasattr(window, "remember"):
            window.pause.get_parent().set_orientation(Gtk.Orientation.VERTICAL)
            window.status.set_halign(Gtk.Align.START)
            caption = window.remember.get_child()
            caption.set_line_wrap(True)
            caption.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            caption.set_max_width_chars(22)
            window.resize_flyout = self.fit_notifications
            self.fit_notifications()
        if kind == "apps":
            try:
                window.disconnect_by_func(Gtk.main_quit)
            except TypeError:
                pass
        window.connect("key-press-event", self.key)
        window.connect("focus-out-event", self.focus_out)
        window.connect("delete-event", lambda *_: (app.dismiss(False), True)[1])
        window.connect("destroy", self.destroyed)
        window.connect("map-event", self.mapped)
        window.realize()
        from shell_pointer import ButtonWatch
        try:
            self.pointer_watch = ButtonWatch(self.pointer_pressed)
        except OSError as error:
            # Keyboard/focus dismissal still works on servers without XInput2.
            print(str(error), file=sys.stderr)
        if app.previous:
            from gi.repository import GdkX11
            display.error_trap_push()
            try:
                foreign = GdkX11.X11Window.foreign_new_for_display(display, app.previous[1])
                if foreign is not None:
                    window.get_window().set_transient_for(foreign)
            finally:
                display.error_trap_pop()

    def mapped(self, *_args):
        self.position()
        self.place_timer = GLib.timeout_add(80, self.position)
        return False

    def fit_notifications(self):
        self.window.scroll.set_propagate_natural_height(not self.window.records)
        if self.window.get_mapped() and not self.place_timer:
            self.place_timer = GLib.idle_add(self.position)

    def position(self):
        self.place_timer = 0
        if self.closing or not self.window.get_visible():
            return False
        area = self.monitor.get_workarea()
        workarea = (area.x, area.y, area.width, area.height)
        size = self.window.get_size()
        if self.kind == "notifications" and hasattr(self.window, "records"):
            width, height = SPECS[self.kind][1:3]
            width = anchor_geometry(workarea, (width, height), self.anchor)[2]
            if not self.window.records:
                height = self.window.get_preferred_height_for_width(width)[1]
                scroll_width = self.window.scroll.get_allocated_width()
                if scroll_width > 1:
                    # Measure wrapped copy inside its viewport, at the actual text scale.
                    list_width = max(1, scroll_width + width - self.window.get_allocated_width())
                    content_height = self.window.list.get_preferred_height_for_width(list_width)[1]
                    chrome_height = self.window.get_allocated_height() - self.window.scroll.get_allocated_height()
                    height = max(height, chrome_height + content_height)
            size = (width, height)
        x, y, w, h = anchor_geometry(workarea, size, self.anchor)
        self.window.resize(w, h)
        self.window.move(x, y)
        from gi.repository import GdkX11
        xid = GdkX11.X11Window.get_xid(self.window.get_window())
        scale = self.window.get_scale_factor()
        run(["i3-msg", f"[id={xid}] floating enable, border none, move absolute position {x * scale} px {y * scale} px"], timeout=2)
        # Opaque rounded silhouette also works without a compositor.
        import cairo
        region = cairo.Region()
        radius = min(14, w // 2, h // 2)
        for row in range(h):
            distance = max(radius - row - .5, row + .5 - (h - radius), 0)
            inset = math.ceil(radius - math.sqrt(max(0, radius * radius - distance * distance))) if distance else 0
            region.union(cairo.RectangleInt(inset, row, max(1, w - inset * 2), 1))
        self.window.get_window().shape_combine_region(region, 0, 0)
        return False

    def key(self, _window, event):
        if event.keyval == Gdk.KEY_Escape:
            self.app.dismiss(True)
            return True
        return False

    def child_active(self):
        for child in Gtk.Window.list_toplevels():
            if child is self.window or not child.get_visible():
                continue
            parent = child.get_transient_for()
            while parent is not None:
                if parent is self.window:
                    return True
                parent = parent.get_transient_for()
        grab = Gtk.grab_get_current()
        if isinstance(grab, Gtk.Menu):
            grab = grab.get_attach_widget()
        if grab is not None and grab.get_toplevel() is self.window:
            return True
        from gi.repository import GdkX11
        xid = GdkX11.X11Window.get_xid(self.window.get_window())
        if xid in self.app.prompt_owners:
            try:
                return external_child(i3_events.request(i3_events.socket_path(), 4), xid)
            except (OSError, ValueError, EOFError):
                pass
        return False

    def focus_out(self, *_args):
        if not self.focus_timer:
            self.focus_timer = GLib.timeout_add(120, self.check_focus)
        return False

    def pointer_pressed(self):
        if self.closing or self.child_active():
            return
        pointer = self.window.get_display().get_default_seat().get_pointer().get_position()
        rect = self.window.get_window().get_frame_extents()
        if rect.x <= pointer.x < rect.x + rect.width and rect.y <= pointer.y < rect.y + rect.height:
            return
        if not self.outside_timer:
            # Let panel/dock commands toggle or replace this surface first.
            area = self.monitor.get_workarea()
            trigger_band = pointer.y < area.y + 56 or pointer.y >= area.y + area.height - 84
            self.outside_timer = GLib.timeout_add(750 if trigger_band else 180, self.dismiss_outside)

    def dismiss_outside(self):
        self.outside_timer = 0
        if not self.closing and self.app.controller is self and not self.child_active():
            self.app.dismiss(False)
        return False

    def check_focus(self):
        if self.closing or self.window.is_active():
            self.focus_timer = 0
            return False
        if self.child_active():
            self.child_focus_until = GLib.get_monotonic_time() + 400000
            return True
        if GLib.get_monotonic_time() < max(self.app.prompt_focus_until, self.child_focus_until):
            return True
        self.focus_timer = 0
        self.app.dismiss(False)
        return False

    def destroyed(self, *_args):
        self.closing = True
        for timer in (self.focus_timer, self.place_timer, self.outside_timer):
            if timer and GLib.MainContext.default().find_source_by_id(timer):
                GLib.source_remove(timer)
        self.focus_timer = self.place_timer = self.outside_timer = 0
        if self.pointer_watch is not None:
            self.pointer_watch.close()
            self.pointer_watch = None


class QuickControls(Gtk.Window):
    def __init__(self, app):
        super().__init__(title="Ooonana Control Center")
        self.closed, self.sync_source = False, 0
        bar = header(self, "Control center", "", "ooonana-controls")
        self.refresh_button = button("Refresh", "view-refresh-symbolic", self.refresh)
        bar.pack_end(self.refresh_button)
        from controls_app import AudioWindow, BrightnessWindow
        self.audio, self.brightness = AudioWindow(volume_only=True), BrightnessWindow()
        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(shell)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_border_width(12)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_overlay_scrolling(False)
        scroll.add(root)
        root.set_focus_vadjustment(scroll.get_vadjustment())
        shell.pack_start(scroll, True, True, 0)
        connections = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for kind, image in (("wifi", "network-wireless-symbolic"), ("bluetooth", "bluetooth-symbolic")):
            control = Gtk.Button()
            control.get_style_context().add_class("shell-connection")
            control.get_accessible().set_name(SPECS[kind][0] + " controls")
            control.connect("clicked", lambda *_args, kind=kind: app.show_surface(kind))
            row = Gtk.Box(spacing=8)
            row.pack_start(icon(image), False, False, 0)
            row.pack_start(label(SPECS[kind][0], wrap=False), True, True, 0)
            row.pack_end(icon("go-next-symbolic"), False, False, 0)
            control.add(row)
            connections.pack_start(control, False, False, 0)
        self.audio_device = label("Checking sound…", "muted", wrap=False)
        self.audio_device.set_ellipsize(Pango.EllipsizeMode.END)
        self.audio_device.set_max_width_chars(36)
        for owner in (self.audio, self.brightness):
            if owner is self.brightness:
                root.pack_start(Gtk.Separator(), False, False, 0)
                root.pack_start(connections, False, False, 0)
                separator = Gtk.Separator()
                separator.set_margin_top(4)
                root.pack_start(separator, False, False, 0)
            kind = "audio" if owner is self.audio else "brightness"
            details = button("", "go-next-symbolic", lambda *_args, kind=kind: app.show_surface(kind))
            details.set_tooltip_text(SPECS[kind][0] + " controls")
            details.get_accessible().set_name(SPECS[kind][0] + " controls")
            details.get_style_context().add_class("shell-icon")
            details.get_image().set_margin_end(0)
            title_row = Gtk.Box(spacing=8)
            owner.value_label.get_parent().remove(owner.value_label)
            title_row.pack_start(owner.value_label, True, True, 0)
            title_row.pack_end(details, False, False, 0)
            root.pack_start(title_row, False, False, 0)
            controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            owner.scale.get_parent().remove(owner.scale)
            controls.pack_start(owner.scale, False, False, 0)
            widgets = [owner.apply_button, owner.mute_button] if owner is self.audio else [owner.apply_button]
            for widget in widgets:
                widget.get_parent().remove(widget)
            controls.pack_start(flow_row(widgets, max_children=len(widgets), min_children=1), False, False, 0)
            root.pack_start(controls, False, False, 0)
            owner.status.get_parent().remove(owner.status)
            if owner is self.brightness:
                controls.show_all()
                controls.set_no_show_all(True)
                self.brightness_controls = controls
                self.brightness_details = Gtk.Expander(label="Backlight details")
                owner.status.set_lines(-1)
                owner.status.set_ellipsize(Pango.EllipsizeMode.NONE)
                owner.status.set_max_width_chars(32)
                owner.status.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                self.brightness_details.add(owner.status)
                root.pack_start(self.brightness_details, False, False, 0)
            else:
                self._shell_initial_focus = details
                root.pack_start(self.audio_device, False, False, 0)
                owner.status.set_lines(2)
                owner.status.set_max_width_chars(36)
                root.pack_start(owner.status, False, False, 0)
            owner.status.connect("notify::label", self.queue_sync)
        self.audio.output_combo.connect("changed", self.queue_sync)
        self.settings_button = button("Settings", "preferences-system-symbolic", lambda *_: self.settings(app))
        footer = Gtk.Box(spacing=8)
        footer.set_border_width(12)
        footer.get_style_context().add_class("shell-footer")
        footer.pack_start(self.settings_button, False, False, 0)
        for kind, image in (("power", "system-shutdown-symbolic"), ("notifications", "dialog-information-symbolic")):
            shortcut = button("", image, lambda *_args, kind=kind: app.show_surface(kind))
            shortcut.get_style_context().add_class("shell-icon")
            shortcut.get_image().set_margin_end(0)
            shortcut.set_tooltip_text(SPECS[kind][0])
            shortcut.get_accessible().set_name(SPECS[kind][0])
            footer.pack_end(shortcut, False, False, 0)
        shell.pack_end(footer, False, False, 0)
        self.connect("destroy", self.on_destroy)
        self.queue_sync()

    def queue_sync(self, *_args):
        if not self.closed and not self.sync_source:
            self.sync_source = GLib.idle_add(self.sync_state)

    def sync_state(self):
        self.sync_source = 0
        if self.closed:
            return False
        self.refresh_button.set_sensitive(not (self.audio.busy or self.brightness.busy))
        name = self.audio.output_combo.get_active_text() or "Output unavailable"
        self.audio_device.set_text(name)
        self.audio_device.set_tooltip_text(name)
        self.audio_device.get_accessible().set_description(name)
        self.brightness_controls.set_visible(self.brightness.ready or self.brightness.busy)
        self.brightness_details.set_tooltip_text(self.brightness.status.get_text())
        return False

    def refresh(self, *_args):
        if not self.closed and not (self.audio.busy or self.brightness.busy):
            self.audio.refresh_audio()
            self.brightness.refresh()
            self.queue_sync()

    def on_destroy(self, *_args):
        self.closed = True
        if self.sync_source and GLib.MainContext.default().find_source_by_id(self.sync_source):
            GLib.source_remove(self.sync_source)
        self.sync_source = 0
        self.audio.destroy()
        self.brightness.destroy()

    @staticmethod
    def settings(app):
        if launch(["ooonana-settings-launch"]):
            app.dismiss(False)


def create_surface(kind, app):
    if kind == "apps":
        from launcher_app import LauncherWindow
        return LauncherWindow()
    if kind == "notifications":
        from notifications_app import NotificationsWindow
        return NotificationsWindow()
    if kind == "controls":
        return QuickControls(app)
    if kind == "wifi":
        from wifi_app import WifiWindow
        return WifiWindow()
    if kind == "bluetooth":
        from bluetooth_app import BluetoothWindow
        return BluetoothWindow()
    from controls_app import AudioWindow, BrightnessWindow, PowerWindow
    return {"audio": AudioWindow, "brightness": BrightnessWindow, "power": PowerWindow}[kind]()


class ShellApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=application_id(), flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = self.controller = self.kind = self.previous = None
        self.pending = {}
        self.prompt_owners = set()
        self.prompt_focus_until = 0
        self.waiting = False

    def do_startup(self):
        Gtk.Application.do_startup(self)
        apply_theme()
        action = Gio.SimpleAction.new("toggle", GLib.VariantType.new("(ss)"))
        action.connect("activate", lambda _action, value: self.toggle(*value.unpack()))
        self.add_action(action)

    def command_environment(self):
        if self.window is None or self.window.get_window() is None:
            return {}
        from gi.repository import GdkX11
        xid = GdkX11.X11Window.get_xid(self.window.get_window())
        self.prompt_owners.add(xid)
        return {"OOONANA_PARENT_XID": str(xid)}

    def toggle(self, kind, anchor=""):
        if kind not in SPECS or anchor not in ("", "left") or (anchor and kind != "apps"):
            return 2
        if self.window is not None and self.kind == kind:
            self.dismiss(True)
        else:
            self.show_surface(kind, anchor or None)
        return 0

    def begin_operation(self):
        group = operation_group(self.kind)
        self.hold()
        self.pending[group] = self.pending.get(group, 0) + 1
        def finish():
            self.pending[group] -= 1
            if not any(self.pending.values()):
                if self.prompt_owners:
                    # X11 child destruction and restored FocusIn can arrive
                    # after the askpass pipe closes. Keep that handoff intact.
                    self.prompt_focus_until = GLib.get_monotonic_time() + 400000
                self.prompt_owners.clear()
            if self.waiting and operation_group(self.kind) == group and not self.pending[group] and self.window is not None:
                waiting_window = self.window
                def resume():
                    if self.window is waiting_window and self.waiting:
                        self.show_surface(self.kind)
                    return False
                GLib.idle_add(resume)
            self.release()
        return finish

    def show_surface(self, kind, anchor=None):
        if kind not in SPECS:
            return False
        if self.window is None:
            try:
                self.previous = focused_client(i3_events.request(i3_events.socket_path(), 4))
            except (OSError, ValueError):
                pass
        self.dismiss(False)
        self.kind = kind
        self.waiting = bool(self.pending.get(operation_group(kind)))
        if self.waiting:
            window = Gtk.Window(title=SPECS[kind][0])
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            root.set_border_width(16)
            root.pack_start(label("Finishing previous request", "card-title"), False, False, 0)
            root.pack_start(label("Controls return when the current request completes.", "muted"), False, False, 0)
            window.add(root)
        else:
            window = create_surface(kind, self)
        self.window = window
        self.add_window(window)
        self.controller = Flyout(self, window, kind, anchor or SPECS[kind][3])
        window.show_all()
        focus = getattr(window, "search", None) or getattr(window, "_shell_initial_focus", None)
        if focus is not None:
            focus.grab_focus()
        return False

    def dismiss(self, restore=False):
        window, self.window = self.window, None
        self.waiting = False
        if window is not None:
            window.destroy()
        if restore and self.previous:
            container, xid = self.previous
            try:
                path = i3_events.socket_path()
                tree = i3_events.request(path, 4)
                visible = {item["name"] for item in i3_events.request(path, 1) if item.get("visible")}
                if visible_client(tree, self.previous, visible):
                    run(["i3-msg", f"[con_id={container} id={xid}] focus"], timeout=2)
            except (OSError, ValueError):
                pass
        self.controller = None

    def do_command_line(self, command):
        args = command.get_arguments()[1:]
        if len(args) not in (1, 2) or args[0] not in SPECS or (len(args) == 2 and (args[0] != "apps" or args[1] != "--panel")):
            return 2
        return self.toggle(args[0], "left" if len(args) == 2 else "")


def run_shell(kind, panel=False):
    if kind not in SPECS:
        return 2
    return ShellApplication().run(["ooonana-shell", kind] + (["--panel"] if panel else []))


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) not in (1, 2) or args[0] not in SPECS or (len(args) == 2 and args != ["apps", "--panel"]):
        raise SystemExit(2)
    raise SystemExit(run_shell(args[0], panel=len(args) == 2))
