#!/usr/bin/env python3
"""Actual locker/grabs/PAM on owned Xvfb and disposable test password only."""
import os
from pathlib import Path
import subprocess
import sys
import time
import hashlib
import tempfile

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


def keymap(symbols):
    # Use the already bundled XKB compiler; no extra distro/package required.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xkb") as fixture:
        fixture.write('xkb_keymap { xkb_keycodes { include "evdev+aliases(qwerty)" }; '
                      'xkb_types { include "complete" }; xkb_compatibility { include "complete" }; '
                      f'xkb_symbols {{ include "{symbols}" }}; xkb_geometry {{ include "pc(pc105)" }}; }};\n')
        fixture.flush()
        run("xkbcomp", "-w", "0", fixture.name, os.environ["DISPLAY"])


try:
    virtual = "--virtual-monitors" in sys.argv
    if virtual:
        assert root.get_width() == 1280 and root.get_height() == 800 and scale == 1
        run("xrandr", "--setmonitor", "OoonanaQA-left", "640/160x800/200+0+0", "screen")
        run("xrandr", "--setmonitor", "OoonanaQA-right", "640/160x800/200+640+0", "none")
        monitors = subprocess.check_output(["xrandr", "--listactivemonitors"], text=True)
        (output / "monitors.txt").write_text(monitors)
        assert "Monitors: 2" in monitors, "Fixture did not provide two active RandR monitors: " + monitors
        run("xsetroot", "-solid", "#dd44aa")
    assert lock_screen.live_account_status() == 0, "Real noninteractive live-account preflight failed"
    with (output / "i3lock.log").open("w") as log:
        args = lock_screen.command()
        # Test owns foreground locker handle; production keeps vendor fork-after-grab.
        launch = ["ooonana-lock", "--foreground"] if "--extended" in sys.argv else args + ["--nofork"]
        process = subprocess.Popen(launch, env=dict(os.environ, OOONANA_LOCK_VISUALS="1"), stdout=log, stderr=log)
        expected = bytes.fromhex(args[args.index("--color") + 1])
        ready_deadline = time.monotonic() + 8
        while True:
            assert process.poll() is None, "Private real locker failed to grab"
            pixel = Gdk.pixbuf_get_from_window(root, 8, 8, 1, 1)
            if pixel and pixel.get_pixels()[:3] == expected:
                break
            assert time.monotonic() < ready_deadline, "Opaque lock palette mismatch"
            time.sleep(.04)
        def heading():
            center = root.get_width() // (4 if virtual else 2)
            sample = Gdk.pixbuf_get_from_window(root, center - 100, 20, 200, 100)
            return bytes(sample.get_pixels())
        if "--require-visuals" in sys.argv:
            text = heading()
            assert any(text[offset:offset + 3] != expected for offset in range(0, len(text), 3)), "Clock/date header absent"
            height = root.get_height()
            if height >= 300:
                baseline = 30 if height < 360 else min(80, height * .18)
                hint_y = min(baseline + 48, height / 2 - 68)
                center = root.get_width() // (4 if virtual else 2)
                hint = Gdk.pixbuf_get_from_window(root, center - 110, int(hint_y - 14), 220, 20)
                pixels = bytes(hint.get_pixels())
                assert any(pixels[pos:pos + 3] != expected for pos in range(0, len(pixels), hint.get_n_channels())), "Compact-screen unlock instruction absent"
            if virtual:
                right = Gdk.pixbuf_get_from_window(root, 860, 20, 200, 100)
                text = bytes(right.get_pixels())
                assert any(text[offset:offset + 3] != expected for offset in range(0, len(text), 3)), "Second monitor lacks clock/date"
                for x in (8, 632, 648, 1272):
                    for y in (8, 792):
                        assert Gdk.pixbuf_get_from_window(root, x, y, 1, 1).get_pixels()[:3] == expected, "Desktop exposed on monitor edge"
                screenshot = Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())
                pixels = bytes(screenshot.get_pixels())
                assert not any(pixels[pos:pos + 3] == b"\xdd\x44\xaa" for pos in range(0, len(pixels), screenshot.get_n_channels())), "Underlying desktop remains visible"
                print("LOCK_MULTIMONITOR_OPAQUE_OK two active RandR monitors, per-monitor headings and covered edges", flush=True)
        capture("idle")
        if "--extended" in sys.argv:
            import ctypes as C
            x = C.CDLL("libX11.so.6")
            x.XOpenDisplay.restype = C.c_void_p
            x.XDefaultRootWindow.argtypes = [C.c_void_p]; x.XDefaultRootWindow.restype = C.c_ulong
            x.XGrabKeyboard.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_int, C.c_int, C.c_ulong]
            x.XCloseDisplay.argtypes = [C.c_void_p]
            display = x.XOpenDisplay(None)
            assert display
            try:
                assert x.XGrabKeyboard(display, x.XDefaultRootWindow(display), False, 1, 1, 0) == 1, "Keyboard is not actually grabbed"
            finally:
                x.XCloseDisplay(display)
            duplicate = subprocess.run(["ooonana-lock"], env=dict(os.environ, OOONANA_LOCK_VISUALS="1"),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            assert duplicate.returncode == 75 and process.poll() is None, "Second launcher replaced active lock"
            run("xdotool", "key", "Escape", "Return")
            time.sleep(.4)
            assert process.poll() is None, "Empty input/Escape released lock"
            keymap("pc+us+de:2+inet(evdev)+group(alt_shift_toggle)")
            run("xdotool", "type", "x")
            run("xdotool", "key", "alt+shift")
            time.sleep(.2)
            capture("layout-switch")
            run("xdotool", "key", "alt+shift", "Escape")
            keymap("pc+us+inet(evdev)")
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
        if "--extended" in sys.argv:
            run("xdotool", "type", "discarded-draft")
            run("xdotool", "key", "Escape")
        run("xdotool", "type", "--delay", "10", credential[:12] + ("x" if "--extended" in sys.argv else ""))
        if "--extended" in sys.argv:
            run("xdotool", "key", "BackSpace")
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
