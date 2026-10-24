#!/usr/bin/env python3
"""Held-open Chromium/Qt palette changes in private native X11 session only."""
from collections import Counter
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
from gi.repository import Gio, GLib

output = Path(sys.argv[1]); output.mkdir(parents=True, exist_ok=True)
root = Gdk.get_default_root_window()


def settle(seconds=.15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(.01)


def wait(predicate, detail, seconds=15):
    end = time.monotonic() + seconds
    while True:
        value = predicate()
        if value: return value
        assert time.monotonic() < end, detail
        settle(.05)


def clients():
    result = {}
    def visit(node, workspace=""):
        if node.get("type") == "workspace": workspace = node["name"]
        if node.get("window"): result[node["window"]] = node, workspace
        for child in node.get("nodes", []) + node.get("floating_nodes", []): visit(child, workspace)
    visit(json.loads(subprocess.check_output(["i3-msg", "-t", "get_tree"], text=True)))
    return result


def client(klass):
    return next((node for node, _ in clients().values()
                 if node.get("window_properties", {}).get("class", "").lower() == klass), None)


def command(value):
    assert all(item.get("success") for item in json.loads(subprocess.check_output(["i3-msg", value], text=True)))


def state():
    return {xid: (node["id"], node["rect"], node.get("focused"), node.get("fullscreen_mode"), workspace)
            for xid, (node, workspace) in clients().items()}


def color(klass):
    node = client(klass); rect, content = node["rect"], node["window_rect"]
    y = 7 if klass == "qterminal" else 65
    image = Gdk.pixbuf_get_from_window(root, rect["x"] + content["x"] + 130,
        rect["y"] + content["y"] + y, min(180, content["width"] - 140), 3)
    pixels, channels = image.get_pixels(), image.get_n_channels()
    return list(Counter(tuple(pixels[pos:pos + 3]) for pos in range(0, len(pixels) - channels + 1, channels)).most_common(1)[0][0])


def capture(name):
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(output / (name + ".png")), "png", [], [])


with tempfile.TemporaryDirectory(prefix="ooonana-client-theme-") as temporary:
    base = Path(temporary)
    env = dict(os.environ, XDG_CONFIG_HOME=str(base / "config"), XDG_CACHE_HOME=str(base / "cache"),
               OOONANA_THEME="dark", OOONANA_THEME_INHERITED="dark")
    for name in ("GTK_THEME", "OOONANA_THEME_OVERRIDE", "QT_QPA_PLATFORMTHEME"): env.pop(name, None)
    preference = base / "config/ooonana/theme"
    preference.parent.mkdir(parents=True); preference.write_text("dark\n")
    config = base / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines() if not line.startswith("exec")) + "\n")
    processes, logs = [], []
    def launch(argv, name):
        log = (output / (name + ".log")).open("w"); logs.append(log)
        child = subprocess.Popen(argv, env=env, stdout=log, stderr=log); processes.append(child)
        return child
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    events = []
    subscription = bus.signal_subscribe("org.freedesktop.portal.Desktop", "org.freedesktop.portal.Settings", "SettingChanged",
        "/org/freedesktop/portal/desktop", None, Gio.DBusSignalFlags.NONE,
        lambda _b, _s, _p, _i, _m, args: events.append(args.unpack()))
    try:
        wm = launch(["i3", "-c", str(config)], "i3")
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0, "Private WM missing")
        def apply():
            result = subprocess.run(["ooonana-theme-env", "apply"], env=env, capture_output=True, text=True, timeout=25)
            assert result.returncode == 0, (result.stdout, result.stderr)
        apply()
        launch([sys.executable, "/usr/lib/ooonana/xsettings_session.py"], "xsettings")
        subprocess.run(["dbus-update-activation-environment", "DISPLAY", "XAUTHORITY", "XDG_CURRENT_DESKTOP", "XDG_RUNTIME_DIR"], check=True)
        def scheme():
            return bus.call_sync("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop", "org.freedesktop.portal.Settings", "Read",
                GLib.Variant("(ss)", ("org.freedesktop.appearance", "color-scheme")), None, Gio.DBusCallFlags.NONE, 10000, None).unpack()[0]
        assert scheme() == 1, scheme()
        for assignment in subprocess.check_output(["ooonana-theme-env", "client-env"], env=env, text=True).splitlines():
            if assignment.startswith("export QT_QPA_PLATFORMTHEME="):
                env["QT_QPA_PLATFORMTHEME"] = shlex.split(assignment.split("=", 1)[1])[0]
        assert env.get("QT_QPA_PLATFORMTHEME") == "xdgdesktopportal"
        qt = launch(["qterminal", "--workdir", str(base), "--execute", "/bin/sh"], "qterminal")
        browser = launch(["chromium", "--user-data-dir=" + str(base / "browser"), "--no-first-run", "--no-default-browser-check",
                          "--disable-background-networking", "--disable-component-update", "--disable-gpu", "--disable-gpu-shader-disk-cache",
                          "--password-store=basic", "about:blank"], "chromium")
        for klass, x in (("qterminal", 20), ("chromium", 650)):
            node = wait(lambda: client(klass), klass + " not mapped")
            command(f'[con_id={node["id"]}] floating enable, resize set 580 px 420 px, move absolute position {x} px 80 px')
        command(f'[con_id={client("chromium")["id"]}] focus')
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+l"], check=True)
        draft = "Ooonana live theme draft"
        subprocess.run(["xdotool", "type", "--clearmodifiers", draft], check=True)
        settle(.5)
        profile = base / "config/qterminal.org/qterminal.ini"
        before_profile = profile.read_bytes()
        initial = {klass: color(klass) for klass in ("qterminal", "chromium")}
        capture("initial-dark")
        observations = []
        for selected, expected in (("light", 2), ("dark", 1)):
            before = state()
            preference.write_text(selected + "\n"); apply()
            wait(lambda: any(e[:2] == ("org.freedesktop.appearance", "color-scheme") and e[2] == expected for e in events), "Portal change signal missing")
            assert scheme() == expected
            settle(.7)
            colors = {klass: color(klass) for klass in initial}
            print("CLIENT_THEME_COLORS", selected, colors, flush=True)
            capture(selected)
            assert state() == before, "Theme altered client identity/focus/geometry/workspace/fullscreen"
            assert qt.poll() is None and browser.poll() is None
            for klass, rgb in colors.items():
                assert (sum(rgb) / 3 > 150) == (selected == "light"), (klass, selected, rgb, initial)
            assert profile.read_bytes() == before_profile, "Existing terminal profile overwritten"
            observations.append({"theme": selected, "colors": colors})
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+a", "ctrl+c"], check=True)
        copied = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()
        assert copied == draft, ("Browser draft lost", copied)
        (output / "receipt.json").write_text(json.dumps({"initial": initial, "observations": observations, "draft_preserved": True}, indent=2) + "\n")
        print("CLIENT_THEME_UI_OK held Chromium/Qt live portal/palette; same windows/state; browser draft and terminal profile retained", flush=True)
    finally:
        bus.signal_unsubscribe(subscription)
        for child in reversed(processes):
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=3)
        for log in logs: log.close()
