#!/usr/bin/env python3
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    GLib,
    Gtk,
    admin_command,
    apply_theme,
    button,
    card,
    command_exists,
    header,
    label,
    launch,
    message,
    run,
)


DEFAULT_REPO = "https://ooonana.gitlab.io/ooonana-repo"
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


def field_row(grid, row, title, widget, help_text=""):
    title_label = label(title, xalign=1.0, wrap=False)
    title_label.set_size_request(130, -1)
    grid.attach(title_label, 0, row, 1, 1)
    grid.attach(widget, 1, row, 1, 1)
    if help_text:
        hint = label(help_text, "muted")
        hint.set_margin_top(2)
        grid.attach(hint, 1, row + 1, 1, 1)
        return row + 2
    return row + 1


class SetupWindow(Gtk.Window):
    def __init__(self, first_boot=False):
        super().__init__(title="Ooonana Setup")
        self.first_boot = first_boot
        self.set_default_size(820, 700)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, "Ooonana Setup", "First boot and system defaults", "system-run-symbolic")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)

        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        hero.get_style_context().add_class("hero")
        hero.set_border_width(22)
        hero.pack_start(label("Welcome to Ooonana OS", "hero-title"), False, False, 0)
        hero.pack_start(
            label(
                "Create your everyday account, choose network defaults, and connect the cloud package repository.",
                "page-subtitle",
            ),
            False,
            False,
            0,
        )
        root.pack_start(hero, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content.set_border_width(20)
        scroll.add(content)
        root.pack_start(scroll, True, True, 0)

        identity = card(
            "Account",
            "Desktop runs without root privileges. Administrative tasks use the wheel policy.",
            "avatar-default-symbolic",
        )
        identity_grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        identity_grid.set_column_spacing(14)
        identity_grid.set_column_homogeneous(False)

        current_user = os.environ.get("USER", "ooonana")
        if not USER_RE.fullmatch(current_user) or current_user == "root":
            current_user = "ooonana"
        self.user_entry = Gtk.Entry()
        self.user_entry.set_text(current_user)
        self.user_entry.set_hexpand(True)
        row = field_row(identity_grid, 0, "User name", self.user_entry, "Lowercase letters, numbers, dash, and underscore.")

        self.password_entry = Gtk.Entry()
        self.password_entry.set_visibility(False)
        self.password_entry.set_placeholder_text("Optional")
        row = field_row(identity_grid, row, "Password", self.password_entry)

        self.password_confirm = Gtk.Entry()
        self.password_confirm.set_visibility(False)
        self.password_confirm.set_placeholder_text("Repeat optional password")
        field_row(identity_grid, row, "Confirm", self.password_confirm)
        identity.pack_start(identity_grid, False, False, 0)
        content.pack_start(identity, False, False, 0)

        network = card(
            "Network",
            "DHCP works for most wired and wireless networks. Wi-Fi can be selected separately.",
            "network-wireless-symbolic",
        )
        network_grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        self.network_combo = Gtk.ComboBoxText()
        self.network_combo.append("dhcp", "Automatic (DHCP)")
        self.network_combo.append("static", "Manual address")
        self.network_combo.set_active_id("dhcp")
        self.network_combo.connect("changed", self.network_changed)
        row = field_row(network_grid, 0, "Address mode", self.network_combo)

        self.address_entry = Gtk.Entry()
        self.address_entry.set_placeholder_text("192.168.1.50/24")
        self.gateway_entry = Gtk.Entry()
        self.gateway_entry.set_placeholder_text("192.168.1.1")
        self.dns_entry = Gtk.Entry()
        self.dns_entry.set_placeholder_text("1.1.1.1,8.8.8.8")
        self.static_rows = []
        for title, widget in (
            ("Address", self.address_entry),
            ("Gateway", self.gateway_entry),
            ("DNS", self.dns_entry),
        ):
            title_widget = label(title, xalign=1.0, wrap=False)
            title_widget.set_size_request(130, -1)
            network_grid.attach(title_widget, 0, row, 1, 1)
            network_grid.attach(widget, 1, row, 1, 1)
            self.static_rows.extend((title_widget, widget))
            row += 1

        wifi_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        wifi_row.pack_start(
            button("Choose Wi-Fi", "network-wireless-symbolic", lambda *_: launch(["ooonana-wifi-panel"])),
            False,
            False,
            0,
        )
        wifi_row.pack_start(label("NetworkManager applies Wi-Fi immediately.", "muted"), False, False, 0)
        network_grid.attach(wifi_row, 1, row, 1, 1)
        network.pack_start(network_grid, False, False, 0)
        content.pack_start(network, False, False, 0)

        defaults = card(
            "Desktop and updates",
            "Dark mode uses Ooonana black and sunset orange. Repository metadata stays small.",
            "preferences-desktop-theme-symbolic",
        )
        defaults_grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        self.theme_combo = Gtk.ComboBoxText()
        self.theme_combo.append("dark", "Dark - black and orange")
        self.theme_combo.append("light", "Light - orange and ink")
        self.theme_combo.set_active_id("dark")
        row = field_row(defaults_grid, 0, "Theme", self.theme_combo)
        self.repo_entry = Gtk.Entry()
        self.repo_entry.set_text(DEFAULT_REPO)
        self.repo_entry.set_hexpand(True)
        field_row(defaults_grid, row, "Package repo", self.repo_entry, "Used by ooonana update and ooonana upgrade.")
        defaults.pack_start(defaults_grid, False, False, 0)
        content.pack_start(defaults, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        footer.set_border_width(14)
        self.spinner = Gtk.Spinner()
        footer.pack_start(self.spinner, False, False, 0)
        self.status = label("Ready", "muted", wrap=False)
        footer.pack_start(self.status, True, True, 0)
        footer.pack_end(button("Apply setup", "object-select-symbolic", self.apply, "suggested-action"), False, False, 0)
        footer.pack_end(button("Not now", "window-close-symbolic", lambda *_: self.destroy()), False, False, 0)
        root.pack_end(footer, False, False, 0)

        self.network_changed()
        self.connect("destroy", Gtk.main_quit)

    def network_changed(self, *_args):
        visible = self.network_combo.get_active_id() == "static"
        for widget in self.static_rows:
            widget.set_visible(visible)

    def validate(self):
        user = self.user_entry.get_text().strip()
        password = self.password_entry.get_text()
        confirm = self.password_confirm.get_text()
        if not USER_RE.fullmatch(user):
            return None, "Use a lowercase user name beginning with a letter or underscore."
        if password != confirm:
            return None, "Passwords do not match."
        if any(char in password for char in "\n\r:"):
            return None, "Password contains an unsupported character."
        mode = self.network_combo.get_active_id() or "dhcp"
        address = self.address_entry.get_text().strip()
        gateway = self.gateway_entry.get_text().strip()
        if mode == "static" and (not address or not gateway):
            return None, "Manual network needs address and gateway."
        repo = self.repo_entry.get_text().strip()
        if not repo.startswith(("https://", "http://", "file://", "/")):
            return None, "Package repository needs an HTTPS, HTTP, file, or local path URI."
        return {
            "user": user,
            "password": password,
            "mode": mode,
            "address": address,
            "gateway": gateway,
            "dns": self.dns_entry.get_text().strip(),
            "theme": self.theme_combo.get_active_id() or "dark",
            "repo": repo,
        }, ""

    def apply(self, widget):
        values, error = self.validate()
        if error:
            message(self, "Check setup details", error, Gtk.MessageType.WARNING)
            return
        widget.set_sensitive(False)
        self.spinner.start()
        self.status.set_text("Applying system defaults...")

        def worker():
            command = [
                "/usr/bin/ooonana-setup",
                "--user",
                values["user"],
                "--network",
                values["mode"],
                "--theme",
                values["theme"],
                "--cloud-repo",
                values["repo"],
                "--done",
            ]
            if values["mode"] == "static":
                command.extend(["--address", values["address"], "--gateway", values["gateway"]])
                if values["dns"]:
                    command.extend(["--dns", values["dns"]])
            rc, output = run(command, admin=True, timeout=60)
            if rc == 0 and values["password"]:
                password_command = ["chpasswd"] if command_exists("chpasswd") else ["busybox", "chpasswd"]
                try:
                    result = subprocess.run(
                        admin_command(password_command),
                        input=f'{values["user"]}:{values["password"]}\n',
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=30,
                        check=False,
                    )
                    rc = result.returncode
                    if result.stdout.strip():
                        output = "\n".join(part for part in (output, result.stdout.strip()) if part)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    rc, output = 124, str(exc)
            GLib.idle_add(self.finished, widget, rc, output)

        threading.Thread(target=worker, daemon=True).start()

    def finished(self, widget, rc, output):
        widget.set_sensitive(True)
        self.spinner.stop()
        if rc != 0:
            self.status.set_text("Setup needs attention")
            message(self, "Setup failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            return False
        self.status.set_text("Setup complete")
        message(
            self,
            "Ooonana is ready",
            "Account, network defaults, theme, and package repository were saved.",
            Gtk.MessageType.INFO,
        )
        self.destroy()
        return False


def main():
    first_boot = "--first-boot" in sys.argv
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana first-boot setup")
        print("controls: account password network wifi theme cloud-repo")
        print("OOONANA_SETUP_NATIVE_OK")
        return 0
    if first_boot and Path("/var/lib/ooonana/setup.done").exists():
        return 0
    apply_theme()
    window = SetupWindow(first_boot=first_boot)
    window.show_all()
    window.network_changed()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
