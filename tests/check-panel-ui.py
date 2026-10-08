#!/usr/bin/env python3
"""Render real source Polybar config with sample status, no radio/audio actions.

Run on an isolated Xvfb display. --rootfs supplies the bundled musl Polybar.
"""
import argparse
import configparser
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import os
import signal
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--rootfs", type=Path, required=True)
parser.add_argument("--long-wifi", action="store_true")
parser.add_argument("--desktop", action="store_true", help="Include source native Settings/dock and original wallpaper")
parser.add_argument("--desktop-overview", action="store_true", help="Wallpaper/panel/dock without Settings window")
args = parser.parse_args()
loader = SourceFileLoader("panel_windows", str(ROOT / "packages/ooonana/usr/bin/ooonana-window-list"))
windows = module_from_spec(spec_from_loader(loader.name, loader))
loader.exec_module(windows)
screen = Gdk.get_default_root_window()
assert os.environ.get('OOONANA_GUI_TEST_DISPLAY') == '1', 'Isolated owned display required'
assert subprocess.run(['i3-msg', '-t', 'get_tree'], capture_output=True).returncode != 0, 'Existing window manager: refuse'
width = screen.get_width()
left, right, gap, limit = windows.panel_layout(width)
rootfs = args.rootfs.resolve()

with tempfile.TemporaryDirectory(prefix="ooonana-panel-ui-") as temporary:
    fixture = Path(temporary)
    wm_config = fixture / "i3.conf"
    wm_config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                                   if not line.startswith("exec")) + "\n")
    builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
    text = builder.split('"$ROOTFS/etc/ooonana/polybar.ini" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
    configuration = configparser.RawConfigParser(strict=False)
    configuration.read_string(text)
    samples = {
        "media": "%{T2}%{T-} " + "Sample track title for layout"[:limit],
        "memory": "RAM 42%", "wifi": " Connected",
        "audio": "%{T2}%{T-} 70%", "battery": "%{T2}%{T-} 85%",
        "notifications": "%{T2}%{T-} 3",
    }
    if args.long_wifi:
        samples["wifi"] = " VeryLongNetworkNameThatMustNeverPushAIAway"
    for section in configuration.sections():
        for key in list(configuration[section]):
            if key.startswith(("click-", "scroll-")):
                configuration.remove_option(section, key)
        if configuration[section].get("type") == "custom/script":
            sample = samples.get(section.removeprefix("module/"), "")
            configuration[section]["exec"] = "printf '%s\\\\n' " + shlex.quote(sample)
            configuration[section]["tail"] = "false"
            configuration[section]["interval"] = "60"
    polybar_config = fixture / "polybar.ini"
    with polybar_config.open("w") as stream:
        configuration.write(stream)
    fonts = fixture / "fonts.conf"
    fonts.write_text(f'<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig>'
                     f'<dir>{rootfs}/usr/share/fonts</dir><dir>/usr/share/fonts</dir>'
                     f'<cachedir>{fixture}/font-cache</cachedir></fontconfig>')
    environment = {**os.environ, "FONTCONFIG_FILE": str(fonts), "OOONANA_PANEL_LEFT": left,
                   "OOONANA_PANEL_RIGHT": right, "OOONANA_PANEL_GAP": str(gap)}
    wm = subprocess.Popen(["i3", "-c", str(wm_config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    panel = dock = settings = wallpaper = None
    try:
        deadline = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < deadline, "Isolated i3 unavailable"
            time.sleep(0.05)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.desktop or args.desktop_overview:
            from common import apply_theme
            from settings_app import SettingsWindow
            from dock_app import Dock
            import i3_events
            Gtk.IconTheme.get_default().append_search_path(str(ROOT / 'packages/ooonana/usr/share/icons/hicolor/scalable/apps'))
            apply_theme()
            if not args.desktop_overview:
                settings = SettingsWindow()
                settings.show_all()
                settings.sidebar.select_row(settings.sidebar.get_row_at_index(3))
            dock = Dock(subscribe=False)
            dock.snapshot = i3_events.request(i3_events.socket_path(), 4)
            dock.refresh()
            wallpaper = subprocess.Popen(['python3', str(ROOT / 'packages/ooonana/usr/bin/ooonana-wallpaper-fit'),
                                          str(ROOT / 'packages/ooonana/usr/share/ooonana/wallpapers/ooonana-notes.jpg')],
                                         start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        with args.output.with_suffix(".log").open("w") as log:
            panel = subprocess.Popen([str(rootfs / "lib/ld-musl-x86_64.so.1"), "--library-path",
                                      f"{rootfs}/lib:{rootfs}/usr/lib:{rootfs}/usr/lib/pulseaudio",
                                      str(rootfs / "usr/bin/polybar"), "-l", "info", "-c", str(polybar_config), "ooonana"],
                                     env=environment, stdout=log, stderr=subprocess.STDOUT)
            for _ in range(160):
                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)
                assert panel.poll() is None, args.output.with_suffix(".log").read_text()
                time.sleep(0.025)
            assert "polybar|error:" not in args.output.with_suffix(".log").read_text(), "Panel config errors"
            pixels = Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height())
            assert pixels is not None
            pixels.savev(str(args.output), "png", [], [])
        print(f"PANEL_UI_OK {width}px sample state: {args.output}")
    finally:
        if dock:
            dock.destroy()
        if settings:
            settings.disconnect_by_func(Gtk.main_quit)
            settings.destroy()
        wallpaper_error = None
        if wallpaper:
            try:
                _out, err = wallpaper.communicate(timeout=5)
                if wallpaper.returncode:
                    wallpaper_error = err
            except subprocess.TimeoutExpired:
                os.killpg(wallpaper.pid, signal.SIGKILL)
                wallpaper.wait(timeout=5)
                wallpaper_error = b'Wallpaper fixture timeout'
        for process in (panel, wm):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Only fixture child, never unrelated user bars/WM.
                    process.kill()
                    process.wait(timeout=5)
        assert wallpaper_error is None, wallpaper_error
