#!/usr/bin/env python3
"""Optional GTK smoke check on a host with a display and PyGObject."""

import sys
from pathlib import Path


ui_dir = Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana/ui"
sys.path.insert(0, str(ui_dir))

from common import CSS, Gtk, apply_theme  # noqa: E402
from settings_app import SettingsWindow  # noqa: E402
from setup_app import SetupWindow  # noqa: E402


ready, _args = Gtk.init_check([])
if not ready:
    raise SystemExit("GTK display unavailable")

errors = []
provider = Gtk.CssProvider()
provider.connect("parsing-error", lambda _provider, _section, error: errors.append(error.message))
provider.load_from_data(CSS)
assert not errors, errors
for css_path in sys.argv[1:]:
    errors.clear()
    provider.load_from_path(css_path)
    assert not errors, (css_path, errors)
apply_theme()

setup = SetupWindow()
assert not setup.static_revealer.get_reveal_child()
setup.network_combo.set_active_id("static")
assert setup.static_revealer.get_reveal_child()
setup.network_combo.set_active_id("dhcp")
assert not setup.static_revealer.get_reveal_child()

settings = SettingsWindow()
assert settings.stack.get_transition_type() == Gtk.StackTransitionType.SLIDE_LEFT_RIGHT
for page_id, _title, _icon in SettingsWindow.PAGES:
    assert settings.stack.get_child_by_name(page_id) is not None, page_id

print("GTK_UI_RUNTIME_OK")
