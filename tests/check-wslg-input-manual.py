#!/usr/bin/env python3
"""Manual physical input on an owned rootless WSLg candidate; no raw text log."""
import json
import os
from pathlib import Path
import subprocess
import sys

assert os.getuid() == 1000 and os.environ.get("OOONANA_WSLG_MANUAL_QA") == "1"
assert Path("/run/ooonana-wslg-qa").is_file(), "Owned QA namespace required"
output = Path("/qa/wslg-input")
output.mkdir(exist_ok=True)
os.environ.update(json.loads(subprocess.check_output(["ooonana-input-method", "--json-env"], text=True)))
subprocess.run(["ooonana-input-method", "--start"], check=True, timeout=10)
sys.path.insert(0, "/usr/lib/ooonana/ui")
from common import Gdk, Gtk, GLib, apply_theme, header

apply_theme()
expected = "Ooonana 한글"
checks = dict(mouse=False, keyboard=False, backspace=False, composition=False, paste=False)
finished = False
window = Gtk.Window(title="Ooonana candidate — WSLg input check")
window.set_default_size(580, 340)
header(window, "Input check", "Private Ooonana candidate · WSLg")
body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
body.set_border_width(18)
window.add(body)
instructions = Gtk.Label(label="Click first field. Type: Ooonana 한글\nUse Ctrl+Space for Hangul. Backspace, then restore last letter.", xalign=0)
instructions.set_line_wrap(True)
body.pack_start(instructions, False, False, 0)
first, second = Gtk.Entry(), Gtk.Entry()
first.get_accessible().set_name("Type QA text")
second.get_accessible().set_name("Paste QA text")
first.set_placeholder_text("Type QA text")
second.set_placeholder_text("Paste copied QA text here")
body.pack_start(first, False, False, 0)
body.pack_start(second, False, False, 0)
status = Gtk.Label(label="Waiting for physical mouse and keyboard input.", xalign=0)
status.set_line_wrap(True)
body.pack_start(status, False, False, 0)
buttons = Gtk.Box(spacing=8)
copy = Gtk.Button(label="Copy QA text")
done = Gtk.Button(label="Finish check")
buttons.pack_start(copy, False, False, 0)
buttons.pack_end(done, False, False, 0)
body.pack_end(buttons, False, False, 0)


def clicked(*_):
    checks["mouse"] = True
    return False


def key(_entry, event):
    checks["keyboard"] = True
    checks["backspace"] |= event.keyval == Gdk.KEY_BackSpace
    return False


def changed(*_):
    checks["composition"] = first.get_text() == expected
    checks["paste"] = second.get_text() == expected
    status.set_text("Ready to finish." if all(checks.values()) else
                    "Remaining: " + ", ".join(name for name, passed in checks.items() if not passed))


def save(complete):
    global finished
    if finished:
        return
    finished = True
    # Record booleans only. Never retain arbitrary clipboard or typed contents.
    (output / "result.json").write_text(json.dumps(dict(checks=checks, complete=complete,
        session="rootless WSLg", nested_i3_tested=False, installed_wsl_updated=False), indent=2)+"\n")
    if complete:
        drawable = window.get_window()
        pixels = Gdk.pixbuf_get_from_window(drawable, 0, 0, window.get_allocated_width(), window.get_allocated_height())
        if pixels is not None:
            pixels.savev(str(output / "complete.png"), "png", [], [])
    Gtk.main_quit()


def finish(*_):
    changed()
    if all(checks.values()):
        save(True)
    else:
        status.set_text("Complete remaining checks before finishing.")


first.connect("button-press-event", clicked)
first.connect("key-press-event", key)
first.connect("changed", changed)
second.connect("changed", changed)
copy.connect("clicked", lambda *_: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(expected, -1))
done.connect("clicked", finish)
window.connect("destroy", lambda *_: save(False))
GLib.timeout_add_seconds(900, lambda: (save(False), False)[1])
window.show_all()
Gtk.main()
result = json.loads((output / "result.json").read_text())
print("WSLG_MANUAL_INPUT_" + ("PASS" if result["complete"] else "PENDING"), flush=True)
raise SystemExit(0 if result["complete"] else 77)
