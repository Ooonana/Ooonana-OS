#!/usr/bin/env python3
"""Capture an X11 desktop for visual release checks."""

from __future__ import annotations

import argparse
import ctypes
from pathlib import Path

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib  # noqa: E402


class CursorImage(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_short), ("y", ctypes.c_short),
        ("width", ctypes.c_ushort), ("height", ctypes.c_ushort),
        ("xhot", ctypes.c_ushort), ("yhot", ctypes.c_ushort),
        ("serial", ctypes.c_ulong), ("pixels", ctypes.POINTER(ctypes.c_ulong)),
        ("atom", ctypes.c_ulong), ("name", ctypes.c_char_p),
    ]


def capture_cursor():
    x11 = ctypes.CDLL("libX11.so.6")
    fixes = ctypes.CDLL("libXfixes.so.3")
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XFree.argtypes = [ctypes.c_void_p]
    fixes.XFixesGetCursorImage.argtypes = [ctypes.c_void_p]
    fixes.XFixesGetCursorImage.restype = ctypes.POINTER(CursorImage)
    display = x11.XOpenDisplay(None)
    if not display:
        raise SystemExit("Cannot open display for cursor capture.")
    pointer = None
    try:
        pointer = fixes.XFixesGetCursorImage(display)
        if not pointer:
            raise SystemExit("Cannot capture X11 cursor.")
        cursor = pointer.contents
        rgba = bytearray()
        for index in range(cursor.width * cursor.height):
            value = cursor.pixels[index] & 0xFFFFFFFF
            alpha = value >> 24
            channels = [(value >> shift) & 255 for shift in (16, 8, 0)]
            if alpha:
                channels = [min(255, (channel * 255 + alpha // 2) // alpha) for channel in channels]
            rgba.extend((*channels, alpha))
        pixels = GdkPixbuf.Pixbuf.new_from_bytes(
            GLib.Bytes.new(bytes(rgba)), GdkPixbuf.Colorspace.RGB, True, 8,
            cursor.width, cursor.height, cursor.width * 4,
        )
        return pixels, cursor.x - cursor.xhot, cursor.y - cursor.yhot, (cursor.xhot, cursor.yhot)
    finally:
        if pointer:
            x11.XFree(pointer)
        x11.XCloseDisplay(display)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--include-cursor", action="store_true")
    parser.add_argument("--cursor-output", type=Path)
    args = parser.parse_args()

    screen = Gdk.Screen.get_default()
    if screen is None:
        raise SystemExit("No X11 screen. Set DISPLAY to nested i3 display.")
    root = screen.get_root_window()
    if root is None:
        raise SystemExit("No X11 root window.")
    width, height = root.get_width(), root.get_height()
    pixels = Gdk.pixbuf_get_from_window(root, 0, 0, width, height)
    if pixels is None:
        raise SystemExit("Could not capture X11 root window.")
    if args.include_cursor or args.cursor_output:
        cursor, left, top, hotspot = capture_cursor()
        if args.cursor_output:
            cursor_path = args.cursor_output.expanduser().resolve()
            cursor_path.parent.mkdir(parents=True, exist_ok=True)
            cursor.savev(str(cursor_path), "png", [], [])
            print(f"cursor: {cursor.get_width()}x{cursor.get_height()}, hotspot={hotspot}")
        if args.include_cursor:
            x, y = max(0, left), max(0, top)
            cursor_width = min(width, left + cursor.get_width()) - x
            cursor_height = min(height, top + cursor.get_height()) - y
            if cursor_width > 0 and cursor_height > 0:
                cursor.composite(pixels, x, y, cursor_width, cursor_height,
                                 left, top, 1, 1, GdkPixbuf.InterpType.NEAREST, 255)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    pixels.savev(str(output), "png", [], [])
    print(f"{output} ({width}x{height})")


if __name__ == "__main__":
    main()
