#!/usr/bin/env python3
"""Private D-Bus protocol fixture. Records sleep requests; never sleeps a host."""
import ctypes as C
import json
import os
from pathlib import Path
import sys
from gi.repository import Gio, GLib

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
directory = Path(sys.argv[1])
assert directory == Path("/qa/session-control/provider")
address = sys.argv[2]
assert address.startswith("unix:path=/qa/session-control/")
connection = Gio.DBusConnection.new_for_address_sync(address,
    Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
xml = '''<node><interface name="org.freedesktop.login1.Manager">
<method name="CanSuspend"><arg type="s" direction="out"/></method>
<method name="Suspend"><arg type="b" direction="in"/></method>
</interface></node>'''
last, checks = "", 0


def locked():
    x = C.CDLL("libX11.so.6")
    x.XOpenDisplay.restype = C.c_void_p
    x.XDefaultRootWindow.argtypes = [C.c_void_p]; x.XDefaultRootWindow.restype = C.c_ulong
    x.XGrabKeyboard.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_int, C.c_int, C.c_ulong]
    x.XUngrabKeyboard.argtypes = [C.c_void_p, C.c_ulong]
    x.XCloseDisplay.argtypes = [C.c_void_p]
    display = x.XOpenDisplay(None)
    assert display
    try:
        status = x.XGrabKeyboard(display, x.XDefaultRootWindow(display), False, 1, 1, 0)
        if status == 0:
            x.XUngrabKeyboard(display, 0)
        return status == 1
    finally:
        x.XCloseDisplay(display)


def method(_connection, _sender, _path, _interface, name, parameters, invocation):
    global last, checks
    value = (directory / "config.json").read_text()
    if value != last:
        last, checks = value, 0
    config = json.loads(value)
    record = {"method": name}
    if name == "CanSuspend":
        states = config.get("states", ["yes"])
        state = states[min(checks, len(states) - 1)]
        checks += 1
        record["state"] = state
        result = GLib.Variant("(s)", (state,))
    elif name == "Suspend":
        record.update(interactive=parameters.unpack()[0], locked=locked())
        result = None
    else:
        invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", "Unknown fixture method")
        return
    with (directory / "calls.jsonl").open("a") as stream:
        stream.write(json.dumps(record) + "\n")
    invocation.return_value(result)


info = Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0]
connection.register_object("/org/freedesktop/login1", info, method, None, None)
Gio.bus_own_name_on_connection(connection, "org.freedesktop.login1", Gio.BusNameOwnerFlags.NONE,
    lambda *_: (directory / "ready").write_text("private provider ready\n"), None)
GLib.MainLoop().run()
