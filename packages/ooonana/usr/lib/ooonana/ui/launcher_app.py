#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Gtk, apply_theme, header, icon, label, message  # noqa: E402
from gi.repository import Gio  # noqa: E402


class LauncherWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Apps")
        self.set_default_size(920, 620)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, "Applications", "Ooonana app launcher", "view-app-grid-symbolic")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_border_width(16)
        self.add(root)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search applications")
        self.search.connect("search-changed", lambda *_: self.flow.invalidate_filter())
        self.search.connect("activate", self.launch_first_visible)
        root.pack_start(self.search, False, False, 0)

        self.flow = Gtk.FlowBox()
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_row_spacing(10)
        self.flow.set_column_spacing(10)
        self.flow.set_min_children_per_line(3)
        self.flow.set_max_children_per_line(6)
        self.flow.set_homogeneous(True)
        self.flow.set_filter_func(self.filter_child)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.flow)
        root.pack_start(scroll, True, True, 0)

        apps = [
            app
            for app in Gio.AppInfo.get_all()
            if app.should_show()
            and not getattr(app, "get_nodisplay", lambda: False)()
        ]
        apps.sort(key=lambda app: (app.get_display_name() or app.get_name()).casefold())
        for app in apps:
            self.add_app(app)

        if not apps:
            root.pack_start(
                label("No desktop applications found.", "status-bad"),
                False,
                False,
                0,
            )
        footer = label(
            f"{len(apps)} applications  |  Mod+D opens launcher  |  Mod+Shift+D opens command view",
            "muted",
        )
        root.pack_start(footer, False, False, 0)
        self.connect("destroy", Gtk.main_quit)

    def add_app(self, app):
        name = app.get_display_name() or app.get_name()
        description = app.get_description() or ""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        box.set_border_width(8)
        gicon = app.get_icon()
        image = (
            Gtk.Image.new_from_gicon(gicon, Gtk.IconSize.DIALOG)
            if gicon
            else icon("application-x-executable-symbolic", Gtk.IconSize.DIALOG)
        )
        image.set_pixel_size(34)
        box.pack_start(image, False, False, 0)
        name_label = label(name, xalign=0.5)
        name_label.set_max_width_chars(18)
        name_label.set_ellipsize(3)
        box.pack_start(name_label, False, False, 0)
        widget = Gtk.Button()
        widget.set_size_request(138, 92)
        widget.add(box)
        widget.set_tooltip_text(description or name)
        widget.connect("clicked", lambda _widget, target=app: self.launch_app(target))
        child = Gtk.FlowBoxChild()
        child.search_text = f"{name} {description} {app.get_executable() or ''}".casefold()
        child.app = app
        child.add(widget)
        self.flow.add(child)

    def filter_child(self, child):
        query = self.search.get_text().strip().casefold()
        return not query or query in child.search_text

    def visible_children(self):
        return [child for child in self.flow.get_children() if child.get_visible()]

    def launch_first_visible(self, *_args):
        visible = self.visible_children()
        if visible:
            self.launch_app(visible[0].app)

    def launch_app(self, app):
        try:
            app.launch([], None)
            self.destroy()
        except Exception as exc:
            message(self, "Application failed", str(exc), Gtk.MessageType.ERROR)


def main():
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana application launcher")
        print("features: desktop entries icons search app grid")
        print("OOONANA_LAUNCHER_NATIVE_OK")
        return 0
    apply_theme()
    window = LauncherWindow()
    window.show_all()
    window.search.grab_focus()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
