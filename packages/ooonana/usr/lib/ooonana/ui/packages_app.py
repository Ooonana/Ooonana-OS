#!/usr/bin/env python3
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    GLib,
    Gtk,
    Pango,
    apply_theme,
    ask_text,
    button,
    header,
    flow_row,
    fit_dialog,
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
        self.write_pending = False
        self.review_open = False
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
        self.status.set_line_wrap(False)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
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
        self.connect("delete-event", self.before_close)

    def before_close(self, *_args):
        if self.busy and self.write_pending:
            self.status.set_text("Package operation still running. Wait for completion before closing.")
            self.status.set_tooltip_text(self.status.get_text())
            return True
        return False

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
            for tone in ("status-good", "status-bad", "status-warn"):
                context.remove_class(tone)
            context.add_class("muted")
            self.progress.show()
            self.progress.pulse()
            self.progress.set_show_text(False)
            self.status.set_text(text)
            self.status.set_tooltip_text(text)
            if not self.pulse_source and not load_preferences()["reduce_motion"]:
                self.pulse_source = GLib.timeout_add(150, self.pulse)
        else:
            self.write_pending = False
            if self.pulse_source:
                GLib.source_remove(self.pulse_source)
                self.pulse_source = 0
            self.progress.hide()

    def set_output(self, title, output):
        text = f"{title}\n{'=' * len(title)}\n\n{output or 'No output.'}\n"
        self.output.get_buffer().set_text(text)
        self.status.set_text(title)
        self.status.set_tooltip_text(title)

    def execute(self, title, command, admin=False, timeout=120, mutating=False):
        if self.closed or self.busy or self.review_open:
            return
        self.write_pending = mutating
        self.set_busy(True, title)

        def done(rc, output):
            if self.closed:
                return
            self.set_busy(False)
            status = "complete" if rc == 0 else f"failed (exit {rc})"
            self.set_output(f"{title}: {status}", output)
            context = self.status.get_style_context()
            for tone in ("muted", "status-good", "status-bad", "status-warn"):
                context.remove_class(tone)
            context.add_class("status-bad" if rc else "status-good")

        run_async(command, done, admin=admin, timeout=timeout)

    def search(self, *_args):
        query = self.search_entry.get_text().strip()
        if not query:
            return
        self.execute(f"Search: {query}", ["ooonana", "search", query], timeout=45)

    def install_package(self, *_args):
        if self.closed or self.busy or self.review_open:
            return
        package = self.package_name("Install package", "Package name")
        if package:
            self.preview(
                f"Installing {package}",
                ["ooonana", "get", package],
                action="Install",
                timeout=300,
            )

    def remove_package(self, *_args):
        if self.closed or self.busy or self.review_open:
            return
        package = self.package_name("Remove package", "Installed package name")
        if package:
            self.preview(
                f"Removing {package}",
                ["ooonana", "remove", package],
                action="Remove",
                timeout=180,
            )

    def update_repos(self, *_args):
        self.execute(
            "Updating package metadata",
            ["ooonana", "update"],
            admin=True,
            timeout=180,
            mutating=True,
        )

    def upgrade_system(self, *_args):
        self.preview(
            "Upgrading Ooonana OS",
            ["ooonana", "upgrade"],
            action="Upgrade",
            timeout=600,
        )

    def package_name(self, title, prompt):
        package = ask_text(self, title, prompt)
        if package and (len(package) > 251 or not re.fullmatch(r"[A-Za-z0-9_.+][A-Za-z0-9_.+-]*", package)):
            message(self, "Check package name", "Enter one package ID using letters, numbers, dot, underscore, plus or dash. Do not enter command options.", Gtk.MessageType.WARNING)
            return ""
        return package

    def preview(self, title, command, action, timeout):
        if self.closed or self.busy or self.review_open:
            return
        self.set_busy(True, "Preparing change review...")
        def done(rc, output):
            if self.closed:
                return False
            self.set_busy(False)
            self.set_output(title + ": review" + (f" failed (exit {rc})" if rc else ""), output)
            if rc:
                self.status.get_style_context().add_class("status-bad")
                return False
            if not output.strip():
                self.status.set_text("Preview returned no details. No packages changed.")
                self.status.get_style_context().add_class("status-warn")
                return False
            if command == ["ooonana", "upgrade"] and output.strip() == "no upgrades":
                self.status.set_text("No upgrades available.")
                return False
            self.review_open = True
            try:
                accepted = self.confirm_plan(title, output, action)
            finally:
                self.review_open = False
            if accepted and not self.closed:
                self.execute(title, command, admin=True, timeout=timeout, mutating=True)
            elif not self.closed:
                self.status.set_text("Review cancelled. No packages changed.")
            return False
        run_async([*command, "--dry-run"], done, admin=True, timeout=60)

    def confirm_plan(self, title, output, action):
        dialog = Gtk.Dialog(title="Review package changes", transient_for=self, modal=True)
        dialog.set_destroy_with_parent(True)
        dialog.set_icon_name("ooonana-packages")
        fit_dialog(dialog, 760, 520)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        confirm = dialog.add_button(action, Gtk.ResponseType.OK)
        confirm.get_style_context().add_class("destructive-action" if action == "Remove" else "suggested-action")
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        content = dialog.get_content_area()
        content.set_border_width(16)
        content.set_spacing(10)
        content.pack_start(label(title, "card-title"), False, False, 0)
        content.pack_start(label("Preview only; no packages changed. Final transaction rechecks repository and dependencies. Major-upgrade policy stays unchanged.", "muted"), False, False, 0)
        plan = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
        plan.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        plan.set_left_margin(12)
        plan.set_right_margin(12)
        plan.set_top_margin(12)
        plan.set_bottom_margin(12)
        plan.get_buffer().set_text(output or "No plan details returned.")
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(plan)
        content.pack_start(scroll, True, True, 0)
        dialog.show_all()
        accepted = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        return accepted

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
