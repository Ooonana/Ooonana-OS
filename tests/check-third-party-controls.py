#!/usr/bin/env python3
"""Isolated i3/Xvfb test; never touches user's desktop windows."""
import ctypes
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
from window_controls import Manager, WIDTH, decoration_targets
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
        tool = subprocess.run(['i3-msg', '-r', '-t', 'get_version'], capture_output=True, text=True, check=True)
        assert tool.stdout.strip(), 'i3-msg is stubbed/broken; restore test-host tool before UI QA'
        assert json.loads(tool.stdout).get('major'), tool.stdout
        terminal = subprocess.Popen(["xterm", "-class", "ThirdPartyTest", "-title", "Controls fixture", "-bg", "#101317", "-fg", "#f5f5f7", "-e", "sh", "-c", "printf 'Third-party controls fixture'; sleep 120"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        manager = Manager()
        wait(lambda: bool(manager.controls))
        path = i3_events.socket_path()
        tree = i3_events.request(path, 4)
        visible = {workspace["name"] for workspace in i3_events.request(path, 1) if workspace.get("visible")}
        targets = decoration_targets(tree, visible, manager.control_scale)
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
        assert [widget.get_accessible().get_name() for widget in control.get_child().get_children()] == [
            "Close window", "Minimize window (Alt+F9)", "Fullscreen (Alt+F10). Move to the top edge for controls."]
        assert control.get_size().width == (82 * manager.control_scale if manager.control_scale else WIDTH)
        assert control.get_size().height == targets[identifier][2], "Controls overlap client contents"
        assert not control.control_region.contains_point(0, 0), "Rectangular popup corner visible"
        assert control.get_window().is_shaped(), "X11 popup shape not applied"
        for widget in control.get_child().get_children():
            size = widget.get_allocation()
            assert size.width == size.height == (24 * manager.control_scale if manager.control_scale else 16), (size.width, size.height)
            assert size.height <= targets[identifier][2]
            assert widget.get_image().get_pixel_size() == (12 * manager.control_scale if manager.control_scale else 10)
            assert widget.get_tooltip_text() == widget.get_accessible().get_name()
            x, y = widget.translate_coordinates(control, 0, 0)
            assert control.control_region.contains_point(x + size.width // 2, y + size.height // 2)
            assert not control.control_region.contains_point(x, y), "Square button corner visible"
        first = control.get_child().get_children()[0]
        x, y = first.translate_coordinates(control, 0, 0)
        assert not control.control_region.contains_point(x + first.get_allocated_width() + 2, y + 8), "Popup gap blocks titlebar"
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
        # Title can be visible before WM_CLASS and initial for_window rules.
        # Moving too soon gets overwritten by fixture's initial position.
        try:
            # Xterm cell-size hints can quantize requested 330px to 328px.
            # Wait for the rule's position, then test controls against actual
            # decoration geometry rather than a platform-dependent client size.
            wait(lambda: peer_present() and peer_present().get('floating') == 'user_on'
                 and peer_present()['rect']['x'] == 80 and peer_present()['rect']['y'] == 80)
        except AssertionError:
            node = peer_present()
            print("PEER_STATE", {key: node.get(key) for key in ("name", "floating", "rect", "window_properties")} if node else None, flush=True)
            raise
        peer_id = peer_present()["id"]
        moved = subprocess.run(["i3-msg", '-r', f"[con_id={peer_id}] move position 720 100; [con_id={peer_id}] focus"], check=True, capture_output=True)
        assert all(item.get('success') for item in json.loads(moved.stdout)), (moved.stdout, moved.stderr)
        wait(lambda: peer_present()['rect']['x'] == 720)
        wait(lambda: identifier in manager.controls and peer_id in manager.controls)
        pointer = Gdk.Display.get_default().get_default_seat().get_pointer()
        pointer.warp(Gdk.Screen.get_default(), 180, 180)
        for _ in range(20):
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            time.sleep(0.02)
        assert peer_present()["focused"], "Hover changed client focus"
        assert manager.controls[identifier].get_style_context().has_class("inactive")
        assert not manager.controls[peer_id].get_style_context().has_class("inactive")
        # Movement need not emit an i3 window event. Root X11 notifications must
        # update controls while idle, without forcing Manager.refresh in test.
        subprocess.run(["i3-msg", f"[con_id={identifier}] move position 140 120"],
                       check=True, capture_output=True)
        wait(lambda: manager.controls[identifier].last_position != targets[identifier])
        tree = i3_events.request(path, 4)
        moved_target = decoration_targets(tree, visible, manager.control_scale)[identifier]
        wait(lambda: manager.controls[identifier].last_position == moved_target)
        wait(lambda: tuple(manager.controls[identifier].get_position()) == moved_target[:2])
        manager.controls[identifier].get_child().get_children()[1].emit("clicked")
        wait(lambda: identifier not in manager.controls)
        assert peer_present()["focused"], "Minimize targeted/focused the wrong client"
        subprocess.run([str(root / "packages/ooonana/usr/bin/ooonana-window-list"), "--window-action", "show", str(identifier)], env=env, check=True, capture_output=True)
        wait(lambda: identifier in manager.controls)
        xtest = ctypes.CDLL("libXtst.so.6")
        xtest.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        xtest.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        manager.xlib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        manager.xlib.XKeysymToKeycode.restype = ctypes.c_ubyte

        def move_pointer(x, y):
            pointer.warp(Gdk.Screen.get_default(), x, y)
            Gdk.Display.get_default().sync()

        def button_event(pressed):
            assert xtest.XTestFakeButtonEvent(manager.display, 1, pressed, 0)
            manager.xlib.XFlush(manager.display)

        def press_control(index):
            popup = manager.fullscreen_bar
            button = popup.get_child().get_children()[index]
            x, y = button.translate_coordinates(popup, 0, 0)
            left, top = popup.get_position()
            move_pointer(left + x + button.get_allocated_width() // 2,
                         top + y + button.get_allocated_height() // 2)
            button_event(True)
            button_event(False)

        def reveal_fullscreen():
            move_pointer(300, 200)
            wait(lambda: manager.fullscreen_windows and not manager.fullscreen_bar.get_mapped())
            move_pointer(300, 0)
            wait(lambda: manager.fullscreen_bar.get_mapped())
            assert manager.fullscreen_bar.target.identifier == identifier
            assert manager.fullscreen_bar.get_size().height == 32

        manager.controls[identifier].get_child().get_children()[2].emit("clicked")
        reveal_fullscreen()
        def painted_bar():
            screen = Gdk.get_default_root_window()
            pixel = Gdk.pixbuf_get_from_window(screen, screen.get_width() - 25, 12, 1, 1)
            return pixel is not None and tuple(pixel.get_pixels()[:3]) == bar_color

        bar_color = (255, 255, 255) if os.environ.get("OOONANA_THEME_OVERRIDE") == "light" else (27, 31, 38)
        wait(painted_bar)
        if len(sys.argv) > 1:
            screen = Gdk.get_default_root_window()
            image = Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), 90)
            capture = Path(sys.argv[1])
            image.savev(str(capture.with_stem(capture.stem + "-fullscreen")), "png", [], [])
        move_pointer(300, 200)
        wait(lambda: not manager.fullscreen_bar.get_mapped())
        move_pointer(300, 0)
        wait(lambda: manager.fullscreen_bar.get_mapped())
        press_control(1)
        wait(lambda: not manager.fullscreen_windows and identifier not in manager.controls)
        subprocess.run([str(root / "packages/ooonana/usr/bin/ooonana-window-list"), "--window-action", "show", str(identifier)],
                       env=env, check=True, capture_output=True)
        wait(lambda: identifier in manager.controls)

        manager.controls[identifier].get_child().get_children()[2].emit("clicked")
        reveal_fullscreen()
        press_control(2)
        wait(lambda: identifier in manager.controls and not manager.fullscreen_windows)

        old_position = manager.controls[identifier].last_position
        manager.controls[identifier].get_child().get_children()[2].emit("clicked")
        reveal_fullscreen()
        move_pointer(300, 16)
        button_event(True)
        wait(lambda: manager.fullscreen_bar.drag_start is not None)
        screen = Gdk.get_default_root_window()
        move_pointer(screen.get_width() - 1, screen.get_height() - 1)
        button_event(False)
        wait(lambda: identifier in manager.controls)
        wait(lambda: manager.controls[identifier].last_position != old_position)
        assert not manager.fullscreen_windows, "Titlebar drag did not leave fullscreen"
        workspace = next(item for item in i3_events.request(path, 1) if item["focused"])
        area = workspace["rect"]
        def fitted(node):
            if node.get("type") == "floating_con" and any(
                    child.get("id") == identifier for child in node["nodes"]):
                rect = node["rect"]
                return (rect["x"] == area["x"] + area["width"] - rect["width"] and
                        rect["y"] == area["y"] + area["height"] - rect["height"])
            return any(fitted(child) for child in node["nodes"] + node["floating_nodes"])
        wait(lambda: fitted(i3_events.request(path, 4)))
        manager.controls[identifier].get_child().get_children()[2].emit("clicked")
        wait(lambda: manager.fullscreen_windows)
        alt = manager.xlib.XKeysymToKeycode(manager.display, 0xffe9)
        f9 = manager.xlib.XKeysymToKeycode(manager.display, 0xffc6)
        assert alt and f9
        for keycode, pressed in ((alt, True), (f9, True), (f9, False), (alt, False)):
            assert xtest.XTestFakeKeyEvent(manager.display, keycode, pressed, 0)
        manager.xlib.XFlush(manager.display)
        wait(lambda: not manager.fullscreen_windows and identifier not in manager.controls)
        subprocess.run([str(root / "packages/ooonana/usr/bin/ooonana-window-list"), "--window-action", "show", str(identifier)],
                       env=env, check=True, capture_output=True)
        wait(lambda: identifier in manager.controls)
        manager.controls[identifier].get_child().get_children()[0].emit("clicked")
        wait(lambda: terminal.poll() is not None)
        # Foreign GTK client-side dialog must not gain a second i3 titlebar.
        native_dialog = Gtk.Window(title="Foreign native header")
        native_dialog.set_wmclass("foreign-csd-test", "ForeignCsdTest")
        native_dialog.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        bar = Gtk.HeaderBar(title="Foreign native header", show_close_button=True)
        native_dialog.set_titlebar(bar)
        native_dialog.add(Gtk.Label(label="Own private CSD dialog"))
        native_dialog.show_all()
        def foreign_node():
            def find(node):
                if (node.get("window_properties") or {}).get("class") == "ForeignCsdTest":
                    return node
                return next((found for child in node.get("nodes", []) + node.get("floating_nodes", [])
                             if (found := find(child))), None)
            return find(i3_events.request(path, 4))
        wait(foreign_node)
        assert foreign_node()["deco_rect"]["height"] == 0, "Duplicated foreign CSD titlebar"
        assert foreign_node()["id"] not in manager.controls
        native_dialog.destroy()
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
