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
    confirmation_dialog,
    header,
    flow_row,
    fit_dialog,
    label,
    launch,
    load_preferences,
    message,
    more_actions,
    run_async,
)


class PackagesWindow(Gtk.Window):
    def __init__(self, updates=False):
        super().__init__(title="Ooonana Updates" if updates else "Ooonana Packages")
        self.updates = updates
        self.search_entry = None
        self.install_updates = None
        self.updates_ready = False
        self.busy = False
        self.closed = False
        self.pulse_source = 0
        self.write_pending = False
        self.review_open = False
        self.action_buttons = []
        self.set_default_size(660 if updates else 940, 460 if updates else 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(
            self,
            self.get_title(),
            "" if updates else "Search and manage packages",
            "system-software-update-symbolic" if updates else "system-software-install-symbolic",
        )

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_border_width(18)
        self.add(root)
        if updates:
            self.build_update_actions(root)
        else:
            self.build_package_actions(root)

        status = "Check for updates to see what can be installed." if updates else "Ready"
        self.status = label(status, "muted", wrap=False)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        root.pack_start(self.status, False, False, 0)
        self.progress = Gtk.ProgressBar()
        self.progress.set_no_show_all(True)
        root.pack_start(self.progress, False, False, 0)

        self.output = Gtk.TextView(editable=False, cursor_visible=False, monospace=not updates)
        self.output.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.output.set_left_margin(14)
        self.output.set_right_margin(14)
        self.output.set_top_margin(14)
        self.output.set_bottom_margin(14)
        self.output.set_pixels_below_lines(3 if updates else 0)
        initial = (
            "Package updates install in place on installed systems and Persistent Live USB.\n\n"
            "Normal Live uses temporary RAM storage. Changes disappear after reboot.\n\n"
            "Kernel and boot changes on Live come with a new ISO."
            if updates else "Search for a package or view installed packages."
        )
        self.output.get_buffer().set_text(initial)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.output)
        root.pack_start(scroll, True, True, 0)
        self.connect("destroy", self.on_destroy)
        self.connect("delete-event", self.before_close)

    def build_update_actions(self, root):
        self.check_button = button("Check for updates", "view-refresh-symbolic", self.check_updates, "suggested-action")
        self.install_updates = button("Install updates", "software-update-available-symbolic", self.upgrade_system)
        self.install_updates.set_sensitive(False)
        packages = button("Manage packages", "system-software-install-symbolic", lambda *_: launch(["ooonana-packages-app"]))
        self.action_buttons.extend((self.check_button, self.install_updates, packages))
        root.pack_start(flow_row(self.action_buttons, max_children=3, min_children=1), False, False, 0)

    def build_package_actions(self, root):
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
            ("Updates", "software-update-available-symbolic", lambda *_: launch(["ooonana-updates"])),
            ("Installed", "emblem-default-symbolic", self.show_installed),
            ("Sources", "folder-remote-symbolic", self.show_sources))]
        tools = [button("Refresh metadata", "view-refresh-symbolic"),
                 button("Repository doctor", "emblem-system-symbolic"),
                 button("Recover interrupted update", "edit-undo-symbolic")]
        more = more_actions(tools, "Repository tools and interrupted-update recovery")
        # Pop down the menu before a tool maps its modal confirmation.
        for tool, callback in zip(tools, (self.update_repos, self.run_doctor, self.recover_updates)):
            tool.connect_after("clicked", callback)
        self.action_buttons.extend(tools)
        actions.append(more)
        self.action_buttons.extend(actions)
        toolbar = flow_row(actions, max_children=6, min_children=1)
        root.pack_start(toolbar, False, False, 0)

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
        if self.search_entry is not None:
            self.search_entry.set_sensitive(not busy)
        if self.install_updates is not None:
            self.install_updates.set_sensitive(not busy and self.updates_ready)
            self.style_update_actions()
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
        self.output.get_buffer().set_text(output or "No output.")
        self.status.set_text(title)
        self.status.set_tooltip_text(title)

    def execute(self, title, command, admin=False, timeout=120, mutating=False, finished=None):
        if self.closed or self.busy or self.review_open:
            return
        self.write_pending = mutating
        self.set_busy(True, title)

        def done(rc, output):
            if self.closed:
                return
            self.set_busy(False)
            if finished is not None:
                finished(rc, output)
                return
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

    def check_updates(self, *_args):
        if self.busy or self.review_open:
            return
        self.updates_ready = False

        def refreshed(rc, output):
            if rc:
                self.set_output("Update check failed. See details below.", output)
                self.status.get_style_context().add_class("status-bad")
                return
            partial = "source unavailable:" in output
            self.execute("Reading available updates…", ["ooonana", "upgrade", "--dry-run"],
                         admin=True, timeout=60, finished=lambda code, plan: self.show_update_plan(code, plan, partial))

        self.execute("Checking for updates…", ["ooonana", "update"],
                     admin=True, timeout=180, finished=refreshed)

    def style_update_actions(self):
        for control, primary in ((self.check_button, not self.updates_ready),
                                 (self.install_updates, self.updates_ready)):
            context = control.get_style_context()
            if primary:
                context.add_class("suggested-action")
            else:
                context.remove_class("suggested-action")

    def show_update_plan(self, rc, output, partial):
        context = self.status.get_style_context()
        if rc:
            self.set_output("Couldn’t read available updates. Check again.", output)
            context.add_class("status-bad")
            return
        lines = output.splitlines()
        changes = [line[6].upper() + line[7:].replace(" -> ", " → ")
                   for line in lines if line.startswith(("would upgrade ", "would install "))]
        boot = [line.removeprefix("Fresh USB image required: ").replace(" -> ", " → ")
                for line in lines if line.startswith("Fresh USB image required: ")]
        major = [line.removeprefix("major update needs --allow-major: ").replace(" -> ", " → ")
                 for line in lines if line.startswith("major update needs --allow-major: ")]
        storage = next((line.removeprefix("Storage: ") for line in lines if line.startswith("Storage: ")), "")
        self.updates_ready = bool(changes) and not major
        self.install_updates.set_sensitive(self.updates_ready)
        self.style_update_actions()
        review = []
        if changes:
            review.append("\n".join(changes))
        if boot:
            review.append("Fresh USB image needed\n" + "\n".join(boot))
        if major:
            review.append("Major upgrade needs administrator review\n" + "\n".join(major))
        if storage:
            review.append(storage)
        if partial:
            review.append("Some repositories could not be reached. Check again when connected.")
        if boot and not changes and not major:
            status = "Boot image update available"
        elif major:
            status = "Major upgrade needs review"
        elif changes:
            status = f"{len(changes)} {'package' if len(changes) == 1 else 'packages'} ready to update"
        else:
            status = "No updates found" if partial else "Packages are up to date"
        self.set_output(status, "\n\n".join(review) or "Check again when you want to look for newer packages.")
        context.add_class("status-warn" if boot or major or partial else "status-good")

    def upgrade_system(self, *_args):
        if self.updates and not self.updates_ready:
            return
        self.preview(
            "Installing updates",
            ["ooonana", "upgrade"],
            action="Install updates",
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
            if command == ["ooonana", "upgrade"]:
                if self.updates:
                    self.show_update_plan(0, output, partial=False)
                    if not self.updates_ready:
                        return False
                elif "no upgrades" in output.splitlines():
                    self.status.set_text("No upgrades available.")
                    return False
            self.review_open = True
            try:
                accepted = self.confirm_plan(title, output, action)
            finally:
                self.review_open = False
            if accepted and not self.closed:
                if self.updates:
                    self.updates_ready = False
                self.execute(title, command, admin=True, timeout=timeout, mutating=True,
                             finished=self.update_finished if self.updates else None)
            elif not self.closed:
                self.status.set_text("Review cancelled. No packages changed.")
            return False
        run_async([*command, "--dry-run"], done, admin=True, timeout=60)

    def update_finished(self, rc, output):
        if rc:
            status = "Updates failed. Check details before retrying."
        elif any(line.startswith("reboot required:") for line in output.splitlines()):
            status = "Updates installed. Restart to finish."
        else:
            status = "Package update complete."
        self.set_output(status, output)
        self.status.get_style_context().add_class("status-bad" if rc else "status-good")

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
        content.pack_start(label("Review the changes before applying them.", "muted"), False, False, 0)
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

    def recover_updates(self, *_args):
        if self.closed or self.busy or self.review_open:
            return
        dialog = confirmation_dialog(self, "Recover interrupted package update?",
            "Restores package-owned files and metadata from saved checkpoints. "
            "Does not start an upgrade. If recovery fails, checkpoints stay available for retry. "
            "Administrator password may be requested.", "Recover")
        self.review_open = True
        try:
            accepted = dialog.run() == Gtk.ResponseType.OK
        finally:
            dialog.destroy()
            self.review_open = False
        if self.closed:
            return
        if accepted:
            self.execute("Recovering interrupted package update", ["ooonana", "recover"],
                         admin=True, timeout=180, mutating=True)
        else:
            self.status.set_text("Recovery cancelled. No packages changed.")
            self.status.set_tooltip_text(self.status.get_text())


def main():
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana Packages")
        print("actions: update search install remove upgrade installed sources doctor")
        print("OOONANA_PACKAGES_NATIVE_OK")
        return 0
    apply_theme()
    window = PackagesWindow(updates="--updates" in sys.argv)
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
