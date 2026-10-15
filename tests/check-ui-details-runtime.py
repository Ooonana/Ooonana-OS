#!/usr/bin/env python3
"""Owned GTK windows only: responsive actions, async UI lifecycle and plots."""
import argparse
import os
from pathlib import Path
import sys
import time

assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1" and os.getuid() != 0
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme, chart_colors, flow_row  # noqa: E402
import health_app  # noqa: E402
import packages_app  # noqa: E402
from signal_map import SignalMapWindow  # noqa: E402
from task_manager_app import MetricCard  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
output = parser.parse_args().output
output.mkdir(parents=True, exist_ok=True)
apply_theme()
Gtk.IconTheme.get_default().append_search_path(str(ROOT / "packages/ooonana/usr/share/icons/hicolor/scalable/apps"))
assert flow_row([Gtk.Button(label=str(index)) for index in range(6)]).get_min_children_per_line() == 3
assert flow_row([Gtk.Button(label=str(index)) for index in range(6)], min_children=2).get_min_children_per_line() == 2


def settle(seconds=0.08):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.005)


def capture(window, name):
    window.show_all()
    settle()
    root = Gdk.get_default_root_window()
    bounds = window.get_window().get_frame_extents()
    assert 0 <= bounds.x and bounds.x + bounds.width <= root.get_width(), (name, bounds.width)
    assert 0 <= bounds.y and bounds.y + bounds.height <= root.get_height(), (name, bounds.height)
    pixels = Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())
    pixels.savev(str(output / (name + ".png")), "png", [], [])


keyboard = Gtk.Window(title="Action-row keyboard fixture")
keyboard.set_default_size(560, 220)
keys = [Gtk.Button(label=str(index)) for index in range(6)]
keyboard.add(flow_row(keys, max_children=3, min_children=2))
keyboard.show_all()
settle()
keyboard.get_window().focus(Gdk.CURRENT_TIME)
settle()
keys[0].grab_focus()
settle()
for target in keys[1:]:
    assert keyboard.child_focus(Gtk.DirectionType.TAB_FORWARD)
    focused = keyboard.get_focus()
    assert focused == target, ("FlowBox focus", target.get_label(), type(focused).__name__,
                               focused.get_label() if isinstance(focused, Gtk.Button) else "wrapper")
keyboard.destroy()


pending = []
packages_app.run_async = lambda command, done, **kwargs: pending.append((command, done))
packages_app.load_preferences = lambda: {"reduce_motion": False}
window = packages_app.PackagesWindow()
window.show_all()
window.execute("Updating metadata", ["fixture", "metadata"])
assert window.busy and len(pending) == 1 and window.pulse_source
assert all(not action.get_sensitive() for action in window.action_buttons)
assert not window.search_entry.get_sensitive()
window.execute("Duplicate", ["fixture", "must-not-run"])
assert len(pending) == 1
capture(window, "packages-busy")
pending.pop()[1](1, "Offline fixture: repository unavailable. Reconnect, then retry.")
assert not window.busy and not window.pulse_source
assert all(action.get_sensitive() for action in window.action_buttons)
assert window.status.get_style_context().has_class("status-bad")
capture(window, "packages-error")
packages_app.load_preferences = lambda: {"reduce_motion": True}
window.execute("Retry metadata", ["fixture", "retry"])
assert not window.pulse_source and not window.status.get_style_context().has_class("status-bad")
pending.pop()[1](0, "Metadata ready: fixture only.")
assert window.status.get_style_context().has_class("status-good")
window.execute("Late response", ["fixture", "late"])
callback = pending.pop()[1]
window.destroy()
callback(0, "Do not mutate destroyed UI")
assert window.closed and not window.pulse_source

health_app.run_async = lambda command, done, **kwargs: pending.append((command, done))
health_app.load_preferences = lambda: {"reduce_motion": True}
window = health_app.HealthWindow()
window.show_all()
assert window.pending and len(pending) == 1
assert all(not action.get_sensitive() for action in window.actions)
window.review()
assert len(pending) == 1
pending.pop()[1](1, "Service unavailable in isolated fixture.")
assert not window.pending and all(action.get_sensitive() for action in window.actions)
capture(window, "health-error")
window.review()
assert window.pending
pending.pop()[1](0, "Upgrade review only. No update performed.")
assert not window.status.get_style_context().has_class("status-bad")
original_dialog = Gtk.MessageDialog


class CancelDialog(original_dialog):
    def run(self):
        assert self.get_default_widget() == self.get_widget_for_response(Gtk.ResponseType.CANCEL)
        return Gtk.ResponseType.CANCEL


health_app.Gtk.MessageDialog = CancelDialog
window.refresh_repo()
health_app.Gtk.MessageDialog = original_dialog
assert not pending, "Cancel must not refresh a repository"
window.check()
callback = pending.pop()[1]
window.destroy()
callback(0, "Late callback must be ignored")

window = SignalMapWindow("Nearby signal map")
items = [dict(name="Long network / 장치 이름 " + str(index) + " extended", key=str(index),
              signal=20 + index * 10, category="router" if index % 2 else "device") for index in range(7)]
window.update_items(items)
capture(window, "signal-map-populated")
assert "router(s)" not in window.legend.get_text()
assert "Long network" in window.area.get_accessible().get_description()
assert len(window.node_positions) == len(items)


class Tooltip:
    def set_text(self, text):
        self.text = text


tooltip = Tooltip()
x, y, _radius, item = window.node_positions[-1]
assert window.query_tooltip(window.area, x, y, False, tooltip)
assert window.item_text(item) == tooltip.text
assert window.query_tooltip(window.area, 0, 0, True, tooltip) and "Long network" in tooltip.text
window.update_items([])
capture(window, "signal-map-empty")
window.destroy()

window = Gtk.Window(title="Chart roles - isolated fixture")
window.set_default_size(440, 200)
metric = MetricCard("CPU")
window.add(metric)
for sample in (10, 40, 20, 80):
    metric.update("Fixture samples", sample)
capture(window, "chart-theme")
allocation = metric.chart.get_allocation()
x, y = (0, 0) if metric.chart.get_has_window() else (allocation.x, allocation.y)
pixels = Gdk.pixbuf_get_from_window(metric.chart.get_window(), x, y,
                                  metric.chart.get_allocated_width(), metric.chart.get_allocated_height())
assert pixels is not None
expected = [round(value * 255) for value in chart_colors()["background"]]
assert all(abs(actual - wanted) <= 2 for actual, wanted in zip(pixels.get_pixels()[:3], expected))
window.destroy()
print("UI_DETAILS_RUNTIME_OK responsive busy/error/retry; reduced motion; late callbacks; cancel default; plotted labels/tooltips")
