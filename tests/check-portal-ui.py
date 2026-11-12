#!/usr/bin/env python3
"""Real candidate portal activation/picker, private nonroot X11 session only.

Protocol: https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.FileChooser.html
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

if os.environ.get("OOONANA_GUI_TEST_DISPLAY") != "1" or os.getuid() == 0:
    raise SystemExit("Explicit isolated nonroot display required")
if subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0:
    raise SystemExit("Refusing existing window manager")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk
from gi.repository import Gio
from window_controls import Manager
import i3_events

DESTINATION = "org.freedesktop.portal.Desktop"
OBJECT = "/org/freedesktop/portal/desktop"
INTERFACE = "org.freedesktop.portal.FileChooser"
output = Path(sys.argv[1])


def wait(predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while True:
        result = predicate()
        if result:
            return result
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        assert time.monotonic() < deadline, "Portal fixture timeout"
        time.sleep(0.03)


def key(value):
    subprocess.run(["xdotool", "key", "--clearmodifiers", value], check=True)


with tempfile.TemporaryDirectory(prefix="ooonana-portal-") as temporary:
    fixture = Path(temporary)
    config = fixture / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                                if not line.startswith("exec")) + "\n")
    owned = fixture / "portal-fixture.txt"
    owned.write_text("Private portal fixture\n")
    wm = subprocess.Popen(["i3", "-c", str(config)])
    manager = None
    subscription = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0)
        manager = Manager()
        subprocess.run(["dbus-update-activation-environment", "DISPLAY", "XAUTHORITY",
                        "XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION",
                        "XDG_RUNTIME_DIR"], check=True)
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

        def call(destination, path, interface, method, parameters, reply):
            return bus.call_sync(destination, path, interface, method, parameters,
                                 GLib.VariantType.new(reply), Gio.DBusCallFlags.NONE, 30000, None)

        version = call(DESTINATION, OBJECT, "org.freedesktop.DBus.Properties", "Get",
                       GLib.Variant("(ss)", (INTERFACE, "version")), "(v)").unpack()[0]
        assert version >= 3, version
        documents = call("org.freedesktop.portal.Documents", "/org/freedesktop/portal/documents",
                         "org.freedesktop.portal.Documents", "GetMountPoint", None, "(ay)").unpack()[0]
        document_mount = Path(bytes(documents).rstrip(b"\0").decode())
        assert document_mount.is_dir(), document_mount
        replies = {}
        subscription = bus.signal_subscribe(DESTINATION, "org.freedesktop.portal.Request", "Response",
            None, None, Gio.DBusSignalFlags.NONE,
            lambda connection, sender, path, interface, signal, parameters: replies.__setitem__(path, parameters.unpack()))

        def dialog():
            def visit(node):
                if node.get("window") and str(node.get("name", "")).startswith("Ooonana portal fixture"):
                    return node
                for child in node.get("nodes", []) + node.get("floating_nodes", []):
                    found = visit(child)
                    if found:
                        return found
                return None
            return visit(i3_events.request(i3_events.socket_path(), 4))

        def request(token):
            handle = call(DESTINATION, OBJECT, INTERFACE, "OpenFile",
                GLib.Variant("(ssa{sv})", ("", "Ooonana portal fixture " + token,
                    {"handle_token": GLib.Variant("s", token), "modal": GLib.Variant("b", True),
                     "current_folder": GLib.Variant("ay", list(os.fsencode(fixture) + b"\0"))})), "(o)").unpack()[0]
            node = wait(lambda: (current := dialog()) and current.get("focused") and current)
            assert node["floating"] in ("auto_on", "user_on"), node
            rectangle = node["rect"]
            screen = Gdk.get_default_root_window()
            assert rectangle["x"] >= 0 and rectangle["y"] >= 0, rectangle
            assert rectangle["x"] + rectangle["width"] <= screen.get_width(), rectangle
            assert rectangle["y"] + rectangle["height"] <= screen.get_height(), rectangle
            manager.refresh()
            wait(lambda: node["id"] in manager.controls)
            def painted():
                control = manager.controls.get(node["id"])
                if not control:
                    return False
                for button, color in zip(control.get_child().get_children(),
                        ((255, 115, 107), (255, 209, 108), (127, 214, 160))):
                    origin = button.translate_coordinates(control, 0, 0)
                    if origin is None or button.get_allocated_width() < 8:
                        return False
                    x, y = control.get_position()
                    pixels = Gdk.pixbuf_get_from_window(screen, x + origin[0] + 3, y + origin[1] + 3,
                        button.get_allocated_width() - 6, button.get_allocated_height() - 6)
                    if pixels is None:
                        return False
                    data, stride, channels = pixels.get_pixels(), pixels.get_rowstride(), pixels.get_n_channels()
                    matches = sum(all(abs(data[row * stride + column * channels + channel] - target) <= 35
                        for channel, target in enumerate(color))
                        for row in range(pixels.get_height()) for column in range(pixels.get_width()))
                    if matches < 12:
                        return False
                return True
            wait(painted)
            print("PORTAL_DIALOG", token, rectangle, flush=True)
            return handle

        handle = request("cancel")
        Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), 0, 0,
            Gdk.get_default_root_window().get_width(), Gdk.get_default_root_window().get_height()).savev(str(output), "png", [], [])
        key("Escape")
        wait(lambda: handle in replies)
        assert replies[handle][0] in (1, 2) and not replies[handle][1].get("uris"), replies[handle]
        wait(lambda: dialog() is None)
        handle = request("open")
        key("ctrl+l")
        key("ctrl+a")
        subprocess.run(["xdotool", "type", "--clearmodifiers", "--", str(owned)], check=True)
        key("Return")
        wait(lambda: handle in replies)
        assert replies[handle][0] == 0 and replies[handle][1]["uris"] == [owned.as_uri()], replies[handle]
        assert owned.read_text() == "Private portal fixture\n"
        for name in (DESTINATION, "org.freedesktop.impl.portal.desktop.gtk", "org.freedesktop.portal.Documents"):
            uid = call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                       "GetConnectionUnixUser", GLib.Variant("(s)", (name,)), "(u)").unpack()[0]
            assert uid == os.getuid(), (name, uid)
        print("PORTAL_UI_OK activation/nonroot/floating/bounds/cancel/open/unchanged-file", flush=True)
    finally:
        if subscription is not None:
            bus.signal_unsubscribe(subscription)
        if manager:
            manager.clear()
        wm.terminate()
        try:
            wm.wait(timeout=5)
        except subprocess.TimeoutExpired:
            wm.kill()
            wm.wait(timeout=5)
