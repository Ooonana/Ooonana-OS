#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    GLib,
    Gtk,
    apply_theme,
    ask_text,
    button,
    header,
    flow_row,
    label,
    load_preferences,
    message,
    run_async,
)


class PackagesWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Packages")
        self.busy = False
        self.closed = False
        self.pulse_source = 0
        self.action_buttons = []
        self.set_default_size(940, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        bar = header(
            self,
            "Ooonana Packages",
            "Cloud package manager",
            "system-software-install-symbolic",
        )
        update = button("Update", "view-refresh-symbolic", self.update_repos)
        self.action_buttons.append(update)
        bar.pack_end(update)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_border_width(18)
        self.add(root)

        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search package names and descriptions")
        self.search_entry.connect("activate", self.search)
        search_row.pack_start(self.search_entry, True, True, 0)
        search = button("Search", "edit-find-symbolic", self.search, "suggested-action")
        self.action_buttons.append(search)
        search_row.pack_start(search, False, False, 0)
        root.pack_start(search_row, False, False, 0)

        actions = [button(title, image, callback) for title, image, callback in (
            ("Install", "list-add-symbolic", self.install_package),
            ("Remove", "list-remove-symbolic", self.remove_package),
            ("Upgrade system", "software-update-available-symbolic", self.upgrade_system),
            ("Installed", "emblem-default-symbolic", self.show_installed),
            ("Sources", "folder-remote-symbolic", self.show_sources),
            ("Doctor", "emblem-system-symbolic", self.run_doctor))]
        self.action_buttons.extend(actions)
        toolbar = flow_row(actions, max_children=6, min_children=2)
        root.pack_start(toolbar, False, False, 0)

        self.status = label("Ready. Update repositories before first install.", "muted")
        root.pack_start(self.status, False, False, 0)
        self.progress = Gtk.ProgressBar()
        self.progress.set_no_show_all(True)
        root.pack_start(self.progress, False, False, 0)

        self.output = Gtk.TextView()
        self.output.set_editable(False)
        self.output.set_cursor_visible(False)
        self.output.set_monospace(True)
        self.output.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.output.set_left_margin(12)
        self.output.set_right_margin(12)
        self.output.set_top_margin(12)
        self.output.set_bottom_margin(12)
        self.output.get_buffer().set_text(
            "Ooonana Packages\n\n"
            "Repository metadata stays small. Package archives download only when installed.\n"
            "Use Search, Install, Remove, Update, or Upgrade above.\n"
        )
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.output)
        root.pack_start(scroll, True, True, 0)
        self.connect("destroy", self.on_destroy)

    def on_destroy(self, *_args):
        self.closed = True
        if self.pulse_source:
            GLib.source_remove(self.pulse_source)
            self.pulse_source = 0
        if Gtk.main_level():
            Gtk.main_quit()

    def pulse(self):
        if self.closed or not self.busy:
            self.pulse_source = 0
            return False
        self.progress.pulse()
        return True

    def set_busy(self, busy, text=""):
        self.busy = busy
        for action in self.action_buttons:
            action.set_sensitive(not busy)
        self.search_entry.set_sensitive(not busy)
        if busy:
            context = self.status.get_style_context()
            for tone in ("status-good", "status-bad"):
                context.remove_class(tone)
            context.add_class("muted")
            self.progress.show()
            self.progress.pulse()
            self.progress.set_show_text(False)
            self.status.set_text(text)
            if not self.pulse_source and not load_preferences()["reduce_motion"]:
                self.pulse_source = GLib.timeout_add(150, self.pulse)
        else:
            if self.pulse_source:
                GLib.source_remove(self.pulse_source)
                self.pulse_source = 0
            self.progress.hide()

    def set_output(self, title, output):
        text = f"{title}\n{'=' * len(title)}\n\n{output or 'No output.'}\n"
        self.output.get_buffer().set_text(text)
        self.status.set_text(title)

    def execute(self, title, command, admin=False, timeout=120):
        if self.closed or self.busy:
            return
        self.set_busy(True, title)

        def done(rc, output):
            if self.closed:
                return
            self.set_busy(False)
            status = "complete" if rc == 0 else f"failed (exit {rc})"
            self.set_output(f"{title}: {status}", output)
            context = self.status.get_style_context()
            for tone in ("muted", "status-good", "status-bad"):
                context.remove_class(tone)
            context.add_class("status-bad" if rc else "status-good")

        run_async(command, done, admin=admin, timeout=timeout)

    def search(self, *_args):
        query = self.search_entry.get_text().strip()
        if not query:
            return
        self.execute(f"Search: {query}", ["ooonana", "search", query], timeout=45)

    def install_package(self, *_args):
        package = ask_text(self, "Install package", "Package name")
        if package:
            self.execute(
                f"Installing {package}",
                ["ooonana", "get", package],
                admin=True,
                timeout=300,
            )

    def remove_package(self, *_args):
        package = ask_text(self, "Remove package", "Installed package name")
        if package:
            self.execute(
                f"Removing {package}",
                ["ooonana", "remove", package],
                admin=True,
                timeout=180,
            )

    def update_repos(self, *_args):
        self.execute(
            "Updating package metadata",
            ["ooonana", "update"],
            admin=True,
            timeout=180,
        )

    def upgrade_system(self, *_args):
        self.execute(
            "Upgrading Ooonana OS",
            ["ooonana", "upgrade"],
            admin=True,
            timeout=600,
        )

    def show_installed(self, *_args):
        self.execute("Installed packages", ["ooonana", "list", "--installed"], timeout=60)

    def show_sources(self, *_args):
        self.execute("Package sources", ["ooonana", "sources"], timeout=30)

    def run_doctor(self, *_args):
        self.execute("Repository doctor", ["ooonana", "repo", "doctor"], timeout=90)


def main():
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana Packages")
        print("actions: update search install remove upgrade installed sources doctor")
        print("OOONANA_PACKAGES_NATIVE_OK")
        return 0
    apply_theme()
    window = PackagesWindow()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
