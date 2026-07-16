#!/usr/bin/env python3
import hashlib
import math

import cairo  # Registers PyGObject's cairo.Context converter.

from common import Gtk, label


class SignalMapWindow(Gtk.Window):
    def __init__(self, title, kind="wireless"):
        super().__init__(title=title)
        self.kind = kind
        self.items = []
        self.set_default_size(720, 620)
        self.set_position(Gtk.WindowPosition.CENTER)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_border_width(14)
        self.add(root)
        heading = label(title, "page-title")
        root.pack_start(heading, False, False, 0)
        root.pack_start(
            label("Estimated proximity from signal strength. Direction is a stable layout, not measured position.", "muted"),
            False,
            False,
            0,
        )
        self.area = Gtk.DrawingArea()
        self.area.set_size_request(620, 500)
        self.area.connect("draw", self.draw)
        root.pack_start(self.area, True, True, 0)

    def update_items(self, items):
        self.items = list(items)
        self.area.queue_draw()

    @staticmethod
    def angle_for(key):
        digest = hashlib.sha256(key.encode("utf-8", errors="replace")).digest()
        return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF * math.tau

    def draw(self, widget, context):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        center_x, center_y = width / 2, height / 2
        radius = max(50, min(width, height) / 2 - 42)

        context.set_source_rgb(0.03, 0.04, 0.05)
        context.paint()
        context.set_line_width(1)
        for ring in (0.25, 0.5, 0.75, 1.0):
            context.set_source_rgba(1.0, 0.70, 0.10, 0.24)
            context.arc(center_x, center_y, radius * ring, 0, math.tau)
            context.stroke()
        context.move_to(center_x - radius, center_y)
        context.line_to(center_x + radius, center_y)
        context.move_to(center_x, center_y - radius)
        context.line_to(center_x, center_y + radius)
        context.stroke()

        context.set_source_rgb(1.0, 0.70, 0.10)
        context.arc(center_x, center_y, 7, 0, math.tau)
        context.fill()

        ordered = sorted(self.items, key=lambda item: int(item.get("signal", 0)), reverse=True)
        for index, item in enumerate(ordered):
            strength = max(0, min(100, int(item.get("signal", 0))))
            key = str(item.get("key") or item.get("name") or "signal")
            angle = self.angle_for(key)
            distance = radius * (0.18 + 0.78 * (1 - strength / 100))
            x = center_x + math.cos(angle) * distance
            y = center_y + math.sin(angle) * distance
            if self.kind == "bluetooth":
                context.set_source_rgb(0.27, 0.73, 1.0)
            else:
                context.set_source_rgb(1.0, 0.70, 0.10)
            context.arc(x, y, 5 + strength / 22, 0, math.tau)
            context.fill()
            if index < 12:
                name = str(item.get("name", key))
                if len(name) > 28:
                    name = name[:25] + "..."
                context.set_source_rgb(0.96, 0.92, 0.82)
                context.set_font_size(11)
                context.move_to(x + 10, y + 4)
                context.show_text(f"{name}  {strength}%")
        return False
