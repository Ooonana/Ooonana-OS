#!/usr/bin/env python3
"""Resolved GTK text/surface contrast and form labels on a private QA display."""
import os
from pathlib import Path
import sys

if os.environ.get("OOONANA_GUI_TEST_DISPLAY") != "1" or os.getuid() == 0:
    raise SystemExit("Dedicated nonroot display required")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme, card, label, light_appearance
from chat_widgets import apply_ai_theme
from setup_app import field_row
from wifi_app import WifiCredentialsDialog


def brightness(color):
    def linear(value):
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
    return sum(linear(value) * weight for value, weight in
               zip((color.red, color.green, color.blue), (0.2126, 0.7152, 0.0722)))


apply_theme()
window = Gtk.Window()
root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
window.add(root)
checks = []
for role in ("page-title", "muted", "status-good", "status-warn", "status-bad"):
    text = label("Readable state", role)
    root.pack_start(text, False, False, 0)
    checks.append((text, window, role))
panel = card("Readable card", "Readable description")
root.pack_start(panel, False, False, 0)
for child in panel.get_children():
    if isinstance(child, Gtk.Label):
        checks.append((child, panel, "card text"))
apply_ai_theme(window)
for role in ("ai-composer", "ai-code", "ai-assistant", "ai-user"):
    box = Gtk.Box()
    box.get_style_context().add_class(role)
    text = label("Readable chat content")
    box.add(text)
    root.pack_start(box, False, False, 0)
    checks.append((text, box, role))
window.show_all()
while Gtk.events_pending():
    Gtk.main_iteration_do(False)
for text, surface, name in checks:
    foreground = text.get_style_context().get_color(Gtk.StateFlags.NORMAL)
    background = surface.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
    assert background.alpha == 1, (name, "nonopaque surface")
    values = sorted((brightness(foreground), brightness(background)))
    assert (values[1] + 0.05) / (values[0] + 0.05) >= 4.5, (name, foreground, background)
grid, entry = Gtk.Grid(), Gtk.Entry()
field_row(grid, 0, "User name", entry)
assert entry.get_accessible().get_name() == "User name"
wifi = WifiCredentialsDialog(None, dict(ssid="QA", security_label="Enterprise", security_kind="enterprise"))
assert wifi.identity.get_accessible().get_name() == "Identity"
assert wifi.password.get_accessible().get_name() == "Password"
wifi.destroy()
window.destroy()
print(f"NATIVE_APPEARANCE_OK {'light' if light_appearance() else 'dark'}; {len(checks)} contrast roles; setup/Wi-Fi labels")
