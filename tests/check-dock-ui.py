#!/usr/bin/env python3
"""Own Xvfb/i3 fixture only. No user's windows, models or sound."""
import os
import shutil
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana/ui"))
import dock_app
from dock_app import Dock, Gdk, Gtk, HOVER_MARGIN, preview_image, windows
from common import apply_theme
from ui_preferences import save_preferences
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
        saved = dock.items
        dock.items = [(item[0], "Very long title " * 8, False, True, *item[4:]),
                      (item[0], "Second minimized session", False, True, *item[4:])]
        minimized = dock.tooltip_content("terminal")
        assert not any(isinstance(child, Gtk.Image) for child in minimized.get_children())
        assert all(label.get_ellipsize() for label in minimized.get_children()[1:])
        assert minimized.get_preferred_width().natural_width <= 300
        assert minimized.get_children()[0].get_children()[1].get_text() == "2 windows"
        dock.items = saved
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
        dock.hover(button, None, 'terminal', True)
        wait(lambda: not dock.hover_states)
        assert image.get_margin_top() == 0 and image.get_margin_bottom() == 2 * HOVER_MARGIN
        assert dock.get_size() == size
        with tempfile.TemporaryDirectory() as preference_home:
            original = os.environ.get('XDG_CONFIG_HOME')
            os.environ['XDG_CONFIG_HOME'] = preference_home
            try:
                save_preferences(reduce_motion=True)
                dock.hover(button, None, 'terminal', True)
                wait(lambda: not dock.hover_states)
                assert image.get_margin_top() == image.get_margin_bottom() == HOVER_MARGIN
            finally:
                if original is None:
                    os.environ.pop('XDG_CONFIG_HOME')
                else:
                    os.environ['XDG_CONFIG_HOME'] = original
        # Include an unpinned client: reserved "other" slot must also fit.
        geometry = dock.monitor_geometry
        snapshot = dock.snapshot
        extra = dict(id=987654, window=987654, name="Compact unpinned fixture",
                     window_properties={"class": "QAOther"}, nodes=[], floating_nodes=[])
        dock.snapshot = {**snapshot, "nodes": [*snapshot.get("nodes", []), extra]}
        for width in (320, 480):
            dock.monitor_geometry = lambda width=width: SimpleNamespace(x=0, y=0, width=width, height=768)
            dock.geometry_state = None
            dock.refresh()
            wait(lambda: dock.get_size().width <= width - 24 and
                 all(control.get_allocated_width() >= 44 and control.get_allocated_height() >= 44
                     for control, _dot, _image in dock.buttons.values()))
            assert "other" in dock.buttons
            submitted = []
            real_async = dock_app.run_async
            dock_app.run_async = lambda command, *_args, **_kwargs: submitted.append(command)
            try:
                dock.open("other")
                dock.press(None, SimpleNamespace(button=3), "other")
            finally:
                dock_app.run_async = real_async
            for command in submitted:
                assert command[-2:] == ["--visible-pins", ",".join(key for key in dock.buttons if key != "other")]
            centered_icons(dock)
            assert all(control.get_allocated_width() >= 44 and control.get_allocated_height() >= 44
                       for control, _dot, _image in dock.buttons.values())
        dock.monitor_geometry = geometry
        dock.snapshot = snapshot
        dock.geometry_state = None
        dock.refresh()
        wait(lambda: dock.get_size() == size)
        button = dock.buttons["terminal"][0]
        coordinates = button.translate_coordinates(dock, 0, 0)
        x, y = coordinates[-2:]
        origin = dock.get_position()
        dock.get_display().get_default_seat().get_pointer().warp(dock.get_screen(), origin[0] + x + 12, origin[1] + y + 12)
        for _ in range(90):
            drain()
            time.sleep(0.02)
        assert next(item[0] for item in windows.windows(i3_events.request(path, 4)) if item[2]) == before
        assert windows.panel_layout(640)[0] == "workspaces media"
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
        if len(sys.argv) > 1:
            for _ in range(20):
                drain()
                time.sleep(0.02)
            window = Gdk.get_default_root_window()
            image = Gdk.pixbuf_get_from_window(window, 0, 0, window.get_width(), window.get_height())
            image.savev(sys.argv[1], "png", [], [])
        print(f"DOCK_UI_OK {size.width}x{size.height}; centered icons; compact Other restore; multi-session actions; native keyboard close; hover focus unchanged")
    finally:
        if dock:
            dock.stopped = True
            dock.destroy()
        if terminal and terminal.poll() is None:
            terminal.terminate()
            terminal.wait(timeout=5)
        for process in owned:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        terminal_log.close()
        wm.terminate()
        wm.wait(timeout=5)
