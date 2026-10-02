#!/usr/bin/env python3
"""Native, keyboard-accessible window action popup; keeps i3 as window manager."""

import argparse
import subprocess

from common import Gdk, Gtk, Pango, apply_theme, icon


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--title", default="Window")
    parser.add_argument("--hidden", action="store_true")
    args = parser.parse_args()
    if args.window <= 0:
        return 2
    apply_theme()
    menu = Gtk.Menu()
    title = Gtk.MenuItem.new_with_label(args.title[:60])
    title.get_child().set_max_width_chars(28)
    title.get_child().set_ellipsize(Pango.EllipsizeMode.END)
    title.set_tooltip_text(args.title[:256])
    title.set_sensitive(False)
    menu.append(title)
    menu.append(Gtk.SeparatorMenuItem())

    def activate(_widget, action):
        subprocess.Popen(["ooonana-window-list", "--window-action", action, str(args.window)], start_new_session=True)

    for name, glyph, action in (
        ("Restore" if args.hidden else "Show window", "view-restore-symbolic", "show"),
        ("Minimize", "window-minimize-symbolic", "minimize"),
        ("Toggle fullscreen", "view-fullscreen-symbolic", "fullscreen"),
        ("Close window", "window-close-symbolic", "close"),
    ):
        row = Gtk.MenuItem()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.pack_start(icon(glyph), False, False, 0)
        box.pack_start(Gtk.Label(label=name, xalign=0), True, True, 0)
        row.add(box)
        row.connect("activate", activate, action)
        menu.append(row)
    menu.connect("deactivate", lambda *_: Gtk.main_quit())
    menu.show_all()
    pointer = Gdk.Display.get_default().get_default_seat().get_pointer()
    _screen, x, y = pointer.get_position()
    anchor = Gdk.Rectangle()
    anchor.x, anchor.y, anchor.width, anchor.height = x, y, 1, 1
    trigger = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
    trigger.window = Gdk.get_default_root_window()
    trigger.set_device(pointer)
    trigger.button = 3
    trigger.time = Gdk.CURRENT_TIME
    menu.popup_at_rect(Gdk.get_default_root_window(), anchor, Gdk.Gravity.NORTH_WEST, Gdk.Gravity.SOUTH_WEST, trigger)
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
