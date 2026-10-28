#!/usr/bin/env python3
"""Installed icons and real Xcursor/XFixes pixels; no claim about physical DPI."""
import configparser
import ctypes as C
import os
from pathlib import Path
import struct
import sys

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert os.environ.get("OOONANA_GUI_INSTALLED_ONLY") == "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gtk

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
theme = Gtk.IconTheme.get_default()
icons = set()
for desktop in Path("/usr/share/applications").glob("ooonana*.desktop"):
    config = configparser.ConfigParser(interpolation=None)
    config.read(desktop)
    name = config["Desktop Entry"]["Icon"]
    assert not Path(name).is_absolute(), desktop
    for size in (16, 32):
        info = theme.lookup_icon(name, size, Gtk.IconLookupFlags.FORCE_SIZE)
        assert info and Path(info.get_filename()).is_file(), (desktop, name, size)
        image = info.load_icon()
        assert image.get_width() == image.get_height() == size, (name, size)
    icons.add(name)
assert len(icons) >= 10, icons


class CursorImage(C.Structure):
    _fields_ = [(name, C.c_uint) for name in ("version", "size", "width", "height", "xhot", "yhot", "delay")] + [("pixels", C.POINTER(C.c_uint32))]


class FixesImage(C.Structure):
    _fields_ = [("x", C.c_short), ("y", C.c_short)] + [(name, C.c_ushort) for name in ("width", "height", "xhot", "yhot")] + [
        ("serial", C.c_ulong), ("pixels", C.POINTER(C.c_ulong)), ("atom", C.c_ulong), ("name", C.c_char_p)]


x11, cursor, fixes = (C.CDLL(name) for name in ("libX11.so.6", "libXcursor.so.1", "libXfixes.so.3"))
x11.XOpenDisplay.argtypes = [C.c_char_p]; x11.XOpenDisplay.restype = C.c_void_p
x11.XDefaultRootWindow.argtypes = [C.c_void_p]; x11.XDefaultRootWindow.restype = C.c_ulong
x11.XDefineCursor.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong]
x11.XSync.argtypes = [C.c_void_p, C.c_int]
x11.XFree.argtypes = [C.c_void_p]
x11.XFreeCursor.argtypes = [C.c_void_p, C.c_ulong]
x11.XCloseDisplay.argtypes = [C.c_void_p]
cursor.XcursorLibraryLoadImage.argtypes = [C.c_char_p, C.c_char_p, C.c_int]
cursor.XcursorLibraryLoadImage.restype = C.POINTER(CursorImage)
cursor.XcursorImageLoadCursor.argtypes = [C.c_void_p, C.POINTER(CursorImage)]
cursor.XcursorImageLoadCursor.restype = C.c_ulong
cursor.XcursorImageDestroy.argtypes = [C.POINTER(CursorImage)]
fixes.XFixesGetCursorImage.argtypes = [C.c_void_p]
fixes.XFixesGetCursorImage.restype = C.POINTER(FixesImage)
data = Path("/usr/share/icons/OoonanaTailless/cursors/left_ptr").read_bytes()
_, header, _, count = struct.unpack_from("<4I", data)
frames = {}
for index in range(count):
    kind, size, offset = struct.unpack_from("<3I", data, header + index * 12)
    if kind == 0xFFFD0002:
        values = struct.unpack_from("<9I", data, offset)
        width, height, xhot, yhot = values[4:8]
        frames[size] = (width, height, xhot, yhot, list(struct.unpack_from(f"<{width*height}I", data, offset + values[0])))
display = x11.XOpenDisplay(None)
assert display
try:
    for alias in (b"left_ptr", b"default", b"arrow"):
        image = cursor.XcursorLibraryLoadImage(alias, b"OoonanaTailless", 19)
        assert image, alias
        xid = 0
        shown = None
        try:
            loaded = image.contents
            expected = frames[19]
            assert (loaded.width, loaded.height, loaded.xhot, loaded.yhot) == expected[:4]
            assert list(loaded.pixels[:loaded.width * loaded.height]) == expected[4], alias
            xid = cursor.XcursorImageLoadCursor(display, image)
            assert xid
            x11.XDefineCursor(display, x11.XDefaultRootWindow(display), xid)
            x11.XSync(display, False)
            shown = fixes.XFixesGetCursorImage(display)
            assert shown
            actual = shown.contents
            assert (actual.width, actual.height, actual.xhot, actual.yhot) == expected[:4]
            assert [pixel & 0xFFFFFFFF for pixel in actual.pixels[:actual.width * actual.height]] == expected[4]
        finally:
            if shown:
                x11.XFree(shown)
            if xid:
                x11.XFreeCursor(display, xid)
            cursor.XcursorImageDestroy(image)
finally:
    x11.XCloseDisplay(display)
(output / "receipt.txt").write_text(f"Installed icons loaded: {len(icons)}\nXcursor/XFixes: 19x19, hotspot 2,2; left_ptr/default/arrow exact pixels\nPhysical DPI/session cursor inheritance still manual\n")
print("DESKTOP_ASSETS_UI_OK installed icon decoding, Xcursor aliases, actual XFixes dimensions/hotspot/pixels", flush=True)
