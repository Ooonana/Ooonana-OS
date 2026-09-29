#!/usr/bin/env python3
"""Click one coordinate inside a test X11 display; never uses host desktop."""

from __future__ import annotations

import argparse
import ctypes
import os


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("x", type=int)
    parser.add_argument("y", type=int)
    parser.add_argument("--button", type=int, default=1)
    args = parser.parse_args()

    display_name = os.environ.get("DISPLAY", "")
    if not display_name.startswith(":") or display_name == ":0":
        raise SystemExit("Set DISPLAY to nested test display, not WSLg :0.")

    x11 = ctypes.CDLL("libX11.so.6")
    xtst = ctypes.CDLL("libXtst.so.6")
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    display = x11.XOpenDisplay(display_name.encode())
    if not display:
        raise SystemExit("Cannot open nested X11 display.")
    xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
    xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xtst.XTestFakeMotionEvent(display, -1, args.x, args.y, 0)
    xtst.XTestFakeButtonEvent(display, args.button, 1, 0)
    xtst.XTestFakeButtonEvent(display, args.button, 0, 0)
    x11.XSync(display, 0)
    x11.XCloseDisplay(display)


if __name__ == "__main__":
    main()
