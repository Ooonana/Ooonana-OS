#!/usr/bin/env python3
"""Render only the builder's YAD form. Never execute an installer or touch disks."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

if os.environ.get("OOONANA_GUI_TEST_DISPLAY") != "1" or os.getuid() == 0:
    raise SystemExit("Dedicated nonroot test display required")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk
from gi.repository import GdkX11

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
for section in ("--help-form", "--help-general", "--help-all"):
    result = subprocess.run(["yad", section], text=True, capture_output=True, timeout=5)
    (args.output / (section.removeprefix("--") + ".txt")).write_text(result.stdout + result.stderr)

source = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
theme_script = args.output / "ooonana-theme-env"
theme_script.write_text(source.split('"$ROOTFS/usr/bin/ooonana-theme-env" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0])
subprocess.run(["sh", str(theme_script), "apply"], check=True, capture_output=True, timeout=20)
form = source.split('form="$(yad ', 1)[1].split('2>/dev/null || true)"', 1)[0]
form = form.replace("\\\n", " ").replace("$default_target", "")
form = form.replace("$disk_summary", "/dev/fixtureUSB  32G  Owned test USB\n/dev/fixtureSSD  512G  Do not select")
# Future monitor-fit variables are replaced only inside this form invocation.
root = Gdk.get_default_root_window()
form = form.replace("$form_width", str(min(720, root.get_width() - 48)))
form = form.replace("$form_height", str(min(680, root.get_height() - 96)))
command = ["yad", *shlex.split(form)]
xid_path = args.output / "form.xid"
assert not xid_path.exists(), "Output must be fresh"
command.append("--print-xid=" + str(xid_path))
assert command.count("--field") == 16, "Installer fields unexpectedly changed"
assert "--scroll" in command and "--focus-field=1" in command, "Mode and later fields must remain reachable"
assert "--button=Cancel:1" in command and "--button=Review installation:0" in command
assert not any(item in command for item in ("--command", "--plug", "--listen")), "Interactive side effect refused"
with (args.output / "form.log").open("w") as log:
    process = subprocess.Popen(command, stdout=log, stderr=log)
    try:
        deadline = time.monotonic() + 8
        window = None
        while window is None:
            assert process.poll() is None, "YAD form exited before capture"
            if xid_path.is_file() and xid_path.read_text().strip():
                xid = int(xid_path.read_text().strip(), 0)
                window = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), xid)
            assert time.monotonic() < deadline, "Owned installer form unavailable"
            time.sleep(0.05)
        time.sleep(0.25)
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        bounds = window.get_frame_extents()
        pixels = Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())
        pixels.savev(str(args.output / "installer-form.png"), "png", [], [])
        print(f"INSTALLER_FORM {bounds.width}x{bounds.height} at {bounds.x},{bounds.y}", flush=True)
        assert 0 <= bounds.x and bounds.x + bounds.width <= root.get_width()
        assert 0 <= bounds.y and bounds.y + bounds.height <= root.get_height()
        print("INSTALLER_UI_OK real YAD form fits; no disk enumeration or install command executed")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
