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

if "--legacy-worker" in sys.argv:
    import signal
    proof = Path(sys.argv[sys.argv.index("--legacy-worker") + 1])
    icons, menus = [], []
    def add_icon(index):
        if index == 0:
            indicator = Gtk.StatusIcon.new_from_icon_name("network-wired")
        else:
            from gi.repository import GdkPixbuf
            data = bytes(channel for y in range(24) for x in range(24)
                         for channel in ((0, 190, 120, 255) if 6 <= x < 18 and 6 <= y < 18 else (0, 0, 0, 0)))
            pixels = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(data), GdkPixbuf.Colorspace.RGB, True, 8, 24, 24, 96)
            indicator = Gtk.StatusIcon.new_from_pixbuf(pixels)
        indicator.set_title("Legacy GTK QA " + str(index)); indicator.set_tooltip_text("Legacy GTK QA")
        indicator.connect("activate", lambda *_: proof.write_text("activate"))
        def popup(_icon, _button, _time):
            menu = Gtk.Menu(); action = Gtk.MenuItem(label="Legacy QA action")
            action.connect("activate", lambda *_: proof.write_text("menu"))
            menu.append(action); menu.show_all(); menus.append(menu)
            menu.popup_at_pointer(Gtk.get_current_event())
            proof.write_text("popup")
        indicator.connect("popup-menu", popup); indicator.set_visible(True); icons.append(indicator)
    add_icon(0)
    def flood():
        for index in range(1, 300): add_icon(index)
        def ready():
            states = [{"index": index, "xid": item.get_x11_window_id(), "size": item.get_size(), "embedded": item.is_embedded()}
                      for index,item in enumerate(icons[:32])]
            proof.with_name("worker-state.json").write_text(json.dumps(states))
            if not all(item["embedded"] and item["size"] > 0 for item in states): return True
            image = icons[31].get_pixbuf()
            proof.with_name("worker-pixels.json").write_text(json.dumps({"size": [image.get_width(), image.get_height()], "center": list(image.get_pixels()[1200:1204]), "icons": states}))
            return False
        GLib.timeout_add(100, ready)
        return False
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, flood)
    GLib.MainLoop().run()
    raise SystemExit(0)

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
    app = worker = nm_applet = legacy_worker = None; fixtures = []
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0, "Private i3 unavailable")
        os.environ["OOONANA_THEME_INHERITED"] = os.environ.get("OOONANA_THEME", "dark")
        os.environ["XDG_CONFIG_HOME"] = str(base / "config")
        if os.environ.get("OOONANA_GUI_TEXT_SCALE") == "2.0":
            Gtk.Settings.get_default().set_property("gtk-xft-dpi", 192 * 1024)
        app = TrayApplication(); assert app.register(None) and not app.get_is_remote()
        assert app.service is not None
        hidden_proof = output / "hidden-legacy-action.txt"
        with (output / "legacy-hidden.log").open("w") as log:
            legacy_worker = subprocess.Popen([sys.executable, "-B", __file__, "--legacy-worker", str(hidden_proof)], stdout=log, stderr=log)
            wait(lambda: len(app.legacy.items) == 1, "Background tray did not embed before first open")
            assert not app.window.get_visible(), "Background docking unexpectedly opened overflow"
            legacy_worker.terminate(); legacy_worker.wait(timeout=5)
            wait(lambda: not app.legacy.items, "Hidden legacy client did not detach")
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
        from legacy_tray import LegacyTray
        import signal
        assert app.legacy is not None and app.legacy.owned, app.error_text
        original_owner = app.legacy.owner_window
        other = LegacyTray(app.window, lambda: None)
        assert not other.owned and app.legacy.lib.XGetSelectionOwner(app.legacy.display, app.legacy.selection) == original_owner
        app.legacy.add(0x7ffffffe); app.legacy.add(app.legacy.owner_window)
        assert not app.legacy.items, "Invalid XID/manager must not embed"
        legacy_proof = output / "legacy-action.txt"
        with (output / "legacy.log").open("w") as legacy_log:
            legacy_worker = subprocess.Popen([sys.executable, "-B", __file__, "--legacy-worker", str(legacy_proof)],
                                             stdout=legacy_log, stderr=legacy_log)
            wait(lambda: len(app.legacy.items) == 1, "Real Gtk.StatusIcon did not embed")
            slot = next(iter(app.legacy.items.values()))["socket"]
            wait(lambda: slot.get_plug_window() is not None, "Legacy socket not attached")
            adjustment = app.window.scroll.get_vadjustment()
            adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())
            settle(.2)
            from gi.repository import GdkX11
            xid = GdkX11.X11Window.get_xid(slot.get_window())
            values = dict(line.split("=", 1) for line in subprocess.check_output(
                ["xdotool", "getwindowgeometry", "--shell", str(xid)], text=True).splitlines())
            assert int(values["WIDTH"]) <= 24 * slot.get_scale_factor()
            subprocess.run(["xdotool", "mousemove", "--sync", str(int(values["X"]) + int(values["WIDTH"]) // 2),
                            str(int(values["Y"]) + int(values["HEIGHT"]) // 2), "click", "1"], check=True)
            wait(lambda: legacy_proof.exists() and legacy_proof.read_text() == "activate", "Real legacy icon click failed")
            subprocess.run(["xdotool", "click", "3"], check=True)
            wait(lambda: legacy_proof.read_text() == "popup", "Legacy app-owned popup failed")
            subprocess.run(["xdotool", "key", "Down", "Return"], check=True)
            wait(lambda: legacy_proof.read_text() == "menu", "Legacy menu action failed")
            capture("legacy-app-menu")
            claimant = other.lib.XCreateSimpleWindow(other.display, other.root, -1, -1, 1, 1, 0, 0, 0)
            other.lib.XSetSelectionOwner(other.display, other.selection, claimant, 0)
            other.lib.XFlush(other.display)
            wait(lambda: not app.legacy.owned and not app.legacy.items, "Legacy selection loss did not detach icons")
            assert legacy_worker.poll() is None, "Selection loss killed foreign tray client"
            app.window.hide(); app.activate()
            assert "another tray" in app.window.status.get_text()
            other.lib.XDestroyWindow(other.display, claimant); other.lib.XFlush(other.display)
            wait(lambda: app.legacy.owned and len(app.legacy.items) == 1, "Legacy owner exit did not recover/re-dock")
            app.window.hide(); app.activate()
            assert "another tray" not in app.window.status.get_text(), "Recovered tray retained stale ownership warning"
            other.close()
            slot = next(iter(app.legacy.items.values()))["socket"]
            adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())
            slot.grab_focus(); settle(.2)
            legacy_proof.write_text("keyboard pending")
            subprocess.run(["xdotool", "key", "space"], check=True)
            wait(lambda: legacy_proof.read_text() == "activate", "Legacy keyboard activation failed")
            legacy_worker.send_signal(signal.SIGUSR1)
            wait(lambda: len(app.legacy.items) == 32, "Legacy capacity/overflow failed")
            wait(lambda: (output / "worker-pixels.json").exists(), "Legacy burst worker did not finish creating icons", seconds=30)
            settle(.3)
            assert len(app.legacy.items) == 32 and not app.window.empty.get_visible()
            assert app.window.get_size().height <= geometry.height
            adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())
            subprocess.run(["xdotool", "mousemove", "0", "0"], check=True)
            settle(.3)
            capture("legacy-overflow")
            final_slot = list(app.legacy.items.values())[-1]["socket"]
            native = final_slot.get_window()
            rendered = Gdk.pixbuf_get_from_window(native, 0, 0, native.get_width(), native.get_height())
            raw = rendered.get_pixels(); stride, channels = rendered.get_rowstride(), rendered.get_n_channels()
            corner = tuple(raw[stride + channels:stride + channels + 3])
            color = app.window.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
            expected = tuple(round(channel * 255) for channel in (color.red, color.green, color.blue))
            assert all(abs(a-b) <= 4 for a,b in zip(corner, expected)), ("Legacy transparent corner lost host background", corner, expected)
            offset = (rendered.get_height() // 2) * stride + (rendered.get_width() // 2) * channels
            center = tuple(raw[offset:offset + 3])
            plug = final_slot.get_plug_window()
            diagnostic = {"socket": [native.get_width(), native.get_height()], "plug": list(plug.get_geometry()), "mapped": plug.is_viewable(), "center": center,
                "server": subprocess.check_output(["xdotool", "getwindowgeometry", "--shell", str(GdkX11.X11Window.get_xid(plug))], text=True)}
            (output / "pixel-diagnostic.json").write_text(json.dumps(diagnostic, indent=2))
            Gdk.pixbuf_get_from_window(plug, 0, 0, plug.get_width(), plug.get_height()).savev(str(output / "plug-pixels.png"), "png", [], [])
            assert all(abs(a-b) <= 4 for a,b in zip(center, (0, 190, 120))), ("Legacy icon paint lost client pixels", center)
            legacy_worker.terminate(); legacy_worker.wait(timeout=5)
            wait(lambda: not app.legacy.items, "Exited legacy app left stale sockets")
        print("TRAY_LEGACY_OK real Gtk.StatusIcon, click/app menu/action, invalid XIDs, no stealing, bounded overflow and owner exit", flush=True)
        (output / "receipt.json").write_text(json.dumps({"scale": os.environ.get("OOONANA_GUI_TEXT_SCALE"), "rows": len(app.window.rows),
            "window": [width, height], "blueman": proof.read_text(), "real_bus": True, "no_hardware": True}, indent=2) + "\n")
        print("TRAY_UI_OK actual SNI/GetAll/Activate/DBusMenu; spoof/path rejection; overflow; stale revision/owner; shipped Blueman; Escape/reopen", flush=True)
    finally:
        for process in (worker, nm_applet, legacy_worker):
            if process is not None and process.poll() is None: process.terminate(); process.wait(timeout=5)
        for fixture in fixtures: fixture.close()
        if app is not None and app.service is not None:
            if app.legacy: app.legacy.close()
            if app.window: app.window.close_menu(); app.window.destroy()
            app.service.close()
        if wm.poll() is None: wm.terminate(); wm.wait(timeout=8)
