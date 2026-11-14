"""Handle horizontal three-finger swipes that X11 apps leave to the desktop."""

import ctypes as C
import math


class GenericCookie(C.Structure):
    _fields_ = [
        ("type", C.c_int), ("serial", C.c_ulong), ("send_event", C.c_int),
        ("display", C.c_void_p), ("extension", C.c_int), ("evtype", C.c_int),
        ("cookie", C.c_uint), ("data", C.c_void_p),
    ]


class XEvent(C.Union):
    _fields_ = [("type", C.c_int), ("cookie", GenericCookie), ("pad", C.c_long * 24)]


class SwipeEvent(C.Structure):
    # XIGestureSwipeEvent up to and including its cancellation flags.
    _fields_ = GenericCookie._fields_[:6] + [
        ("time", C.c_ulong), ("deviceid", C.c_int), ("sourceid", C.c_int),
        ("fingers", C.c_int), ("root", C.c_ulong), ("event", C.c_ulong), ("child", C.c_ulong),
        ("root_x", C.c_double), ("root_y", C.c_double), ("event_x", C.c_double),
        ("event_y", C.c_double), ("delta_x", C.c_double), ("delta_y", C.c_double),
        ("unaccelerated_x", C.c_double), ("unaccelerated_y", C.c_double), ("flags", C.c_int),
    ]


class XIEventMask(C.Structure):
    _fields_ = [("deviceid", C.c_int), ("mask_len", C.c_int), ("mask", C.c_void_p)]


# XInput 2.4 event IDs from XI2.h.
SWIPE_BEGIN, SWIPE_UPDATE, SWIPE_END = 30, 31, 32
GENERIC_EVENT = 35
SWIPE_CANCELLED = 1


class WorkspaceSwipe:
    def __init__(self):
        self.active = {}

    def feed(self, event):
        source = event.sourceid
        if event.evtype == SWIPE_BEGIN:
            self.active.pop(source, None)
            if event.fingers == 3:
                self.active[source] = (0.0, 0.0)
        elif event.evtype == SWIPE_UPDATE and source in self.active:
            if event.fingers != 3:
                self.active.pop(source)
            else:
                x, y = self.active[source]
                self.active[source] = (x + event.delta_x, y + event.delta_y)
        elif event.evtype == SWIPE_END:
            total = self.active.pop(source, None)
            if total is not None and event.fingers == 3 and not event.flags & SWIPE_CANCELLED:
                x, y = total
                if math.isfinite(x) and math.isfinite(y) and abs(x) >= 60 and abs(x) >= 1.5 * abs(y):
                    return "next_on_output" if x < 0 else "prev_on_output"
        return None


def subscribe(xlib, display, root):
    ints = C.POINTER(C.c_int)
    xlib.XQueryExtension.argtypes = [C.c_void_p, C.c_char_p, ints, ints, ints]
    opcode, event_base, error_base = C.c_int(), C.c_int(), C.c_int()
    if not xlib.XQueryExtension(display, b"XInputExtension", C.byref(opcode),
                                C.byref(event_base), C.byref(error_base)):
        return 0
    try:
        xi = C.CDLL("libXi.so.6")
    except OSError:
        return 0
    xi.XIQueryVersion.argtypes = [C.c_void_p, ints, ints]
    major, minor = C.c_int(2), C.c_int(4)
    if xi.XIQueryVersion(display, C.byref(major), C.byref(minor)) or (major.value, minor.value) < (2, 4):
        return 0
    data = (C.c_ubyte * 5)()
    for event in (SWIPE_BEGIN, SWIPE_UPDATE, SWIPE_END):
        data[event // 8] |= 1 << event % 8
    mask = XIEventMask(1, len(data), C.cast(data, C.c_void_p))  # XIAllMasterDevices
    xi.XISelectEvents.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(XIEventMask), C.c_int]
    if xi.XISelectEvents(display, root, C.byref(mask), 1):
        return 0
    xlib.XGetEventData.argtypes = [C.c_void_p, C.POINTER(GenericCookie)]
    xlib.XGetEventData.restype = C.c_int
    xlib.XFreeEventData.argtypes = [C.c_void_p, C.POINTER(GenericCookie)]
    xlib.XFreeEventData.restype = None
    return opcode.value


def swipe_direction(xlib, display, cookie, swipe):
    if (cookie.send_event or cookie.evtype not in (SWIPE_BEGIN, SWIPE_UPDATE, SWIPE_END)
            or not xlib.XGetEventData(display, C.byref(cookie))):
        return None
    try:
        return swipe.feed(C.cast(cookie.data, C.POINTER(SwipeEvent)).contents)
    finally:
        xlib.XFreeEventData(display, C.byref(cookie))
