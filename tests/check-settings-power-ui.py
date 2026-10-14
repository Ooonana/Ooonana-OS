#!/usr/bin/env python3
"""Private native state transitions. Every power/theme command is mocked."""
import os
from pathlib import Path
import sys
import tempfile
import time

if os.environ.get("OOONANA_GUI_TEST_DISPLAY") != "1" or os.getuid() == 0:
    raise SystemExit("Dedicated nonroot test display required")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
import settings_app as settings
import controls_app as controls
from common import Gdk, GLib, Gtk, apply_theme

def drain():
    for _ in range(8):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.015)

def capture(window, name):
    drain()
    root = Gdk.get_default_root_window()
    bounds = window.get_window().get_frame_extents()
    assert bounds.x >= 0 and bounds.y >= 0
    assert bounds.x + bounds.width <= root.get_width() and bounds.y + bounds.height <= root.get_height(), (name, bounds)
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev("/qa/" + name + ".png", "png", [], [])

jobs, messages, calls = [], [], []
settings.run_async = lambda command, done, **kwargs: jobs.append((command, done))
settings.run_async_task = lambda task, done: jobs.append((task, done))
settings.launch = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Unexpected launch"))
settings.message = lambda _parent, title, *_args: messages.append(title)
controls.run_async = lambda command, done, **kwargs: jobs.append((command, done))
controls.launch = settings.launch
controls.message = settings.message
theme_rc = 1
def run(command, **kwargs):
    calls.append((command, kwargs))
    return theme_rc, "Isolated failure fixture" if theme_rc else ""
settings.run = run
apply_theme()
with tempfile.TemporaryDirectory() as temporary:
    os.environ["HOME"] = temporary
    os.environ["XDG_CONFIG_HOME"] = temporary + "/.config"
    window = settings.SettingsWindow()
    window.show_all()
    window.sidebar.select_row(window.sidebar.get_row_at_index(3))
    assert not any(command == ["ooonana-memory", "status"] for command, _kwargs in calls), "Memory blocked UI thread"
    jobs.clear()
    path = Path(temporary) / ".config/ooonana/theme"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"dark\n")
    window.theme_combo.set_active_id("light")
    window.apply_selected_theme()
    assert window.appearance_pending and not messages
    assert all(not widget.get_sensitive() for widget in window.appearance_actions)
    task, done = jobs.pop()
    done(*task())
    assert path.read_bytes() == b"dark\n" and messages[-1] == "Theme failed"
    assert calls[-1][1]["env"] == {"OOONANA_THEME": "light"}
    path.unlink()
    window.apply_selected_theme()
    task, done = jobs.pop()
    done(*task())
    assert not path.exists(), "Failed theme created saved preference"
    theme_rc = 0
    window.apply_selected_theme()
    task, done = jobs.pop()
    done(*task())
    assert path.read_bytes() == b"light\n" and not window.appearance_pending
    previous = window.status_widgets["wallpaper"].get_text()
    window.apply_wallpaper("/fixture/missing-image.jpg", "fill")
    window.apply_wallpaper("/fixture/duplicate.jpg", "fit")
    assert len(jobs) == 1 and window.status_widgets["wallpaper"].get_text() == previous
    command, done = jobs.pop()
    assert command == ["ooonana-wallpaper", "--mode", "fill", "/fixture/missing-image.jpg"]
    done(1, "Setter failed")
    assert window.status_widgets["wallpaper"].get_text() == previous
    window.apply_wallpaper("/fixture/saved-image.jpg", "fit")
    _command, done = jobs.pop()
    done(0, "")
    assert window.status_widgets["wallpaper"].get_text() == "saved-image.jpg"
    assert window.status_widgets["wallpaper"].get_tooltip_text() == "/fixture/saved-image.jpg"
    window.refresh_status()
    old = next(callback for command, callback in jobs if command == ["ooonana-memory", "status"])
    jobs.clear()
    window.refresh_status()
    latest = next(callback for command, callback in jobs if command == ["ooonana-memory", "status"])
    old(0, "OLD")
    assert window.status_widgets["memory"].get_text() != "OLD"
    latest(0, "LATEST")
    assert window.status_widgets["memory"].get_text() == "LATEST"
    jobs.clear()
    capture(window, "settings-appearance")
    window.apply_wallpaper("/fixture/late.jpg", "fit")
    _command, late = jobs.pop()
    window.destroy()
    late(0, "")
    assert window.closed

    power = controls.PowerWindow()
    power.show_all()
    def response(value, screenshot=False):
        def respond():
            dialog = next(item for item in Gtk.Window.list_toplevels() if isinstance(item, Gtk.MessageDialog))
            assert dialog.get_default_widget() is dialog.get_widget_for_response(Gtk.ResponseType.CANCEL)
            if screenshot:
                capture(dialog, "power-logout-review")
            dialog.response(value)
            return False
        GLib.timeout_add(100, respond)
    for action in ("logout", "reboot", "shutdown"):
        response(Gtk.ResponseType.CANCEL, action == "logout")
        power.confirm(action)
        assert not jobs, "Cancel submitted power request"
    for action, expected in (("logout", ["i3-msg", "exit"]), ("reboot", ["bunana", "--restart"]),
                             ("shutdown", ["bunana", "--shutdown"])):
        response(Gtk.ResponseType.OK)
        power.confirm(action)
        power.restart_i3()
        assert len(jobs) == 1 and power.pending
        command, done = jobs.pop()
        assert command == expected
        done(1, "Isolated rejection")
        assert not power.pending and "failed" in power.status.get_text()
    power.lock()
    command, done = jobs.pop()
    assert command == ["i3lock"]
    done(127, "Lock unavailable")
    assert not jobs, "Failed lock fell back to display blanking"
    capture(power, "power-failure")
    power.destroy()
print("SETTINGS_POWER_UI_OK completion/rollback/explicit theme; async memory/stale callbacks; wallpaper; safe Cancel; power errors; lock refusal")
