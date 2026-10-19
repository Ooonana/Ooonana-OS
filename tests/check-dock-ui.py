#!/usr/bin/env python3
"""Own Xvfb/i3 fixture only. No user's windows, models or sound."""
import os
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana/ui"))
from dock_app import Dock, Gdk, GdkX11, Gtk, preview_image, windows
from common import apply_theme, header
from dock_model import PinStore
from gi.repository import Gio
import i3_events

def drain():
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)

def wait(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while not predicate():
        drain()
        assert time.monotonic() < deadline, "Dock fixture timeout"
        time.sleep(0.02)

def centered_icons(dock):
    for control, dot, image in dock.buttons.values():
        overlay = control.get_child()
        assert isinstance(overlay, Gtk.Overlay)
        assert overlay.get_overlay_pass_through(dot)
        x, y = image.translate_coordinates(control, 0, 0)[-2:]
        assert abs(x + image.get_allocated_width() / 2 - control.get_allocated_width() / 2) <= 1
        assert abs(y + image.get_allocated_height() / 2 - control.get_allocated_height() / 2) <= 1

with tempfile.TemporaryDirectory() as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (root / "branding/i3/config").read_text().splitlines()
                                if not line.startswith("exec")) + "\n")
    environment = {**os.environ, "PATH": str(root / "packages/ooonana/usr/bin") + ":" + os.environ["PATH"]}
    os.environ["PATH"] = environment["PATH"]
    wm = subprocess.Popen(["i3", "-c", str(config)], env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    terminal, dock = None, None
    owned = []
    native = []
    terminal_log = tempfile.TemporaryFile()
    try:
        def connected():
            try:
                return bool(i3_events.socket_path())
            except (OSError, subprocess.SubprocessError):
                return False
        wait(connected)
        terminal = subprocess.Popen(["xterm", "-title", "Preview fixture", "-bg", "#101317", "-fg", "#f5f5f7", "-e", "sh", "-c", "printf 'Preview fixture'; sleep 120"], env=environment, stdout=terminal_log, stderr=terminal_log)
        path = i3_events.socket_path()
        def terminal_ready():
            if terminal.poll() is not None:
                terminal_log.seek(0)
                raise AssertionError("Xterm fixture exited: " + terminal_log.read().decode(errors="replace"))
            return any(item[1] == "Preview fixture" for item in windows.windows(i3_events.request(path, 4)))
        wait(terminal_ready)
        Gtk.IconTheme.get_default().append_search_path(str(root / "packages/ooonana/usr/share/icons/hicolor/scalable/apps"))
        Gtk.Settings.get_default().set_property("gtk-xft-dpi", int(96 * 1024 * float(os.environ.get("OOONANA_GUI_TEXT_SCALE", "1.0"))))
        apply_theme()
        dock = Dock(subscribe=False)
        dock.snapshot = i3_events.request(path, 4)
        dock.refresh()
        drain()
        assert not dock.get_accept_focus() and not dock.get_focus_on_map()
        item = next(item for item in dock.items if item[1] == "Preview fixture")
        picture = preview_image(dock.nodes[item[0]])
        assert picture is not None and picture.get_width() <= 240 and picture.get_height() <= 150
        assert preview_image(dock.nodes[item[0]], hidden=True) is None
        before = next(item[0] for item in windows.windows(i3_events.request(path, 4)) if item[2])
        content = dock.tooltip_content("terminal")
        assert any(isinstance(child, Gtk.Image) for child in content.get_children())
        heading = content.get_children()[0].get_children()[0]
        assert heading.get_xalign() == 0 and heading.get_style_context().has_class("dock-preview-title")
        caption = content.get_children()[-1]
        assert caption.get_xalign() == 0 and caption.get_style_context().has_class("dock-preview-caption")
        assert content.get_preferred_width().natural_width <= 300
        assert next(item[0] for item in windows.windows(i3_events.request(path, 4)) if item[2]) == before
        button = dock.buttons["terminal"][0]
        assert not dock.get_resizable()
        assert any(isinstance(child, Gtk.Separator) for child in dock.row.get_children())
        assert button.get_style_context().has_class("active")
        assert button.get_accessible().get_description() == "1 window · Focused"
        assert dock.buttons["apps"][0].get_accessible().get_description() == "Not running"
        saved = dock.groups["terminal"]
        dock.groups["terminal"] = [(item[0], "Very long title " * 8, False, True, *item[4:]),
                      (item[0], "Second minimized session", False, True, *item[4:])]
        minimized = dock.tooltip_content("terminal")
        assert not any(isinstance(child, Gtk.Image) for child in minimized.get_children())
        assert all(label.get_ellipsize() for label in minimized.get_children()[1:])
        assert minimized.get_preferred_width().natural_width <= 300
        assert minimized.get_children()[0].get_children()[1].get_text() == "2 windows"
        dock.groups["terminal"] = saved
        image = dock.buttons['terminal'][2]
        size = dock.get_size()
        assert 56 <= size.height <= 64, size
        assert image.get_pixel_size() == 32
        assert button.get_allocated_width() >= 44 and button.get_allocated_height() >= 44
        centered_icons(dock)
        # Wider window counts remain overlays, never layout rows.
        marker = dock.buttons['terminal'][1]
        marker.set_text('99')
        for _ in range(5):
            drain()
            time.sleep(0.02)
        centered_icons(dock)
        assert dock.get_size() == size
        marker.set_text('•')
        # Flat dock never lifts/scales icons or changes frame size on hover.
        assert image.get_margin_top() == image.get_margin_bottom() == 0
        assert dock.get_size() == size
        # Many unpinned apps: overflow appears only when real space runs out.
        geometry = dock.monitor_geometry
        snapshot = dock.snapshot
        extras = [dict(id=987654 + index, window=987654 + index, name=f"Compact unpinned fixture {index}",
                       window_properties={"class": f"QAOther{index}"}, nodes=[], floating_nodes=[])
                  for index in range(12)]
        dock.snapshot = {**snapshot, "nodes": [*snapshot.get("nodes", []), *extras]}
        for width in (320, 480):
            dock.monitor_geometry = lambda width=width: SimpleNamespace(x=0, y=0, width=width, height=768)
            dock.geometry_state = None
            dock.refresh()
            wait(lambda: dock.get_size().width <= width - 24 and
                 all(control.get_allocated_width() >= 44 and control.get_allocated_height() >= 44
                     for control, _dot, _image in dock.buttons.values()))
            assert "other" in dock.buttons
            assert len(dock.matches("other")) == sum(len(dock.groups.get(key, [])) for key in dock.overflow)
            overflow_menu = dock.context_menu("other")
            assert {getattr(row, "ooonana_app", None) for row in overflow_menu.get_children()} - {None} == {
                key for key in dock.overflow if not dock.groups.get(key)}
            assert len([row for row in overflow_menu.get_children() if isinstance(row, Gtk.MenuItem)
                        and (row.get_accessible().get_name() or "").startswith("Compact unpinned fixture")]) == len(dock.matches("other"))
            overflow_menu.destroy()
            centered_icons(dock)
            assert all(control.get_allocated_width() >= 44 and control.get_allocated_height() >= 44
                       for control, _dot, _image in dock.buttons.values())
        dock.monitor_geometry = geometry
        dock.snapshot = snapshot
        dock.geometry_state = None
        dock.refresh()
        wait(lambda: dock.get_size() == size)
        button = dock.buttons["terminal"][0]
        image = dock.buttons["terminal"][2]
        coordinates = button.translate_coordinates(dock, 0, 0)
        x, y = coordinates[-2:]
        origin = dock.get_position()
        dock.get_display().get_default_seat().get_pointer().warp(dock.get_screen(), origin[0] + x + 12, origin[1] + y + 12)
        for _ in range(90):
            drain()
            time.sleep(0.02)
        assert next(item[0] for item in windows.windows(i3_events.request(path, 4)) if item[2]) == before
        assert image.get_margin_top() == image.get_margin_bottom() == 0
        centered_icons(dock)
        assert windows.panel_layout(640)[0] == "task-view media"
        assert windows.panel_layout(1024)[2] == 0 and windows.panel_layout(1280)[2] == 1

        def current():
            return windows.windows(i3_events.request(path, 4))
        def dock_node(identifier):
            return next(node for node, _hidden in windows.leaves(i3_events.request(path, 4)) if node["id"] == identifier)
        def by_title(title):
            return next((entry for entry in current() if entry[1] == title), None)
        secondary = subprocess.Popen(["xterm", "-title", "Secondary fixture", "-e", "sleep", "120"], env=environment)
        owned.append(secondary)
        wait(lambda: by_title("Secondary fixture"))
        selected = by_title("Secondary fixture")
        primary = by_title("Preview fixture")
        real_choose = windows.choose
        windows.choose = lambda choices, _prompt: next(entry for entry in choices if entry[0] == selected[0])
        try:
            windows.dock_open(current(), "terminal")
        finally:
            windows.choose = real_choose
        wait(lambda: by_title("Secondary fixture")[2])
        def sync_dock():
            dock.snapshot = i3_events.request(path, 4)
            dock.refresh()
            wait(lambda: all(control.get_allocated_width() >= 44 for control, *_ in dock.buttons.values()))
        # Real app click uses MRU without a middle-screen chooser. One restore,
        # not every minimized sibling, and clicking focused app never hides it.
        sync_dock()
        windows.focus(primary)
        wait(lambda: by_title("Preview fixture")[2])
        sync_dock()
        for entry in (primary, selected):
            windows.window_action(entry, "minimize")
        wait(lambda: by_title("Preview fixture")[3] and by_title("Secondary fixture")[3])
        sync_dock()
        dock.open("terminal")
        wait(lambda: by_title("Preview fixture")[2] and not by_title("Preview fixture")[3])
        assert by_title("Secondary fixture")[3]
        sync_dock()
        dock.open("terminal")
        wait(lambda: by_title("Preview fixture")[2])
        assert by_title("Secondary fixture")[3]

        def native_group_menu(key="terminal"):
            sync_dock()
            control = dock.buttons[key][0]
            point = control.translate_coordinates(dock, 0, 0)
            origin = dock.get_position()
            scale = dock.get_scale_factor()
            subprocess.run(["xdotool", "mousemove", "--sync",
                            str((origin[0] + point[0] + control.get_allocated_width() // 2) * scale),
                            str((origin[1] + point[1] + control.get_allocated_height() // 2) * scale), "click", "3"], check=True)
            wait(lambda: dock.menu is not None and dock.menu.get_visible())
            root_window = Gdk.get_default_root_window()
            rect = dock.menu.get_toplevel().get_window().get_frame_extents()
            assert 0 <= rect.x and rect.x + rect.width <= root_window.get_width(), rect
            assert 0 <= rect.y and rect.y + rect.height <= root_window.get_height(), rect

        def activate_menu(name):
            rows = [row for row in dock.menu.get_children() if row.get_sensitive() and not isinstance(row, Gtk.SeparatorMenuItem)]
            index = next(index for index, row in enumerate(rows) if row.get_accessible().get_name() == name)
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Home", *(["Down"] * index), "Return"], check=True)

        def drag_icon(source, target):
            sync_dock()
            events = []
            for signal in ("drag-begin", "drag-data-get", "drag-end"):
                dock.buttons[source][0].connect(signal, lambda _widget, *args, signal=signal: events.append(signal))
            dock.buttons[target][0].connect("drag-data-received", lambda *_: events.append("drag-data-received"))
            def center(key):
                control = dock.buttons[key][0]
                point = control.translate_coordinates(dock, 0, 0)
                origin = dock.get_position()
                scale = dock.get_scale_factor()
                return [str((origin[0] + point[0] + control.get_allocated_width() // 2) * scale),
                        str((origin[1] + point[1] + control.get_allocated_height() // 2) * scale)]
            start, end = center(source), center(target)
            middle = [str(int(start[0]) + (12 if int(end[0]) >= int(start[0]) else -12)), start[1]]
            gesture = subprocess.Popen(["xdotool", "mousemove", "--sync", *start, "mousedown", "1", "sleep", ".4",
                                        "mousemove", "--sync", *middle, "sleep", ".2",
                                        "mousemove", "--sync", *end, "sleep", ".4", "mouseup", "1"])
            wait(lambda: gesture.poll() is not None and dock.drag_key is None)
            for _ in range(20):
                drain()
                time.sleep(.02)
            assert gesture.returncode == 0
            print('DOCK_DRAG_EVENTS', source, target, events, flush=True)
            assert 'drag-begin' in events and 'drag-end' in events, (source, target, start, end, events)
            centered_icons(dock)

        native_group_menu()
        canvas = Gdk.get_default_root_window()
        Gdk.pixbuf_get_from_window(canvas, 0, 0, canvas.get_width(), canvas.get_height()).savev("/qa/dock-app-windows.png", "png", [], [])
        # First direct window row is focused primary, next is hidden secondary.
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Home", "Down", "Return"], check=True)
        wait(lambda: by_title("Secondary fixture")[2] and not by_title("Secondary fixture")[3])
        wait(lambda: dock.menu is None)
        assert not by_title("Preview fixture")[3]
        native_group_menu()
        # Flat app menu actions explicitly name the target; no nested submenu.
        assert not any(row.get_submenu() for row in dock.menu.get_children())
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Home", "Down", "Down", "Down", "Return"], check=True)
        wait(lambda: by_title("Secondary fixture")[3])
        wait(lambda: dock.menu is None)
        assert not by_title("Preview fixture")[3]
        sync_dock()
        dock.open("terminal")
        wait(lambda: by_title("Preview fixture")[2])
        assert by_title("Secondary fixture")[3], "Visible session must win over hidden sibling"
        native_group_menu()
        app_menu = dock.menu
        # Per-window keyboard context does not focus/restore another session.
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Home", "Down", "shift+F10"], check=True)
        wait(lambda: dock.menu is not None and dock.menu is not app_menu and dock.menu.get_visible())
        assert by_title("Secondary fixture")[3] and by_title("Preview fixture")[2]
        assert not any(row.get_submenu() for row in dock.menu.get_children())
        canvas = Gdk.get_default_root_window()
        Gdk.pixbuf_get_from_window(canvas, 0, 0, canvas.get_width(), canvas.get_height()).savev("/qa/dock-window-actions.png", "png", [], [])
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"], check=True)
        wait(lambda: dock.menu is None)
        assert by_title("Secondary fixture")[3]
        windows.window_action(selected, "minimize")
        wait(lambda: by_title("Secondary fixture")[3])
        windows.dock_open([by_title("Secondary fixture")], "terminal")
        wait(lambda: by_title("Secondary fixture")[2] and not by_title("Secondary fixture")[3])
        windows.window_action(by_title("Secondary fixture"), "fullscreen")
        wait(lambda: dock_node(selected[0]).get("fullscreen_mode") == 1)
        windows.window_action(by_title("Secondary fixture"), "fullscreen")
        wait(lambda: not dock_node(selected[0]).get("fullscreen_mode"))
        windows.window_action(by_title("Secondary fixture"), "close")
        wait(lambda: by_title("Secondary fixture") is None)
        assert by_title("Preview fixture")[0] == primary[0]

        # Actual shared native headers/roles, a transient Gtk dialog and an app
        # title change. These are owned fixtures, not real Settings operations.
        settings = Gtk.Window(title="Ooonana Settings")
        header(settings, "Settings")
        settings.add(Gtk.Label(label="Owned native Settings header fixture"))
        packages = Gtk.Window(title="Ooonana Packages")
        header(packages, "Packages")
        packages.add(Gtk.Label(label="Owned native Packages header fixture"))
        chooser = Gtk.Dialog(title="Owned transient chooser", transient_for=settings)
        chooser.get_content_area().add(Gtk.Label(label="Owned transient relationship fixture"))
        native.extend([settings, packages, chooser])
        for window in native:
            window.show_all()
        def native_item(window):
            xid = GdkX11.X11Window.get_xid(window.get_window())
            snapshot = i3_events.request(path, 4)
            con = next((node["id"] for node, _hidden in windows.leaves(snapshot) if node.get("window") == xid), None)
            return next((item for item in windows.windows(snapshot) if item[0] == con), None)
        try:
            wait(lambda: all(native_item(window) for window in native))
        except AssertionError:
            Path('/qa/native-groups-timeout.json').write_text(json.dumps(i3_events.request(path, 4), indent=2))
            canvas = Gdk.get_default_root_window()
            Gdk.pixbuf_get_from_window(canvas, 0, 0, canvas.get_width(), canvas.get_height()).savev('/qa/native-groups-timeout.png', 'png', [], [])
            raise
        settings_item, packages_item, chooser_item = map(native_item, native)
        print('NATIVE_DOCK_IDENTITIES', json.dumps([settings_item, packages_item, chooser_item]), flush=True)
        sync_dock()
        assert {entry[0] for entry in dock.matches("ooonana-settings")} == {settings_item[0], chooser_item[0]}
        assert {entry[0] for entry in dock.matches("ooonana-packages")} == {packages_item[0]}
        settings.set_title("Owned renamed Settings window")
        wait(lambda: native_item(settings)[1] != settings_item[1])
        sync_dock()
        assert {entry[0] for entry in dock.matches("ooonana-settings")} == {settings_item[0], chooser_item[0]}
        canvas = Gdk.get_default_root_window()
        Gdk.pixbuf_get_from_window(canvas, 0, 0, canvas.get_width(), canvas.get_height()).savev("/qa/dock-app-groups.png", "png", [], [])
        for window in reversed(native):
            window.destroy()
        native.clear()
        wait(lambda: not any(entry[0] in {settings_item[0], packages_item[0], chooser_item[0]} for entry in current()))
        sync_dock()

        # Real Gio declared New window action launches only another owned XTerm.
        app_dir = Path.home() / ".local/share/applications"
        app_dir.mkdir(parents=True, exist_ok=True)
        desktop = app_dir / "ooonana-qa-dock-action.desktop"
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Owned dock action\n'
                           'Exec=/usr/bin/xterm -class QADockAction -title "Owned action first" -e sleep 120\nStartupWMClass=QADockAction\nIcon=utilities-terminal\nActions=new-window;\n'
                           '[Desktop Action new-window]\nName=New window\n'
                           'Exec=/usr/bin/xterm -class QADockAction -title "Owned action second" -e sleep 120\n')
        wait(lambda: any(app.get_id() == desktop.name for app in Gio.AppInfo.get_all()))
        app = next(app for app in Gio.AppInfo.get_all() if app.get_id() == desktop.name)
        assert app and app.list_actions() == ["new-window"]
        dock.catalog_changed()
        action_client = subprocess.Popen(["xterm", "-class", "QADockAction", "-title", "Owned action first", "-e", "sleep", "120"], env=environment)
        owned.append(action_client)
        wait(lambda: by_title("Owned action first"))
        native_group_menu("class:qadockaction")
        activate_menu("New window")
        wait(lambda: by_title("Owned action second"))
        sync_dock()
        assert len(dock.matches("class:qadockaction")) == 2 and "class:qadockaction" in dock.buttons
        native_group_menu("class:qadockaction")
        activate_menu("Pin to dock")
        wait(lambda: any(record["key"] == "class:qadockaction" for record in dock.pins.records))
        saved_path = dock.pins.path
        assert PinStore(saved_path, []).records == dock.pins.records
        saved = saved_path.read_text()
        assert "Owned action" not in saved and "window:" not in saved
        drag_icon("class:qadockaction", "terminal")
        assert dock.pins.records[0]["key"] == "class:qadockaction", "Actual held drag must reorder pinned apps"
        assert PinStore(saved_path, []).records == dock.pins.records
        for title in ("Owned action first", "Owned action second"):
            windows.window_action(by_title(title), "close")
        wait(lambda: by_title("Owned action first") is None and by_title("Owned action second") is None)
        sync_dock()
        assert "class:qadockaction" in dock.buttons and not dock.matches("class:qadockaction")
        dock.open("class:qadockaction")
        wait(lambda: by_title("Owned action first"))
        native_group_menu("class:qadockaction")
        activate_menu("Unpin from dock")
        wait(lambda: not any(record["key"] == "class:qadockaction" for record in dock.pins.records))
        assert by_title("Owned action first"), "Unpin must never close running app"
        sync_dock()
        pinned_keys = {record["key"] for record in dock.pins.records}
        assert all(list(dock.buttons).index(key) < list(dock.buttons).index("class:qadockaction") for key in pinned_keys if key in dock.buttons)
        another = subprocess.Popen(["xterm", "-class", "QADockSecond", "-title", "Owned unpinned other", "-e", "sleep", "120"], env=environment)
        owned.append(another)
        wait(lambda: by_title("Owned unpinned other"))
        sync_dock()
        drag_icon("class:qadocksecond", "class:qadockaction")
        assert list(dock.buttons).index("class:qadocksecond") < list(dock.buttons).index("class:qadockaction")
        before_cross = list(dock.pins.records)
        drag_icon("terminal", "class:qadockaction")
        assert dock.pins.records == before_cross, "Dragging across sections must not silently pin/unpin"
        native_group_menu("class:qadocksecond")
        activate_menu("Move right")
        wait(lambda: list(dock.buttons).index("class:qadockaction") < list(dock.buttons).index("class:qadocksecond"))
        restored = Dock(subscribe=False)
        assert restored.pins.records == dock.pins.records and restored.pins.order == dock.pins.order
        restored.destroy()
        # Real UID1000 permission refusal must retain old layout and allow retry.
        readonly = Path(temporary) / "readonly-pins"
        readonly.mkdir(mode=0o555)
        dock.pins.path = readonly / "dock.json"
        before_failure = list(dock.pins.records)
        native_group_menu("class:qadockaction")
        activate_menu("Pin to dock")
        wait(lambda: bool(dock.pins.error) and dock.menu is not None)
        assert dock.pins.records == before_failure and not dock.pins.path.exists()
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"], check=True)
        wait(lambda: dock.menu is None)
        dock.pins.path = saved_path
        native_group_menu("class:qadockaction")
        activate_menu("Pin to dock")
        wait(lambda: any(record["key"] == "class:qadockaction" for record in dock.pins.records))
        assert not dock.pins.error
        native_group_menu("class:qadockaction")
        activate_menu("Unpin from dock")
        wait(lambda: not any(record["key"] == "class:qadockaction" for record in dock.pins.records))
        for title in ("Owned action first", "Owned unpinned other"):
            windows.window_action(by_title(title), "close")
        wait(lambda: by_title("Owned action first") is None and by_title("Owned unpinned other") is None)
        sync_dock()
        assert "class:qadockaction" not in dock.buttons and "class:qadocksecond" not in dock.buttons

        # Real compact Other restore, then complete native keyboard menu path.
        assert shutil.which("rofi"), "Keyboard dock fixture requires real rofi (use signed candidate overlay)"
        music = subprocess.Popen(["xterm", "-class", "OoonanaApp", "-title", "Ooonana Music", "-e", "sleep", "120"], env=environment)
        owned.append(music)
        wait(lambda: by_title("Ooonana Music"))
        music_item = by_title("Ooonana Music")
        assert windows.pin_for(music_item) == "music"
        windows.window_action(music_item, "minimize")
        wait(lambda: by_title("Ooonana Music")[3])
        cli = str(root / "packages/ooonana/usr/bin/ooonana-window-list")
        subprocess.run([sys.executable, cli, "--dock-open", "other", "--visible-pins", "apps,terminal,browser,files"],
                       env=environment, check=True, timeout=5)
        wait(lambda: by_title("Ooonana Music")[2] and not by_title("Ooonana Music")[3])
        def visible_class(name):
            return subprocess.run(["xdotool", "search", "--onlyvisible", "--class", name], capture_output=True).returncode == 0
        def keyboard_menu(select=True):
            keyboard = subprocess.Popen([sys.executable, cli, "--dock-menu"], env=environment)
            owned.append(keyboard)
            wait(lambda: visible_class("Rofi"))
            if select:
                subprocess.run(["xdotool", "type", "--clearmodifiers", "--", "Music"], check=True)
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Return" if select else "Escape"], check=True)
            wait(lambda: keyboard.poll() is not None)
            if select:
                wait(lambda: visible_class("window_menu"))
        keyboard_menu(select=False)
        assert by_title("Ooonana Music")[0] == music_item[0]
        keyboard_menu()
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"], check=True)
        wait(lambda: not visible_class("window_menu"))
        assert by_title("Ooonana Music")[0] == music_item[0]
        keyboard_menu()
        # Dock hands off to mapped Gtk menu, last item is Close window.
        canvas = Gdk.get_default_root_window()
        Gdk.pixbuf_get_from_window(canvas, 0, 0, canvas.get_width(), canvas.get_height()).savev("/qa/dock-keyboard-menu.png", "png", [], [])
        subprocess.run(["xdotool", "key", "--clearmodifiers", "End", "Return"], check=True)
        wait(lambda: by_title("Ooonana Music") is None)
        assert by_title("Preview fixture")[0] == primary[0]

        # Task View uses real rofi/X11 input and restores the exact hidden client.
        def task_view(query=None, shortcut=False):
            if shortcut:
                subprocess.run(["xdotool", "key", "--clearmodifiers", "super+ctrl+Tab"], check=True)
                process = None
            else:
                process = subprocess.Popen([sys.executable, cli, "--task-view"], env=environment)
                owned.append(process)
            wait(lambda: visible_class("Rofi"))
            if shortcut:
                canvas = Gdk.get_default_root_window()
                identifiers = subprocess.check_output(["xdotool", "search", "--onlyvisible", "--class", "Rofi"], text=True).split()
                geometry = dict(line.split("=", 1) for line in subprocess.check_output(
                    ["xdotool", "getwindowgeometry", "--shell", identifiers[-1]], text=True).splitlines() if "=" in line)
                x, y, width, height = (int(geometry[key]) for key in ("X", "Y", "WIDTH", "HEIGHT"))
                assert x >= 0 and y >= 0 and x + width <= canvas.get_width() and y + height <= canvas.get_height(), geometry
                Gdk.pixbuf_get_from_window(canvas, 0, 0, canvas.get_width(), canvas.get_height()).savev(
                    "/qa/task-view-overview.png", "png", [], [])
            if query is not None:
                subprocess.run(["xdotool", "type", "--clearmodifiers", "--", query], check=True)
                drain()
                time.sleep(.2)
            if query == "Preview fixture":
                canvas = Gdk.get_default_root_window()
                Gdk.pixbuf_get_from_window(canvas, 0, 0, canvas.get_width(), canvas.get_height()).savev(
                    "/qa/task-view.png", "png", [], [])
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape" if query is None else "Return"], check=True)
            wait(lambda: not visible_class("Rofi"))
            if process:
                wait(lambda: process.poll() is not None)
                assert process.returncode == 0
        task_view(shortcut=True)
        assert by_title("Preview fixture")[0] == primary[0]
        windows.window_action(by_title("Preview fixture"), "minimize")
        wait(lambda: by_title("Preview fixture")[3])
        task_view("Preview fixture")
        wait(lambda: by_title("Preview fixture")[2] and not by_title("Preview fixture")[3])
        assert by_title("Preview fixture")[0] == primary[0]
        task_view("New desktop")
        wait(lambda: any(item["focused"] and item["num"] == 2 for item in i3_events.request(path, 1)))
        task_view("Desktop · 1")
        wait(lambda: any(item["focused"] and item["num"] == 1 for item in i3_events.request(path, 1)))
        assert by_title("Preview fixture")[0] == primary[0]
        if len(sys.argv) > 1:
            for _ in range(20):
                drain()
                time.sleep(0.02)
            window = Gdk.get_default_root_window()
            image = Gdk.pixbuf_get_from_window(window, 0, 0, window.get_width(), window.get_height())
            image.savev(sys.argv[1], "png", [], [])
        print(f"DOCK_UI_OK {size.width}x{size.height}; flat centered icons; idle/running overflow; exact MRU restore; direct window actions; pin/unpin/relaunch/reload; real held-drag reorder/separate sections; readonly save retry; native keyboard close; Task View; hover focus unchanged")
    finally:
        if dock:
            dock.stopped = True
            dock.destroy()
        if terminal and terminal.poll() is None:
            terminal.terminate()
            terminal.wait(timeout=5)
        for window in reversed(native):
            window.destroy()
        for process in owned:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        terminal_log.close()
        wm.terminate()
        wm.wait(timeout=5)
