#!/usr/bin/env python3
"""Owned i3/GTK Settings details; commands, services and preference writes mocked."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1" and os.getuid() != 0
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme
import settings_app as settings

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--baseline", action="store_true")
parser.add_argument("--text-scale", type=float, default=float(os.environ.get("OOONANA_GUI_TEXT_SCALE", "1.25")))
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
Gtk.Settings.get_default().set_property("gtk-xft-dpi", int(96 * 1024 * args.text_scale))
apply_theme()
findings, jobs, messages = [], [], []
settings.run_async = lambda command, done, **kwargs: jobs.append((command, done, kwargs))
settings.run_async_task = lambda command, done: jobs.append((command, done, {}))
settings.message = lambda _parent, title, *_args: messages.append(title)
settings.launch = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Unexpected app launch"))
real_read = settings.read_file
settings.read_file = lambda path, default="": "fixture-linux" if str(path) == "/proc/sys/kernel/osrelease" else real_read(path, default)
settings.command_exists = lambda _command: True
repo = "file:///var/lib/ooonana/" + "long-local-repository-name-" * 18
settings.SettingsWindow.repo_uri = staticmethod(lambda: repo)


def check(condition, detail):
    if not condition:
        findings.append(detail)


def settle():
    deadline = time.monotonic() + 0.2
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.005)


def capture(window, name):
    settle()
    screen = Gdk.get_default_root_window()
    rect = window.get_window().get_frame_extents()
    check(0 <= rect.x and rect.x + rect.width <= screen.get_width() and
          0 <= rect.y and rect.y + rect.height <= screen.get_height(), name + ": frame outside screen")
    Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height()).savev(str(args.output / (name + ".png")), "png", [], [])


def respond_dialog(name, inspect=None):
    def respond():
        dialog = next(item for item in Gtk.Window.list_toplevels() if isinstance(item, Gtk.Dialog) and item.get_visible())
        try:
            capture(dialog, name)
            if inspect:
                inspect(dialog)
        finally:
            dialog.response(Gtk.ResponseType.CANCEL if dialog.get_widget_for_response(Gtk.ResponseType.CANCEL) else Gtk.ResponseType.CLOSE)
        return False
    GLib.timeout_add(350, respond)


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


with tempfile.TemporaryDirectory(prefix="ooonana-settings-details-") as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines() if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < deadline
            time.sleep(0.03)
        window = settings.SettingsWindow()
        window.show_all()
        jobs.clear()
        window.sidebar.select_row(window.sidebar.get_row_at_index(5))
        capture(window, "settings-long-source")
        source = window.status_widgets["repo_detail"]
        source.grab_focus()
        capture(window, "settings-source-focused")
        page = window.stack.get_visible_child()
        _x, source_y = source.translate_coordinates(page, 0, 0)[-2:]
        check(0 <= source_y and source_y + source.get_allocated_height() <= page.get_allocated_height(), "Focused source value remains outside viewport")
        check(source.get_tooltip_text() == repo and source.get_selectable(), "Long source lacks full selectable/tooltip access")
        check(source.get_allocated_height() < 120 * args.text_scale, "Long repository value dominates Settings")
        if Gdk.get_default_root_window().get_width() < 720:
            check(window.page_picker.get_visible() and not window.sidebar.get_visible(), "Compact page navigation missing")
            window.page_picker.grab_focus()
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Home"], check=True)
            settle()
            check(window.stack.get_visible_child_name() == "overview", "Page picker Home failed")
            subprocess.run(["xdotool", "key", "--clearmodifiers", "End"], check=True)
            settle()
            check(window.stack.get_visible_child_name() == "system", "Page picker End failed")
            window.resized(window, SimpleNamespace(width=1000))
            check(all(row.get_child().get_visible() for row in window.sidebar.get_children()), "Expanded sidebar rows were never shown")
            window.resized(window, window.get_allocation())
        window.sidebar.select_row(window.sidebar.get_row_at_index(3))

        previous = window.reduce_motion.get_active()
        saved = settings.save_preferences
        settings.save_preferences = lambda **_kwargs: (_ for _ in ()).throw(OSError("Fixture read-only preferences"))
        window.reduce_motion.set_active(not previous)
        check(window.reduce_motion.get_active() == previous, "Failed motion preference stays falsely selected")
        settings.save_preferences = saved

        respond_dialog("settings-wallpaper-picker", lambda dialog: (
            check(dialog.get_modal(), "Wallpaper picker lacks modal focus"),
            check(dialog.get_destroy_with_parent(), "Wallpaper picker survives parent close"),
            check(dialog.get_default_widget() is dialog.get_widget_for_response(Gtk.ResponseType.CANCEL), "Wallpaper picker lacks default Cancel")))
        window.choose_wallpaper()
        check(not jobs, "Wallpaper Cancel submitted work")

        selected = "/usr/share/ooonana/wallpapers/ooonana-notes.jpg"
        def select_image():
            dialog = next(item for item in Gtk.Window.list_toplevels() if isinstance(item, Gtk.Dialog) and item.get_visible())
            chooser = next(child for child in descendants(dialog) if isinstance(child, Gtk.FileChooserWidget))
            chooser.set_filename(selected)
            deadline = time.monotonic() + 3
            def apply_image():
                if chooser.get_filename() != selected and time.monotonic() < deadline:
                    return True
                check(chooser.get_filename() == selected, "Image selection did not settle")
                check(dialog.get_widget_for_response(Gtk.ResponseType.OK).get_sensitive(), "Selected image cannot apply")
                dialog.response(Gtk.ResponseType.OK)
                return False
            GLib.timeout_add(100, apply_image)
            return False
        GLib.timeout_add(250, select_image)
        window.choose_wallpaper()
        check(len(jobs) == 1 and jobs[0][0][-1] == selected, "Selected image did not queue wallpaper")
        jobs.pop()[1](1, "Fixture rejects setter; no desktop changed")

        settings.read_file = lambda path, default="": ("Fixture log line with long output " * 8 + "\n") * 30 if str(path).startswith("/var/log/") else real_read(path, default)
        def inspect_log(dialog):
            check(dialog.get_destroy_with_parent(), "Service log survives parent close")
            copy = next(widget for widget in descendants(dialog) if isinstance(widget, Gtk.Button) and widget.get_label() == "Copy log")
            copy.clicked()
            copied = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()
            check(copied and "Fixture log line" in copied, "Copy log lost diagnostic text")
        respond_dialog("settings-service-log", inspect_log)
        window.show_service_log()
        settings.read_file = lambda path, default="": "fixture-linux" if str(path) == "/proc/sys/kernel/osrelease" else real_read(path, default)

        window.sidebar.select_row(window.sidebar.get_row_at_index(1))
        window.refresh_status()
        service_done = next(done for command, done, _kwargs in jobs if callable(command))
        jobs.clear()
        service_done(0, dict(nm_rc=1, nm_out="NetworkManager unavailable", wifi_rc=1, wifi_out="unknown", bt_rc=1, bt_out="D-Bus unavailable"))
        check("running" not in window.status_widgets["bluetooth"].get_text().lower(), "Failed Bluetooth query claims BlueZ running")
        capture(window, "settings-service-failure")
        repairs = [widget for widget in descendants(window) if isinstance(widget, Gtk.Button) and widget.get_label() == "Repair"]
        window.repair_services(repairs[0])
        window.repair_services(repairs[-1])
        check(len(jobs) == 1, "Separate Repair buttons submit duplicate service mutation")
        check(all(not widget.get_sensitive() for widget in repairs), "Parallel Repair remains enabled")
        repair_done = jobs[0][1]
        jobs.clear()
        repair_done(1, "Fixture denied; no service touched")
        check(not window.service_pending and all(widget.get_sensitive() for widget in repairs), "Repair failure cannot retry")
        check("failed" in window.status_widgets["repair_network"].get_text().lower(), "Repair failure lost inline state")
        jobs.clear()
        window.sidebar.select_row(window.sidebar.get_row_at_index(5))
        update = next(widget for widget in descendants(window.stack.get_visible_child()) if isinstance(widget, Gtk.Button) and widget.get_label() in ("Update", "Refresh metadata"))
        window.package_update(update)
        window.package_update(update)
        check(len(jobs) == 1, "Metadata refresh can be submitted twice")
        done = jobs[0][1]
        jobs.clear()
        done(1, "Fixture metadata failure")
        check(not window.metadata_pending and update.get_sensitive(), "Metadata failure cannot retry")
        check("failed" in window.status_widgets["metadata"].get_text().lower(), "Metadata failure lost inline state")
        jobs.clear()
        window.package_update(update)
        jobs.pop()[1](0, "Fixture metadata only")
        check("No packages installed" in window.status_widgets["metadata"].get_text(), "Metadata success claims package install")
        jobs.clear()
        window.package_update(update)
        done = jobs.pop()[1]
        before = len(messages)
        window.destroy()
        done(1, "Fixture delayed denial")
        check(len(messages) == before, "Closed Settings spawns delayed package dialog")
        closing = settings.SettingsWindow()
        closing.show_all()
        jobs.clear()
        GLib.timeout_add(250, lambda: (closing.destroy(), False)[1])
        closing.choose_wallpaper()
        check(closing.closed and not jobs, "Closing picker parent applied wallpaper")
    finally:
        wm.terminate()
        wm.wait(timeout=5)

for finding in findings:
    print("SETTINGS_DETAILS_FINDING: " + finding, flush=True)
if findings and not args.baseline:
    raise SystemExit(1)
if not findings:
    print("SETTINGS_DETAILS_UI_OK bounded values/dialogs; scaled text; preference rollback; honest services; duplicate/late refusal")
