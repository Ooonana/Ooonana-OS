"""Passive XInput2 button observer. No input grabs, keyboard events or recording."""
import ctypes as C
from gi.repository import GLib


class Cookie(C.Structure):
    _fields_ = [("type", C.c_int), ("serial", C.c_ulong), ("send_event", C.c_int),
               ("display", C.c_void_p), ("extension", C.c_int), ("evtype", C.c_int),
               ("cookie", C.c_uint), ("data", C.c_void_p)]


class Event(C.Union):
    _fields_ = [("cookie", Cookie), ("padding", C.c_long * 24)]


class Mask(C.Structure):
    _fields_ = [("deviceid", C.c_int), ("mask_len", C.c_int), ("mask", C.POINTER(C.c_ubyte))]


class ButtonWatch:
    def __init__(self, callback):
        self.display, self.watch, self.callback = None, 0, callback
        self.lib, self.xi = C.CDLL("libX11.so.6"), C.CDLL("libXi.so.6")
        signatures = {
            "XOpenDisplay": ([C.c_char_p], C.c_void_p),
            "XCloseDisplay": ([C.c_void_p], C.c_int),
            "XDefaultRootWindow": ([C.c_void_p], C.c_ulong),
            "XQueryExtension": ([C.c_void_p, C.c_char_p] + [C.POINTER(C.c_int)] * 3, C.c_int),
            "XConnectionNumber": ([C.c_void_p], C.c_int),
            "XPending": ([C.c_void_p], C.c_int),
            "XNextEvent": ([C.c_void_p, C.POINTER(Event)], C.c_int),
            "XFlush": ([C.c_void_p], C.c_int),
            "XGetEventData": ([C.c_void_p, C.POINTER(Cookie)], C.c_int),
            "XFreeEventData": ([C.c_void_p, C.POINTER(Cookie)], None),
        }
        for name, (arguments, result) in signatures.items():
            method = getattr(self.lib, name)
            method.argtypes, method.restype = arguments, result
        self.xi.XIQueryVersion.argtypes = [C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_int)]
        self.xi.XISelectEvents.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(Mask), C.c_int]
        self.display = self.lib.XOpenDisplay(None)
        if not self.display:
            raise OSError("Flyout pointer connection unavailable")
        opcode, first_event, error = C.c_int(), C.c_int(), C.c_int()
        major, minor = C.c_int(2), C.c_int(0)
        if not self.lib.XQueryExtension(self.display, b"XInputExtension", C.byref(opcode), C.byref(first_event), C.byref(error)) or self.xi.XIQueryVersion(self.display, C.byref(major), C.byref(minor)):
            self.close()
            raise OSError("Flyout pointer requires XInput2")
        self.opcode = opcode.value
        bits = (C.c_ubyte * 2)(0, 1 << 7)  # XI_RawButtonPress = 15.
        mask = Mask(1, 2, bits)  # XIAllMasterDevices, one event per logical click.
        self.xi.XISelectEvents(self.display, self.lib.XDefaultRootWindow(self.display), C.byref(mask), 1)
        self.lib.XFlush(self.display)
        self.watch = GLib.io_add_watch(self.lib.XConnectionNumber(self.display), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.events)

    def events(self, _fd, condition):
        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            self.watch = 0
            self.close()
            return False
        while self.display and self.lib.XPending(self.display):
            event = Event()
            self.lib.XNextEvent(self.display, C.byref(event))
            cookie = event.cookie
            if cookie.type == 35 and cookie.extension == self.opcode and self.lib.XGetEventData(self.display, C.byref(cookie)):
                try:
                    if cookie.evtype == 15:
                        self.callback()
                finally:
                    self.lib.XFreeEventData(self.display, C.byref(cookie))
        return True

    def close(self):
        if self.watch:
            GLib.source_remove(self.watch)
            self.watch = 0
        if self.display:
            self.lib.XCloseDisplay(self.display)
            self.display = None
