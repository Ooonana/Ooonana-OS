#!/usr/bin/env python3
import getpass
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    Gtk,
    apply_theme,
    button,
    card,
    command_exists,
    header,
    icon,
    label,
    launch,
    message,
    page_intro,
    read_file,
    run,
    run_async,
    run_async_task,
)


class SettingsWindow(Gtk.Window):
    PAGES = [
        ("overview", "Overview", "computer-symbolic"),
        ("network", "Network", "network-wireless-symbolic"),
        ("hardware", "Hardware", "preferences-desktop-peripherals-symbolic"),
        ("appearance", "Appearance", "preferences-desktop-theme-symbolic"),
        ("apps", "Applications", "view-app-grid-symbolic"),
        ("system", "System", "preferences-system-symbolic"),
    ]

    def __init__(self):
        super().__init__(title="Ooonana Settings")
        self.set_default_size(1040, 680)
        self.set_size_request(820, 540)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.status_widgets = {}
        self.headerbar = header(
            self,
            "Ooonana Settings",
            f"{getpass.getuser()}@{socket.gethostname()}",
            "preferences-system-symbolic",
        )
        self.headerbar.pack_end(
            button("Refresh", "view-refresh-symbolic", lambda *_: self.refresh_status())
        )

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(root)

        self.sidebar = Gtk.ListBox()
        self.sidebar.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar.get_style_context().add_class("sidebar")
        self.sidebar.set_size_request(210, -1)
        self.sidebar.connect("row-selected", self.on_page_selected)
        root.pack_start(self.sidebar, False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(140)
        root.pack_start(self.stack, True, True, 0)

        builders = {
            "overview": self.build_overview,
            "network": self.build_network,
            "hardware": self.build_hardware,
            "appearance": self.build_appearance,
            "apps": self.build_apps,
            "system": self.build_system,
        }
        for page_id, title, icon_name in self.PAGES:
            row = Gtk.ListBoxRow()
            row.page_id = page_id
            content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            content.pack_start(icon(icon_name, Gtk.IconSize.LARGE_TOOLBAR), False, False, 0)
            content.pack_start(label(title), True, True, 0)
            row.add(content)
            self.sidebar.add(row)
            self.stack.add_named(self.scrolled_page(builders[page_id]()), page_id)

        self.sidebar.select_row(self.sidebar.get_row_at_index(0))
        self.connect("destroy", Gtk.main_quit)
        self.refresh_status()

    @staticmethod
    def scrolled_page(content):
        viewport = Gtk.Viewport()
        viewport.set_shadow_type(Gtk.ShadowType.NONE)
        viewport.add(content)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(viewport)
        return scroll

    @staticmethod
    def page(title, subtitle):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_border_width(24)
        box.pack_start(page_intro(title, subtitle), False, False, 0)
        return box

    @staticmethod
    def actions(*widgets):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for widget in widgets:
            row.pack_start(widget, False, False, 0)
        return row

    def status_card(self, key, title, description, icon_name, *actions):
        widget = card(title, description, icon_name)
        status = label("Checking...", "status-warn")
        self.status_widgets[key] = status
        widget.pack_start(status, False, False, 0)
        if actions:
            widget.pack_start(self.actions(*actions), False, False, 0)
        return widget

    def two_column_grid(self):
        grid = Gtk.Grid(column_spacing=14, row_spacing=14)
        grid.set_column_homogeneous(True)
        return grid

    def build_overview(self):
        page = self.page("Overview", "Desktop, services, account, and Ooonana health.")
        grid = self.two_column_grid()
        grid.attach(
            self.status_card(
                "session",
                "Desktop session",
                "Unprivileged user session with root services isolated.",
                "avatar-default-symbolic",
                button("Terminal", "utilities-terminal-symbolic", self.open_terminal),
            ),
            0,
            0,
            1,
            1,
        )
        grid.attach(
            self.status_card(
                "network",
                "Network",
                "NetworkManager, Wi-Fi, and active connection.",
                "network-wireless-symbolic",
                button("Wi-Fi", "network-wireless-symbolic", lambda *_: launch(["ooonana-wifi-panel"])),
            ),
            1,
            0,
            1,
            1,
        )
        grid.attach(
            self.status_card(
                "bluetooth",
                "Bluetooth",
                "BlueZ service, controller, and power state.",
                "bluetooth-symbolic",
                button("Devices", "bluetooth-symbolic", lambda *_: launch(["ooonana-bluetooth-panel"])),
            ),
            0,
            1,
            1,
            1,
        )
        grid.attach(
            self.status_card(
                "repo",
                "Package source",
                "Cloud metadata downloads on update; archives download on install.",
                "folder-download-symbolic",
                button("Packages", "system-software-install-symbolic", lambda *_: launch(["ooonana-packages-app"])),
            ),
            1,
            1,
            1,
            1,
        )
        page.pack_start(grid, False, False, 0)
        quick = card("Quick actions", "Common Ooonana tasks.", "system-run-symbolic")
        quick.pack_start(
            self.actions(
                button("Ooonana AI", "system-search-symbolic", lambda *_: launch(["ooonana-ai-launch"])),
                button("Files", "system-file-manager-symbolic", lambda *_: launch(["ooonana-files"])),
                button("Browser", "web-browser-symbolic", lambda *_: launch(["ooonana-browser"])),
                button("Install OS", "drive-harddisk-symbolic", lambda *_: launch(["ooonana-gui-installer"])),
            ),
            False,
            False,
            0,
        )
        page.pack_start(quick, False, False, 0)
        return page

    def build_network(self):
        page = self.page("Network", "Wireless, Bluetooth, radio state, and service repair.")
        wifi = card("Wi-Fi", "Scan, connect, disconnect, and edit saved networks.", "network-wireless-symbolic")
        self.status_widgets["wifi_detail"] = label("Checking...", "status-warn")
        wifi.pack_start(self.status_widgets["wifi_detail"], False, False, 0)
        wifi.pack_start(
            self.actions(
                button("Open Wi-Fi", "network-wireless-symbolic", lambda *_: launch(["ooonana-wifi-panel"]), "suggested-action"),
                button("Connection editor", "document-edit-symbolic", lambda *_: launch(["nm-connection-editor"])),
                button("Repair", "view-refresh-symbolic", self.repair_services),
            ),
            False,
            False,
            0,
        )
        page.pack_start(wifi, False, False, 0)

        bluetooth = card("Bluetooth", "Power, scan, pair, trust, connect, and remove devices.", "bluetooth-symbolic")
        self.status_widgets["bluetooth_detail"] = label("Checking...", "status-warn")
        bluetooth.pack_start(self.status_widgets["bluetooth_detail"], False, False, 0)
        bluetooth.pack_start(
            self.actions(
                button("Open Bluetooth", "bluetooth-symbolic", lambda *_: launch(["ooonana-bluetooth-panel"]), "suggested-action"),
                button("Blueman", "preferences-system-bluetooth-symbolic", lambda *_: launch(["blueman-manager"])),
                button("Repair", "view-refresh-symbolic", self.repair_services),
            ),
            False,
            False,
            0,
        )
        page.pack_start(bluetooth, False, False, 0)
        return page

    def build_hardware(self):
        page = self.page("Hardware", "Display, sound, brightness, touchpad, and device diagnostics.")
        grid = self.two_column_grid()
        items = [
            ("Display", "Arrange monitors and resolution.", "video-display-symbolic", ["arandr"]),
            ("Sound", "Output devices and volume mixer.", "audio-volume-high-symbolic", ["ooonana-audio-panel"]),
            ("Brightness", "Backlight level and hotkey control.", "display-brightness-symbolic", ["ooonana-brightness-panel"]),
            ("Touchpad", "Enable, disable, and inspect input devices.", "input-touchpad-symbolic", ["ooonana-touchpad", "status"]),
        ]
        for index, (title, description, icon_name, command) in enumerate(items):
            box = card(title, description, icon_name)
            box.pack_start(
                button("Open", icon_name, lambda _w, cmd=command: launch(cmd), "suggested-action"),
                False,
                False,
                0,
            )
            grid.attach(box, index % 2, index // 2, 1, 1)
        page.pack_start(grid, False, False, 0)
        diagnostics = card("Hardware diagnostics", "Reprobe drivers and inspect boot-time service logs.", "utilities-system-monitor-symbolic")
        diagnostics.pack_start(
            self.actions(
                button("Reprobe", "view-refresh-symbolic", self.repair_services),
                button("Service log", "text-x-log-symbolic", self.show_service_log),
            ),
            False,
            False,
            0,
        )
        page.pack_start(diagnostics, False, False, 0)
        return page

    def build_appearance(self):
        page = self.page("Appearance", "Ooonana dark mode, light mode, wallpaper, and desktop refresh.")
        theme = card("Color theme", "Dark uses black surfaces and sunset-orange focus.", "preferences-desktop-theme-symbolic")
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.theme_combo = Gtk.ComboBoxText()
        self.theme_combo.append("dark", "Dark")
        self.theme_combo.append("light", "Light")
        current = self.current_theme()
        self.theme_combo.set_active_id(current if current in ("dark", "light") else "dark")
        row.pack_start(self.theme_combo, True, True, 0)
        row.pack_start(button("Apply", "object-select-symbolic", self.apply_selected_theme, "suggested-action"), False, False, 0)
        theme.pack_start(row, False, False, 0)
        page.pack_start(theme, False, False, 0)

        wallpaper = card("Wallpaper", "Choose image and control scaling without restarting i3.", "preferences-desktop-wallpaper-symbolic")
        self.status_widgets["wallpaper"] = label(self.wallpaper_status(), "muted")
        wallpaper.pack_start(self.status_widgets["wallpaper"], False, False, 0)
        mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.wallpaper_mode_combo = Gtk.ComboBoxText()
        self.wallpaper_mode_combo.append("fit", "Fit height / black bars")
        self.wallpaper_mode_combo.append("fill", "Fill screen / crop")
        self.wallpaper_mode_combo.append("center", "Center at original size")
        self.wallpaper_mode_combo.append("stretch", "Stretch to screen")
        self.wallpaper_mode_combo.append("tile", "Tile")
        self.wallpaper_mode_combo.set_active_id(self.current_wallpaper_mode())
        mode_row.pack_start(self.wallpaper_mode_combo, True, True, 0)
        mode_row.pack_start(
            button("Apply layout", "object-select-symbolic", self.apply_wallpaper_mode),
            False,
            False,
            0,
        )
        wallpaper.pack_start(mode_row, False, False, 0)
        wallpaper.pack_start(
            self.actions(
                button("Choose image", "document-open-symbolic", self.choose_wallpaper, "suggested-action"),
                button("Default", "edit-undo-symbolic", self.default_wallpaper),
            ),
            False,
            False,
            0,
        )
        page.pack_start(wallpaper, False, False, 0)
        return page

    def build_apps(self):
        page = self.page("Applications", "Launch Ooonana tools and default desktop applications.")
        grid = self.two_column_grid()
        apps = [
            ("Ooonana AI", "Chat, tools, tasks, and desktop actions.", "system-search-symbolic", ["ooonana-ai-launch"]),
            ("Packages", "Search, install, remove, and upgrade.", "system-software-install-symbolic", ["ooonana-packages-app"]),
            ("Browser", "Chromium under unprivileged desktop user.", "web-browser-symbolic", ["ooonana-browser"]),
            ("Files", "Nemo file manager.", "system-file-manager-symbolic", ["ooonana-files"]),
            ("Editor", "Geany graphical editor.", "accessories-text-editor-symbolic", ["ooonana-editor"]),
            ("Processes", "System process monitor.", "utilities-system-monitor-symbolic", ["ooonana-processes"]),
        ]
        for index, (title, description, icon_name, command) in enumerate(apps):
            box = card(title, description, icon_name)
            box.pack_start(
                button("Launch", icon_name, lambda _w, cmd=command: launch(cmd), "suggested-action"),
                False,
                False,
                0,
            )
            grid.attach(box, index % 2, index // 2, 1, 1)
        page.pack_start(grid, False, False, 0)
        return page

    def build_system(self):
        page = self.page("System", "Account, OS edition, package source, installer, and power.")
        identity = card("Account", "Desktop runs without root privileges.", "avatar-default-symbolic")
        self.status_widgets["identity"] = label("")
        identity.pack_start(self.status_widgets["identity"], False, False, 0)
        page.pack_start(identity, False, False, 0)

        source = card("Ooonana repository", "Primary GitLab Pages package source.", "folder-remote-symbolic")
        self.status_widgets["repo_detail"] = label("")
        source.pack_start(self.status_widgets["repo_detail"], False, False, 0)
        source.pack_start(
            self.actions(
                button("Update", "view-refresh-symbolic", self.package_update),
                button("Open packages", "system-software-install-symbolic", lambda *_: launch(["ooonana-packages-app"])),
            ),
            False,
            False,
            0,
        )
        page.pack_start(source, False, False, 0)

        install = card("Install and power", "Disk writes happen only after installer confirmation.", "drive-harddisk-symbolic")
        install.pack_start(
            self.actions(
                button("Install Ooonana", "drive-harddisk-symbolic", lambda *_: launch(["ooonana-gui-installer"]), "suggested-action"),
                button("Power menu", "system-shutdown-symbolic", lambda *_: launch(["ooonana-power-menu"])),
            ),
            False,
            False,
            0,
        )
        page.pack_start(install, False, False, 0)
        return page

    def on_page_selected(self, _listbox, row):
        if row:
            self.stack.set_visible_child_name(row.page_id)

    def set_status(self, key, text, state="good"):
        widget = self.status_widgets.get(key)
        if not widget:
            return
        widget.set_text(text)
        context = widget.get_style_context()
        for css in ("status-good", "status-warn", "status-bad"):
            context.remove_class(css)
        context.add_class(f"status-{state}")

    def refresh_status(self):
        user = getpass.getuser()
        uid = os.geteuid()
        state = "good" if uid != 0 else "bad"
        self.set_status("session", f"{user} (uid {uid})" + (" - root session" if uid == 0 else " - protected desktop"), state)
        self.set_status("identity", f"User: {user}\nUID: {uid}\nHost: {socket.gethostname()}\nEdition: {read_file('/etc/ooonana/edition', 'full-i3')}", state)
        self.set_status("network", "Checking NetworkManager...", "warn")
        self.set_status("wifi_detail", "Checking Wi-Fi service...", "warn")
        self.set_status("bluetooth", "Checking BlueZ...", "warn")
        self.set_status("bluetooth_detail", "Checking Bluetooth service...", "warn")

        repo = self.repo_uri()
        self.set_status("repo", repo, "good" if repo.startswith("http") else "warn")
        self.set_status("repo_detail", repo, "good" if repo.startswith("http") else "warn")
        if "wallpaper" in self.status_widgets:
            self.status_widgets["wallpaper"].set_text(self.wallpaper_status())

        def task():
            nm_rc, nm_out = run(["nmcli", "-t", "-f", "STATE,CONNECTIVITY", "general"], timeout=3)
            wifi_rc, wifi_out = run(["nmcli", "-t", "-f", "WIFI", "radio"], timeout=3)
            bt_rc, bt_out = run(["bluetoothctl", "show"], admin=True, timeout=4)
            return 0, {
                "nm_rc": nm_rc,
                "nm_out": nm_out,
                "wifi_rc": wifi_rc,
                "wifi_out": wifi_out,
                "bt_rc": bt_rc,
                "bt_out": bt_out,
            }

        def done(_rc, data):
            nm_text = data["nm_out"] or "NetworkManager not ready"
            wifi_text = data["wifi_out"] or "unknown"
            self.set_status("network", nm_text, "good" if data["nm_rc"] == 0 else "bad")
            self.set_status("wifi_detail", f"Service: {nm_text}\nWi-Fi radio: {wifi_text}", "good" if data["nm_rc"] == 0 and data["wifi_rc"] == 0 else "bad")

            bt_out = data["bt_out"]
            if data["bt_rc"] == 0 and "Controller " in bt_out:
                powered = next((line.split(":", 1)[1].strip() for line in bt_out.splitlines() if "Powered:" in line), "unknown")
                bt_text = f"Controller ready - powered {powered}"
                bt_state = "good" if powered == "yes" else "warn"
            elif command_exists("bluetoothctl"):
                bt_text = "BlueZ running; no Bluetooth controller detected"
                bt_state = "bad"
            else:
                bt_text = "bluetoothctl missing"
                bt_state = "bad"
            self.set_status("bluetooth", bt_text, bt_state)
            self.set_status("bluetooth_detail", bt_text, bt_state)

        run_async_task(task, done)

    @staticmethod
    def repo_uri():
        source = read_file("/etc/ooonana/sources.d/cloud.repo", "")
        for line in source.splitlines():
            if line.startswith("OOONANA_REPO_URI="):
                return line.split("=", 1)[1].strip().strip('"')
        return "https://ooonana.gitlab.io/ooonana-repo"

    @staticmethod
    def current_theme():
        user_theme = Path.home() / ".config/ooonana/theme"
        return read_file(user_theme, read_file("/etc/ooonana/theme", "dark"))

    @staticmethod
    def current_wallpaper():
        user_wallpaper = Path.home() / ".config/ooonana/wallpaper"
        return read_file(user_wallpaper, "/usr/share/ooonana/wallpapers/ooonana-notes.jpg")

    @staticmethod
    def current_wallpaper_mode():
        mode = read_file(Path.home() / ".config/ooonana/wallpaper-mode", "fit")
        return mode if mode in ("fit", "fill", "center", "stretch", "tile") else "fit"

    def wallpaper_status(self):
        return f"{self.current_wallpaper()}\nLayout: {self.current_wallpaper_mode()}"

    def open_terminal(self, *_args):
        launch(["ooonana-theme-env", "xterm"])

    def apply_selected_theme(self, *_args):
        selected = self.theme_combo.get_active_id() or "dark"
        path = Path.home() / ".config/ooonana/theme"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(selected + "\n", encoding="utf-8")
        launch(["ooonana-theme-env", "apply"])
        message(self, "Theme applied", f"{selected.title()} theme active. New apps use updated style.")

    def choose_wallpaper(self, *_args):
        dialog = Gtk.FileChooserDialog(
            title="Choose Ooonana wallpaper",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Apply", Gtk.ResponseType.OK)
        image_filter = Gtk.FileFilter()
        image_filter.set_name("Images")
        image_filter.add_pixbuf_formats()
        dialog.add_filter(image_filter)
        dialog.set_current_folder("/usr/share/ooonana/wallpapers")
        if dialog.run() == Gtk.ResponseType.OK:
            mode = self.wallpaper_mode_combo.get_active_id() or "fit"
            launch(["ooonana-wallpaper", "--mode", mode, dialog.get_filename()])
            self.status_widgets["wallpaper"].set_text(f"{dialog.get_filename()}\nLayout: {mode}")
        dialog.destroy()

    def default_wallpaper(self, *_args):
        path = "/usr/share/ooonana/wallpapers/ooonana-notes.jpg"
        self.wallpaper_mode_combo.set_active_id("fit")
        launch(["ooonana-wallpaper", "--mode", "fit", path])
        self.status_widgets["wallpaper"].set_text(f"{path}\nLayout: fit")

    def apply_wallpaper_mode(self, *_args):
        mode = self.wallpaper_mode_combo.get_active_id() or "fit"
        wallpaper = self.current_wallpaper()
        launch(["ooonana-wallpaper", "--mode", mode, wallpaper])
        self.status_widgets["wallpaper"].set_text(f"{wallpaper}\nLayout: {mode}")

    def repair_services(self, widget):
        widget.set_sensitive(False)

        def done(_rc, output):
            widget.set_sensitive(True)
            self.refresh_status()
            if output and "failed" in output.lower():
                message(self, "Service repair", output, Gtk.MessageType.WARNING)

        run_async(["ooonana-service-repair", "force"], done, admin=True, timeout=30)

    def show_service_log(self, *_args):
        text = "\n\n".join(
            [
                read_file("/var/log/ooonana-services.log", "No service log yet."),
                read_file("/var/log/bluetoothd.log", "No Bluetooth log yet."),
                read_file("/var/log/NetworkManager.log", "No NetworkManager log yet."),
            ]
        )
        dialog = Gtk.Dialog(title="Ooonana service log", transient_for=self, modal=True)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(780, 520)
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_monospace(True)
        view.get_buffer().set_text(text)
        scroll = Gtk.ScrolledWindow()
        scroll.add(view)
        dialog.get_content_area().pack_start(scroll, True, True, 0)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def package_update(self, widget):
        widget.set_sensitive(False)

        def done(rc, output):
            widget.set_sensitive(True)
            message(
                self,
                "Package update complete" if rc == 0 else "Package update failed",
                output or f"Exit status {rc}",
                Gtk.MessageType.INFO if rc == 0 else Gtk.MessageType.ERROR,
            )
            self.refresh_status()

        run_async(["ooonana", "update"], done, admin=True, timeout=90)


def main():
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana Settings")
        print("pages: overview network hardware appearance applications system")
        print("OOONANA_SETTINGS_NATIVE_OK")
        return 0
    apply_theme()
    window = SettingsWindow()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
