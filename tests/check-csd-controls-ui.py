#!/usr/bin/env python3
"""Real GTK CSD buttons, generated session theme, private i3/X11 only."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)

if "--worker" not in sys.argv:
    # GTK must read real generated per-user settings before initialization.
    with tempfile.TemporaryDirectory(prefix="ooonana-csd-theme-") as temporary:
        helper = Path(temporary) / "ooonana-theme-env"
        builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
        script = builder.split('"$ROOTFS/usr/bin/ooonana-theme-env" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
        helper.write_text(script)
        helper.chmod(0o700)
        env = {**os.environ, "XDG_CONFIG_HOME": temporary + "/config"}
        subprocess.run([str(helper), "apply"], env=env, check=True, capture_output=True)
        raise SystemExit(subprocess.run([sys.executable, __file__, str(output), "--worker"], env=env).returncode)

sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme, header
from gi.repository import GdkX11
from window_controls import Manager
from dock_app import windows
import i3_events


def settle(seconds=.1):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.01)


def wait(predicate, message):
    deadline = time.monotonic() + 8
    while not predicate():
        assert time.monotonic() < deadline, message
        settle(.03)


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        children = []
        widget.forall(children.append)
        for child in children:
            yield from descendants(child)


apply_theme()
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
with tempfile.TemporaryDirectory(prefix="ooonana-csd-wm-") as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                               if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    foreign = native = manager = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0, "Private WM unavailable")
        socket = i3_events.socket_path()
        foreign = Gtk.Window(title="Foreign GTK controls")
        foreign.set_wmclass("foreign-csd", "ForeignCsdTest")
        foreign.set_default_size(240, 160)
        foreign.set_titlebar(Gtk.HeaderBar(title="GTK", show_close_button=True))
        foreign.add(Gtk.Label(label="Client-owned GTK header"))
        foreign.show_all()
        native = Gtk.Window(title="Native controls")
        native.set_default_size(240, 160)
        header(native, "Native")
        native.add(Gtk.Label(label="Ooonana native header"))
        native.show_all()
        fxid = GdkX11.X11Window.get_xid(foreign.get_window())
        nxid = GdkX11.X11Window.get_xid(native.get_window())
        def state():
            return {node["window"]: node for node, _ in windows.leaves(i3_events.request(socket, 4)) if node.get("window")}
        wait(lambda: fxid in state() and nxid in state(), "Header windows missing")
        display = Gdk.get_default_root_window()
        scale = foreign.get_scale_factor()
        subprocess.run(["i3-msg", f"[id={fxid}] floating enable, move position 12 58; "
                        f"[id={nxid}] move position {display.get_width() * scale // 2 + 12} 58"], check=True, capture_output=True)
        manager = Manager()
        manager.refresh()
        settle(.25)
        candidates = [widget for widget in descendants(foreign.get_titlebar()) if isinstance(widget, Gtk.Button)]
        print("CSD_BUTTON_CLASSES", [widget.get_style_context().list_classes() for widget in candidates], flush=True)
        buttons = {role: next(widget for widget in candidates if widget.get_style_context().has_class(role))
                   for role in ("close", "minimize", "maximize")}
        reference = next(widget for widget in descendants(native.get_titlebar()) if widget.get_name() == "ooonana-window-close")
        sizes = {role: (widget.get_allocated_width(), widget.get_allocated_height()) for role, widget in buttons.items()}
        left = buttons["close"].translate_coordinates(foreign, 0, 0)[0]
        native_left = reference.translate_coordinates(native, 0, 0)[0]
        record = {"gdk_scale": scale, "wm_scale": manager.control_scale, "sizes": sizes,
                  "left": left, "native_left": native_left,
                  "gtk_layout": Gtk.Settings.get_default().get_property("gtk-decoration-layout")}
        print("CSD_CONTROL_METRICS", json.dumps(record), flush=True)
        assert all(size == (24, 24) for size in sizes.values()), "GTK CSD controls exceed native diameter"
        assert left == native_left, "GTK CSD left placement differs"
        assert all(state()[xid]["deco_rect"]["height"] == 0 for xid in (fxid, nxid)), "Duplicated CSD titlebar"
        assert all(state()[xid]["id"] not in manager.controls for xid in (fxid, nxid)), "Overlay covers CSD"
        def painted():
            image = Gdk.pixbuf_get_from_window(display, 0, 0, display.get_width(), display.get_height())
            if image is None:
                return False
            raw = dict(line.split("=", 1) for line in subprocess.check_output(
                ["xdotool", "getwindowgeometry", "--shell", str(fxid)], text=True).splitlines())
            pixels, stride, channels = image.get_pixels(), image.get_rowstride(), image.get_n_channels()
            for role, expected in (("close", (255, 115, 107)), ("minimize", (255, 209, 108)), ("maximize", (127, 214, 160))):
                button = buttons[role]
                point = button.translate_coordinates(foreign, 0, 0)
                if point is None or not button.get_mapped():
                    return False
                x = int(raw["X"]) + (point[0] + button.get_allocated_width() // 5) * scale
                y = int(raw["Y"]) + (point[1] + button.get_allocated_height() // 2) * scale
                offset = y * stride + x * channels
                if tuple(pixels[offset:offset + 3]) != expected:
                    return False
            return True
        wait(painted, "CSD controls mapped but did not visibly paint")
        def glyph_ink(image, window, button, xid):
            point = button.translate_coordinates(window, 0, 0)
            raw = dict(line.split("=", 1) for line in subprocess.check_output(
                ["xdotool", "getwindowgeometry", "--shell", str(xid)], text=True).splitlines())
            left = int(raw["X"]) + (point[0] + (button.get_allocated_width() - 12) // 2) * scale
            top = int(raw["Y"]) + (point[1] + (button.get_allocated_height() - 12) // 2) * scale
            pixels, stride, channels = image.get_pixels(), image.get_rowstride(), image.get_n_channels()
            # Compare contrast silhouettes, not an arbitrary dark-pixel cutoff:
            # GTK background icons and GtkImage use slightly different AA.
            return [max(0., min(1., (214 - pixels[(top + y) * stride + (left + x) * channels + 1]) / 195))
                    for y in range(12 * scale) for x in range(12 * scale)]
        native_fullscreen = next(widget for widget in descendants(native.get_titlebar())
                                 if widget.get_name() == "ooonana-window-fullscreen")
        glyph_frame = {}
        def soften_antialiasing(ink):
            # A one-physical-pixel filter compares silhouette geometry rather
            # than GtkImage/backdrop/background-image edge rasterization.
            # It does not permit a logical-pixel placement or diameter change.
            side = 12 * scale
            result = []
            for y in range(side):
                for x in range(side):
                    samples = [ink[yy * side + xx] for yy in range(max(0, y - 1), min(side, y + 2))
                               for xx in range(max(0, x - 1), min(side, x + 2))]
                    result.append(sum(samples) / len(samples))
            return result

        def glyph_ready():
            image = Gdk.pixbuf_get_from_window(display, 0, 0, display.get_width(), display.get_height())
            expected = glyph_ink(image, native, native_fullscreen, nxid)
            actual = glyph_ink(image, foreign, buttons["maximize"], fxid)
            expected_shape, actual_shape = map(soften_antialiasing, (expected, actual))
            norm = math.sqrt(sum(value * value for value in expected_shape) * sum(value * value for value in actual_shape))
            agreement = sum(a * b for a, b in zip(expected_shape, actual_shape)) / max(1e-9, norm)
            glyph_frame.update(image=image, agreement=agreement, expected=expected, actual=actual)
            area_ratio = sum(actual) / max(1e-9, sum(expected))
            return sum(expected) > 0 and agreement >= .95 and .7 <= area_ratio <= 1.3
        try:
            wait(glyph_ready, "CSD fullscreen glyph differs from native icon")
        finally:
            if glyph_frame:
                glyph_frame["image"].savev(str(output / "headers.png"), "png", [], [])
                print("CSD_FULLSCREEN_GLYPH_AGREEMENT", glyph_frame["agreement"],
                      "weighted-ink", sum(glyph_frame["expected"]), sum(glyph_frame["actual"]), flush=True)
        # Negative control: AA tolerance must not accept the old square glyph.
        wrong_icon = Gtk.CssProvider()
        wrong_icon.load_from_data(b'button.maximize { background-image: -gtk-icontheme("window-maximize-symbolic"); }')
        glyph_style = buttons["maximize"].get_style_context()
        glyph_style.add_provider(wrong_icon, Gtk.STYLE_PROVIDER_PRIORITY_USER + 10)
        settle(.25)
        assert not glyph_ready(), "Glyph comparison accepts old square maximize icon"
        print("CSD_WRONG_GLYPH_REJECTED", glyph_frame["agreement"], flush=True)
        glyph_style.remove_provider(wrong_icon)
        wait(glyph_ready, "Correct CSD glyph did not restore")
        if os.environ.get("OOONANA_WINDOW_CONTROLS") == "left":
            assert manager.control_scale == scale
            def click(role):
                # GTK rebuilds internal decoration buttons after fullscreen.
                widget = next(item for item in descendants(foreign.get_titlebar())
                              if isinstance(item, Gtk.Button) and item.get_style_context().has_class(role))
                wait(lambda: widget.get_mapped(), "CSD button did not remap")
                point = widget.translate_coordinates(foreign, 0, 0)
                raw = dict(line.split("=", 1) for line in subprocess.check_output(
                    ["xdotool", "getwindowgeometry", "--shell", str(fxid)], text=True).splitlines())
                x = int(raw["X"]) + (point[0] + widget.get_allocated_width() // 2) * scale
                y = int(raw["Y"]) + (point[1] + widget.get_allocated_height() // 2) * scale
                subprocess.run(["xdotool", "mousemove", "--sync", str(x), str(y), "click", "1"], check=True)
            def entry():
                return next(item for item in windows.windows(i3_events.request(socket, 4)) if item[0] == state()[fxid]["id"])
            click("minimize")
            wait(lambda: entry()[3], "CSD Minimize request ignored")
            windows.focus(entry())
            wait(lambda: not entry()[3], "CSD minimized session did not restore")
            settle(.2)
            click("maximize")
            wait(lambda: state()[fxid].get("fullscreen_mode"), "CSD Fullscreen request ignored/double-toggled")
            subprocess.run(["xdotool", "key", "--clearmodifiers", "alt+F10"], check=True)
            wait(lambda: not state()[fxid].get("fullscreen_mode"), "CSD Fullscreen keyboard restore failed")
            settle(.2)
            click("close")
            wait(lambda: fxid not in state(), "CSD Close click failed")
            assert nxid in state(), "CSD action touched another window"
        print("CSD_CONTROLS_UI_OK generated GTK settings/style, native diameter/left inset, no duplicate frame; opt-in real actions", flush=True)
    finally:
        if manager is not None:
            manager.clear()
        for window in (foreign, native):
            if window is not None:
                window.destroy()
        wm.terminate()
        wm.wait(timeout=5)
