#!/usr/bin/env python3
"""Private GTK/i3 Task Manager edge cases; sensors/process termination mocked."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1" and os.getuid() != 0
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana"))
from common import Gdk, GLib, Gtk, apply_theme
import task_manager_app as task

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", int(96 * 1024 * float(os.environ.get("OOONANA_GUI_TEXT_SCALE", "1.0"))))
apply_theme()
findings, actions, notices = [], [], []
uid = os.getuid()
rows = [("Fixture long task 한글 " + "worker-" * 15, 85000 + index, float(index % 20), 4096.5,
         "fixture-user-" * 8, "S", "/usr/bin/fixture " + "argument-" * 50, 2**40 + index, uid)
        for index in range(160)]
counter, missing = 1000, False
real_read = task.read_text


def read(path, limit=65536):
    global counter
    if str(path) == "/proc/stat":
        counter += 100
        return "" if missing else f"cpu {counter} 0 1 800 50 0 0 0\n"
    if str(path) == "/proc/meminfo":
        return "" if missing else "MemTotal: 33554432 kB\nMemAvailable: 16777216 kB\nSwapTotal: 67108864 kB\nSwapFree: 33554432 kB\n"
    return real_read(path, limit)


task.read_text = read
task.TaskManagerWindow.process_rows = lambda _self, _delta: list(rows)
task.thermal_fan_snapshot = lambda: ("Package sensor label-" * 18 + " 57°C", "Fan sensor label-" * 18 + " 2100 RPM")
task.zram_consumption = lambda: (6 * 1024**3, 1024**3, 2 * 1024**3)
task.gpu_busy = lambda: ("Fixture GPU", None if missing else 12.0)
task.network_bytes = lambda: None if missing else ("wlp0s20f3", counter * 10000, counter * 1000)
task.disk_bytes = lambda: None if missing else (counter * 5000, counter * 500)
task.root_storage = lambda: None if missing else (256 * 1024**3, 64 * 1024**3)
task.message = lambda _parent, title, *_args: notices.append(title)


def terminate(pid, start, owner):
    actions.append((pid, start, owner))
    if not any(row[1] == pid and row[7] == start and row[8] == owner for row in rows):
        raise task.ProcessChanged("Fixture identity changed")


task.terminate_owned_process = terminate


def check(condition, detail):
    if not condition:
        findings.append(detail)
        print("TASK_DETAILS_FINDING: " + detail, flush=True)


def settle():
    deadline = time.monotonic() + .25
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.005)


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


def capture(window, name):
    settle()
    screen = Gdk.get_default_root_window()
    rect = window.get_window().get_frame_extents()
    check(0 <= rect.x and rect.x + rect.width <= screen.get_width() and
          0 <= rect.y and rect.y + rect.height <= screen.get_height(), name + ": frame outside display")
    Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height()).savev(str(output / (name + ".png")), "png", [], [])


def select(window, pid):
    row = next(row for row in window.sorted if row[1] == pid)
    window.tree.get_selection().select_iter(row.iter)


def respond(window, response, inspect=None):
    def answer():
        dialog = next(item for item in Gtk.Window.list_toplevels() if isinstance(item, Gtk.MessageDialog) and item.get_visible())
        try:
            capture(dialog, "task-confirmation")
            check(dialog.get_default_widget() is dialog.get_widget_for_response(Gtk.ResponseType.CANCEL), "End task lacks default Cancel")
            check(dialog.get_destroy_with_parent(), "End task dialog survives parent close")
            if inspect:
                inspect(dialog)
        finally:
            dialog.response(response)
        return False
    GLib.timeout_add(300, answer)


with tempfile.TemporaryDirectory(prefix="ooonana-task-details-") as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines() if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < deadline
            time.sleep(.03)
        window = task.TaskManagerWindow()
        window.show_all()
        settle()
        if Gdk.get_default_root_window().get_width() < 760:
            check(window.page_picker.get_visible() and not window.sidebar.get_visible(), "Compact page picker missing")
            window.page_picker.grab_focus()
            subprocess.run(["xdotool", "key", "--clearmodifiers", "End"], check=True)
            settle()
            check(window.stack.get_visible_child_name() == "performance", "Page picker End failed")
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Home"], check=True)
            settle()
            check(window.stack.get_visible_child_name() == "processes", "Page picker Home failed")
        window.refresh()
        window.stack.set_visible_child_name("performance")
        capture(window, "task-crowded-metrics")
        for name, metric in window.metrics.items():
            check(metric.value.get_tooltip_text() == metric.value.get_text(), name + ": missing full metric tooltip")
            check(metric.value.get_selectable(), name + ": metric cannot be selected/copied")
            text_height = metric.value.create_pango_layout("Metric").get_pixel_size()[1]
            check(metric.value.get_allocated_height() <= text_height * 3 + 8, name + ": metric label dominates card")
        metric = window.metrics["gpu"]
        metric.update("Fixture GPU: counter unavailable", None)
        check(not metric.history and not metric.progress.get_visible() and not metric.chart.get_visible(), "Unavailable metric shows zero/stale chart")
        missing = True
        try:
            window.refresh()
        except Exception as error:
            findings.append("Counter disappearance raises " + type(error).__name__)
        for name in ("cpu", "ram", "storage"):
            check("unavailable" in window.metrics[name].value.get_text().lower(), name + ": failed counter preserves stale caption")
        missing = False
        window.refresh()
        window.refresh()

        window.stack.set_visible_child_name("processes")
        window.search.set_text("no-such-process-fixture")
        window.filtered.refilter()
        capture(window, "task-no-matches")
        check(any(isinstance(item, Gtk.Label) and "No matching" in item.get_text() and item.get_visible()
                  for item in descendants(window)), "Process search lacks no-match guidance")
        check("0 of" in window.process_summary.get_text(), "Filtered summary reports total as visible count")
        check(not window.end_button.get_sensitive(), "Empty filter retains destructive action")
        window.search.set_text("")
        window.filtered.refilter()
        window.refresh()
        select(window, 85001)
        selected = window.selected_identity()
        scroll = window.tree.get_parent()
        adjustment = scroll.get_vadjustment()
        adjustment.set_value(min(600, adjustment.get_upper() - adjustment.get_page_size()))
        settle()
        before = adjustment.get_value()
        window.refresh()
        settle()
        check(window.selected_identity() == selected, "Refresh changed selected process identity")
        check(abs(adjustment.get_value() - before) < 2, "Refresh jumps process scroll position")
        capture(window, "task-processes-long-content")
        check(window.tree.get_has_tooltip(), "Process rows lack full command/identity tooltip")
        for column, (title, column_id) in zip(window.tree.get_columns(), window.COLUMNS):
            text_width = window.tree.create_pango_layout(title).get_pixel_size()[0]
            check(column.get_width() >= text_width + 22, title + ": header clipped at text scale")
            if column_id in (1, 2, 3):
                value = str(selected[0]) if column_id == 1 else "100.0" if column_id == 2 else "4096.5"
                check(column.get_width() >= window.tree.create_pango_layout(value).get_pixel_size()[0] + 12,
                      title + ": numeric value clipped")
        window.tree.grab_focus()
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+c"], check=True)
        settle()
        expected_details = window.row_details(next(row for row in window.sorted if row[1] == selected[0]))
        check(Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text() == expected_details, "Ctrl+C loses full command/identity details")
        selected_row = next(row for row in window.sorted if row[1] == selected[0])
        window.tree.set_cursor(selected_row.path)
        window.tree.scroll_to_cell(selected_row.path, None, True, .5, 0)
        settle()
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+F1"], check=True)
        settle()
        tips = [item for item in Gtk.Window.list_toplevels() if item.get_visible() and item.get_type_hint() == Gdk.WindowTypeHint.TOOLTIP]
        check(bool(tips), "Keyboard task tooltip did not open")
        if tips:
            capture(tips[0], "task-keyboard-tooltip")
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+F1"], check=True)
        settle()

        rows[1] = (*rows[1][:8], 0)
        window.refresh()
        check(not window.end_button.get_sensitive(), "Owner change leaves End task enabled")
        before = len(actions)
        window.end_selected()
        check("End task refused" in notices and len(actions) == before, "Changed owner was not refused")
        rows[1] = (*rows[1][:8], uid)
        window.refresh()
        check(window.end_button.get_sensitive(), "Restored owned task cannot be selected")

        def during_cancel(_dialog):
            window.refresh()
            check(not window.end_button.get_sensitive(), "Refresh re-enables End task during confirmation")
        respond(window, Gtk.ResponseType.CANCEL, during_cancel)
        window.end_selected()
        check(not actions, "Cancel terminated task")
        respond(window, Gtk.ResponseType.OK, lambda _dialog: select(window, 85002))
        window.end_selected()
        check(actions == [(selected[0], selected[1], uid)], "Confirmation retargeted to changed selection")
        select(window, 85001)
        def reused(_dialog):
            rows[1] = (*rows[1][:7], rows[1][7] + 1, uid)
            window.refresh()
        respond(window, Gtk.ResponseType.OK, reused)
        window.end_selected()
        check("Task changed" in notices, "Reused process identity was not visibly refused")
        check(window.selected_identity() is None, "Reused PID inherited old selection")

        select(window, 85002)
        GLib.timeout_add(250, lambda: (window.destroy(), False)[1])
        before = len(actions)
        window.end_selected()
        check(window.closed and len(actions) == before, "Closing confirmation parent terminated task")
        settle()
    finally:
        wm.terminate()
        wm.wait(timeout=5)

if findings:
    raise SystemExit(1)
print("TASK_DETAILS_UI_OK mocked counters; bounded/copyable values; search/scroll/identity; safe confirmation")
