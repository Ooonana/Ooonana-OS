#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    Gtk,
    apply_theme,
    ask_text,
    button,
    header,
    label,
    message,
    run_async,
)


class PackagesWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Packages")
        self.set_default_size(980, 650)
        self.set_position(Gtk.WindowPosition.CENTER)
        bar = header(
            self,
            "Ooonana Packages",
            "Cloud package manager",
            "system-software-install-symbolic",
        )
        bar.pack_end(button("Update", "view-refresh-symbolic", self.update_repos))

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_border_width(18)
        self.add(root)

        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search package names and descriptions")
        self.search_entry.connect("activate", self.search)
        search_row.pack_start(self.search_entry, True, True, 0)
        search_row.pack_start(
            button("Search", "edit-find-symbolic", self.search, "suggested-action"),
            False,
            False,
            0,
        )
        root.pack_start(search_row, False, False, 0)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.pack_start(
            button("Install", "list-add-symbolic", self.install_package),
            False,
            False,
            0,
        )
        toolbar.pack_start(
            button("Remove", "list-remove-symbolic", self.remove_package),
            False,
            False,
            0,
        )
        toolbar.pack_start(
            button("Upgrade system", "software-update-available-symbolic", self.upgrade_system),
            False,
            False,
            0,
        )
        toolbar.pack_start(
            button("Installed", "emblem-default-symbolic", self.show_installed),
            False,
            False,
            0,
        )
        toolbar.pack_start(
            button("Sources", "folder-remote-symbolic", self.show_sources),
            False,
            False,
            0,
        )
        toolbar.pack_end(
            button("Doctor", "emblem-system-symbolic", self.run_doctor),
            False,
            False,
            0,
        )
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
        self.output.get_buffer().set_text(
            "Ooonana Packages\n\n"
            "Repository metadata stays small. Package archives download only when installed.\n"
            "Use Search, Install, Remove, Update, or Upgrade above.\n"
        )
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.output)
        root.pack_start(scroll, True, True, 0)
        self.connect("destroy", Gtk.main_quit)

    def set_busy(self, busy, text=""):
        if busy:
            self.progress.show()
            self.progress.pulse()
            self.progress.set_show_text(True)
            self.progress.set_text(text)
            self.status.set_text(text)
        else:
            self.progress.hide()

    def set_output(self, title, output):
        text = f"{title}\n{'=' * len(title)}\n\n{output or 'No output.'}\n"
        self.output.get_buffer().set_text(text)
        self.status.set_text(title)

    def execute(self, title, command, admin=False, timeout=120):
        self.set_busy(True, title)

        def done(rc, output):
            self.set_busy(False)
            status = "complete" if rc == 0 else f"failed (exit {rc})"
            self.set_output(f"{title}: {status}", output)

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
