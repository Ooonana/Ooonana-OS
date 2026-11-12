#!/usr/bin/env python3
import ipaddress
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    GLib,
    Gtk,
    Pango,
    admin_command,
    apply_theme,
    button,
    card,
    command_exists,
    fit_dialog,
    header,
    label,
    launch,
    message,
    run,
    transition_ms,
)
from ui_preferences import load_preferences


DEFAULT_REPO = "https://ooonana.gitlab.io/ooonana-repo"
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


def field_row(grid, row, title, widget, help_text=""):
    stacked = getattr(grid, "stacked", False)
    title_label = label(title, xalign=0.0 if stacked else 1.0)
    title_label.set_mnemonic_widget(widget)
    widget.get_accessible().set_name(title)
    title_label.set_size_request(-1 if stacked else 130, -1)
    grid.attach(title_label, 0, row, 1, 1)
    grid.attach(widget, 0 if stacked else 1, row + 1 if stacked else row, 1, 1)
    row += 2 if stacked else 1
    if help_text:
        hint = label(help_text, "muted")
        hint.set_margin_top(2)
        grid.attach(hint, 0 if stacked else 1, row, 1, 1)
        row += 1
    return row


class SetupWindow(Gtk.Window):
    def __init__(self, first_boot=False):
        super().__init__(title="Ooonana Setup")
        self.closed = False
        self.pending = False
        self.review_dialog = None
        self.invalid_field = None
        self.first_boot = first_boot
        self.set_default_size(800, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, "Ooonana Setup", "First boot and system defaults", "system-run-symbolic")
        self.stack_fields = self.create_pango_layout("Compressed swap").get_pixel_size()[0] > self.get_default_size().width * .28

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)

        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        hero.get_style_context().add_class("hero")
        hero.set_border_width(0)
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

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_kinetic_scrolling(True)
        scroll.set_overlay_scrolling(False)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content.set_border_width(20)
        self.content = content
        scroll.add(content)
        content.set_focus_vadjustment(scroll.get_vadjustment())
        content.set_focus_hadjustment(scroll.get_hadjustment())
        content.pack_start(hero, False, False, 0)
        root.pack_start(scroll, True, True, 0)

        identity = card(
            "Account",
            "Desktop runs without root privileges. Administrative tasks use the wheel policy.",
            "avatar-default-symbolic",
        )
        identity_grid = self.form_grid()
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
        self.password_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.password_entry.set_placeholder_text("Optional")
        row = field_row(identity_grid, row, "Password", self.password_entry)

        self.password_confirm = Gtk.Entry()
        self.password_confirm.set_visibility(False)
        self.password_confirm.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.password_confirm.set_placeholder_text("Repeat optional password")
        field_row(identity_grid, row, "Confirm", self.password_confirm)
        identity.pack_start(identity_grid, False, False, 0)
        content.pack_start(identity, False, False, 0)

        network = card(
            "Network",
            "DHCP works for most wired and wireless networks. Wi-Fi can be selected separately.",
            "network-wireless-symbolic",
        )
        network_grid = self.form_grid()
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
        self.static_revealer = Gtk.Revealer()
        self.static_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.static_revealer.set_transition_duration(transition_ms())
        static_grid = self.form_grid()
        static_row = 0
        for title, widget in (
            ("Address", self.address_entry),
            ("Gateway", self.gateway_entry),
            ("DNS", self.dns_entry),
        ):
            widget.set_hexpand(True)
            static_row = field_row(static_grid, static_row, title, widget)
        self.static_revealer.add(static_grid)
        network_grid.attach(self.static_revealer, 0, row, 1 if self.stack_fields else 2, 1)
        row += 1

        wifi_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if self.stack_fields else Gtk.Orientation.HORIZONTAL, spacing=8)
        wifi_row.pack_start(
            button("Choose Wi-Fi", "network-wireless-symbolic", lambda *_: launch(["ooonana-wifi-panel"])),
            False,
            False,
            0,
        )
        wifi_row.pack_start(label("NetworkManager applies Wi-Fi immediately.", "muted"), False, False, 0)
        network_grid.attach(wifi_row, 0 if self.stack_fields else 1, row, 1, 1)
        network.pack_start(network_grid, False, False, 0)
        content.pack_start(network, False, False, 0)

        defaults = card(
            "Desktop and updates",
            "Dark mode uses solid graphite and warm orange. Repository metadata stays small.",
            "preferences-desktop-theme-symbolic",
        )
        defaults_grid = self.form_grid()
        self.theme_combo = Gtk.ComboBoxText()
        self.theme_combo.append("dark", "Dark - graphite and orange")
        self.theme_combo.append("light", "Light - paper and ink")
        self.theme_combo.set_active_id("dark")
        row = field_row(defaults_grid, 0, "Theme", self.theme_combo)
        self.repo_entry = Gtk.Entry()
        self.repo_entry.set_text(DEFAULT_REPO)
        self.repo_entry.set_hexpand(True)
        field_row(defaults_grid, row, "Package repo", self.repo_entry, "Used by ooonana update and ooonana upgrade.")
        defaults.pack_start(defaults_grid, False, False, 0)
        content.pack_start(defaults, False, False, 0)

        memory = card(
            "Memory and swap",
            "Compressed swap runs in RAM. Disk swap uses only a partition already chosen during installation. Applies next boot.",
            "utilities-system-monitor-symbolic",
        )
        memory_grid = self.form_grid()
        self.zram_combo = Gtk.ComboBoxText()
        for percent, title in (("0", "Off"), ("25", "Light - 25%"), ("50", "Balanced - 50%"), ("75", "Large - 75%"), ("100", "Maximum - 100%")):
            self.zram_combo.append(percent, title)
        self.zram_combo.set_active_id("50")
        row = field_row(memory_grid, 0, "Compressed swap", self.zram_combo)
        self.disk_swap_check = Gtk.CheckButton(label="Use installer-configured disk swap")
        self.disk_swap_check.set_active(True)
        swap_label = self.disk_swap_check.get_child()
        swap_label.set_line_wrap(True)
        swap_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        swap_label.set_max_width_chars(30)
        memory_grid.attach(self.disk_swap_check, 0 if self.stack_fields else 1, row, 1, 1)
        memory.pack_start(memory_grid, False, False, 0)
        content.pack_start(memory, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        footer.set_border_width(14)
        self.spinner = Gtk.Spinner()
        footer.pack_start(self.spinner, False, False, 0)
        self.status = label("Scroll for memory, theme, and package repo ↓", "muted", wrap=False)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        self.status.set_max_width_chars(28)
        self.status.set_hexpand(True)
        self.status.set_tooltip_text(self.status.get_text())
        footer.pack_start(self.status, True, True, 0)
        self.apply_button = button("Apply setup", "object-select-symbolic", self.apply, "suggested-action")
        self.cancel_button = button("Not now", "window-close-symbolic", lambda *_: self.destroy())
        footer.pack_end(self.apply_button, False, False, 0)
        footer.pack_end(self.cancel_button, False, False, 0)
        root.pack_end(footer, False, False, 0)

        self.network_changed()
        self.connect("delete-event", self.before_close)
        self.connect("destroy", self.on_destroy)
        fit_dialog(self, 800, 600)

    def form_grid(self):
        grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        grid.stacked = self.stack_fields
        return grid

    def feedback(self, text, state="neutral"):
        if self.closed:
            return
        self.status.set_text(text)
        self.status.set_tooltip_text(text)
        self.status.get_accessible().set_description(text)
        context = self.status.get_style_context()
        for name in ("neutral", "bad", "good", "warn"):
            context.remove_class("status-" + name)
        context.add_class("status-" + state)

    def on_destroy(self, *_args):
        self.closed = True
        self.spinner.stop()
        if self.review_dialog is not None:
            self.review_dialog.destroy()
            self.review_dialog = None
        if Gtk.main_level():
            Gtk.main_quit()

    def before_close(self, *_args):
        if self.pending:
            self.feedback("Setup running · wait before closing", "warn")
        return self.pending

    def network_changed(self, *_args):
        self.static_revealer.set_reveal_child(self.network_combo.get_active_id() == "static")

    def validate(self):
        if self.invalid_field is not None:
            self.invalid_field.get_style_context().remove_class("error")
            self.invalid_field.get_accessible().set_description("")
        self.invalid_field = None

        def invalid(widget, text):
            self.invalid_field = widget
            return None, text

        user = self.user_entry.get_text().strip()
        password = self.password_entry.get_text()
        confirm = self.password_confirm.get_text()
        if not USER_RE.fullmatch(user):
            return invalid(self.user_entry, "Use a lowercase user name beginning with a letter or underscore.")
        if password != confirm:
            return invalid(self.password_confirm, "Passwords do not match.")
        if any(char in password for char in "\n\r:"):
            return invalid(self.password_entry, "Password contains an unsupported character.")
        mode = self.network_combo.get_active_id() or "dhcp"
        address = self.address_entry.get_text().strip()
        gateway = self.gateway_entry.get_text().strip()
        dns = self.dns_entry.get_text().strip()
        if mode == "static":
            try:
                if "/" not in address:
                    raise ValueError()
                ipaddress.IPv4Interface(address)
            except ValueError:
                return invalid(self.address_entry, "Enter an IPv4 address and prefix, for example 192.168.1.50/24.")
            try:
                ipaddress.IPv4Address(gateway)
            except ValueError:
                return invalid(self.gateway_entry, "Enter a valid IPv4 gateway, for example 192.168.1.1.")
            try:
                dns = ",".join(str(ipaddress.IPv4Address(item)) for item in re.split(r"[,\s]+", dns) if item)
            except ValueError:
                return invalid(self.dns_entry, "Enter IPv4 DNS addresses separated by commas or spaces.")
        repo = self.repo_entry.get_text().strip()
        try:
            parsed = urlsplit(repo)
            valid_repo = repo.startswith("/") or (parsed.scheme in ("https", "http") and bool(parsed.hostname)) or (parsed.scheme == "file" and bool(parsed.path))
        except ValueError:
            valid_repo = False
        if not valid_repo or any(not char.isprintable() for char in repo):
            return invalid(self.repo_entry, "Use an HTTPS, HTTP, file URI, or absolute local path for the package repository.")
        return {
            "user": user,
            "password": password,
            "mode": mode,
            "address": address,
            "gateway": gateway,
            "dns": dns,
            "theme": self.theme_combo.get_active_id() or "dark",
            "zram_percent": self.zram_combo.get_active_id() or "50",
            "disk_swap": "on" if self.disk_swap_check.get_active() else "off",
            "repo": repo,
        }, ""

    def apply(self, widget):
        if self.closed or self.pending or self.review_dialog is not None:
            return
        values, error = self.validate()
        if error:
            self.feedback(error, "bad")
            self.invalid_field.get_style_context().add_class("error")
            self.invalid_field.get_accessible().set_description(error)
            self.invalid_field.grab_focus()
            return
        review = Gtk.Dialog(title="Review setup", transient_for=self, modal=True)
        review.set_destroy_with_parent(True)
        review.set_icon_name("ooonana-setup")
        fit_dialog(review, 620, 480)
        summary = label(
            f'Account: {values["user"]}\nNetwork: {values["mode"]}\nTheme: {values["theme"]}\n'
            + (f'Address: {values["address"]}\nGateway: {values["gateway"]}\nDNS: {values["dns"] or "Not specified"}\n' if values["mode"] == "static" else "")
            + f'Package repository: {values["repo"]}\n'
            + f'Password: {"Supplied" if values["password"] else "Not supplied"}\n'
            +
            f'Compressed swap: {values["zram_percent"]}% of RAM, subject to system cap\n'
            f'Existing installer disk swap: {values["disk_swap"]}\n\n'
            "Setup does not create or format disk partitions. Memory policy applies next boot."
        )
        summary.set_selectable(True)
        summary.set_valign(Gtk.Align.START)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(summary)
        area = review.get_content_area()
        area.set_border_width(16)
        area.set_spacing(10)
        area.pack_start(label("Review setup", "card-title"), False, False, 0)
        area.pack_start(scroll, True, True, 0)
        review.add_button("Back", Gtk.ResponseType.CANCEL)
        review.add_button("Apply setup", Gtk.ResponseType.OK).get_style_context().add_class("suggested-action")
        review.set_default_response(Gtk.ResponseType.CANCEL)
        self.review_dialog = review
        review.show_all()
        try:
            response = review.run()
        finally:
            review.destroy()
            self.review_dialog = None
        if self.closed or response != Gtk.ResponseType.OK:
            return
        self.pending = True
        self.apply_button.set_sensitive(False)
        self.cancel_button.set_sensitive(False)
        self.content.set_sensitive(False)
        if not load_preferences()["reduce_motion"]:
            self.spinner.start()
        self.feedback("Applying system defaults…", "warn")

        def worker():
            command = [
                "/usr/bin/ooonana-setup",
                "--user",
                values["user"],
                "--network",
                values["mode"],
                "--theme",
                values["theme"],
                "--zram-percent",
                values["zram_percent"],
                "--disk-swap",
                values["disk_swap"],
                "--cloud-repo",
                values["repo"],
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
            if rc == 0:
                done_rc, done_output = run(["/usr/bin/ooonana-setup", "--done"], admin=True, timeout=15)
                rc = done_rc
                output = "\n".join(part for part in (output, done_output) if part)
            GLib.idle_add(self.finished, widget, rc, output)

        threading.Thread(target=worker, daemon=True).start()

    def finished(self, widget, rc, output):
        if self.closed:
            return False
        self.pending = False
        self.apply_button.set_sensitive(True)
        self.cancel_button.set_sensitive(True)
        self.content.set_sensitive(True)
        self.spinner.stop()
        if rc != 0:
            self.feedback("Setup failed; changes may be partial. " + (output or f"Exit status {rc}") + " Check details, then retry.", "bad")
            return False
        self.feedback("Setup complete", "good")
        message(
            self,
            "Ooonana is ready",
            "Account, network, theme, memory policy, and package repository were saved. Swap settings apply next boot.",
            Gtk.MessageType.INFO,
        )
        self.destroy()
        return False


def main():
    first_boot = "--first-boot" in sys.argv
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana first-boot setup")
        print("controls: account password network wifi theme zram disk-swap cloud-repo")
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
