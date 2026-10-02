#!/usr/bin/env python3
"""Optional GTK smoke check on a host with a display and PyGObject."""

import sys
import tempfile
from pathlib import Path


ui_dir = Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana/ui"
sys.path.insert(0, str(ui_dir))

from common import CSS, WINDOW_CONTROL_CSS, Gtk, apply_theme, host_radio_unavailable, icon  # noqa: E402
from wifi_app import WifiWindow  # noqa: E402
from bluetooth_app import BluetoothWindow  # noqa: E402
from settings_app import SettingsWindow  # noqa: E402
from setup_app import SetupWindow  # noqa: E402
from task_manager_app import TaskManagerWindow, cpu_totals, meminfo_values, parse_process_stat, thermal_fan_snapshot  # noqa: E402


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

print("GTK_UI_RUNTIME_OK")
