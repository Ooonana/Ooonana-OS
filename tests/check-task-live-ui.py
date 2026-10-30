#!/usr/bin/env python3
"""Actual /proc sampling and owned process control on private X11/PID namespace."""
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme
from task_manager_app import TaskManagerWindow

output = Path(sys.argv[1]); output.mkdir(parents=True, exist_ok=True)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", round(96 * 1024 * float(os.environ.get("OOONANA_GUI_TEXT_SCALE", "1"))))
apply_theme()
children, window, wm = [], None, None


def drain(seconds=.1):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.005)


def capture(name):
    drain()
    root = Gdk.get_default_root_window()
    bounds = window.get_window().get_frame_extents()
    assert bounds.x >= 0 and bounds.y >= 0 and bounds.x + bounds.width <= root.get_width() and bounds.y + bounds.height <= root.get_height(), (name, bounds)
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(output/(name+".png")), "png", [], [])


def select(pid):
    row = next(row for row in window.sorted if row[1] == pid)
    window.tree.get_selection().select_path(row.path)
    return window.selected_identity()


def response(value):
    def answer():
        dialog = next(item for item in Gtk.Window.list_toplevels() if isinstance(item, Gtk.MessageDialog) and item.get_visible())
        assert dialog.get_default_widget() is dialog.get_widget_for_response(Gtk.ResponseType.CANCEL)
        dialog.response(value)
        return False
    GLib.timeout_add(200, answer)


with tempfile.TemporaryDirectory(prefix="ooonana-live-task-wm-") as temporary:
    config = Path(temporary)/"i3.conf"
    config.write_text("\n".join(line for line in (ROOT/"branding/i3/config").read_text().splitlines() if not line.startswith("exec"))+"\n")
    try:
        wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic()+8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < deadline
            time.sleep(.03)
        def task_windows():
            tree = json.loads(subprocess.check_output(["i3-msg", "-t", "get_tree"], text=True))
            pending, found = [tree], []
            while pending:
                item = pending.pop()
                if item.get("window_properties", {}).get("window_role") == "ooonana-task-manager": found.append(item)
                pending.extend(item.get("nodes", []) + item.get("floating_nodes", []))
            return found
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+shift+Escape"], check=True)
        deadline = time.monotonic()+12
        while not task_windows():
            assert time.monotonic() < deadline, "Installed Ctrl+Shift+Escape launcher failed"
            time.sleep(.05)
        launched, = task_windows()
        subprocess.run(["i3-msg", f"[con_id={launched['id']}] kill"], check=True, capture_output=True)
        while task_windows():
            assert time.monotonic() < deadline, "Shortcut-launched app did not close"
            time.sleep(.05)
        for _ in range(192):
            children.append(subprocess.Popen(["/bin/sleep", "120"]))
        assert all(child.poll() is None for child in children), "Owned worker fixture failed to start"
        window = TaskManagerWindow(); window.show_all(); drain()
        timings = []
        for _ in range(5):
            start = time.perf_counter(); window.refresh(); timings.append(time.perf_counter()-start)
            drain(.12)
        identities = {(row[1], row[7]) for row in window.store}
        assert all(any(pid == child.pid for pid, _start in identities) for child in children)
        assert max(timings) < 3, ("Refresh blocked private desktop", timings)
        window.search.set_text("/bin/sleep 120"); drain(.3)
        assert len(window.filtered) == len(children), (len(window.filtered), len(children))
        window.sorted.set_sort_column_id(1, Gtk.SortType.DESCENDING)
        target = children[len(children)//2]
        identity = select(target.pid)
        window.refresh(); drain()
        assert window.selected_identity() == identity
        window.tree.grab_focus()
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+c"], check=True)
        drain()
        assert str(target.pid) in Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()
        capture("processes-real")
        response(Gtk.ResponseType.CANCEL); window.end_selected()
        assert target.poll() is None, "Cancelled confirmation stopped owned task"
        response(Gtk.ResponseType.OK); window.end_selected()
        assert target.wait(timeout=5) == -15
        window.refresh(); drain()
        assert all(row[1] != target.pid for row in window.store)
        assert all(child.poll() is None for child in children if child is not target)
        assert len(window.filtered) == len(children)-1
        window.stack.set_visible_child_name("performance"); drain()
        capture("performance-real")
        receipt = dict(shortcut_launched_installed_app=True, owned_workers=192, refresh_seconds=timings, median_seconds=statistics.median(timings),
            rows=len(window.store), cancelled_target_survived=True, terminated_only_owned_target=True,
            metrics={name: card.value.get_text() for name, card in window.metrics.items()},
            physical_hardware_certified=False)
        (output/"receipt.json").write_text(json.dumps(receipt, indent=2)+"\n")
        print("TASK_LIVE_UI_OK", json.dumps(receipt), flush=True)
    finally:
        if window is not None: window.destroy()
        for child in children:
            if child.poll() is None: child.terminate()
        for child in children: child.wait(timeout=5)
        if wm is not None:
            wm.terminate(); wm.wait(timeout=5)
