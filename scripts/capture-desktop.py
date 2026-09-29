#!/usr/bin/env python3
"""Capture an X11 desktop for visual release checks."""

from __future__ import annotations

import argparse
from pathlib import Path

import gi

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
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
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    pixels.savev(str(output), "png", [], [])
    print(f"{output} ({width}x{height})")


if __name__ == "__main__":
    main()
