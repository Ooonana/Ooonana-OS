#!/usr/bin/env python3
"""Measure rendered text/control proportions. Private desktop display only."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1" and os.getuid() != 0
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--mode", choices=("native", "source"))
parser.add_argument("--baseline", action="store_true")
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
if args.mode is None:
    failed = False
    for mode in ("native", "source"):
        command = [sys.executable, __file__, str(args.output), "--mode", mode]
        if args.baseline:
            command.append("--baseline")
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        (args.output / (mode + ".log")).write_text(result.stdout + result.stderr)
        print(result.stdout, end="", flush=True)
        failed |= result.returncode != 0
    raise SystemExit(1 if failed else 0)

if args.mode == "source":
    source = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
    helper = args.output / "ooonana-theme-env"
    helper.write_text(source.split('"$ROOTFS/usr/bin/ooonana-theme-env" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0])
    helper.chmod(0o755)
    subprocess.run([str(helper), "apply"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)

sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme, button, header, label
scale = float(os.environ.get("OOONANA_GUI_TEXT_SCALE", "1.25"))
Gtk.Settings.get_default().set_property("gtk-xft-dpi", int(96 * 1024 * scale))
if args.mode == "native":
    apply_theme()
window = Gtk.Window(title="Ooonana control proportions")
window.set_default_size(560, 340)
header(window, "Control proportions", "Unchanged text · desktop sizing")
grid = Gtk.Grid(column_spacing=16, row_spacing=12)
grid.set_border_width(16)
window.add(grid)
action = button("Apply", "object-select-symbolic")
action.set_hexpand(True)
entry = Gtk.Entry()
entry.set_text("Example value")
combo = Gtk.ComboBoxText()
combo.append_text("Fit desktop")
combo.set_active(0)
widgets = {"button": action, "entry": entry, "combo": combo}
for index, (name, widget) in enumerate(widgets.items()):
    grid.attach(Gtk.Label(label=name.title(), xalign=0), 0, index, 1, 1)
    grid.attach(widget, 1, index, 1, 1)
window.show_all()
deadline = time.monotonic() + 0.3
while time.monotonic() < deadline:
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    time.sleep(0.005)
report, failures = {}, []
for name, widget in widgets.items():
    text_height = widget.create_pango_layout("Example value").get_pixel_size()[1]
    height = widget.get_allocated_height()
    report[name] = dict(height=height, text_height=text_height, overhead=height-text_height,
                        font=widget.get_style_context().get_font(Gtk.StateFlags.NORMAL).to_string())
    if widget.get_style_context().get_font(Gtk.StateFlags.NORMAL).get_size() != 10 * 1024:
        failures.append(name + " typography differs from desktop 10pt")
    if height < max(28, text_height + 8) or height > max(36, text_height + 18):
        failures.append(name)
button_text_width = action.create_pango_layout(action.get_label()).get_pixel_size()[0]
report["button"].update(width=action.get_allocated_width(), text_width=button_text_width)
if action.get_allocated_width() > button_text_width + 72:
    failures.append("stretched action width")
screen = Gdk.get_default_root_window()
Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height()).savev(str(args.output / (args.mode + ".png")), "png", [], [])
(args.output / (args.mode + ".json")).write_text(json.dumps(report, indent=2) + "\n")
print("CONTROL_DENSITY " + args.mode + " " + json.dumps(report), flush=True)
window.destroy()
if args.mode == "native":
    # Heading refinements must not shrink body copy or defeat user DPI.
    specimen = Gtk.Window(title="Ooonana typography")
    specimen.set_default_size(560, 420)
    header(specimen, "Typography", "Compact headings · unchanged body text")
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    content.set_border_width(16)
    specimen.add(content)
    roles = {}
    for role, text in (("hero-title", "Ooonana"), ("page-title", "Appearance"),
                       ("card-title", "Desktop settings"), ("body", "Readable text · 한글 입력")):
        widget = label(text, None if role == "body" else role)
        content.pack_start(widget, False, False, 0)
        roles[role] = widget
    search = Gtk.SearchEntry()
    search.set_placeholder_text("Search applications")
    search.get_style_context().add_class("spotlight-search")
    content.pack_start(search, False, False, 0)
    roles["spotlight-search"] = search
    specimen.show_all()
    deadline = time.monotonic() + 0.3
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.005)
    expected = {"body": 10, "card-title": 11, "spotlight-search": 12,
                "page-title": 14, "hero-title": 18}
    sizes = {}
    for role, widget in roles.items():
        size = widget.get_style_context().get_font(Gtk.StateFlags.NORMAL).get_size() / 1024
        sizes[role] = size
        if size != expected[role]:
            failures.append(f"{role} expected {expected[role]}pt, got {size}pt")
    if Gtk.Settings.get_default().get_property("gtk-xft-dpi") != int(96 * 1024 * scale):
        failures.append("typography changed accessibility DPI")
    Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height()).savev(
        str(args.output / "typography.png"), "png", [], [])
    print("TYPOGRAPHY_ROLES " + json.dumps(sizes), flush=True)
    specimen.destroy()
if failures:
    print("CONTROL_DENSITY_FINDING oversized/undersized desktop controls: " + ", ".join(failures), flush=True)
    if not args.baseline:
        raise SystemExit(1)
else:
    print("CONTROL_DENSITY_UI_OK " + args.mode + "; desktop 10pt; bounded control overhead", flush=True)
