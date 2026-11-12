#!/usr/bin/env python3
"""Same running native Power process/window follows atomic appearance changes."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))

if "--worker" in sys.argv:
    import cairo
    import common
    from common import Gdk, GLib, Gtk, apply_theme
    from controls_app import PowerWindow
    from dock_app import Dock
    from gi.repository import GdkX11
    apply_theme()
    window = PowerWindow()
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    dock = Dock(subscribe=False)
    dock.show_all()
    def snapshot(*_args):
        command = sys.stdin.readline().strip()
        if command == "quit" or not command:
            window.destroy()
            return False
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 48, 48)
        Gtk.render_background(window.get_style_context(), cairo.Context(surface), 0, 0, 48, 48)
        surface.flush()
        offset = 24 * surface.get_stride() + 24 * 4
        color = bytes(surface.get_data()[offset:offset + 3])[::-1]
        Gtk.render_background(dock.get_style_context(), cairo.Context(surface), 0, 0, 48, 48)
        surface.flush()
        dock_color = bytes(surface.get_data()[offset:offset + 3])[::-1]
        settings = Gtk.Settings.get_default()
        print(json.dumps({"pid": os.getpid(), "xid": GdkX11.X11Window.get_xid(window.get_window()),
            "color": list(color), "dock_color": list(dock_color), "dark": settings.get_property("gtk-application-prefer-dark-theme"),
            "animations": settings.get_property("gtk-enable-animations"),
            "provider": id(common._theme_provider), "monitors": len(common._appearance_watch.monitors)}), flush=True)
        return True
    GLib.io_add_watch(sys.stdin.fileno(), GLib.IO_IN | GLib.IO_HUP, snapshot)
    Gtk.main()
    raise SystemExit(0)

from common import Gdk
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
def request(worker):
    worker.stdin.write("snapshot\n"); worker.stdin.flush()
    assert select.select([worker.stdout], [], [], 5)[0], "Live native process did not respond"
    line = worker.stdout.readline()
    assert line, "Live native process exited"
    return json.loads(line)

def state():
    tree = json.loads(subprocess.check_output(["i3-msg", "-t", "get_tree"], text=True))
    result = {}
    def visit(node):
        if node.get("window"):
            result[node["window"]] = (node["id"], node["rect"], node.get("focused"), node.get("fullscreen_mode"))
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            visit(child)
    visit(tree)
    return result

with tempfile.TemporaryDirectory(prefix="ooonana-live-theme-") as temporary:
    base = Path(temporary)
    config = base / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                                if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    worker = None
    try:
        deadline = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < deadline, "Private WM unavailable"
            time.sleep(.03)
        preference = base / "config/ooonana/theme"
        preference.parent.mkdir(parents=True)
        def write(value):
            path = preference.with_name(".theme.owned-qa")
            path.write_text(value + "\n")
            path.replace(preference)
        for pinned in (False, True):
            write("dark")
            env = dict(os.environ, XDG_CONFIG_HOME=str(base / "config"), OOONANA_THEME="dark", OOONANA_THEME_INHERITED="dark")
            env.pop("OOONANA_THEME_OVERRIDE", None)
            if pinned:
                env["OOONANA_THEME_OVERRIDE"] = "dark"
            with (output / ("pinned.log" if pinned else "following.log")).open("w") as log:
                worker = subprocess.Popen([sys.executable, __file__, "--worker"], env=env,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True, bufsize=1)
                initial = request(worker)
                time.sleep(.3)
                baseline = state()
                for selected in ("light", "dark"):
                    write(selected)
                    expected = [16, 19, 23] if pinned or selected == "dark" else [245, 245, 247]
                    expected_dock = [27, 31, 38] if pinned or selected == "dark" else [255, 255, 255]
                    deadline = time.monotonic() + 8
                    while True:
                        current = request(worker)
                        if current["color"] == expected and current["dock_color"] == expected_dock:
                            break
                        assert time.monotonic() < deadline, (selected, current, expected)
                        time.sleep(.03)
                    assert current["pid"] == initial["pid"] and current["xid"] == initial["xid"]
                    assert current["provider"] == initial["provider"] and current["monitors"] <= 3
                    assert state() == baseline, "Live appearance changed window state"
                    if not pinned:
                        root = Gdk.get_default_root_window()
                        scale = root.get_scale_factor()
                        rect = baseline[current["xid"]][1]
                        deadline = time.monotonic() + 8
                        while True:
                            pixel = Gdk.pixbuf_get_from_window(root, (rect["x"] + 20 * scale) // scale,
                                (rect["y"] + rect["height"] - 16 * scale) // scale, 1, 1)
                            if pixel and list(pixel.get_pixels()[:3]) == expected:
                                break
                            assert time.monotonic() < deadline, "Computed theme changed but mapped native body did not repaint"
                            time.sleep(.03)
                        # Let child controls finish their existing color transition.
                        time.sleep(.2)
                        Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                            str(output / (selected + "-same-window.png")), "png", [], [])
                ui = preference.with_name("ui.json")
                ui.write_text('{"reduce_motion": true}\n')
                deadline = time.monotonic() + 8
                while request(worker)["animations"]:
                    assert time.monotonic() < deadline, "Live reduced-motion preference ignored"
                    time.sleep(.03)
                worker.stdin.write("quit\n"); worker.stdin.flush()
                assert worker.wait(timeout=5) == 0
                worker = None
            print("NATIVE_LIVE_THEME_OK", "explicit pin retained" if pinned else "same Power process/window dark-light-dark", flush=True)
    finally:
        if worker is not None and worker.poll() is None:
            worker.terminate(); worker.wait(timeout=5)
        wm.terminate(); wm.wait(timeout=5)
