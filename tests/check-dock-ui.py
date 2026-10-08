#!/usr/bin/env python3
"""Own Xvfb/i3 fixture only. No user's windows, models or sound."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana/ui"))
from dock_app import Dock, Gdk, Gtk, preview_image, windows
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

with tempfile.TemporaryDirectory() as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (root / "branding/i3/config").read_text().splitlines()
                                if not line.startswith("exec")) + "\n")
    environment = {**os.environ, "PATH": str(root / "packages/ooonana/usr/bin") + ":" + os.environ["PATH"]}
    os.environ["PATH"] = environment["PATH"]
    wm = subprocess.Popen(["i3", "-c", str(config)], env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    terminal, dock = None, None
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
        assert next(item[0] for item in windows.windows(i3_events.request(path, 4)) if item[2]) == before
        button = dock.buttons["terminal"][0]
        image = dock.buttons['terminal'][2]
        size = dock.get_size()
        dock.hover(button, None, 'terminal', True)
        wait(lambda: not dock.hover_states)
        assert image.get_margin_top() == 0 and image.get_margin_bottom() == 8
        assert dock.get_size() == size
        with tempfile.TemporaryDirectory() as preference_home:
            original = os.environ.get('XDG_CONFIG_HOME')
            os.environ['XDG_CONFIG_HOME'] = preference_home
            try:
                save_preferences(reduce_motion=True)
                dock.hover(button, None, 'terminal', True)
                wait(lambda: not dock.hover_states)
                assert image.get_margin_top() == image.get_margin_bottom() == 4
            finally:
                if original is None:
                    os.environ.pop('XDG_CONFIG_HOME')
                else:
                    os.environ['XDG_CONFIG_HOME'] = original
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
        if len(sys.argv) > 1:
            for _ in range(20):
                drain()
                time.sleep(0.02)
            window = Gdk.get_default_root_window()
            image = Gdk.pixbuf_get_from_window(window, 0, 0, window.get_width(), window.get_height())
            image.savev(sys.argv[1], "png", [], [])
        print("DOCK_UI_OK preview bounded; hover focus unchanged; compact panel")
    finally:
        if dock:
            dock.stopped = True
            dock.destroy()
        if terminal and terminal.poll() is None:
            terminal.terminate()
            terminal.wait(timeout=5)
        terminal_log.close()
        wm.terminate()
        wm.wait(timeout=5)
