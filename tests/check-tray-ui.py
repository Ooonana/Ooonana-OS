#!/usr/bin/env python3
"""Private real SNI bus/GTK/menu round trip and shipped Blueman adapter; no radios."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana"))
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk
from gi.repository import Gio
Gtk.init([])

if "--blueman-worker" in sys.argv:
    from blueman.main.indicators.StatusNotifierItem import StatusNotifierItem
    proof = Path(sys.argv[sys.argv.index("--blueman-worker") + 1])
    class FixtureTray:
        def activate(self): pass
        def activate_status_icon(self): proof.write_text("activate\n")
        def activate_menu_item(self, *ids): proof.write_text("menu:" + str(ids) + "\n")
    implementation = StatusNotifierItem(FixtureTray(), "bluetooth-symbolic")
    implementation.set_tooltip_title("Blueman adapter QA")
    implementation.set_menu([{"id": 7, "text": "_Adapter fixture action", "icon_name": "bluetooth-symbolic", "sensitive": True}])
    GLib.MainLoop().run()
    raise SystemExit(0)

from tray_app import TrayApplication
from tray_service import WATCHER, WATCH_PATH, ITEM, TrayService
output = Path(sys.argv[1]); output.mkdir(parents=True, exist_ok=True)
screen = Gdk.get_default_root_window()


def settle(seconds=.15):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(.01)


def wait(predicate, message, seconds=10):
    until = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < until, message
        settle(.03)
    settle(.08)


def call(bus, destination, path, interface, method, params):
    result = []
    def done(bus, reply):
        try: result.append((bus.call_finish(reply).unpack(), None))
        except GLib.Error as error: result.append((None, error))
    bus.call(destination, path, interface, method, params, None, Gio.DBusCallFlags.NONE, 2500, None, done)
    wait(lambda: bool(result), "Private bus reply missing")
    return result[0]


def capture(name):
    settle()
    Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height()).savev(str(output / (name + ".png")), "png", [], [])


class Fixture:
    def __init__(self, title):
        self.bus = Gio.DBusConnection.new_for_address_sync(os.environ["DBUS_SESSION_BUS_ADDRESS"],
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        self.title, self.status, self.revision, self.actions = title, "Active", 1, []
        xml = '''<node><interface name="org.kde.StatusNotifierItem">
        <property name="Title" type="s" access="read"/><property name="Id" type="s" access="read"/>
        <property name="IconName" type="s" access="read"/><property name="Status" type="s" access="read"/>
        <property name="Menu" type="o" access="read"/><property name="ItemIsMenu" type="b" access="read"/>
        <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
        <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
        <signal name="NewTitle"/><signal name="NewStatus"><arg type="s"/></signal>
        </interface></node>'''
        self.bus.register_object("/StatusNotifierItem", Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0], self.method, self.property, None)
        menu = '''<node><interface name="com.canonical.dbusmenu">
        <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
        <method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
        <arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/></method>
        <method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/></method>
        <signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
        </interface></node>'''
        self.bus.register_object("/Menu", Gio.DBusNodeInfo.new_for_xml(menu).interfaces[0], self.menu, None, None)
        value, error = call(self.bus, WATCHER, WATCH_PATH, WATCHER, "RegisterStatusNotifierItem", GLib.Variant("(s)", ("/StatusNotifierItem",)))
        assert error is None, error

    def property(self, _bus, _sender, _path, _interface, name):
        return {"Title": GLib.Variant("s", self.title), "Id": GLib.Variant("s", "private-fixture"),
                "IconName": GLib.Variant("s", "preferences-system-symbolic"), "Status": GLib.Variant("s", self.status),
                "Menu": GLib.Variant("o", "/Menu"), "ItemIsMenu": GLib.Variant("b", False)}[name]

    def method(self, _bus, _sender, _path, _interface, method, params, invocation):
        self.actions.append(method); invocation.return_value(GLib.Variant("()", ()))

    def menu(self, _bus, _sender, _path, _interface, method, params, invocation):
        if method == "AboutToShow": invocation.return_value(GLib.Variant("(b)", (False,)))
        elif method == "GetLayout":
            children = []
            for identifier, title, enabled in ((1, "_Open fixture", True), (2, "Disabled action", False)):
                children.append(GLib.Variant("(ia{sv}av)", (identifier, {"label": GLib.Variant("s", title), "enabled": GLib.Variant("b", enabled)}, [])))
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (self.revision, (0, {}, children))))
        else:
            self.actions.append(params.unpack()); invocation.return_value(GLib.Variant("()", ()))

    def close(self): self.bus.close_sync(None)


with tempfile.TemporaryDirectory(prefix="ooonana-tray-ui-") as temporary:
    base = Path(temporary)
    config = base / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines() if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    app = worker = nm_applet = None; fixtures = []
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0, "Private i3 unavailable")
        os.environ["OOONANA_THEME_INHERITED"] = os.environ.get("OOONANA_THEME", "dark")
        os.environ["XDG_CONFIG_HOME"] = str(base / "config")
        if os.environ.get("OOONANA_GUI_TEXT_SCALE") == "2.0":
            Gtk.Settings.get_default().set_property("gtk-xft-dpi", 192 * 1024)
        app = TrayApplication(); assert app.register(None) and not app.get_is_remote()
        assert app.service is not None
        original_owner = app.service.owner(WATCHER)
        # Actual second launcher reaches existing app; no extra watcher/window.
        secondary = subprocess.Popen([sys.executable, "-B", str(ROOT / "packages/ooonana/usr/lib/ooonana/ui/tray_app.py"), "--background"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        wait(lambda: secondary.poll() is not None, "Secondary launcher did not delegate")
        assert secondary.returncode == 0 and app.service.owner(WATCHER) == original_owner
        app.activate(); settle()
        capture("empty")
        first = Fixture("Wi-Fi 日本語 한글 — very long background app name " * 3); fixtures.append(first)
        wait(lambda: any(item.props.get("Title") == first.title.strip() for item in app.service.items.values()), "Real registration/GetAll failed")
        item = next(iter(app.service.items.values())); row = app.window.rows[item.identifier]
        row[1].emit("clicked")
        wait(lambda: "Activate" in first.actions, "Real app Activate missing")
        row[2].emit("clicked")
        wait(lambda: app.window.menu is not None, "Real remote app menu missing")
        menu = app.window.menu
        assert menu.get_children()[0].get_sensitive() and not menu.get_children()[1].get_sensitive()
        capture("app-menu")
        menu.get_children()[0].activate()
        wait(lambda: any(isinstance(value, tuple) and value[0] == 1 for value in first.actions), "Menu Event round trip missing")
        app.window.close_menu()
        row[2].emit("clicked"); wait(lambda: app.window.menu is not None, "Menu reopen missing")
        first.revision += 1
        first.bus.emit_signal(None, "/Menu", "com.canonical.dbusmenu", "LayoutUpdated", GLib.Variant("(ui)", (first.revision, 0)))
        wait(lambda: app.window.menu is None, "Stale revision menu not closed")
        # Spoofing another peer and malformed object addresses must fail.
        second = Fixture("Second app"); fixtures.append(second)
        _, error = call(second.bus, WATCHER, WATCH_PATH, WATCHER, "RegisterStatusNotifierItem", GLib.Variant("(s)", (first.bus.get_unique_name(),)))
        assert error is not None, "Foreign peer registration accepted"
        _, error = call(second.bus, WATCHER, WATCH_PATH, WATCHER, "RegisterStatusNotifierItem", GLib.Variant("(s)", ("/bad/../path",)))
        assert error is not None
        observer_bus = Gio.DBusConnection.new_for_address_sync(os.environ["DBUS_SESSION_BUS_ADDRESS"],
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        observer = TrayService(lambda: None, lambda *_: None, observer_bus)
        wait(lambda: len(observer.items) == 2, "Existing watcher registry not adopted")
        assert not observer.owned and app.service.owner(WATCHER) == original_owner
        observer.close(); observer_bus.close_sync(None)
        assert app.service.owner(WATCHER) == original_owner, "Observer replaced/released foreign watcher"
        # Queue old-owner loss, replace its alias before dispatch. Old signal
        # must never remove new peer or redirect old widget actions to it.
        alias = "org.ooonana.TrayFixture"
        def request(bus):
            return bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName",
                GLib.Variant("(su)", (alias, 4)), None, Gio.DBusCallFlags.NONE, 1000, None)
        request(first.bus)
        app.service.remove(first.bus.get_unique_name() + "/StatusNotifierItem")
        app.service.add(alias)
        old_alias = app.service.items[alias + "/StatusNotifierItem"]
        first.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ReleaseName",
            GLib.Variant("(s)", (alias,)), None, Gio.DBusCallFlags.NONE, 1000, None)
        request(second.bus)
        app.service.remove(second.bus.get_unique_name() + "/StatusNotifierItem")
        app.service.add(alias)
        replacement = app.service.items[alias + "/StatusNotifierItem"]
        settle()
        assert not app.service.current(old_alias) and app.service.current(replacement) and replacement.owner == second.bus.get_unique_name()
        # Restore independent fixtures for subsequent UI/stale-action checks.
        app.service.remove(alias + "/StatusNotifierItem")
        app.service.add(first.bus.get_unique_name() + "/StatusNotifierItem")
        app.service.add(second.bus.get_unique_name() + "/StatusNotifierItem")
        item = app.service.items[first.bus.get_unique_name() + "/StatusNotifierItem"]
        # Two viewport heights worth of real peers; popup must scroll, not crowd panel.
        for index in range(10): fixtures.append(Fixture(f"Background app {index + 1}"))
        wait(lambda: len(app.window.rows) == 12, "Overflow rows missing")
        focused = next(iter(app.window.rows.values()))[1]
        focused.grab_focus(); settle()
        anchor = app.window.scroll.get_vadjustment().get_value()
        first.title = "Updated 한글 title"
        first.bus.emit_signal(None, "/StatusNotifierItem", ITEM, "NewTitle", None)
        wait(lambda: app.service.items[first.bus.get_unique_name() + "/StatusNotifierItem"].props.get("Title") == first.title,
             "Live indicator property update missing")
        assert app.window.get_focus() is focused and app.window.scroll.get_vadjustment().get_value() == anchor
        settle(); capture("overflow")
        area = app.window.get_display().get_primary_monitor() or app.window.get_display().get_monitor(0)
        geometry = area.get_workarea(); width, height = app.window.get_size()
        assert width <= geometry.width and height <= geometry.height, (width, height, geometry)
        # Actual shipped Blueman SNI/menu implementation, radio layer replaced only.
        proof = output / "blueman-action.txt"
        with (output / "blueman.log").open("w") as log:
            worker = subprocess.Popen([sys.executable, "-B", __file__, "--blueman-worker", str(proof)], stdout=log, stderr=log)
            wait(lambda: any(item.path == "/org/blueman/sni" and item.props.get("Title") for item in app.service.items.values()), "Shipped Blueman adapter failed")
            blue = next(item for item in app.service.items.values() if item.path == "/org/blueman/sni")
            settle(.3)
            app.window.rows[blue.identifier][2].emit("clicked")
            wait(lambda: app.window.menu is not None, "Blueman real menu missing")
            app.window.menu.get_children()[0].activate()
            wait(proof.exists, "Blueman real action callback missing")
            assert proof.read_text().startswith("menu:(7"), proof.read_text()
        app.window.close_menu()
        if os.environ.get("OOONANA_TRAY_REAL_NM") == "1":
            with (output / "nm-applet.log").open("w") as log:
                nm_applet = subprocess.Popen(["nm-applet", "--indicator"], stdout=log, stderr=log)
                def nm_item():
                    try: owner = app.service.owner("org.freedesktop.network-manager-applet")
                    except GLib.Error: return None
                    return next((item for item in app.service.items.values() if item.owner == owner and item.props.get("Menu")), None)
                wait(lambda: nm_applet.poll() is None and nm_item() is not None, "Real nm-applet indicator registration failed")
                network = nm_item()
                app.window.rows[network.identifier][2].emit("clicked")
                wait(lambda: app.window.menu is not None, "Real nm-applet menu failed")
                capture("real-network-manager-menu")
                app.window.close_menu()
                print("TRAY_REAL_NM_OK actual private NetworkManager/nm-applet; real menu; no network action", flush=True)
        stale = item
        first.close(); fixtures.remove(first)
        wait(lambda: not app.service.current(stale), "Exited app remains actionable")
        app.window.present()
        wait(app.window.has_toplevel_focus, "Overflow window did not receive keyboard focus")
        subprocess.run(["xdotool", "key", "Escape"], check=True, timeout=5)
        wait(lambda: not app.window.get_visible(), "Real Escape did not close overflow")
        app.activate(); assert app.window.get_visible()
        first_row = next(iter(app.window.rows.values()))
        wait(first_row[1].has_focus, "First app not keyboard focused")
        subprocess.run(["xdotool", "key", "Tab"], check=True, timeout=5)
        wait(first_row[2].has_focus, "Tab did not reach app menu")
        subprocess.run(["xdotool", "key", "Return"], check=True, timeout=5)
        wait(lambda: app.window.menu is not None, "Keyboard app menu did not open")
        subprocess.run(["xdotool", "key", "Escape"], check=True, timeout=5)
        wait(lambda: app.window.menu is None, "Menu Escape failed")
        assert app.window.get_visible(), "Menu Escape also closed overflow window"
        capture("reopened")
        (output / "receipt.json").write_text(json.dumps({"scale": os.environ.get("OOONANA_GUI_TEXT_SCALE"), "rows": len(app.window.rows),
            "window": [width, height], "blueman": proof.read_text(), "real_bus": True, "no_hardware": True}, indent=2) + "\n")
        print("TRAY_UI_OK actual SNI/GetAll/Activate/DBusMenu; spoof/path rejection; overflow; stale revision/owner; shipped Blueman; Escape/reopen", flush=True)
    finally:
        for process in (worker, nm_applet):
            if process is not None and process.poll() is None: process.terminate(); process.wait(timeout=5)
        for fixture in fixtures: fixture.close()
        if app is not None and app.service is not None:
            if app.window: app.window.close_menu(); app.window.destroy()
            app.service.close()
        if wm.poll() is None: wm.terminate(); wm.wait(timeout=8)
