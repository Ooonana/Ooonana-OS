#!/usr/bin/env python3
"""Isolated i3/Xvfb test; never touches user's desktop windows."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk
from window_controls import Manager, decoration_targets
import i3_events


def wait(predicate, timeout=8):
    until = time.monotonic() + timeout
    while not predicate():
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        assert time.monotonic() < until, "Controls fixture timeout"
        time.sleep(0.02)


with tempfile.TemporaryDirectory() as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (root / "branding/i3/config").read_text().splitlines()
                                if not line.startswith("exec")) + '\nfor_window [class="ThirdPartyTest"] floating enable, resize set 520 330, move position 80 80\n')
    env = {**os.environ, "PATH": str(root / "packages/ooonana/usr/bin") + ":" + os.environ["PATH"]}
    os.environ["PATH"] = env["PATH"]
    wm = subprocess.Popen(["i3", "-c", str(config)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    terminal = peer = None
    manager = None
    try:
        def ready():
            try:
                return bool(i3_events.socket_path())
            except (OSError, subprocess.SubprocessError):
                return False
        wait(ready)
        terminal = subprocess.Popen(["xterm", "-class", "ThirdPartyTest", "-title", "Controls fixture", "-bg", "#101317", "-fg", "#f5f5f7", "-e", "sh", "-c", "printf 'Third-party controls fixture'; sleep 120"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        manager = Manager()
        wait(lambda: bool(manager.controls))
        path = i3_events.socket_path()
        tree = i3_events.request(path, 4)
        visible = {workspace["name"] for workspace in i3_events.request(path, 1) if workspace.get("visible")}
        targets = decoration_targets(tree, visible)
        identifier = next(iter(targets))
        control = manager.controls[identifier]
        assert not control.get_accept_focus() and not control.get_focus_on_map()
        assert control.last_position == targets[identifier]
        wait(lambda: control.get_mapped())
        for _index in range(20):
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            time.sleep(0.02)
        print("CONTROL_GEOMETRY", targets[identifier], tuple(control.get_position()), tuple(control.get_size()), flush=True)
        assert [widget.get_accessible().get_name() for widget in control.get_child().get_children()] == ["Close window", "Minimize window", "Toggle fullscreen"]
        if len(sys.argv) > 1:
            screen = Gdk.get_default_root_window()
            image = Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height())
            image.savev(sys.argv[1], "png", [], [])
        # Pointer crossing and controls on an unfocused client must not focus it.
        peer = subprocess.Popen(["xterm", "-class", "ThirdPartyTest", "-title", "Second fixture", "-e", "sleep", "120"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def peer_present():
            tree = i3_events.request(path, 4)
            def find(node):
                if node.get("window") and node.get("name") == "Second fixture":
                    return node
                return next((found for child in node.get("nodes", []) + node.get("floating_nodes", []) if (found := find(child))), None)
            return find(tree)
        wait(peer_present)
        peer_id = peer_present()["id"]
        subprocess.run(["i3-msg", f"[con_id={peer_id}] move position 720 100; [con_id={peer_id}] focus"], check=True, capture_output=True)
        wait(lambda: identifier in manager.controls and peer_id in manager.controls)
        pointer = Gdk.Display.get_default().get_default_seat().get_pointer()
        pointer.warp(Gdk.Screen.get_default(), 180, 180)
        for _ in range(20):
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            time.sleep(0.02)
        assert peer_present()["focused"], "Hover changed client focus"
        manager.controls[identifier].get_child().get_children()[1].emit("clicked")
        wait(lambda: identifier not in manager.controls)
        assert peer_present()["focused"], "Minimize targeted/focused the wrong client"
        subprocess.run([str(root / "packages/ooonana/usr/bin/ooonana-window-list"), "--window-action", "show", str(identifier)], env=env, check=True, capture_output=True)
        wait(lambda: identifier in manager.controls)
        manager.controls[identifier].get_child().get_children()[2].emit("clicked")
        wait(lambda: identifier not in manager.controls)
        subprocess.run([str(root / "packages/ooonana/usr/bin/ooonana-window-list"), "--window-action", "fullscreen", str(identifier)], env=env, check=True, capture_output=True)
        wait(lambda: identifier in manager.controls)
        manager.controls[identifier].get_child().get_children()[0].emit("clicked")
        wait(lambda: terminal.poll() is not None)
        # Real native right-click menu dispatches an action to this fixture only.
        import window_menu
        arguments = sys.argv
        menu_errors = []
        def select_minimize():
            menu = Gtk.grab_get_current()
            try:
                assert isinstance(menu, Gtk.Menu) and menu.get_mapped(), "Native action menu did not map/grab"
                rows = menu.get_children()
                assert len(rows) == 6
                rows[3].emit("activate")
            except Exception as error:
                menu_errors.append(error)
            finally:
                if isinstance(menu, Gtk.Menu):
                    menu.popdown()
                if Gtk.main_level():
                    Gtk.main_quit()
            return False
        try:
            sys.argv = ["window-menu", "--window", str(peer_id), "--title", "Second fixture"]
            GLib.timeout_add(250, select_minimize)
            assert window_menu.main() == 0
        finally:
            sys.argv = arguments
        assert not menu_errors, menu_errors
        wait(lambda: peer_id not in manager.controls)
        print("THIRD_PARTY_CONTROLS_OK")
    finally:
        if manager:
            manager.clear()
        if terminal and terminal.poll() is None:
            terminal.terminate()
            terminal.wait(timeout=5)
        if peer and peer.poll() is None:
            peer.terminate()
            peer.wait(timeout=5)
        wm.terminate()
        wm.wait(timeout=5)
