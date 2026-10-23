#!/usr/bin/env python3
"""Actual locker/grabs/PAM on owned Xvfb and disposable test password only."""
import os
from pathlib import Path
import subprocess
import sys
import time
import hashlib

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana"))
import lock_screen
from desktop_theme import XResources
import gi
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk
Gdk.init([])
output = Path(sys.argv[1]); output.mkdir(parents=True, exist_ok=True)
root = Gdk.get_default_root_window()
resources = XResources()
original = resources.read("RESOURCE_MANAGER")
scale = root.get_scale_factor()
assert resources.replace("RESOURCE_MANAGER", original, f"Xft.dpi: {96 * scale}\n".encode())
process = None


def capture(name):
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(output / (name + ".png")), "png", [], [])


def run(*args):
    subprocess.run(args, check=True, capture_output=True, timeout=5)


try:
    assert lock_screen.live_account_status() == 0, "Real noninteractive live-account preflight failed"
    with (output / "i3lock.log").open("w") as log:
        args = lock_screen.command()
        # Test owns foreground locker handle; production keeps vendor fork-after-grab.
        process = subprocess.Popen(args + ["--nofork"], env=dict(os.environ, OOONANA_LOCK_VISUALS="1"), stdout=log, stderr=log)
        time.sleep(.5)
        assert process.poll() is None, "Private real locker failed to grab"
        expected = bytes.fromhex(args[args.index("--color") + 1])
        pixel = Gdk.pixbuf_get_from_window(root, 8, 8, 1, 1)
        assert pixel and pixel.get_pixels()[:3] == expected, "Opaque lock palette mismatch"
        def heading():
            sample = Gdk.pixbuf_get_from_window(root, root.get_width() // 2 - 100, 20, 200, 100)
            return bytes(sample.get_pixels())
        if "--require-visuals" in sys.argv:
            text = heading()
            assert any(text[offset:offset + 3] != expected for offset in range(0, len(text), 3)), "Clock/date header absent"
        capture("idle")
        run("xdotool", "key", "Caps_Lock")
        run("xdotool", "type", "--delay", "10", "wrong-private-qa-password")
        capture("caps-input")
        run("xdotool", "key", "Return")
        time.sleep(3)
        assert process.poll() is None, "Wrong password unlocked private session"
        capture("wrong-password")
        run("xdotool", "key", "Caps_Lock")
        # Wait out vendor's wrong-password input cooldown before retry.
        time.sleep(2.5)
        run("xdotool", "key", "ctrl+u")
        credential = "Ooonana-private-lock-QA-20261023"
        run("xdotool", "type", "--delay", "10", credential[:12])
        if "--clock-wait" in sys.argv:
            assert "--require-visuals" in sys.argv
            before = hashlib.sha256(heading()).digest()
            until = time.monotonic() + 65
            while hashlib.sha256(heading()).digest() == before:
                assert time.monotonic() < until, "Real minute clock failed to redraw"
                assert process.poll() is None, "Clock timer released lock"
                time.sleep(.2)
            capture("minute-tick-with-draft")
        run("xdotool", "type", "--delay", "10", credential[12:])
        run("xdotool", "key", "Return")
        assert process.wait(timeout=12) == 0, "Correct disposable password did not unlock"
    print("LOCK_UI_REAL_OK", os.environ.get("OOONANA_THEME"), "device", scale,
          "opaque palette; actual grab/input; wrong rejection; correct unlock; vendor PAM unchanged; clock-wait", "--clock-wait" in sys.argv, flush=True)
finally:
    if process is not None and process.poll() is None:
        process.terminate()
        process.wait(timeout=5)
    resources.replace("RESOURCE_MANAGER", resources.read("RESOURCE_MANAGER"), original)
    resources.close()
