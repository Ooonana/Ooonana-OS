#!/usr/bin/env python3
"""Real .desktop discovery/Return/app handoff on an owned i3 session only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme
from gi.repository import GdkX11, GLib
from launcher_app import LauncherWindow

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
        for desktop_id, query, expected_title, process_marker, name in (
                (entry.name, "Ooonana QA Session Launch", title, "xterm", "terminal"),
                ("ooonana-settings.desktop", "Ooonana Settings", "Ooonana Settings", "settings_app.py", "settings")):
            launcher = LauncherWindow()
            # The parent test owns the loop; closing launcher must not quit it.
            launcher.disconnect_by_func(Gtk.main_quit)
            launcher.show_all()
            wait(lambda: launcher.get_realized(), "Launcher not realized")
            xid = GdkX11.X11Window.get_xid(launcher.get_window())
            wait(lambda: any(node["window"] == xid for node in clients()), "Launcher not managed")
            launcher.search.set_text(query)
            wait(lambda: len(launcher.visible_rows()) == 1, "Real desktop entry not discovered uniquely")
            row = launcher.visible_rows()[0]
            assert row.app.get_id() == desktop_id, (desktop_id, row.app.get_id())
            launcher.select_first()
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
            wait(lambda: any(item.get("name") == expected_title for item in clients()), "Real app did not open")
            app = next(item for item in clients() if item.get("name") == expected_title)
            pid = int(subprocess.check_output(["xdotool", "getwindowpid", str(app["window"])], text=True))
            process = Path("/proc") / str(pid)
            assert process.stat().st_uid == os.getuid(), "Unexpected launched process owner"
            args = (process / "cmdline").read_bytes().split(b"\0")
            assert any(process_marker.encode() in arg for arg in args), args
            wait(lambda: any(item.get("focused") and item["window"] == app["window"] for item in clients()),
                 "Launched app did not receive focus")
            capture(name + "-app")
            command("[con_id=%d] kill" % app["id"])
            wait(lambda: not any(item["window"] == app["window"] for item in clients()), "Owned app did not close")
            print("LAUNCHER_REAL_HANDOFF_OK", desktop_id, process_marker, flush=True)
            launcher = None
        print("LAUNCHER_SESSION_RESULTS", json.dumps(findings), flush=True)
        assert not findings, "; ".join(findings)
        print("LAUNCHER_SESSION_UI_OK real discovery, X11 Return, native/third-party launch and focus", flush=True)
    finally:
        if launcher is not None:
            launcher.destroy()
        entry.unlink(missing_ok=True)
        wm.terminate()
        wm.wait(timeout=4)
