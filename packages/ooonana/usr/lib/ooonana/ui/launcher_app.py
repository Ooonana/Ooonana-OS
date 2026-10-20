#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Gdk, Gtk, Pango, apply_theme, header, icon, label, launch, message  # noqa: E402
from gi.repository import Gio  # noqa: E402


PREFERRED_COMMANDS = {
    "chromium.desktop": ["ooonana-browser"],
    "nemo.desktop": ["ooonana-files"],
    "geany.desktop": ["ooonana-editor"],
    "xterm.desktop": ["ooonana-theme-env", "xterm"],
    "uxterm.desktop": ["ooonana-theme-env", "xterm"],
    "pavucontrol.desktop": ["ooonana-audio-panel"],
    "blueman-manager.desktop": ["ooonana-bluetooth-panel"],
    "nm-connection-editor.desktop": ["ooonana-wifi-panel"],
}

ICON_OVERRIDES = {
    "chromium.desktop": "ooonana-browser",
    "chromium-browser.desktop": "ooonana-browser",
    "google-chrome.desktop": "ooonana-browser",
    "ooonana-browser.desktop": "ooonana-browser",
}


class LauncherWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Spotlight")
        self.set_default_size(760, 520)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(True)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(False)
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)
        self.titlebar = header(
            self,
            "Ooonana Spotlight",
            "Applications",
            "system-search-symbolic",
        )
        self.set_wmclass("ooonana-spotlight", "OoonanaSpotlight")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.get_style_context().add_class("spotlight")
        self.add(root)

        search_box = Gtk.Box()
        search_box.set_border_width(12)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search applications")
        self.search.get_style_context().add_class("spotlight-search")
        self.search.connect("changed", self.search_changed)
        self.search.connect("activate", self.launch_selected)
        self.search.connect("key-press-event", self.search_key)
        search_box.pack_start(self.search, True, True, 0)
        root.pack_start(search_box, False, False, 0)

        self.results = Gtk.ListBox()
        self.results.get_style_context().add_class("spotlight-results")
        self.results.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.results.set_activate_on_single_click(True)
        self.results.set_filter_func(self.filter_row)
        self.results.set_sort_func(self.sort_rows)
        self.results.connect("row-activated", self.activate_row)
        self.result_scroll = Gtk.ScrolledWindow()
        self.result_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.result_scroll.add(self.results)
        root.pack_start(self.result_scroll, True, True, 0)
        self.empty_state = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.empty_state.set_border_width(24)
        self.empty_state.set_valign(Gtk.Align.CENTER)
        self.empty_title = label("No applications found", "card-title")
        self.empty_hint = label("Install applications using Packages, then reopen Spotlight.", "muted")
        self.empty_state.pack_start(self.empty_title, False, False, 0)
        self.empty_state.pack_start(self.empty_hint, False, False, 0)
        self.empty_state.show_all()
        self.empty_state.set_no_show_all(True)
        root.pack_start(self.empty_state, True, True, 0)

        apps = [
            app
            for app in Gio.AppInfo.get_all()
            if app.should_show() and not getattr(app, "get_nodisplay", lambda: False)()
        ]
        apps.sort(key=lambda app: (
            not (app.get_id() or "").startswith("ooonana-"),
            (app.get_display_name() or app.get_name()).casefold(),
        ))
        for app in apps:
            self.add_app(app)
        self.result_scroll.show_all()
        self.result_scroll.set_no_show_all(True)
        self.select_first()

        self.connect("key-press-event", self.window_key)
        self.connect("destroy", Gtk.main_quit)

    def add_app(self, app):
        name = app.get_display_name() or app.get_name()
        description = app.get_description() or app.get_executable() or "Application"
        row = Gtk.ListBoxRow()
        row.app = app
        row.search_name = name.casefold()
        row.default_order = len(self.results.get_children())
        row.search_text = f"{name} {description} {app.get_executable() or ''}".casefold()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        gicon = app.get_icon()
        image = None
        custom = ICON_OVERRIDES.get((app.get_id() or "").lower())
        theme = Gtk.IconTheme.get_default()
        if custom and theme and theme.has_icon(custom):
            image = Gtk.Image.new_from_icon_name(custom, Gtk.IconSize.DIALOG)
        elif isinstance(gicon, Gio.ThemedIcon):
            theme = Gtk.IconTheme.get_default()
            selected = next((name for name in gicon.get_names() if theme and theme.has_icon(name)), None)
            if selected:
                image = Gtk.Image.new_from_icon_name(selected, Gtk.IconSize.DIALOG)
        elif isinstance(gicon, Gio.FileIcon):
            path = gicon.get_file().get_path()
            if path and Path(path).is_file():
                image = Gtk.Image.new_from_gicon(gicon, Gtk.IconSize.DIALOG)
        elif gicon:
            image = Gtk.Image.new_from_gicon(gicon, Gtk.IconSize.DIALOG)
        if image is None:
            fallback = {
                "arandr.desktop": "video-display-symbolic",
                "xterm.desktop": "utilities-terminal-symbolic",
                "uxterm.desktop": "utilities-terminal-symbolic",
            }.get((app.get_id() or "").lower(), "application-x-executable-symbolic")
            image = icon(fallback, Gtk.IconSize.DIALOG)
        image.set_pixel_size(34)
        box.pack_start(image, False, False, 0)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name_label = label(name, "spotlight-app-name", wrap=False)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(48)
        name_label.set_tooltip_text(name)
        detail = label(description, "muted")
        detail.set_line_wrap(False)
        detail.set_ellipsize(Pango.EllipsizeMode.END)
        detail.set_max_width_chars(72)
        detail.set_tooltip_text(description)
        text.pack_start(name_label, False, False, 0)
        text.pack_start(detail, False, False, 0)
        box.pack_start(text, True, True, 0)
        box.pack_end(icon("go-next-symbolic"), False, False, 0)
        row.add(box)
        row.get_accessible().set_name(name)
        row.get_accessible().set_description(description)
        self.results.add(row)
        row.show_all()

    def filter_row(self, row):
        query = self.search.get_text().strip().casefold()
        return hasattr(row, "search_text") and (not query or query in row.search_text)

    def visible_rows(self):
        return [row for row in self.results.get_children() if row.get_child_visible()]

    def sort_rows(self, left, right):
        query = self.search.get_text().strip().casefold()
        def score(row):
            name = row.search_name
            rank = (0 if name == query else 1 if name.startswith(query) else
                    2 if any(word.startswith(query) for word in name.split()) else
                    3 if query in name else 4) if query else 0
            return rank, row.default_order
        return (score(left) > score(right)) - (score(left) < score(right))

    def search_changed(self, *_args):
        self.results.invalidate_filter()
        self.results.invalidate_sort()
        self.select_first()

    def select_first(self):
        rows = self.visible_rows()
        self.results.select_row(rows[0] if rows else None)
        total = len(self.results.get_children())
        query = self.search.get_text().strip()
        self.titlebar.set_subtitle(
            f"{len(rows)} of {total} {'application' if total == 1 else 'applications'}" if query else
            f"{total} {'application' if total == 1 else 'applications'}")
        self.empty_title.set_text("No matching applications" if query else "No applications found")
        self.empty_hint.set_text("Try another name or clear the search." if query else
                                 "Install applications using Packages, then reopen Spotlight.")
        self.empty_state.set_visible(not rows)
        self.result_scroll.set_visible(bool(rows))
        return False

    def search_key(self, _entry, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if event.keyval not in (Gdk.KEY_Down, Gdk.KEY_Up):
            return False
        rows = self.visible_rows()
        if not rows:
            return True
        selected = self.results.get_selected_row()
        index = rows.index(selected) if selected in rows else 0
        index = min(len(rows) - 1, index + 1) if event.keyval == Gdk.KEY_Down else max(0, index - 1)
        self.results.select_row(rows[index])
        rows[index].grab_focus()
        return True

    def window_key(self, _window, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def launch_selected(self, *_args):
        row = self.results.get_selected_row()
        if row is None:
            rows = self.visible_rows()
            row = rows[0] if rows else None
        if row is not None:
            self.launch_app(row.app)

    def activate_row(self, _listbox, row):
        self.launch_app(row.app)

    def launch_app(self, app):
        app_id = app.get_id() or ""
        preferred = PREFERRED_COMMANDS.get(app_id)
        if preferred:
            if launch(preferred):
                self.close()
            else:
                message(
                    self,
                    "Application failed",
                    f"Could not launch {' '.join(preferred)}",
                    Gtk.MessageType.ERROR,
                )
            return
        try:
            display = Gdk.Display.get_default()
            context = display.get_app_launch_context() if display else None
            if context:
                context.set_timestamp(Gtk.get_current_event_time())
            app.launch([], context)
            self.close()
        except Exception as exc:
            message(self, "Application failed", str(exc), Gtk.MessageType.ERROR)


def main():
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana Spotlight launcher")
        print("features: desktop entries icons instant search keyboard selection")
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
