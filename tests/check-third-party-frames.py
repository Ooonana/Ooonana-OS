#!/usr/bin/env python3
"""Real client/frame capture on explicitly isolated Xvfb/Xephyr; private profiles."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk
from window_controls import Manager, WIDTH
import i3_events

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("app", choices=("geany", "nemo", "chromium"))
parser.add_argument("output", type=Path)
parser.add_argument("--csd", action="store_true")
parser.add_argument("--compositor", action="store_true", help="Capture packaged rounding policy through private xrender compositor")
args = parser.parse_args()
if os.environ.get("OOONANA_GUI_TEST_DISPLAY") != "1":
    raise SystemExit("Explicit isolated display required")
if subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0:
    raise SystemExit("Refusing display with existing window manager")


def drain():
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)


def wait(predicate):
    deadline = time.monotonic() + 30
    while not predicate():
        drain()
        assert time.monotonic() < deadline, "Client/frame timeout"
        time.sleep(0.03)


def find_client():
    def visit(node):
        if node.get("window"):
            klass = str((node.get("window_properties") or {}).get("class", "")).lower()
            if klass.startswith(args.app):
                return node
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            found = visit(child)
            if found:
                return found
        return None
    return visit(i3_events.request(i3_events.socket_path(), 4))


args.output.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="ooonana-client-frame-") as temporary, args.output.with_suffix(".log").open("w") as log:
    fixture = Path(temporary)
    config = fixture / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                                if not line.startswith("exec")) + "\n")
    environment = {**os.environ, "GDK_BACKEND": "x11", "GTK_THEME": "Adwaita:dark",
                   "GTK_CSD": "1" if args.csd else "0", "XDG_CONFIG_HOME": str(fixture / "config"),
                   "XDG_CACHE_HOME": str(fixture / "cache"), "XDG_STATE_HOME": str(fixture / "state"),
                   "PATH": str(ROOT / "packages/ooonana/usr/bin") + ":" + os.environ["PATH"]}
    environment.pop("WAYLAND_DISPLAY", None)
    environment["NO_AT_BRIDGE"] = "1"
    os.environ["PATH"] = environment["PATH"]
    command = {
        "geany": ["geany", "--new-instance", "--config=" + str(fixture / "geany")],
        "nemo": ["nemo", "--no-desktop", str(fixture)],
        "chromium": ["chromium", "--user-data-dir=" + str(fixture / "chromium"), "--no-first-run",
                     "--disable-background-networking", "--disable-component-update", "--disable-gpu", "about:blank"],
    }[args.app]
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=log, stderr=log)
    client = None
    manager = None
    compositor = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0)
        if args.compositor:
            builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
            policy = builder.split('"$ROOTFS/etc/ooonana/picom.conf" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
            compositor_config = fixture / "picom.conf"
            compositor_config.write_text(policy)
            subprocess.run(["xsetroot", "-solid", "#555963"], check=True)
            compositor = subprocess.Popen(["picom", "--backend", "xrender", "--config", str(compositor_config)],
                                          stdout=log, stderr=log)
        client = subprocess.Popen(command, env=environment, stdout=log, stderr=log, start_new_session=True)
        wait(find_client)
        manager = Manager()
        manager.refresh()
        for _ in range(50):
            drain()
            time.sleep(0.03)
        node = find_client()
        assert node is not None and client.poll() is None
        assert compositor is None or compositor.poll() is None, "Private compositor failed; see capture log"
        properties = subprocess.run(["xprop", "-id", str(node["window"]), "_GTK_FRAME_EXTENTS", "_MOTIF_WM_HINTS"],
                                    capture_output=True, text=True).stdout
        root = Gdk.get_default_root_window()
        Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(args.output), "png", [], [])
        record = {"app": args.app, "csd": args.csd, "compositor": args.compositor, "deco": node["deco_rect"], "rect": node["rect"],
                  "properties": properties, "controls": {str(k): list(v.get_size()) for k, v in manager.controls.items()}}
        args.output.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record), flush=True)
        assert node["rect"]["y"] >= 0, "Client titlebar opened above display"
        assert node["rect"]["y"] + node["rect"]["height"] <= root.get_height(), "Client opened below display"
        assert all(control.get_size().height == node["deco_rect"]["height"]
                   for control in manager.controls.values()), "Controls overlap client contents"
        identifier = node["id"]
        if identifier in manager.controls:
            # Exercise current actions against real clients, not fake GTK windows.
            manager.controls[identifier].get_child().get_children()[1].clicked()
            wait(lambda: identifier not in manager.controls)
            subprocess.run(["ooonana-window-list", "--window-action", "show", str(identifier)],
                           env=environment, check=True, capture_output=True)
            wait(lambda: identifier in manager.controls)
            manager.controls[identifier].get_child().get_children()[2].clicked()
            wait(lambda: bool(find_client().get("fullscreen_mode")))
            wait(lambda: identifier not in manager.controls)
            subprocess.run(["ooonana-window-list", "--window-action", "fullscreen", str(identifier)],
                           env=environment, check=True, capture_output=True)
            wait(lambda: identifier in manager.controls)
            # Programmatic movement exercises real ConfigureNotify tracking.
            moved = subprocess.check_output(["i3-msg", f"[con_id={identifier}] move position 160 100"], text=True)
            assert all(result["success"] for result in json.loads(moved)), moved
            node = find_client()
            rect, deco = node["rect"], node["deco_rect"]
            expected = (rect["x"] + deco["x"] + deco["width"] - WIDTH,
                        rect["y"] + deco["y"], deco["height"])
            wait(lambda: manager.controls[identifier].last_position == expected)
            control = manager.controls[identifier]
            wait(lambda: tuple(control.get_position()) == control.last_position[:2])
            control.get_child().get_children()[0].clicked()
            wait(lambda: find_client() is None)
            print("REAL_CLIENT_ACTIONS_OK minimize/restore/fullscreen/restore/move/close", flush=True)
    finally:
        if manager:
            manager.clear()
        # Always release private compositor/WM, even if browser exit stalls.
        try:
            for process in (compositor, wm):
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
        finally:
            if client and client.poll() is None:
                os.killpg(client.pid, signal.SIGTERM)
                try:
                    client.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(client.pid, signal.SIGKILL)
                    client.wait(timeout=10)
