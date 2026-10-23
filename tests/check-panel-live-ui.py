#!/usr/bin/env python3
"""Real Polybar supervisor palette handoff, same native dock/client, private X11."""
import configparser
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk
from gi.repository import GdkX11

output = Path(sys.argv[1]); output.mkdir(parents=True, exist_ok=True)
screen = Gdk.get_default_root_window()


def wait(predicate, message):
    until = time.monotonic() + 10
    while True:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        if predicate(): return
        assert time.monotonic() < until, message
        time.sleep(.04)


def windows(kind):
    result = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", kind], capture_output=True, text=True)
    return tuple(result.stdout.split()) if result.returncode == 0 else ()


def pid(xid):
    return subprocess.check_output(["xdotool", "getwindowpid", xid], text=True).strip()


def panel_pid():
    items = windows("polybar")
    try:
        return pid(items[0]) if len(items) == 1 else None
    except subprocess.CalledProcessError:
        return None  # Bar may be between owned stop/start during refresh.


def color():
    return Gdk.pixbuf_get_from_window(screen, screen.get_width() // 2, 12, 1, 1).get_pixels()[:3]


with tempfile.TemporaryDirectory(prefix="ooonana-panel-live-") as temporary:
    base = Path(temporary)
    preference = base / "config/ooonana/theme"; preference.parent.mkdir(parents=True)
    os.environ.update(XDG_CONFIG_HOME=str(base / "config"), OOONANA_THEME="dark", OOONANA_THEME_INHERITED="dark")
    os.environ.pop("OOONANA_THEME_OVERRIDE", None)
    preference.write_text("dark\n")
    wm_config = base / "i3.conf"
    wm_config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines() if not line.startswith("exec")) + "\n")
    source = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
    config = configparser.RawConfigParser(strict=False)
    config.read_string(source.split('"$ROOTFS/etc/ooonana/polybar.ini" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0])
    samples = {"media": "%{T2}%{T-} 한글歌曲", "memory": "RAM 100%", "wifi": " 매우긴무선이름",
               "battery": "%{T2}%{T-} 100%", "audio": "%{T2}%{T-} 100%", "notifications": "%{T2}%{T-} 999+"}
    for section in config.sections():
        for key in list(config[section]):
            if key.startswith(("click-", "scroll-")): config.remove_option(section, key)
        if config[section].get("type") == "custom/script":
            config[section]["exec"] = "printf '%s\\\\n' " + shlex.quote(samples.get(section.removeprefix("module/"), ""))
            config[section]["tail"] = "false"; config[section]["interval"] = "60"
    panel_config = base / "polybar.ini"
    with panel_config.open("w") as stream: config.write(stream)
    runner = """
import sys
sys.path.insert(0, sys.argv[1])
import panel_session as panel
panel.PANEL_COMMAND = ['polybar', '-l', 'info', '-c', sys.argv[2], 'ooonana']
sys.argv = ['ooonana-panel-start']
raise SystemExit(panel.main())
"""
    wm = subprocess.Popen(["i3", "-c", str(wm_config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    supervisor = held = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0, "Private WM unavailable")
        held = Gtk.Window(title="Held client — isolated panel QA")
        held.add(Gtk.Label(label="Theme switch must retain this window and dock."))
        held.set_default_size(380, 160); held.show_all()
        wait(lambda: held.get_window() is not None, "Held client not mapped")
        xid = GdkX11.X11Window.get_xid(held.get_window())
        def client_state():
            snapshot = json.loads(subprocess.check_output(["i3-msg", "-t", "get_tree"], text=True))
            def find(node):
                if node.get("window") == xid:
                    return (node["id"], node["rect"], node.get("focused"), node.get("fullscreen_mode"))
                return next((found for child in node.get("nodes", []) + node.get("floating_nodes", []) if (found := find(child))), None)
            return find(snapshot)
        with (output / "panel.log").open("w") as log:
            supervisor = subprocess.Popen([sys.executable, "-B", "-c", runner,
                str(ROOT / "packages/ooonana/usr/lib/ooonana"), str(panel_config)], stdout=log, stderr=log)
            wait(lambda: len(windows("OoonanaDock")) == 1 and len(windows("polybar")) == 1 and color() == bytes.fromhex("1b1f26"), "Initial native dock/panel missing")
            dock = windows("OoonanaDock"); dock_pid = pid(dock[0]); initial = client_state()
            receipts = []
            for theme, expected in (("dark", "1b1f26"), ("light", "ffffff"), ("dark", "1b1f26")):
                previous = panel_pid()
                if theme != "dark" or receipts:
                    replacement = preference.with_suffix(".next"); replacement.write_text(theme + "\n"); replacement.replace(preference)
                    # X server may reuse same resource ID after old connection
                    # closes; owned new process PID, not XID churn, proves relaunch.
                    wait(lambda: supervisor.poll() is None and panel_pid() not in (None, previous) and color() == bytes.fromhex(expected), "Real panel failed live palette refresh")
                assert supervisor.poll() is None and windows("OoonanaDock") == dock and pid(dock[0]) == dock_pid
                assert client_state() == initial, "Panel refresh changed client geometry/focus/state"
                Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height()).savev(str(output / f'{len(receipts)}-{theme}.png'), "png", [], [])
                receipts.append({"theme": theme, "panel": windows("polybar"), "panel_pid": panel_pid(), "dock": dock, "dock_pid": dock_pid, "client": initial})
            (output / "receipt.json").write_text(json.dumps(receipts, indent=2) + "\n")
            assert "polybar|error:" not in (output / "panel.log").read_text()
        print("PANEL_LIVE_UI_OK real Polybar dark/Paper/dark; same supervisor/native dock/client; atomic preferences", flush=True)
    finally:
        if held is not None: held.destroy()
        for process in (supervisor, wm):
            if process is not None and process.poll() is None:
                process.terminate()
                try: process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
