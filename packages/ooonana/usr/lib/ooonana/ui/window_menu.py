#!/usr/bin/env python3
"""Native, keyboard-accessible window action popup; keeps i3 as window manager."""

import argparse
import subprocess

from common import Gdk, Gtk, Pango, apply_theme, icon


def append_actions(menu, hidden, callback, fullscreen=None):
    """Same native actions in titlebar/legacy and app-group dock menus."""
    for name, glyph, action in (
        ("Restore" if hidden else "Show window", "view-restore-symbolic", "show"),
        ("Minimize", "window-minimize-symbolic", "minimize"),
        ("Toggle fullscreen" if fullscreen is None else "Exit fullscreen" if fullscreen else "Enter fullscreen",
         "view-fullscreen-symbolic", "fullscreen"),
        ("Close window", "window-close-symbolic", "close"),
    ):
        row = Gtk.MenuItem()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.pack_start(icon(glyph), False, False, 0)
        box.pack_start(Gtk.Label(label=name, xalign=0), True, True, 0)
        row.add(box)
        row.get_accessible().set_name(name)
        row.connect("activate", lambda _widget, action=action: callback(action))
        row.set_sensitive(not (hidden and action == "minimize"))
        menu.append(row)


def popup(menu, widget=None, event=None, keyboard=False):
    """GTK flips/clamps native menus at screen edges; no manual pixel offsets."""
    if event is None:
        seat = Gdk.Display.get_default().get_default_seat()
        event = Gdk.Event.new(Gdk.EventType.KEY_PRESS if keyboard else Gdk.EventType.BUTTON_PRESS)
        event.window = Gdk.get_default_root_window()
        event.set_device(seat.get_keyboard() if keyboard else seat.get_pointer())
        if keyboard:
            event.keyval = Gdk.KEY_Menu
        else:
            event.button = 3
        event.time = Gdk.CURRENT_TIME
    menu.show_all()
    if widget is not None:
        menu.popup_at_widget(widget, Gdk.Gravity.NORTH, Gdk.Gravity.SOUTH, event)
    else:
        pointer = Gdk.Display.get_default().get_default_seat().get_pointer()
        _screen, x, y = pointer.get_position()
        anchor = Gdk.Rectangle()
        anchor.x, anchor.y, anchor.width, anchor.height = x, y, 1, 1
        menu.popup_at_rect(Gdk.get_default_root_window(), anchor, Gdk.Gravity.NORTH_WEST,
                           Gdk.Gravity.SOUTH_WEST, event)
    if keyboard:
        menu.select_first(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--title", default="Window")
    parser.add_argument("--hidden", action="store_true")
    parser.add_argument("--keyboard", action="store_true")
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

    def activate(action):
        subprocess.Popen(["ooonana-window-list", "--window-action", action, str(args.window)], start_new_session=True)

    append_actions(menu, args.hidden, activate)
    menu.connect("deactivate", lambda *_: Gtk.main_quit())
    popup(menu, keyboard=args.keyboard)
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
