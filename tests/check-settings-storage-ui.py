#!/usr/bin/env python3
"""Real private preference writes/reopen/fault/retry; no settings command mocked."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme, message_dialog
from settings_app import SettingsWindow
from ui_preferences import config_path, load_preferences

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", int(96 * 1024 * float(os.environ["OOONANA_GUI_TEXT_SCALE"])))
apply_theme()


def settle():
    end = time.monotonic() + 0.15
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


def capture(name):
    settle()
    root = Gdk.get_default_root_window()
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
        str(output / (name + ".png")), "png", [], [])


with tempfile.TemporaryDirectory(prefix="ooonana-settings-storage-") as temporary:
    fixture = Path(temporary)
    os.environ["XDG_CONFIG_HOME"] = str(fixture / "config")
    config = fixture / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                               if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    window = None
    blocked = None
    try:
        end = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < end, "Private window manager unavailable"
            time.sleep(0.02)
        window = SettingsWindow()
        window.show_all()
        assert not window.reduce_motion.get_active()
        window.reduce_motion.set_active(True)
        path = config_path()
        assert path.is_relative_to(fixture) and path.stat().st_mode & 0o777 == 0o600
        assert load_preferences()["reduce_motion"]
        window.destroy()
        window = SettingsWindow()
        window.show_all()
        window.sidebar.select_row(window.sidebar.get_row_at_index(3))
        assert window.reduce_motion.get_active(), "Reopened Settings lost persisted choice"
        window.reduce_motion.set_active(False)
        before = path.read_bytes()
        blocked = path.parent
        blocked.chmod(0o500)
        failures = []
        seen = []

        def dismiss_error():
            dialog = next(item for item in Gtk.Window.list_toplevels()
                          if isinstance(item, Gtk.MessageDialog) and item.get_visible())
            try:
                assert dialog.get_transient_for() is window
                root = Gdk.get_default_root_window()
                frame = dialog.get_window().get_frame_extents()
                capture("preference-write-failure")
                print("SETTINGS_STORAGE_ERROR_FRAME", frame.x, frame.y, frame.width, frame.height,
                      root.get_width(), root.get_height(), flush=True)
                assert 0 <= frame.x and frame.x + frame.width <= root.get_width()
                assert 0 <= frame.y and frame.y + frame.height <= root.get_height()
                seen.append(True)
            except Exception as exc:
                failures.append(type(exc).__name__)
            finally:
                dialog.response(Gtk.ResponseType.CLOSE)
            return False

        GLib.timeout_add(250, dismiss_error)
        window.reduce_motion.set_active(True)
        assert seen and not failures, "Storage failure dialog did not fit/retain parent"
        assert not window.reduce_motion.get_active() and path.read_bytes() == before
        blocked.chmod(0o700)
        blocked = None
        window.reduce_motion.set_active(True)
        assert load_preferences()["reduce_motion"], "Actual preference retry did not persist"
        window.destroy()
        window = SettingsWindow()
        window.show_all()
        window.sidebar.select_row(window.sidebar.get_row_at_index(3))
        assert window.reduce_motion.get_active()
        capture("preference-reopened")
        for name, text in (("message-unbroken", "x" * 580), ("message-diagnostics", "Detail line\n" * 60)):
            dialog = message_dialog(window, "Operation unavailable", text, Gtk.MessageType.ERROR)
            dialog.show_all()
            capture(name)
            root = Gdk.get_default_root_window()
            frame = dialog.get_window().get_frame_extents()
            assert 0 <= frame.x and frame.x + frame.width <= root.get_width(), name + ": horizontal overflow"
            assert 0 <= frame.y and frame.y + frame.height <= root.get_height(), name + ": vertical overflow"
            dialog.destroy()
        print("SETTINGS_STORAGE_UI_OK actual 0600 writes, reopen, read-only failure rollback, parent/bounds, retry", flush=True)
    finally:
        if blocked is not None:
            blocked.chmod(0o700)
        if window is not None:
            window.destroy()
        wm.terminate()
        wm.wait(timeout=5)
