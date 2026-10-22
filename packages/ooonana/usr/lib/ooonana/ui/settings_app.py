#!/usr/bin/env python3
import getpass
import os
import socket
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui_preferences import config_path, load_preferences, resolved_theme, save_preferences, transition_ms
from storage_health import storage_health
from common import (  # noqa: E402
    Gdk,
    Gtk,
    Pango,
    apply_theme,
    button,
    card,
    section,
    command_exists,
    flow_row,
    fit_dialog,
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
        self.set_default_size(1000, 620)
        self.set_size_request(820, 540)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.status_widgets = {}
        self.closed = False
        self.status_version = 0
        self.appearance_pending = False
        self.appearance_actions = []
        self.service_actions = []
        self.service_pending = False
        self.metadata_pending = False
        self.dialog_open = False
        self.motion_sync = False
        self.card_grids = []
        self.appearance_rows = []
        self.headerbar = header(
            self,
            "Ooonana Settings",
            "",
            None,
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
        self.stack.set_hhomogeneous(False)
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(transition_ms())
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.page_picker = Gtk.ComboBoxText()
        self.page_picker.set_no_show_all(True)
        self.page_picker.set_margin_start(16)
        self.page_picker.set_margin_end(16)
        self.page_picker.set_margin_top(8)
        self.page_picker.get_accessible().set_name("Settings page")
        self.page_picker.set_tooltip_text("Choose Settings page")
        self.page_picker.connect("changed", self.page_changed)
        content.pack_start(self.page_picker, False, False, 0)
        content.pack_start(self.stack, True, True, 0)
        root.pack_start(content, True, True, 0)

        builders = {
            "overview": self.build_overview,
            "network": self.build_network,
            "hardware": self.build_hardware,
            "appearance": self.build_appearance,
            "apps": self.build_apps,
            "system": self.build_system,
        }
        for page_id, title, icon_name in self.PAGES:
            self.page_picker.append(page_id, title)
            row = Gtk.ListBoxRow()
            row.page_id = page_id
            content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            content.pack_start(icon(icon_name, Gtk.IconSize.LARGE_TOOLBAR), False, False, 0)
            content.pack_start(label(title), True, True, 0)
            row.add(content)
            self.sidebar.add(row)
            self.stack.add_named(self.scrolled_page(builders[page_id]()), page_id)

        self.sidebar.select_row(self.sidebar.get_row_at_index(0))
        self.compact_layout = None
        self.connect("size-allocate", self.resized)
        self.resized(self, self.get_default_size())
        self.connect("destroy", self.on_destroy)
        self.refresh_status()

    @staticmethod
    def scrolled_page(content):
        viewport = Gtk.Viewport()
        viewport.set_shadow_type(Gtk.ShadowType.NONE)
        viewport.add(content)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_overlay_scrolling(False)
        scroll.add(viewport)
        content.set_focus_vadjustment(scroll.get_vadjustment())
        content.set_focus_hadjustment(scroll.get_hadjustment())
        return scroll

    @staticmethod
    def page(title, subtitle):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_border_width(24)
        box.pack_start(page_intro(title, subtitle), False, False, 0)
        return box

    @staticmethod
    def actions(*widgets):
        return flow_row(widgets, max_children=max(1, len(widgets)), min_children=1)

    def service_action(self, title):
        control = button(title, "view-refresh-symbolic", self.repair_services)
        self.service_actions.append(control)
        return control

    def feedback(self, key):
        widget = label("", "muted")
        widget.set_no_show_all(True)
        self.status_widgets[key] = widget
        return widget

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
        self.card_grids.append(grid)
        return grid

    def resized(self, _window, allocation):
        compact, narrow = allocation.width < 900, allocation.width < 720
        if (compact, narrow) == self.compact_layout:
            return
        self.compact_layout = (compact, narrow)
        self.sidebar.set_no_show_all(narrow)
        if not narrow:
            self.sidebar.show_all()
        self.sidebar.set_visible(not narrow)
        self.page_picker.set_visible(narrow)
        for row in self.appearance_rows:
            row.set_orientation(Gtk.Orientation.VERTICAL if compact else Gtk.Orientation.HORIZONTAL)
        self.sidebar.set_size_request(175 if compact else 210, -1)
        for grid in self.card_grids:
            for child in grid.get_children():
                if not hasattr(child, "wide_cell"):
                    child.wide_cell = tuple(grid.child_get_property(child, name) for name in
                                            ("left-attach", "top-attach", "width", "height"))
                left, top, width, height = child.wide_cell
                grid.child_set_property(child, "left-attach", 0 if compact else left)
                grid.child_set_property(child, "top-attach", top * 2 + left if compact else top)
                grid.child_set_property(child, "width", 1 if compact else width)

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
        grid.attach(
            self.status_card(
                "memory",
                "Memory and swap",
                "Available RAM, compressed swap, and live storage mode.",
                "utilities-system-monitor-symbolic",
                button("Processes", "utilities-system-monitor-symbolic", lambda *_: launch(["ooonana-processes"])),
            ),
            0,
            2,
            2,
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
                self.service_action("Repair"),
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
                self.service_action("Repair"),
            ),
            False,
            False,
            0,
        )
        page.pack_start(bluetooth, False, False, 0)
        page.pack_start(self.feedback("repair_network"), False, False, 0)
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
                self.service_action("Reprobe"),
                button("Service log", "text-x-log-symbolic", self.show_service_log),
            ),
            False,
            False,
            0,
        )
        page.pack_start(diagnostics, False, False, 0)
        page.pack_start(self.feedback("repair_hardware"), False, False, 0)
        return page

    def build_appearance(self):
        page = self.page("Appearance", "Ooonana dark mode, light mode, wallpaper, and desktop refresh.")
        page.set_spacing(16)
        page.set_border_width(20)
        theme = section("Color theme", "Dark uses black surfaces and sunset-orange focus.", "preferences-desktop-theme-symbolic")
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.theme_combo = Gtk.ComboBoxText()
        self.theme_combo.get_accessible().set_name("Color theme")
        self.appearance_actions.append(self.theme_combo)
        self.appearance_rows.append(row)
        self.theme_combo.append("dark", "Dark")
        self.theme_combo.append("light", "Light")
        current = self.current_theme()
        self.theme_combo.set_active_id(current if current in ("dark", "light") else "dark")
        row.pack_start(self.theme_combo, True, True, 0)
        theme_apply = button("Apply", "object-select-symbolic", self.apply_selected_theme, "suggested-action")
        self.appearance_actions.append(theme_apply)
        row.pack_start(theme_apply, False, False, 0)
        theme.pack_start(row, False, False, 0)
        page.pack_start(theme, False, False, 0)

        motion = section("Motion", "Short slide transitions; solid backgrounds throughout.", "media-playback-start-symbolic")
        self.reduce_motion = Gtk.CheckButton.new_with_label("Reduce motion")
        self.reduce_motion.set_active(load_preferences()["reduce_motion"])
        self.reduce_motion.connect("toggled", self.motion_changed)
        motion.pack_start(self.reduce_motion, False, False, 0)
        page.pack_start(motion, False, False, 0)

        wallpaper = section("Wallpaper", "Choose image and control scaling without restarting i3.", "preferences-desktop-wallpaper-symbolic")
        self.status_widgets["wallpaper"] = label(self.wallpaper_status(), "muted")
        self.status_widgets["wallpaper"].set_tooltip_text(self.current_wallpaper())
        wallpaper.pack_start(self.status_widgets["wallpaper"], False, False, 0)
        mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.wallpaper_mode_combo = Gtk.ComboBoxText()
        self.wallpaper_mode_combo.get_accessible().set_name("Wallpaper layout")
        self.appearance_actions.append(self.wallpaper_mode_combo)
        self.appearance_rows.append(mode_row)
        self.wallpaper_mode_combo.append("fit", "Fit desktop / keep dock clear")
        self.wallpaper_mode_combo.append("fill", "Fill screen / crop")
        self.wallpaper_mode_combo.append("center", "Center at original size")
        self.wallpaper_mode_combo.append("stretch", "Stretch to screen")
        self.wallpaper_mode_combo.append("tile", "Tile")
        self.wallpaper_mode_combo.set_active_id(self.current_wallpaper_mode())
        for renderer in self.wallpaper_mode_combo.get_cells():
            if isinstance(renderer, Gtk.CellRendererText):
                renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
                renderer.set_property('max-width-chars', 24)
        mode_row.pack_start(self.wallpaper_mode_combo, True, True, 0)
        layout_apply = button("Apply layout", "object-select-symbolic", self.apply_wallpaper_mode)
        self.appearance_actions.append(layout_apply)
        mode_row.pack_start(layout_apply, False, False, 0)
        wallpaper.pack_start(mode_row, False, False, 0)
        choose = button("Choose image", "document-open-symbolic", self.choose_wallpaper, "suggested-action")
        default = button("Default", "edit-undo-symbolic", self.default_wallpaper)
        self.appearance_actions.extend((choose, default))
        wallpaper.pack_start(self.actions(choose, default), False, False, 0)
        page.pack_start(wallpaper, False, False, 0)
        self.appearance_status = label("", "muted")
        page.pack_start(self.appearance_status, False, False, 0)
        return page

    def on_destroy(self, *_args):
        self.closed = True
        if Gtk.main_level():
            Gtk.main_quit()

    def build_apps(self):
        page = self.page("Applications", "Launch Ooonana tools and default desktop applications.")
        grid = self.two_column_grid()
        apps = [
            ("Ooonana AI", "Chat, tools, tasks, and desktop actions.", "system-search-symbolic", ["ooonana-ai-launch"]),
            ("Packages", "Search, install, remove, and upgrade.", "system-software-install-symbolic", ["ooonana-packages-app"]),
            ("Browser", "Chromium under unprivileged desktop user.", "web-browser-symbolic", ["ooonana-browser"]),
            ("Files", "Nemo file manager.", "system-file-manager-symbolic", ["ooonana-files"]),
            ("Editor", "Geany graphical editor.", "accessories-text-editor-symbolic", ["ooonana-editor"]),
            ("Music", "Local library, playback, and volume.", "multimedia-player-symbolic", ["ooonana-music"]),
            ("Task Manager", "Processes and CPU, GPU, RAM, disk, and network performance.", "utilities-system-monitor-symbolic", ["ooonana-processes"]),
        ]
        for index, (title, description, icon_name, command) in enumerate(apps):
            box = card(title, description, icon_name)
            box.pack_start(
                button("Launch", icon_name, lambda _w, cmd=command: launch(cmd)),
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
                button("Refresh metadata", "view-refresh-symbolic", self.package_update),
                button("Open packages", "system-software-install-symbolic", lambda *_: launch(["ooonana-packages-app"])),
            ),
            False,
            False,
            0,
        )
        page.pack_start(source, False, False, 0)
        page.pack_start(self.feedback("metadata"), False, False, 0)

        storage = card("Live storage", "Persistent USB saves changes; temporary sessions do not. Backup/migration requires offline maintenance.", "drive-removable-media-symbolic")
        self.status_widgets["storage"] = label("")
        storage.pack_start(self.status_widgets["storage"], False, False, 0)
        page.pack_start(storage, False, False, 0)

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
            if self.page_picker.get_active_id() != row.page_id:
                self.page_picker.set_active_id(row.page_id)

    def page_changed(self, picker):
        page_id = picker.get_active_id()
        for index, (candidate, _title, _icon) in enumerate(self.PAGES):
            if candidate == page_id:
                row = self.sidebar.get_row_at_index(index)
                if row and self.sidebar.get_selected_row() is not row:
                    self.sidebar.select_row(row)
                return

    def motion_changed(self, widget):
        if self.closed or self.motion_sync:
            return
        previous = load_preferences()["reduce_motion"]
        try:
            save_preferences(reduce_motion=widget.get_active())
        except OSError as exc:
            self.motion_sync = True
            try:
                widget.set_active(previous)
            finally:
                self.motion_sync = False
            message(self, "Could not save motion preference", str(exc), Gtk.MessageType.WARNING)
            return
        settings = Gtk.Settings.get_default()
        if settings:
            settings.set_property("gtk-enable-animations", not widget.get_active())
        self.stack.set_transition_duration(transition_ms())

    def set_status(self, key, text, state="good"):
        widget = self.status_widgets.get(key)
        if not widget:
            return
        widget.set_text(text)
        widget.set_selectable(True)
        widget.set_tooltip_text(text)
        widget.get_accessible().set_description(text)
        if key != "memory":
            widget.set_lines(5 if key == "identity" else 3)
            widget.set_ellipsize(Pango.EllipsizeMode.END)
        if key in ("repair_network", "repair_hardware", "metadata"):
            widget.show()
        context = widget.get_style_context()
        for css in ("status-good", "status-warn", "status-bad", "status-neutral"):
            context.remove_class(css)
        context.add_class(f"status-{state}")

    def refresh_status(self):
        if self.closed:
            return
        self.status_version += 1
        version = self.status_version
        user = getpass.getuser()
        uid = os.geteuid()
        state = "good" if uid != 0 else "bad"
        self.set_status("session", f"{user} (uid {uid})" + (" - root session" if uid == 0 else " - protected desktop"), state)
        self.set_status("identity", f"User: {user}\nUID: {uid}\nHost: {socket.gethostname()}\nEdition: {read_file('/etc/ooonana/edition', 'full-i3')}", state)
        self.set_status("memory", "Checking memory...", "warn")
        def memory_done(rc, text):
            if not self.closed and version == self.status_version:
                self.set_status("memory", text or "Memory status unavailable",
                                "good" if rc == 0 and "Swap: 0 MiB" not in text else "warn")
        run_async(["ooonana-memory", "status"], memory_done, timeout=3)
        self.set_status("network", "Checking NetworkManager...", "warn")
        self.set_status("wifi_detail", "Checking Wi-Fi service...", "warn")
        self.set_status("bluetooth", "Checking BlueZ...", "warn")
        self.set_status("bluetooth_detail", "Checking Bluetooth service...", "warn")

        repo = self.repo_uri()
        health = storage_health()
        self.set_status("storage", health["caption"], "bad" if health["level"] == "critical" else "warn" if health["level"] == "low" else "neutral")
        self.set_status("repo", repo, "neutral")
        self.set_status("repo_detail", repo, "neutral")
        if "wallpaper" in self.status_widgets:
            self.status_widgets["wallpaper"].set_text(self.wallpaper_status())
            self.status_widgets["wallpaper"].set_tooltip_text(self.current_wallpaper())

        wsl = bool(os.environ.get("WSL_DISTRO_NAME")) or "microsoft" in read_file("/proc/sys/kernel/osrelease", "").lower()
        if wsl and not Path("/run/dbus/system_bus_socket").exists():
            self.set_status("network", "Network managed by Windows", "neutral")
            self.set_status("wifi_detail", "Wi-Fi is controlled in Windows while using WSL.", "neutral")
            self.set_status("bluetooth", "Bluetooth managed by Windows", "neutral")
            self.set_status("bluetooth_detail", "Direct Bluetooth access needs a controller passed into WSL.", "neutral")
            return

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

        def done(rc, data):
            if self.closed or version != self.status_version:
                return
            if rc != 0 or not isinstance(data, dict):
                for key in ("network", "wifi_detail", "bluetooth", "bluetooth_detail"):
                    self.set_status(key, str(data) or "Status unavailable; try Refresh.", "bad")
                return
            nm_text = data["nm_out"] or "NetworkManager not ready"
            wifi_text = data["wifi_out"] or "unknown"
            self.set_status("network", nm_text, "good" if data["nm_rc"] == 0 else "bad")
            self.set_status("wifi_detail", f"Service: {nm_text}\nWi-Fi radio: {wifi_text}", "good" if data["nm_rc"] == 0 and data["wifi_rc"] == 0 else "bad")

            bt_out = data["bt_out"]
            if data["bt_rc"] == 0 and "Controller " in bt_out:
                powered = next((line.split(":", 1)[1].strip() for line in bt_out.splitlines() if "Powered:" in line), "unknown")
                bt_text = f"Controller ready - powered {powered}"
                bt_state = "good" if powered == "yes" else "warn"
            elif data["bt_rc"] != 0 and command_exists("bluetoothctl"):
                bt_text = "Bluetooth status unavailable; open Devices or try Refresh.\n" + bt_out
                bt_state = "bad"
            elif data["bt_rc"] == 0:
                bt_text = "No Bluetooth controller reported."
                bt_state = "warn"
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
        return resolved_theme() or "dark"

    @staticmethod
    def current_wallpaper():
        user_wallpaper = Path.home() / ".config/ooonana/wallpaper"
        return read_file(user_wallpaper, "/usr/share/ooonana/wallpapers/ooonana-notes.jpg")

    @staticmethod
    def current_wallpaper_mode():
        mode = read_file(Path.home() / ".config/ooonana/wallpaper-mode", "fit")
        return mode if mode in ("fit", "fill", "center", "stretch", "tile") else "fit"

    def wallpaper_status(self):
        return Path(self.current_wallpaper()).name

    def open_terminal(self, *_args):
        launch(["ooonana-theme-env", "xterm"])

    @staticmethod
    def save_theme(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix="theme.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def appearance_busy(self, text):
        if self.closed or self.appearance_pending:
            return False
        self.appearance_pending = True
        for widget in self.appearance_actions:
            widget.set_sensitive(False)
        self.appearance_status.set_text(text)
        return True

    def appearance_done(self, rc, output, title):
        if self.closed:
            return
        self.appearance_pending = False
        for widget in self.appearance_actions:
            widget.set_sensitive(True)
        self.appearance_status.set_text(title + (" failed. Try again." if rc else " applied."))
        if rc:
            message(self, title + " failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)

    def apply_selected_theme(self, *_args):
        selected = self.theme_combo.get_active_id() or "dark"
        if not self.appearance_busy("Applying theme..."):
            return
        path = config_path().with_name("theme")
        def task():
            previous = path.read_bytes() if path.exists() else None
            current = (selected + "\n").encode()
            self.save_theme(path, current)
            rc, output = run(["ooonana-theme-env", "apply"],
                             env={"OOONANA_THEME": selected, "OOONANA_THEME_OVERRIDE": selected}, timeout=30)
            if rc and path.read_bytes() == current:
                if previous is None:
                    path.unlink()
                else:
                    self.save_theme(path, previous)
            return rc, output
        def done(rc, output):
            if not rc and not self.closed:
                os.environ["OOONANA_THEME"] = selected
                os.environ["OOONANA_THEME_INHERITED"] = selected
                os.environ.pop("OOONANA_THEME_OVERRIDE", None)
                apply_theme()
            self.appearance_done(rc, output, "Theme")
        run_async_task(task, done)

    def choose_wallpaper(self, *_args):
        if self.closed or self.appearance_pending or self.dialog_open:
            return
        self.dialog_open = True
        dialog = Gtk.Dialog(title="Choose Ooonana wallpaper", transient_for=self, modal=True)
        dialog.set_destroy_with_parent(True)
        header(dialog, "Choose wallpaper", "", "preferences-desktop-wallpaper-symbolic")
        fit_dialog(dialog, 780, 540)
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Apply", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        chooser = Gtk.FileChooserWidget(action=Gtk.FileChooserAction.OPEN)
        chooser.set_local_only(True)
        chooser.get_accessible().set_name("Wallpaper image")
        image_filter = Gtk.FileFilter()
        image_filter.set_name("Images")
        image_filter.add_pixbuf_formats()
        chooser.add_filter(image_filter)
        chooser.set_current_folder("/usr/share/ooonana/wallpapers")
        apply = dialog.get_widget_for_response(Gtk.ResponseType.OK)
        apply.set_sensitive(False)
        chooser.connect("selection-changed", lambda *_: apply.set_sensitive(bool(chooser.get_filename())))
        chooser.connect("file-activated", lambda *_: dialog.response(Gtk.ResponseType.OK))
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_overlay_scrolling(False)
        scroll.add(chooser)
        dialog.get_content_area().pack_start(scroll, True, True, 0)
        dialog.show_all()
        try:
            selected = chooser.get_filename() if dialog.run() == Gtk.ResponseType.OK else None
        finally:
            dialog.destroy()
            self.dialog_open = False
        if selected and not self.closed:
            self.apply_wallpaper(selected, self.wallpaper_mode_combo.get_active_id() or "fit")

    def default_wallpaper(self, *_args):
        path = "/usr/share/ooonana/wallpapers/ooonana-notes.jpg"
        self.apply_wallpaper(path, "fit")

    def apply_wallpaper_mode(self, *_args):
        mode = self.wallpaper_mode_combo.get_active_id() or "fit"
        wallpaper = self.current_wallpaper()
        self.apply_wallpaper(wallpaper, mode)

    def apply_wallpaper(self, path, mode):
        if not self.appearance_busy("Applying wallpaper..."):
            return
        def done(rc, output):
            if not rc and not self.closed:
                self.status_widgets["wallpaper"].set_text(Path(path).name)
                self.status_widgets["wallpaper"].set_tooltip_text(path)
                self.wallpaper_mode_combo.set_active_id(mode)
            self.appearance_done(rc, output, "Wallpaper")
        run_async(["ooonana-wallpaper", "--mode", mode, path], done, timeout=30)

    def repair_services(self, widget):
        if self.closed or self.service_pending:
            return
        self.service_pending = True
        for control in self.service_actions:
            control.set_sensitive(False)
        for key in ("repair_network", "repair_hardware"):
            self.set_status(key, "Rechecking services…", "neutral")

        def done(rc, output):
            if self.closed:
                return
            self.service_pending = False
            for control in self.service_actions:
                control.set_sensitive(True)
            self.refresh_status()
            for key in ("repair_network", "repair_hardware"):
                self.set_status(key, "Service repair failed. Try again or open Service log." if rc else "Services rechecked.", "bad" if rc else "neutral")
            if rc != 0:
                message(self, "Service repair failed", output or f"Exit status {rc}", Gtk.MessageType.WARNING)

        run_async(["ooonana-service-repair", "force"], done, admin=True, timeout=30)

    def show_service_log(self, *_args):
        if self.closed or self.dialog_open:
            return
        self.dialog_open = True
        text = "\n\n".join(
            [
                read_file("/var/log/ooonana-services.log", "No service log yet."),
                read_file("/var/log/bluetoothd.log", "No Bluetooth log yet."),
                read_file("/var/log/NetworkManager.log", "No NetworkManager log yet."),
            ]
        )
        dialog = Gtk.Dialog(title="Ooonana service log", transient_for=self, modal=True)
        dialog.set_destroy_with_parent(True)
        header(dialog, "Service log", "", "text-x-log-symbolic")
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_response(Gtk.ResponseType.CLOSE)
        fit_dialog(dialog, 780, 520)
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_monospace(True)
        view.set_cursor_visible(False)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.set_left_margin(12)
        view.set_right_margin(12)
        view.set_top_margin(12)
        view.set_bottom_margin(12)
        view.get_buffer().set_text(text)
        scroll = Gtk.ScrolledWindow()
        scroll.set_overlay_scrolling(False)
        scroll.add(view)
        dialog.get_content_area().pack_start(scroll, True, True, 0)
        copy = button("Copy log", "edit-copy-symbolic", lambda *_: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1))
        dialog.get_action_area().pack_start(copy, False, False, 0)
        dialog.show_all()
        try:
            dialog.run()
        finally:
            dialog.destroy()
            self.dialog_open = False

    def package_update(self, widget):
        if self.closed or self.metadata_pending:
            return
        self.metadata_pending = True
        widget.set_sensitive(False)
        self.set_status("metadata", "Refreshing repository metadata…", "neutral")

        def done(rc, output):
            if self.closed:
                return
            self.metadata_pending = False
            widget.set_sensitive(True)
            self.set_status("metadata", "Metadata refresh failed. Try Refresh metadata again." if rc else "Metadata refreshed. No packages installed.", "bad" if rc else "neutral")
            if rc:
                message(self, "Metadata refresh failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
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
    if "--page" in sys.argv:
        position = sys.argv.index("--page") + 1
        if position < len(sys.argv):
            for index, (page_id, _title, _icon) in enumerate(SettingsWindow.PAGES):
                if page_id == sys.argv[position]:
                    window.sidebar.select_row(window.sidebar.get_row_at_index(index))
                    break
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
