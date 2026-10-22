"""Event-driven Xsettings owner. Never replace another display's manager."""
import ctypes as C
import json
import os
from pathlib import Path
import re
import shlex
import struct
import sys

from desktop_theme import XResources

LIMIT = 65536


def parse(text):
    if len(text.encode("utf-8")) > LIMIT or "\0" in text:
        raise ValueError("Oversized or NUL Xsettings config")
    settings = {}
    for line in text.splitlines():
        parts = shlex.split(line, comments=True)
        if not parts:
            continue
        name = parts[0]
        if len(name) > 255 or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_]*)*", name) or name in settings:
            raise ValueError("Invalid or repeated Xsetting")
        raw = line.strip()[len(name):].lstrip()
        if raw.startswith('"') and len(parts) == 2:
            value, end = json.JSONDecoder().raw_decode(raw)
            if not isinstance(value, str) or "\0" in value or raw[end:].strip() and not raw[end:].lstrip().startswith("#"):
                raise ValueError("Invalid Xsetting string")
        elif len(parts) == 2 and re.fullmatch(r"-?[0-9]+", parts[1]):
            value = int(parts[1])
            if not -(2 ** 31) <= value < 2 ** 31:
                raise ValueError("Xsetting integer out of range")
        else:
            match = re.fullmatch(r"\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)(?:\s*#.*)?", raw)
            if not match or any(int(part) > 65535 for part in match.groups()):
                raise ValueError("Invalid Xsetting value")
            value = tuple(map(int, match.groups()))
        settings[name] = value
        if len(settings) > 256:
            raise ValueError("Too many Xsettings")
    return settings


def encode(settings, serial):
    # Xsettings wire order is explicit little endian, independent of host ABI.
    def padded(data):
        return data + bytes(-len(data) % 4)
    result = bytearray(struct.pack("<B3xII", 0, serial, len(settings)))
    for name, value in sorted(settings.items()):
        kind = 1 if isinstance(value, str) else 2 if isinstance(value, tuple) else 0
        key = name.encode("utf-8")
        result.extend(struct.pack("<BBH", kind, 0, len(key)) + padded(key) + struct.pack("<I", serial))
        if kind == 1:
            text = value.encode("utf-8")
            result.extend(struct.pack("<I", len(text)) + padded(text))
        else:
            result.extend(struct.pack("<4H" if kind == 2 else "<i", *(value if kind == 2 else (value,))))
    if len(result) > LIMIT:
        raise ValueError("Xsettings property exceeds limit")
    return bytes(result)


class ClientMessage(C.Structure):
    _fields_ = [("type", C.c_int), ("serial", C.c_ulong), ("send_event", C.c_int),
               ("display", C.c_void_p), ("window", C.c_ulong), ("message_type", C.c_ulong),
               ("format", C.c_int), ("data", C.c_long * 5)]


class Event(C.Union):
    pass


class PropertyEvent(C.Structure):
    _fields_ = [("type", C.c_int), ("serial", C.c_ulong), ("send_event", C.c_int),
               ("display", C.c_void_p), ("window", C.c_ulong), ("atom", C.c_ulong),
               ("time", C.c_ulong), ("state", C.c_int)]


Event._fields_ = [("type", C.c_int), ("message", ClientMessage), ("property", PropertyEvent), ("padding", C.c_long * 24)]


class Manager(XResources):
    def __init__(self):
        super().__init__()
        pointer, ulong, integer = C.c_void_p, C.c_ulong, C.c_int
        signatures = {
            "XScreenCount": ([pointer], integer), "XRootWindow": ([pointer, integer], ulong),
            "XCreateSimpleWindow": ([pointer, ulong, integer, integer, C.c_uint, C.c_uint,
                                     C.c_uint, ulong, ulong], ulong),
            "XGetSelectionOwner": ([pointer, ulong], ulong),
            "XSetSelectionOwner": ([pointer, ulong, ulong, ulong], integer),
            "XSendEvent": ([pointer, ulong, integer, C.c_long, C.POINTER(Event)], integer),
            "XConnectionNumber": ([pointer], integer), "XPending": ([pointer], integer),
            "XNextEvent": ([pointer, C.POINTER(Event)], integer),
            "XSelectInput": ([pointer, ulong, C.c_long], integer),
            "XWindowEvent": ([pointer, ulong, C.c_long, C.POINTER(Event)], integer),
        }
        for name, (arguments, result) in signatures.items():
            method = getattr(self.lib, name)
            method.argtypes, method.restype = arguments, result
        self.windows = []
        self.serial = 0
        self.property = self.lib.XInternAtom(self.display, b"_XSETTINGS_SETTINGS", 0)

    def claim(self):
        selections = [(self.lib.XRootWindow(self.display, screen),
                       self.lib.XInternAtom(self.display, f"_XSETTINGS_S{screen}".encode(), 0))
                      for screen in range(self.lib.XScreenCount(self.display))]
        self.lib.XGrabServer(self.display)
        try:
            # Check and claim under same server grab: no check/spawn race.
            if any(self.lib.XGetSelectionOwner(self.display, atom) for _root, atom in selections):
                return False
            for root, atom in selections:
                window = self.lib.XCreateSimpleWindow(self.display, root, -1, -1, 1, 1, 0, 0, 0)
                # ICCCM manager announcements use real X server time, not wall
                # clock or CurrentTime. Own requests proceed during server grab.
                self.lib.XSelectInput(self.display, window, 1 << 22)
                self.lib.XChangeProperty(self.display, window, self.property, self.property, 8, 0, C.create_string_buffer(b"\0"), 1)
                event = Event()
                self.lib.XWindowEvent(self.display, window, 1 << 22, C.byref(event))
                self.lib.XSelectInput(self.display, window, 0)
                timestamp = event.property.time
                self.lib.XSetSelectionOwner(self.display, atom, window, timestamp)
                self.windows.append((root, atom, window, timestamp))
            self.lib.XSync(self.display, 0)
            return True
        finally:
            self.lib.XUngrabServer(self.display)
            self.lib.XFlush(self.display)

    def publish(self, settings, announce=False):
        self.serial = (self.serial + 1) % (2 ** 32)
        data = encode(settings, self.serial)
        buffer = C.create_string_buffer(data)
        for root, atom, window, timestamp in self.windows:
            if self.lib.XGetSelectionOwner(self.display, atom) != window:
                return False
            self.lib.XChangeProperty(self.display, window, self.property, self.property, 8, 0, buffer, len(data))
            if announce:
                event = Event()
                event.message = ClientMessage(33, 0, 1, self.display, root,
                    self.lib.XInternAtom(self.display, b"MANAGER", 0), 32, (C.c_long * 5)(timestamp, atom, window, 0, 0))
                self.lib.XSendEvent(self.display, root, 0, 1 << 17, C.byref(event))
        self.lib.XFlush(self.display)
        return True


def main():
    from gi.repository import Gio, GLib
    from ui.theme_watch import AppearanceWatch
    paths = (Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "ooonana/xsettingsd.conf",
             Path("/etc/ooonana/xsettingsd.conf"))

    def current():
        for path in paths:
            try:
                with path.open(encoding="utf-8") as stream:
                    return parse(stream.read(LIMIT + 1))
            except FileNotFoundError:
                continue
            except (OSError, ValueError) as error:
                print("Theme: Xsettings retained; " + str(error), file=sys.stderr)
                return None  # Invalid user config must not silently select system defaults.
        return None

    manager = Manager()
    watch = None
    try:
        settings = current()
        if settings is None or not manager.claim():
            print("Theme: existing Xsettings manager/config retained.", file=sys.stderr)
            return 0
        manager.publish(settings, announce=True)
        loop = GLib.MainLoop()

        def changed():
            settings = current()
            if settings is not None and not manager.publish(settings):
                loop.quit()  # Selection transferred: never steal it back.

        def events(_descriptor, condition):
            if condition & (GLib.IO_HUP | GLib.IO_ERR):
                loop.quit()
                return False
            while manager.lib.XPending(manager.display):
                event = Event()
                manager.lib.XNextEvent(manager.display, C.byref(event))
                if event.type == 29:  # SelectionClear
                    loop.quit()
                    return False
            return True

        watch = AppearanceWatch(Gio, GLib, paths, current, changed)
        # Reconcile writes between initial read/claim and watch installation.
        changed()
        descriptor = manager.lib.XConnectionNumber(manager.display)
        GLib.io_add_watch(descriptor, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, events)
        import signal
        for number in (signal.SIGTERM, signal.SIGINT):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, number, lambda: (loop.quit(), False)[1])
        loop.run()
        return 0
    finally:
        if watch:
            watch.close()
        manager.close()


if __name__ == "__main__":
    raise SystemExit(main())
