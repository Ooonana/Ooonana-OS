#!/usr/bin/env python3
"""Optional isolated GTK test; termination targets only its own child process."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme
from gi.repository import Gio
from launcher_app import LauncherWindow
from task_manager_app import TaskManagerWindow

if os.environ.get("OOONANA_GUI_TEST_DISPLAY") != "1" or os.getuid() == 0:
    raise SystemExit("Dedicated test display and nonroot test user required")


def drain():
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)


def wait(predicate):
    deadline = time.monotonic() + 8
    while not predicate():
        drain()
        assert time.monotonic() < deadline, "Desktop fixture timeout"
        time.sleep(0.02)


apply_theme()
launcher = LauncherWindow()
launcher.add_app(Gio.AppInfo.create_from_commandline("true", "Ooonana QA Fixture One", Gio.AppInfoCreateFlags.NONE))
launcher.add_app(Gio.AppInfo.create_from_commandline("true", "Ooonana QA Fixture Two", Gio.AppInfoCreateFlags.NONE))
launcher.show_all()
launcher.search.set_text("Ooonana QA Fixture")
launcher.search_changed()
wait(lambda: len(launcher.visible_rows()) == 2)
launcher.select_first()
event = Gdk.EventKey()
event.keyval = Gdk.KEY_Down
assert launcher.search_key(launcher.search, event)
assert launcher.results.get_selected_row() is launcher.visible_rows()[1]
event.keyval = Gdk.KEY_Up
assert launcher.search_key(launcher.search, event)
assert launcher.results.get_selected_row() is launcher.visible_rows()[0]
# Real GTK editing/clipboard actions; not evidence of an installed IME engine.
launcher.search.set_text("abc한글")
launcher.search.set_position(-1)
launcher.search.emit("backspace")
assert launcher.search.get_text() == "abc한"
clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
clipboard.set_text("QA clipboard 한글", -1)
launcher.search.select_region(0, -1)
launcher.search.emit("paste-clipboard")
wait(lambda: launcher.search.get_text() == "QA clipboard 한글")
launcher.disconnect_by_func(Gtk.main_quit)
launcher.destroy()

child = subprocess.Popen(["sleep", "120"])
manager = TaskManagerWindow()
try:
    manager.show_all()
    manager.search.set_text(str(child.pid))
    manager.filtered.refilter()
    manager.refresh()
    row = next(row for row in manager.sorted if row[1] == child.pid)
    manager.tree.get_selection().select_iter(row.iter)
    assert manager.selected_identity()[0] == child.pid and manager.end_button.get_sensitive()
    manager.sorted.set_sort_column_id(1, Gtk.SortType.ASCENDING)
    assert manager.sorted.get_sort_column_id() == (1, Gtk.SortType.ASCENDING)
    samples = len(manager.metrics["cpu"].history)
    manager.refresh()
    assert len(manager.metrics["cpu"].history) > samples

    def respond(response):
        def callback():
            dialog = next(window for window in Gtk.Window.list_toplevels()
                          if isinstance(window, Gtk.MessageDialog) and window.get_transient_for() is manager)
            assert str(child.pid) in dialog.get_property("text")
            dialog.response(response)
            return False
        GLib.timeout_add(100, callback)

    respond(Gtk.ResponseType.CANCEL)
    manager.end_selected()
    assert child.poll() is None, "Cancel killed fixture"
    respond(Gtk.ResponseType.OK)
    manager.end_selected()
    wait(lambda: child.poll() is not None)
    assert child.returncode == -signal.SIGTERM
    manager.refresh()
    assert not any(row[1] == child.pid for row in manager.store)
finally:
    manager.disconnect_by_func(manager.on_destroy)
    manager.closed = True
    manager.destroy()
    if child.poll() is None:
        child.terminate()
        child.wait(timeout=5)
print("DESKTOP_INTERACTIONS_OK launcher arrows/search; Unicode Backspace/clipboard; task filter/sort/graphs/cancel/terminate")
