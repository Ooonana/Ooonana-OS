#!/usr/bin/env python3
"""Optional GTK smoke check on a host with a display and PyGObject."""

import sys
import tempfile
import time
from types import SimpleNamespace
from pathlib import Path


ui_dir = Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana/ui"
sys.path.insert(0, str(ui_dir))

from common import CSS, WINDOW_CONTROL_CSS, Gdk, Gtk, apply_theme, host_radio_unavailable, icon  # noqa: E402
from wifi_app import WifiWindow  # noqa: E402
from bluetooth_app import BluetoothWindow  # noqa: E402
from settings_app import SettingsWindow  # noqa: E402
from setup_app import SetupWindow  # noqa: E402
from task_manager_app import TaskManagerWindow, cpu_totals, meminfo_values, parse_process_stat, thermal_fan_snapshot  # noqa: E402
from gi.repository import GdkPixbuf  # noqa: E402


ready, _args = Gtk.init_check([])
if not ready:
    raise SystemExit("GTK display unavailable")

errors = []
provider = Gtk.CssProvider()
provider.connect("parsing-error", lambda _provider, _section, error: errors.append(error.message))
provider.load_from_data(CSS)
assert not errors, errors
provider.load_from_data(WINDOW_CONTROL_CSS)
assert not errors, errors
for css_path in sys.argv[1:]:
    errors.clear()
    provider.load_from_path(css_path)
    assert not errors, (css_path, errors)
apply_theme()

# Resolve real GTK styles, not CSS substring matches. Never activate actions.
style_window = Gtk.Window(title="Button states · isolated QA")
style_window.set_default_size(600, 320)
style_grid = Gtk.Grid(column_spacing=12, row_spacing=12, margin=20)
style_window.add(style_grid)
animations = Gtk.Settings.get_default().get_property("gtk-enable-animations")
Gtk.Settings.get_default().set_property("gtk-enable-animations", False)
states = (("Default", Gtk.StateFlags.NORMAL), ("Hover", Gtk.StateFlags.PRELIGHT),
          ("Pressed", Gtk.StateFlags.ACTIVE | Gtk.StateFlags.PRELIGHT),
          ("Focus", Gtk.StateFlags.FOCUSED), ("Disabled", Gtk.StateFlags.INSENSITIVE))
roles = ((None, "Action"), ("suggested-action", "Apply"), ("destructive-action", "Remove"))
styled = []
for column, (name, _state) in enumerate(states):
    style_grid.attach(Gtk.Label(label=name), column, 0, 1, 1)
for row, (role, label) in enumerate(roles, start=1):
    for column, (_name, state) in enumerate(states):
        widget = Gtk.Button(label=label)
        if role:
            widget.get_style_context().add_class(role)
        style_grid.attach(widget, column, row, 1, 1)
        styled.append((widget, role, state))
style_window.show_all()
while Gtk.events_pending():
    Gtk.main_iteration_do(False)

def luminance(color):
    linear = lambda value: value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
    return sum(weight * linear(value) for weight, value in
               zip((0.2126, 0.7152, 0.0722), (color.red, color.green, color.blue)))

backgrounds = {}
for widget, role, state in styled:
    if state == Gtk.StateFlags.INSENSITIVE:
        widget.set_sensitive(False)
    else:
        widget.set_state_flags(state, True)
    context = widget.get_style_context()
    actual = widget.get_state_flags()
    background = context.get_background_color(actual)
    foreground = context.get_color(actual)
    backgrounds[role, state] = background.to_string()
    if state != Gtk.StateFlags.INSENSITIVE:
        bright, dark = sorted((luminance(background), luminance(foreground)), reverse=True)
        assert (bright + 0.05) / (dark + 0.05) >= 4.5, (role, state, foreground, background)
for role, _label in roles:
    assert len({backgrounds[role, state] for _name, state in states[:3]}) == 3, role
    assert backgrounds[role, Gtk.StateFlags.FOCUSED] == backgrounds[role, Gtk.StateFlags.NORMAL]
for _ in range(10):
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    time.sleep(0.01)
if Path("/qa").is_dir():
    native = style_window.get_window()
    Gdk.pixbuf_get_from_window(native, 0, 0, native.get_width(), native.get_height()).savev(
        "/qa/button-states.png", "png", [], [])
style_window.destroy()
Gtk.Settings.get_default().set_property("gtk-enable-animations", animations)
for filename in ("logo.png", "logo.svg", "wallpaper.png"):
    image = GdkPixbuf.Pixbuf.new_from_file(str(ui_dir.parents[5] / "branding" / filename))
    assert image.get_width() > 0 and image.get_height() > 0, filename
spinner = Gtk.IconTheme.get_default().lookup_icon("process-working-symbolic", 16, Gtk.IconLookupFlags.FORCE_SIZE)
assert spinner is not None and spinner.load_icon().get_width() > 0, "Spinner image loader missing"
for name in ("preferences-desktop-theme-symbolic", "preferences-desktop-peripherals-symbolic", "utilities-system-monitor-symbolic"):
    selected, _size = icon(name).get_icon_name()
    assert Gtk.IconTheme.get_default().has_icon(selected), (name, selected)
if host_radio_unavailable("wifi"):
    wifi = WifiWindow()
    assert "Windows" in wifi.service_label.get_text()
    assert not wifi.toolbar.get_sensitive()
if host_radio_unavailable("bluetooth"):
    bluetooth = BluetoothWindow()
    assert "Windows" in bluetooth.service_status.get_text()
    assert not bluetooth.toolbar.get_sensitive()

setup = SetupWindow()
controls = next(child for child in setup.get_titlebar().get_children() if isinstance(child, Gtk.Box))
assert [widget.get_accessible().get_name() for widget in controls.get_children()] == ["Close window", "Minimize window", "Toggle fullscreen"]
assert setup.get_default_size().width == 800
assert 320 <= setup.get_default_size().height <= 600
assert not setup.static_revealer.get_reveal_child()
setup.network_combo.set_active_id("static")
assert setup.static_revealer.get_reveal_child()
setup.network_combo.set_active_id("dhcp")
assert not setup.static_revealer.get_reveal_child()

settings = SettingsWindow()
assert settings.stack.get_transition_type() == Gtk.StackTransitionType.SLIDE_LEFT_RIGHT
for page_id, _title, _icon in SettingsWindow.PAGES:
    assert settings.stack.get_child_by_name(page_id) is not None, page_id
settings.resized(settings, SimpleNamespace(width=640))
assert settings.compact_layout
assert all(row.get_orientation() == Gtk.Orientation.VERTICAL for row in settings.appearance_rows)
for grid in settings.card_grids:
    for child in grid.get_children():
        assert grid.child_get_property(child, "left-attach") == 0
settings.resized(settings, SimpleNamespace(width=1100))
assert not settings.compact_layout
assert all(row.get_orientation() == Gtk.Orientation.HORIZONTAL for row in settings.appearance_rows)
for grid in settings.card_grids:
    for child in grid.get_children():
        assert tuple(grid.child_get_property(child, name) for name in
                     ("left-attach", "top-attach", "width", "height")) == child.wide_cell

assert meminfo_values("MemTotal: 1024 kB\nMemAvailable: 512 kB\n")["MemAvailable"] == 512
assert cpu_totals("cpu  1 2 3 4 5 6\n") == (21, 9)
assert parse_process_stat("1 (test process) S " + " ".join(["0"] * 19)) == ("S", 0, 0)
with tempfile.TemporaryDirectory() as temporary:
    hwmon = Path(temporary) / "hwmon" / "hwmon0"
    hwmon.mkdir(parents=True)
    (hwmon / "name").write_text("coretemp")
    (hwmon / "temp1_label").write_text("Package id 0")
    (hwmon / "temp1_input").write_text("47500")
    (hwmon / "fan1_input").write_text("2134")
    assert thermal_fan_snapshot(hwmon.parent, Path(temporary) / "thermal") == (
        "Package id 0 48°C", "coretemp 2134 RPM"
    )
manager = TaskManagerWindow()
assert manager.stack.get_child_by_name("processes") is not None
assert manager.stack.get_child_by_name("performance") is not None
assert len(manager.tree.get_columns()) == 7
long_uptime = 2**40
row = manager.store.append(("Long uptime fixture", 1234, 0.0, 1.0, "qa", "S", "qa", long_uptime, 2**32 - 2))
assert manager.store[row][7] == long_uptime
assert manager.store[row][8] == 2**32 - 2
manager.store.remove(row)

print("GTK_UI_RUNTIME_OK")
