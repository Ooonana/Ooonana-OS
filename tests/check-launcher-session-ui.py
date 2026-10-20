#!/usr/bin/env python3
"""Real .desktop discovery/Return/app handoff on an owned i3 session only."""
import json
import configparser
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme
from gi.repository import GdkX11, GLib
from launcher_app import LauncherWindow
from window_controls import Manager

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
findings = []


def settle(seconds=0.12):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


def wait(predicate, detail):
    end = time.monotonic() + 12
    while not predicate():
        assert time.monotonic() < end, detail
        settle(0.04)
    settle()


def request(kind):
    return json.loads(subprocess.check_output(["i3-msg", "-t", kind], text=True))


def clients():
    result = []
    def visit(node):
        if node.get("window"):
            result.append(node)
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            visit(child)
    visit(request("get_tree"))
    return result


def command(text):
    response = json.loads(subprocess.check_output(["i3-msg", text], text=True))
    assert all(item.get("success") for item in response), (text, response)


def check(condition, detail):
    if not condition:
        findings.append(detail)
        print("LAUNCHER_SESSION_FINDING", detail, flush=True)


def capture(name):
    settle()
    root = Gdk.get_default_root_window()
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
        str(output / (name + ".png")), "png", [], [])


apply_theme()
Gtk.Settings.get_default().set_property("gtk-xft-dpi", round(96 * 1024 * float(os.environ.get("OOONANA_GUI_TEXT_SCALE", "1.0"))))
print("LAUNCHER_TEST_XFT_DPI", Gtk.Settings.get_default().get_property("gtk-xft-dpi"), flush=True)
subprocess.run(["ooonana-theme-env", "apply"], check=True, capture_output=True, timeout=20)
schemes = Path.home() / ".config/geany/colorschemes"
schemes.mkdir(parents=True)
for scheme in (ROOT / "packages/ooonana/usr/share/geany/colorschemes").glob("*.conf"):
    shutil.copyfile(scheme, schemes / scheme.name)
with tempfile.TemporaryDirectory(prefix="ooonana-launcher-session-") as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                               if not line.startswith("exec")) + "\n")
    entries = Path(GLib.get_user_data_dir()) / "applications"
    entries.mkdir(parents=True, exist_ok=True)
    entry = entries / ("ooonana-qa-launch-%s.desktop" % os.getpid())
    assert not entry.exists()
    title = "OoonanaQA-Launch-%s" % os.getpid()
    entry.write_text("[Desktop Entry]\nType=Application\nName=Ooonana QA Session Launch\n"
                     "Exec=xterm -title %s -e sleep 90\nIcon=utilities-terminal\nTerminal=false\n" % title)
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    launcher = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0,
             "Owned i3 unavailable")
        manager = Manager()
        manager.refresh()
        for desktop_id, query, expected_title, process_marker, name in (
                (entry.name, "Ooonana QA Session Launch", title, "xterm", "terminal"),
                ("ooonana-settings.desktop", "Ooonana Settings", "Ooonana Settings", "settings_app.py", "settings"),
                ("xterm.desktop", "XTerm", None, "xterm", "preferred-terminal"),
                ("geany.desktop", "Geany", None, "geany", "preferred-editor"),
                ("nemo.desktop", "Files", None, "nemo", "preferred-files")):
            launcher = LauncherWindow()
            # The parent test owns the loop; closing launcher must not quit it.
            launcher.disconnect_by_func(Gtk.main_quit)
            launcher.show_all()
            wait(lambda: launcher.get_realized(), "Launcher not realized")
            xid = GdkX11.X11Window.get_xid(launcher.get_window())
            wait(lambda: any(node["window"] == xid for node in clients()), "Launcher not managed")
            launcher.search.set_text(query)
            assert all(launcher.filter_row(row) for row in launcher.visible_rows()), "Search must filter before idle/Return"
            wait(lambda: any(row.app.get_id() == desktop_id for row in launcher.visible_rows()),
                 "Real desktop entry not discovered: " + desktop_id)
            row = next(row for row in launcher.visible_rows() if row.app.get_id() == desktop_id)
            launcher.results.select_row(row)
            if name == "preferred-files":
                assert launcher.visible_rows()[0].app.get_id() == desktop_id, "Exact Files name must outrank description matches"
            command("[id=%d] focus" % xid)
            launcher.search.grab_focus()
            settle()
            monitor = next(item["rect"] for item in request("get_outputs") if item.get("active"))
            node = next(item for item in clients() if item["window"] == xid)
            rect = node["rect"]
            print("LAUNCHER_SESSION_BOUNDS", name, rect, monitor, flush=True)
            check(rect["x"] >= monitor["x"] and rect["y"] >= monitor["y"]
                  and rect["x"] + rect["width"] <= monitor["x"] + monitor["width"]
                  and rect["y"] + rect["height"] <= monitor["y"] + monitor["height"],
                  "Managed Spotlight exceeds output bounds: " + name)
            capture(name + "-launcher")
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], check=True)
            wait(lambda: not launcher.get_visible(), "Return did not dismiss launcher after launch")
            def target_client():
                return next((item for item in clients() if item["window"] != xid and (
                    item.get("name") == expected_title if expected_title else
                    str((item.get("window_properties") or {}).get("class", "")).casefold() == process_marker)), None)
            try:
                wait(target_client, "Real app did not open: " + desktop_id)
            except AssertionError:
                capture(name + "-failed")
                print("LAUNCHER_CLIENT_DIAGNOSTICS", json.dumps(clients()), flush=True)
                print("LAUNCHER_PROCESS_DIAGNOSTICS", subprocess.check_output(["ps", "-ef"], text=True), flush=True)
                raise
            app = target_client()
            pid = int(subprocess.check_output(["xdotool", "getwindowpid", str(app["window"])], text=True))
            process = Path("/proc") / str(pid)
            assert process.stat().st_uid == os.getuid(), "Unexpected launched process owner"
            args = (process / "cmdline").read_bytes().split(b"\0")
            assert any(process_marker.encode() in arg for arg in args), args
            if name == "preferred-editor":
                preferences = configparser.ConfigParser()
                preferences.read(Path.home() / ".config/geany/geany.conf")
                assert preferences["geany"]["color_scheme"] == "ooonana-%s.conf" % os.environ["OOONANA_THEME"]
                assert preferences["geany"]["editor_font"] == "Monospace 11"
            if name == "preferred-files":
                assert str(Path.home()).encode() in args, "Files wrapper did not target Home"
            wait(lambda: any(item.get("focused") and item["window"] == app["window"] for item in clients()),
                 "Launched app did not receive focus")
            capture(name + "-app")
            app = target_client()
            rect = app["rect"]
            check(rect["x"] >= monitor["x"] and rect["y"] >= monitor["y"]
                  and rect["x"] + rect["width"] <= monitor["x"] + monitor["width"]
                  and rect["y"] + rect["height"] <= monitor["y"] + monitor["height"],
                  "Launched app exceeds output bounds: " + name + " " + str(rect))
            if name in ("preferred-editor", "preferred-files"):
                check(rect["x"] >= monitor["x"] + 12 and rect["y"] >= monitor["y"] + 58
                      and rect["x"] + rect["width"] <= monitor["x"] + monitor["width"] - 12
                      and rect["y"] + rect["height"] <= monitor["y"] + monitor["height"] - 84,
                      "New app overlaps panel/dock clearance: " + name + " " + str(rect))
                command("[con_id=%d] resize set 400 px 300 px; [con_id=%d] move absolute position 32 px 70 px" % (app["id"], app["id"]))
                settle(0.3)
                user_rect = dict(target_client()["rect"])
                manager.refresh()
                settle(0.3)
                assert target_client()["rect"] == user_rect, "Initial-fit guard must not reset later user geometry"
            command("[con_id=%d] kill" % app["id"])
            wait(lambda: not any(item["window"] == app["window"] for item in clients()), "Owned app did not close")
            print("LAUNCHER_REAL_HANDOFF_OK", desktop_id, process_marker, flush=True)
            launcher = None
        print("LAUNCHER_SESSION_RESULTS", json.dumps(findings), flush=True)
        assert not findings, "; ".join(findings)
        print("LAUNCHER_SESSION_UI_OK real discovery, X11 Return, native/third-party launch/focus, preferred terminal/editor/files and default app bounds", flush=True)
    finally:
        if launcher is not None:
            launcher.destroy()
        entry.unlink(missing_ok=True)
        wm.terminate()
        wm.wait(timeout=4)
