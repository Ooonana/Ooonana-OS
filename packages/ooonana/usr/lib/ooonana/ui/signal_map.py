#!/usr/bin/env python3
import hashlib
import math

import cairo  # Registers PyGObject's cairo.Context converter.

from common import Gtk, Pango, PangoCairo, header, label


class SignalMapWindow(Gtk.Window):
    def __init__(self, title, kind="wireless"):
        super().__init__(title=title)
        self.kind = kind
        self.items = []
        self.set_default_size(720, 620)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, title, "Signal map", "find-location-symbolic")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_border_width(14)
        self.add(root)
        heading = label(title, "page-title")
        root.pack_start(heading, False, False, 0)
        root.pack_start(
            label("Computer is center. Distance uses signal strength. Direction is stable layout, not measured bearing.", "muted"),
            False,
            False,
            0,
        )
        self.router_toggle = None
        self.device_toggle = None
        self.legend = label("", "muted")

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        if kind == "wireless":
            self.router_toggle = Gtk.CheckButton.new_with_label("Wi-Fi routers (orange)")
            self.device_toggle = Gtk.CheckButton.new_with_label("Nearby LAN devices (green)")
            controls.pack_start(self.router_toggle, False, False, 0)
            controls.pack_start(self.device_toggle, False, False, 0)
        elif kind == "bluetooth":
            self.device_toggle = Gtk.CheckButton.new_with_label("Nearby Bluetooth devices (blue)")
            controls.pack_start(self.device_toggle, False, False, 0)
        for toggle in (self.router_toggle, self.device_toggle):
            if toggle:
                toggle.set_active(True)
                toggle.connect("toggled", self.filter_changed)
        root.pack_start(controls, False, False, 0)
        root.pack_start(self.legend, False, False, 0)

        self.area = Gtk.DrawingArea()
        self.area.set_size_request(620, 500)
        self.area.connect("draw", self.draw)
        root.pack_start(self.area, True, True, 0)

    def update_items(self, items):
        self.items = list(items)
        self.update_legend()
        self.area.queue_draw()

    def filter_changed(self, _toggle):
        self.update_legend()
        self.area.queue_draw()

    def filtered_items(self):
        visible = []
        for item in self.items:
            category = item.get("category", "router")
            if category == "router" and self.router_toggle and not self.router_toggle.get_active():
                continue
            if category == "device" and self.device_toggle and not self.device_toggle.get_active():
                continue
            visible.append(item)
        return visible

    def update_legend(self):
        routers = sum(item.get("category", "router") == "router" for item in self.items)
        devices = sum(item.get("category") == "device" for item in self.items)
        if self.kind == "wireless":
            self.legend.set_text(f"{routers} router(s) | {devices} known LAN device(s)")
        else:
            self.legend.set_text(f"{devices} Bluetooth device(s)")

    @staticmethod
    def angle_for(key):
        digest = hashlib.sha256(key.encode("utf-8", errors="replace")).digest()
        return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF * math.tau

    @staticmethod
    def draw_text(context, text, x, y, size=11, color=(0.96, 0.92, 0.82)):
        layout = PangoCairo.create_layout(context)
        font = Pango.FontDescription(f"Sans {size}")
        layout.set_font_description(font)
        layout.set_text(str(text), -1)
        context.set_source_rgb(*color)
        context.move_to(x, y)
        PangoCairo.show_layout(context, layout)

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
        self.draw_text(context, "This computer", center_x + 12, center_y - 7)

        for text, x, y in (
            ("N", center_x - 4, center_y - radius - 10),
            ("E", center_x + radius + 12, center_y + 4),
            ("S", center_x - 4, center_y + radius + 20),
            ("W", center_x - radius - 22, center_y + 4),
        ):
            self.draw_text(context, text, x, y - 10, 12, (0.61, 0.66, 0.72))

        ordered = sorted(self.filtered_items(), key=lambda item: int(item.get("signal", 0)), reverse=True)
        for index, item in enumerate(ordered):
            strength = max(0, min(100, int(item.get("signal", 0))))
            key = str(item.get("key") or item.get("name") or "signal")
            angle = self.angle_for(key)
            distance = radius * (0.18 + 0.78 * (1 - strength / 100))
            x = center_x + math.cos(angle) * distance
            y = center_y + math.sin(angle) * distance
            category = item.get("category", "router")
            if self.kind == "bluetooth":
                context.set_source_rgb(0.27, 0.73, 1.0)
            elif category == "device":
                context.set_source_rgb(0.31, 0.86, 0.50)
            else:
                context.set_source_rgb(1.0, 0.70, 0.10)
            context.arc(x, y, 5 + strength / 22, 0, math.tau)
            context.fill()
            if index < 12:
                name = str(item.get("name", key))
                if len(name) > 28:
                    name = name[:25] + "..."
                suffix = f"{strength}%" if item.get("signal_known", True) else "known LAN peer"
                self.draw_text(context, f"{name}  {suffix}", x + 10, y - 7)
        return False
