#!/usr/bin/env python3
"""Ooonana's shared live and desktop installer wizard."""

import os
from pathlib import Path
import sys
import tempfile

try:
    from common import (Gdk, GLib, Gtk, apply_theme, button, header, icon, label, launch,
                        light_appearance, run_async_task, transition_ms, use_glass_surface)
    from installer_backend import InstallBackend, command_for, image_device
except (ImportError, ValueError):
    if __name__ == "__main__":
        sys.exit(78)
    raise


ASSETS = Path(__file__).resolve().parents[3] / "share/ooonana"
BOOT_MARK = ASSETS / "boot-mark.png"
TITLE = "Install Ooonana OS"
PAGES = ("Destination", "Account", "System settings", "Review")
THEMES = {"glass": "Glass", "dark": "Graphite", "light": "Paper"}
DEFAULT_REPO = "https://ooonana.gitlab.io/ooonana-repo"


def vertical(spacing=0):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)


def styled(widget, name):
    widget.get_style_context().add_class(name)
    return widget


def entry(name, value="", password=False):
    result = Gtk.Entry()
    result.set_text(value)
    result.set_hexpand(True)
    result.get_accessible().set_name(name)
    if password:
        result.set_visibility(False)
        result.set_input_purpose(Gtk.InputPurpose.PASSWORD)
    return result


def field(parent, name, widget):
    group = vertical(5)
    caption = label(name, "installer-caption")
    caption.set_mnemonic_widget(widget)
    group.pack_start(caption, False, False, 0)
    group.pack_start(widget, False, False, 0)
    parent.pack_start(group, False, False, 0)
    return group


def notice(text=""):
    box = styled(Gtk.Box(spacing=10), "installer-notice")
    box.pack_start(icon("dialog-warning-symbolic"), False, False, 0)
    caption = label(text)
    box.pack_start(caption, True, True, 0)
    return box, caption


def read_only_text():
    view = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
    view.set_left_margin(10)
    view.set_right_margin(10)
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_min_content_height(144)
    scroll.add(view)
    return scroll, view.get_buffer()


def apply_installer_style(window, boot):
    light = not boot and light_appearance()
    panel, text, muted, border, hover, selected, accent, warning = (
        ("#f7f8fa", "#20252d", "#4c5766", "#ccd3dd", "#e9edf3", "#fff1d6", "#845200", "#fff1da")
        if light else
        ("#181b22", "#f6f4f0", "#c3c6ce", "#40454f", "#252a33", "#382e24", "#ffd991", "#362b23")
    )
    css = f"""
    window.installer-boot {{
        background: #111419 url('{ASSETS / "grub-ui/backdrop.png"}') center / cover no-repeat;
    }}
    .installer-frame {{
        background-color: {panel}; color: {text}; border: 1px solid {border};
        border-radius: 16px;
    }}
    .installer-frame viewport, .installer-frame scrolledwindow {{ background: transparent; }}
    .installer-desktop .installer-frame {{
        border-top: none; border-top-left-radius: 0; border-top-right-radius: 0;
    }}
    .installer-desktop.glass-theme.composited-surface .installer-frame {{ background-color: rgba(24,27,34,.88); }}
    headerbar.installer-header, headerbar.installer-header:backdrop {{
        background-image: none; background-color: {panel}; border-color: {border}; min-height: 36px;
    }}
    .installer-header .title {{ color: {text}; }}
    .installer-brand {{ color: #f6f4f0; font-size: 17pt; font-weight: 600; }}
    .installer-title {{ color: {text}; font-size: 22pt; font-weight: 600; }}
    .installer-caption {{ color: {muted}; font-weight: 600; }}
    .installer-detail, .installer-step {{ color: {muted}; }}
    .installer-step {{ padding: 9px 11px; border-radius: 8px; }}
    .installer-step.current {{ color: {accent}; background-color: {selected}; font-weight: 600; }}
    .installer-rail {{ border-right: 1px solid {border}; padding: 20px 14px; }}
    .installer-footer {{ border-top: 1px solid {border}; padding: 14px 22px; }}
    .installer-footer button {{ min-height: 27px; padding: 5px 15px; }}
    .installer-primary {{ background: #ffbc52; color: #21170d; border-color: #ffbc52; text-shadow: none; }}
    .installer-primary:hover {{ background: #ffd287; }}
    .installer-primary:disabled {{ background: {hover}; border-color: {border}; color: {muted}; }}
    .installer-mode {{ border: 1px solid {border}; border-radius: 8px; padding: 8px 11px; }}
    .installer-mode.current {{ background: {selected}; color: {accent}; border-color: #936f39; }}
    .installer-mode radio:checked {{ background-image: none; background-color: #ffbc52;
                                    border-color: #ffbc52; color: #251909; }}
    .installer-disks {{ background: transparent; }}
    .installer-disks row {{ padding: 9px 11px; border: 1px solid transparent; border-radius: 8px; }}
    .installer-disks row:hover {{ background: {hover}; }}
    .installer-disks row:selected {{ background: {selected}; border-color: #936f39; color: {text}; }}
    .installer-disks row:disabled {{ color: {muted}; }}
    .installer-notice {{ background: {warning}; color: {accent}; border: 1px solid #936f39;
                          border-radius: 8px; padding: 8px 10px; }}
    .installer-value {{ color: {text}; font-weight: 600; }}
    .installer-summary-row {{ border-top: 1px solid {border}; min-height: 21px; padding: 7px 8px; }}
    .installer-erase-value {{ color: {accent}; }}
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_screen(window.get_screen(), provider,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
    window.connect("destroy", lambda obj: Gtk.StyleContext.remove_provider_for_screen(obj.get_screen(), provider))


class InstallerWindow(Gtk.ApplicationWindow):
    def __init__(self, application=None, *, boot=False, backend=None):
        super().__init__(application=application, title=TITLE)
        self.boot = boot
        self.backend = backend if backend is not None else InstallBackend()
        self.devices = {}
        self.selected = None
        self.mode = "disk"
        self.page = 0
        self.pending = False
        self.prepared = None
        self.log_dir = None
        self.log_timer = 0
        self.closing = False
        self.set_icon_name("ooonana-installer")
        self.set_role("ooonana-installer")
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("delete-event", lambda *_: self.pending)
        self.connect("destroy", self.destroyed)
        self.connect("key-press-event", self.key_press)

        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        area = monitor.get_workarea()
        self.compact = area.width < 860 or self.create_pango_layout("System settings").get_pixel_size()[0] > 155
        margin = 12 if self.compact else 28
        width = min(1064 if boot else 830, area.width - 2 * margin)
        height = min(545 if boot else 602, area.height - (96 if boot else 64))

        if boot:
            styled(self, "installer-boot")
            self.set_decorated(False)
            self.fullscreen()
        else:
            styled(self, "installer-desktop")
            use_glass_surface(self)
            self.set_default_size(width, height)
            styled(header(self, TITLE, icon_name=None), "installer-header")
        apply_installer_style(self, boot)

        frame = styled(vertical(), "installer-frame")
        if boot:
            outer = vertical(24 if not self.compact else 10)
            outer.set_halign(Gtk.Align.CENTER)
            outer.set_valign(Gtk.Align.CENTER)
            outer.set_margin_bottom(20 if not self.compact else 0)
            outer.set_size_request(width, -1)
            frame.set_size_request(-1, height)
            brand = Gtk.Box(spacing=13)
            mark = Gtk.Image.new_from_file(str(ASSETS / "grub-ui/icons/ooonana-install.png"))
            if BOOT_MARK.is_file():
                from gi.repository import GdkPixbuf
                mark.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(str(BOOT_MARK), 46, 32, True))
            brand.pack_start(mark, False, False, 0)
            brand.pack_start(label(TITLE, "installer-brand"), True, True, 0)
            outer.pack_start(brand, False, False, 0)
            outer.pack_start(frame, True, True, 0)
            self.add(outer)
        else:
            self.add(frame)

        body = Gtk.Box()
        frame.pack_start(body, True, True, 0)
        self.steps = []
        if boot and not self.compact:
            rail = styled(vertical(5), "installer-rail")
            rail.set_size_request(246, -1)
            for stage in PAGES:
                marker = label(stage, "installer-step")
                rail.pack_start(marker, False, False, 0)
                self.steps.append(marker)
            body.pack_start(rail, False, False, 0)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_overlay_scrolling(False)
        self.scroll.set_propagate_natural_height(False)
        body.pack_start(self.scroll, True, True, 0)
        page_container = vertical(10)
        page_container.set_border_width(18 if self.compact else 26)
        self.scroll.add(page_container)
        page_container.set_focus_vadjustment(self.scroll.get_vadjustment())
        self.step_label = styled(label(), "installer-detail")
        self.step_label.set_no_show_all(True)
        page_container.pack_start(self.step_label, False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_homogeneous(False)
        self.stack.set_transition_duration(transition_ms())
        page_container.pack_start(self.stack, True, True, 0)
        self.stack.add_named(self.destination_page(), "0")
        self.stack.add_named(self.account_page(), "1")
        self.stack.add_named(self.settings_page(), "2")
        self.review = vertical(10)
        self.stack.add_named(self.review, "3")
        self.result = vertical(12)
        self.stack.add_named(self.result, "4")

        footer = styled(Gtk.Box(spacing=10), "installer-footer")
        self.back = button("Cancel", callback=self.go_back)
        self.next = styled(button("Continue", callback=self.advance), "installer-primary")
        if not self.compact:
            self.next.set_size_request(134, -1)
        self.next.set_can_default(False)
        self.next.set_receives_default(False)
        self.spinner = Gtk.Spinner()
        self.status = label("", "installer-detail")
        footer.pack_start(self.back, False, False, 0)
        footer.pack_start(self.spinner, False, False, 0)
        footer.pack_start(self.status, True, True, 0)
        footer.pack_end(self.next, False, False, 0)
        frame.pack_end(footer, False, False, 0)
        self.review_warning, self.review_warning_text = notice()
        self.review_warning.set_no_show_all(True)
        self.review_warning.set_margin_start(18 if self.compact else 26)
        self.review_warning.set_margin_end(18 if self.compact else 26)
        self.review_warning.set_margin_bottom(12)
        frame.pack_end(self.review_warning, False, False, 0)
        self.show_all()
        self.set_page(0)
        self.refresh_drives()

    def destination_page(self):
        page = vertical(14)
        heading = Gtk.Box(spacing=8)
        heading.pack_start(label("Choose installation disk", "installer-title"), True, True, 0)
        refresh = button("Refresh", "view-refresh-symbolic", lambda *_: self.refresh_drives())
        refresh.set_valign(Gtk.Align.CENTER)
        heading.pack_end(refresh, False, False, 0)
        page.pack_start(heading, False, False, 0)
        modes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if self.compact else Gtk.Orientation.HORIZONTAL, spacing=8)
        self.erase = styled(Gtk.RadioButton.new_with_label_from_widget(None, "Erase disk"), "installer-mode")
        self.custom = styled(Gtk.RadioButton.new_with_label_from_widget(self.erase, "Custom partitions"), "installer-mode")
        for mode in (self.erase, self.custom):
            modes.pack_start(mode, False, False, 0)
        field(page, "Installation mode", modes)

        self.disks = styled(Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE), "installer-disks")
        self.disks.set_activate_on_single_click(False)
        self.disks.connect("row-selected", self.disk_selected)
        self.disk_group = field(page, "Target drive", self.disks)
        self.disk_note = label("", "installer-detail")
        self.disk_note.set_no_show_all(True)
        page.pack_start(self.disk_note, False, False, 0)

        self.alternative = Gtk.Expander(label="Use an existing disk image")
        self.image_path = entry("Disk image path")
        self.image_path.set_placeholder_text("/path/to/disk.img")
        self.image_path.connect("changed", lambda *_: self.refresh_destination())
        self.alternative.add(self.image_path)
        self.alternative.connect("notify::expanded", lambda *_: self.refresh_destination())
        page.pack_start(self.alternative, False, False, 0)

        self.partition_fields = vertical(10)
        self.partition_fields.set_no_show_all(True)
        self.partitions = {}
        for role, title, format_default in (("root", "Root partition", True), ("home", "Home partition (optional)", True),
                                           ("swap", "Swap partition (optional)", True), ("efi", "EFI partition", False)):
            combo = Gtk.ComboBoxText()
            combo.get_accessible().set_name(title)
            field(self.partition_fields, title, combo)
            check = Gtk.CheckButton(label=f"Format {role} partition", active=format_default)
            self.partition_fields.pack_start(check, False, False, 0)
            self.partitions[role] = combo, check
            combo.connect("changed", self.partition_changed, role)
        page.pack_start(self.partition_fields, False, False, 0)
        self.disk_warning, self.disk_warning_text = notice()
        self.disk_warning.set_no_show_all(True)
        page.pack_start(self.disk_warning, False, False, 0)
        self.erase.connect("toggled", self.change_mode)
        return page

    def account_page(self):
        page = vertical(14)
        page.pack_start(label("Create account", "installer-title"), False, False, 0)
        page.pack_start(label("Use this account to sign in and authorize system changes.", "installer-detail"),
                        False, False, 0)
        self.user = entry("User name", "ooonana")
        self.password = entry("Password", password=True)
        self.confirm = entry("Confirm password", password=True)
        field(page, "User name", self.user)
        field(page, "Password", self.password)
        field(page, "Confirm password", self.confirm)
        return page

    def settings_page(self):
        page = vertical(13)
        page.pack_start(label("System settings", "installer-title"), False, False, 0)
        self.hostname = entry("Hostname", "ooonana")
        self.theme = Gtk.ComboBoxText()
        for identifier, title in THEMES.items():
            self.theme.append(identifier, title)
        self.theme.set_active_id("glass")
        self.swap = Gtk.SpinButton.new_with_range(0, 131072, 1)
        self.swap.set_numeric(True)
        self.swap.get_accessible().set_name("Disk swap (MiB)")
        self.repo = entry("Package repository", DEFAULT_REPO)
        self.source = entry("Source root", "/")
        field(page, "Hostname", self.hostname)
        field(page, "Theme", self.theme)
        self.swap_group = field(page, "Disk swap (MiB)", self.swap)
        self.swap_group.pack_start(label("0 uses compressed swap only.", "installer-detail"), False, False, 0)
        advanced = Gtk.Expander(label="Package source and installation files")
        options = vertical(10)
        field(options, "Package repository", self.repo)
        field(options, "Source root", self.source)
        advanced.add(options)
        page.pack_start(advanced, False, False, 0)
        return page

    def refresh_drives(self):
        self.set_pending(True, "Reading drives…")
        run_async_task(self.backend.inventory, self.drives_loaded)

    def drives_loaded(self, rc, value):
        if self.closing:
            return
        self.devices = {} if rc else value
        self.selected = None
        for row in self.disks.get_children():
            self.disks.remove(row)
        for device in self.devices.values():
            if device.kind != "disk":
                continue
            row = Gtk.ListBoxRow()
            row.device = device
            row.set_selectable(not device.unavailable)
            row.set_activatable(False)
            item = Gtk.Box(spacing=12)
            indicator = icon("security-high-symbolic" if device.unavailable else "drive-harddisk-symbolic")
            item.pack_start(indicator, False, False, 0)
            description = vertical(4)
            title = "Boot USB" if device.unavailable == "Boot media is protected" else device.model
            description.pack_start(label(title, "installer-value"), False, False, 0)
            note = f"{device.path}  ·  {device.unavailable}" if device.unavailable else device.path
            description.pack_start(label(note, "installer-detail"), False, False, 0)
            item.pack_start(description, True, True, 0)
            item.pack_end(label(device.capacity, "installer-detail"), False, False, 0)
            row.add(item)
            row.set_sensitive(not device.unavailable)
            self.disks.add(row)
        self.disks.show_all()
        self.disks.unselect_all()
        self.load_partitions()
        self.set_pending(False)
        self.disk_note.set_text(
            "Could not read drives. Select Refresh to retry." if rc else "No drives found.")
        self.refresh_destination()

    def disk_selected(self, _box, row):
        self.selected = row.device if row is not None else None
        self.refresh_destination()

    def load_partitions(self):
        self.loading_partitions = True
        for role, (combo, check) in self.partitions.items():
            combo.remove_all()
            combo.append("", "None" if role in ("home", "swap") else "Select partition")
            combo.set_active(0)
            check.set_sensitive(False)
            if role == "root":
                for device in self.devices.values():
                    if device.kind == "part" and not device.unavailable:
                        combo.append(device.path, f"{device.path}  ·  {device.capacity}")
        self.loading_partitions = False

    def partition_changed(self, _combo, role):
        if getattr(self, "loading_partitions", False):
            return
        combo, check = self.partitions[role]
        path = combo.get_active_id()
        check.set_sensitive(bool(path))
        if role == "root":
            root = self.devices.get(path)
            self.loading_partitions = True
            for other, (choice, check) in self.partitions.items():
                if other == "root":
                    continue
                choice.remove_all()
                choice.append("", "None" if other in ("home", "swap") else "Select partition")
                if root:
                    for device in self.devices.values():
                        if (device.kind == "part" and device.disk == root.disk
                                and not device.unavailable and device.path != root.path):
                            choice.append(device.path, f"{device.path}  ·  {device.capacity}")
                choice.set_active(0)
                check.set_sensitive(False)
            self.loading_partitions = False
        self.refresh_destination()

    def change_mode(self, *_args):
        self.mode = "disk" if self.erase.get_active() else "partition"
        self.refresh_destination()

    def refresh_destination(self):
        whole = self.mode == "disk"
        for widget in (self.erase, self.custom):
            style = widget.get_style_context()
            (style.add_class if widget.get_active() else style.remove_class)("current")
        list_visible = whole and not self.alternative.get_expanded()
        self.disk_group.set_visible(list_visible)
        self.disk_note.set_visible(list_visible and not self.disks.get_children())
        self.alternative.set_visible(whole)
        self.partition_fields.set_visible(not whole)
        if not whole:
            for child in self.partition_fields.get_children():
                child.show_all()
        target = self.selected if whole and not self.alternative.get_expanded() else None
        self.disk_warning_text.set_text(f"Erase disk removes all data on {target.model}." if target else "")
        self.disk_warning.set_visible(target is not None)
        if target:
            for child in self.disk_warning.get_children():
                child.show()
        if hasattr(self, "next") and self.page == 0 and not self.pending:
            ready = bool(self.image_path.get_text()) if self.alternative.get_expanded() else target is not None
            if not whole:
                ready = all(self.partitions[key][0].get_active_id() for key in ("root", "efi"))
            self.next.set_sensitive(ready)

    def set_page(self, page):
        self.page = page
        # Show review and progress without a snapshot of the preceding form.
        transition = Gtk.StackTransitionType.NONE if page >= 3 else Gtk.StackTransitionType.SLIDE_LEFT_RIGHT
        self.stack.set_visible_child_full(str(page), transition)
        for index, widget in enumerate(self.steps):
            context = widget.get_style_context()
            (context.add_class if index == page else context.remove_class)("current")
        self.step_label.set_visible(not self.steps and page < 3)
        if page < 4:
            self.step_label.set_text(f"Step {page+1} of {len(PAGES)}  ·  {PAGES[page]}")
        self.back.set_label("Cancel" if page == 0 else "Back")
        self.back.set_visible(page < 4)
        self.review_warning.set_visible(page == 3)
        self.next.set_label(("Continue", "Continue", "Review installation", "Install now", "Close")[page])
        self.swap_group.set_visible(self.mode == "disk")
        self.set_pending(False)
        self.scroll.get_vadjustment().set_value(0)
        if page == 0:
            self.refresh_destination()
        elif page == 1:
            self.user.grab_focus()
        elif page == 2:
            self.hostname.grab_focus()
        else:
            self.back.grab_focus()

    def set_pending(self, pending, text=""):
        self.pending = pending
        self.back.set_sensitive(not pending)
        self.next.set_sensitive(not pending)
        self.stack.set_sensitive(not pending)
        self.status.set_text(text)
        self.status.set_visible(bool(text))
        self.spinner.set_visible(pending)
        if pending:
            self.spinner.start()
        else:
            self.spinner.stop()

    def go_back(self, *_args):
        if self.pending:
            return
        self.prepared = None
        if self.page in (0, 4):
            self.close()
        elif self.page < 4:
            self.set_page(self.page - 1)

    def key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape and not self.pending:
            self.go_back()
            return True
        return False

    def destinations(self):
        partitions = {}
        if self.mode == "disk":
            if self.alternative.get_expanded():
                target = image_device(self.image_path.get_text())
            else:
                target = self.selected
            if target is None:
                raise ValueError("Select a destination drive.")
            return target, (), partitions
        for role, (combo, check) in self.partitions.items():
            partitions[role] = (combo.get_active_id() or "", check.get_active())
        root = partitions["root"][0]
        paths = [path for path, _format in partitions.values() if path]
        if not root or not partitions["efi"][0]:
            raise ValueError("Select root and EFI partitions.")
        if len(paths) != len(set(paths)):
            raise ValueError("Choose a different partition for each role.")
        return self.devices[root], tuple(self.devices[path] for path in paths if path != root), partitions

    def validate_account(self):
        password = self.password.get_text()
        if not self.user.get_text().strip() or not password:
            raise ValueError("Enter a user name and password.")
        if password != self.confirm.get_text() or any(ch in password for ch in "\r\n\0"):
            raise ValueError("Enter matching passwords on one line.")

    def advance(self, *_args):
        if self.pending:
            return
        try:
            if self.page == 0:
                self.target, self.extra, self.plan = self.destinations()
                self.set_page(1)
            elif self.page == 1:
                self.validate_account()
                self.set_page(2)
            elif self.page == 2:
                self.preview()
            elif self.page == 3:
                self.start_install()
            else:
                self.close()
        except (OSError, ValueError) as exc:
            self.set_pending(False, str(exc))

    def preview(self):
        self.validate_account()
        self.swap.update()
        swap_size = self.swap.get_value_as_int() if self.mode == "disk" else 0
        if 0 < swap_size < 512:
            raise ValueError("Use 0 or at least 512 MiB of disk swap.")
        self.argv = command_for(self.mode, self.target.path, self.user.get_text().strip(),
                                self.hostname.get_text().strip(), self.theme.get_active_id(),
                                self.repo.get_text().strip(), self.source.get_text().strip() or "/",
                                swap_size, self.plan)
        password = self.password.get_text()
        self.set_pending(True, "Checking destination…")
        run_async_task(lambda: self.backend.preview(self.argv, password, (self.target, *self.extra)),
                       self.preview_ready)

    def preview_ready(self, rc, result):
        if self.closing:
            return
        if rc:
            self.set_pending(False, "Installation blocked. Review details.")
            self.show_blocked(result)
            return
        self.prepared, detail = result
        self.build_review(detail)
        self.set_page(3)

    def show_blocked(self, result):
        dialog = Gtk.Dialog(title="Installation blocked", transient_for=self, modal=True)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_response(Gtk.ResponseType.CLOSE)
        dialog.set_default_size(min(self.get_size().width - 40, 700), 320)
        scroll, buffer = read_only_text()
        buffer.set_text(result)
        dialog.get_content_area().pack_start(scroll, True, True, 12)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def build_review(self, detail):
        for child in self.review.get_children():
            self.review.remove(child)
        self.review.pack_start(label("Review installation", "installer-title"), False, False, 0)
        self.review.pack_start(label("Verify destination and settings before installing.", "installer-detail"),
                               False, False, 0)
        destination = f"{self.target.model}  ·  {self.target.capacity}\n{self.target.path}"
        swap_size = self.swap.get_value_as_int()
        values = [("Destination", destination), ("Install mode", "Erase disk" if self.mode == "disk" else "Custom partitions"),
                  ("Account", self.user.get_text().strip()), ("Hostname", self.hostname.get_text().strip())]
        if self.mode == "disk":
            values.append(("Disk swap", f"{swap_size / 1024:g} GiB" if swap_size else "Compressed swap only"))
            warning = f"All data on {self.target.model} will be erased."
        else:
            for role, (path, should_format) in self.plan.items():
                if path:
                    values.append((role.capitalize(), f"{path}  ·  {'Format' if should_format else 'Keep'}"))
            warning = "Installation changes the listed partitions. Check each format choice."
        values.extend((("Theme", THEMES[self.theme.get_active_id()]),
                       ("Package source", "Ooonana repository" if self.repo.get_text().strip() == DEFAULT_REPO
                        else self.repo.get_text().strip() or "Local only")))
        source_root = self.source.get_text().strip()
        if source_root and source_root != "/":
            values.append(("Source root", source_root))
        table = vertical()
        for name, value in values:
            row = styled(vertical(3) if self.compact else Gtk.Box(spacing=14), "installer-summary-row")
            name_label = label(name, "installer-detail")
            if not self.compact:
                name_label.set_size_request(205, -1)
            row.pack_start(name_label, False, False, 0)
            value_label = label(value, "installer-value")
            if name == "Install mode" and self.mode == "disk":
                styled(value_label, "installer-erase-value")
            row.pack_start(value_label, True, True, 0)
            table.pack_start(row, False, False, 0)
        self.review.pack_start(table, False, False, 0)
        self.review_warning_text.set_text(warning)
        for child in self.review_warning.get_children():
            child.show()
        details = Gtk.Expander(label="Installation plan")
        scroll, buffer = read_only_text()
        buffer.set_text(detail)
        details.add(scroll)
        self.review.pack_start(details, False, False, 0)
        self.review.show_all()

    def start_install(self):
        if not self.prepared:
            return
        self.log_dir = tempfile.TemporaryDirectory(prefix="ooonana-install-ui-")
        self.log_path = Path(self.log_dir.name) / "install.log"
        password = self.password.get_text()
        self.password.set_text("")
        self.confirm.set_text("")
        token, self.prepared = self.prepared, None
        self.result_heading = label("Installing Ooonana OS", "installer-title")
        self.result.pack_start(self.result_heading, False, False, 0)
        self.result_note = label("Wait for installation to finish before restarting.", "installer-detail")
        self.result.pack_start(self.result_note, False, False, 0)
        scroll, self.log_buffer = read_only_text()
        self.result.pack_start(scroll, True, True, 0)
        self.result.show_all()
        self.set_page(4)
        self.set_pending(True, "Installing…")
        # Keep the log readable while navigation and window closing are blocked.
        self.stack.set_sensitive(True)
        self.log_timer = GLib.timeout_add(400, self.update_log)
        run_async_task(lambda: self.backend.install(self.argv, password, token, self.log_path), self.install_finished)

    def update_log(self):
        if self.log_path.is_file():
            with self.log_path.open("rb") as stream:
                stream.seek(max(0, self.log_path.stat().st_size - 65536))
                self.log_buffer.set_text(stream.read(65536).decode("utf-8", "replace"))
        return True

    def install_finished(self, rc, error):
        GLib.source_remove(self.log_timer)
        self.log_timer = 0
        self.update_log()
        if error:
            self.log_buffer.insert(self.log_buffer.get_end_iter(), "\n" + error)
        self.result_heading.set_text("Installation failed" if rc else "Installation complete")
        self.result_note.set_text("Review the install log before retrying." if rc
                                  else "Restart when ready and boot from the installed disk.")
        if rc:
            self.result.pack_start(button("Open shell", callback=lambda *_: launch(
                ["ooonana-theme-env", "xterm", "-e", "/bin/sh", "-l"])), False, False, 0)
            self.result.show_all()
        self.set_pending(False)

    def destroyed(self, *_args):
        self.closing = True
        if self.log_timer:
            GLib.source_remove(self.log_timer)
        if self.log_dir is not None:
            self.log_dir.cleanup()


class InstallerApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.ooonana.Installer")

    def do_activate(self):
        window = self.get_active_window()
        if window is None:
            apply_theme()
            window = InstallerWindow(self, boot=os.environ.get("OOONANA_INSTALLER_BOOT") == "1")
        window.present()


def main():
    if not Gtk.init_check(None)[0]:
        return 78
    return InstallerApplication().run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
