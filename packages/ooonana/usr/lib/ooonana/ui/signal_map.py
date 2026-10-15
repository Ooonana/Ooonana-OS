#!/usr/bin/env python3
import hashlib
import math

import cairo  # Registers PyGObject's cairo.Context converter.

from common import Gtk, Pango, PangoCairo, chart_colors, flow_row, header, label


class SignalMapWindow(Gtk.Window):
    def __init__(self, title, kind="wireless"):
        super().__init__(title=title)
        self.kind = kind
        self.items = []
        self.set_default_size(720, 560)
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

        toggles = []
        if kind == "wireless":
            self.router_toggle = Gtk.CheckButton.new_with_label("Wi-Fi routers (orange)")
            self.device_toggle = Gtk.CheckButton.new_with_label("Nearby LAN devices (green)")
            toggles.extend((self.router_toggle, self.device_toggle))
        elif kind == "bluetooth":
            self.device_toggle = Gtk.CheckButton.new_with_label("Nearby Bluetooth devices (blue)")
            toggles.append(self.device_toggle)
        for toggle in (self.router_toggle, self.device_toggle):
            if toggle:
                toggle.set_active(True)
                toggle.connect("toggled", self.filter_changed)
        root.pack_start(flow_row(toggles, max_children=2, min_children=1), False, False, 0)
        root.pack_start(self.legend, False, False, 0)

        self.area = Gtk.DrawingArea()
        self.area.set_size_request(240, 180)
        self.area.set_hexpand(True)
        self.area.set_vexpand(True)
        self.area.set_can_focus(True)
        self.area.set_has_tooltip(True)
        self.area.get_accessible().set_name("Nearby devices signal map")
        self.area.connect("query-tooltip", self.query_tooltip)
        self.node_positions = []
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
            self.legend.set_text(f"{routers} {'router' if routers == 1 else 'routers'} | "
                                 f"{devices} known LAN {'device' if devices == 1 else 'devices'}")
        else:
            self.legend.set_text(f"{devices} Bluetooth {'device' if devices == 1 else 'devices'}")
        self.area.get_accessible().set_description("\n".join(self.item_text(item) for item in self.filtered_items())
                                                   or "No devices. Scan from Wi-Fi or Bluetooth.")

    @staticmethod
    def item_text(item):
        name = str(item.get("name") or item.get("key") or "Device")
        strength = max(0, min(100, int(item.get("signal", 0))))
        suffix = f"{strength}%" if item.get("signal_known", True) else "known LAN peer"
        return f"{name}  {suffix}"

    def query_tooltip(self, _area, x, y, keyboard, tooltip):
        if keyboard:
            text = "\n".join(self.item_text(item) for item in self.filtered_items()[:12])
        else:
            node = next((item for px, py, radius, item in reversed(self.node_positions)
                         if (x - px) ** 2 + (y - py) ** 2 <= (radius + 8) ** 2), None)
            text = self.item_text(node) if node else ""
        if text:
            tooltip.set_text(text)
        return bool(text)

    @staticmethod
    def angle_for(key):
        digest = hashlib.sha256(key.encode("utf-8", errors="replace")).digest()
        return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF * math.tau

    @staticmethod
    def draw_text(context, text, x, y, size=11, color=(0.96, 0.92, 0.82), max_width=None, occupied=None, bounds=None):
        layout = PangoCairo.create_layout(context)
        font = Pango.FontDescription(f"Sans {size}")
        layout.set_font_description(font)
        layout.set_text(str(text), -1)
        layout.set_single_paragraph_mode(True)
        text_width, text_height = layout.get_pixel_size()
        if max_width is not None and text_width > max_width:
            layout.set_width(max(1, int(max_width)) * Pango.SCALE)
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            text_width, text_height = layout.get_pixel_size()
        if bounds:
            position = SignalMapWindow.label_position(*bounds, x, y, text_width, text_height, occupied or [])
            if position is None:
                return None
            x, y = position
        context.set_source_rgb(*color)
        context.move_to(x, y)
        PangoCairo.show_layout(context, layout)
        return x, y, text_width, text_height

    @staticmethod
    def label_position(width, height, x, y, text_width, text_height, occupied):
        # Try both sides and nearby rows. Never clip or paint over another label.
        if text_width + 16 > width or text_height + 16 > height:
            return None
        for offset in (0, text_height + 8, -text_height - 8, 2 * (text_height + 8), -2 * (text_height + 8)):
            for candidate_x in (x + 12, x - text_width - 12):
                left = max(8, min(candidate_x, width - text_width - 8))
                top = max(8, min(y - text_height / 2 + offset, height - text_height - 8))
                if all(left + text_width + 4 <= ox or ox + ow + 4 <= left or
                       top + text_height + 4 <= oy or oy + oh + 4 <= top
                       for ox, oy, ow, oh in occupied):
                    return left, top
        return None

    def draw(self, widget, context):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        center_x, center_y = width / 2, height / 2
        radius = max(50, min(width, height) / 2 - 42)

        colors = chart_colors()
        context.set_source_rgb(*colors["background"])
        context.paint()
        context.set_line_width(1)
        for ring in (0.25, 0.5, 0.75, 1.0):
            context.set_source_rgb(*colors["grid"])
            context.arc(center_x, center_y, radius * ring, 0, math.tau)
            context.stroke()
        context.move_to(center_x - radius, center_y)
        context.line_to(center_x + radius, center_y)
        context.move_to(center_x, center_y - radius)
        context.line_to(center_x, center_y + radius)
        context.stroke()

        context.set_source_rgb(*colors["accent"])
        context.arc(center_x, center_y, 7, 0, math.tau)
        context.fill()
        ordered = sorted(self.filtered_items(), key=lambda item: int(item.get("signal", 0)), reverse=True)
        self.node_positions = []
        for item in ordered:
            strength = max(0, min(100, int(item.get("signal", 0))))
            key = str(item.get("key") or item.get("name") or "signal")
            angle = self.angle_for(key)
            distance = radius * (0.18 + 0.78 * (1 - strength / 100))
            x = center_x + math.cos(angle) * distance
            y = center_y + math.sin(angle) * distance
            category = item.get("category", "router")
            if self.kind == "bluetooth":
                context.set_source_rgb(*colors["blue"])
            elif category == "device":
                context.set_source_rgb(*colors["green"])
            else:
                context.set_source_rgb(*colors["accent"])
            node_radius = 5 + strength / 22
            context.arc(x, y, node_radius, 0, math.tau)
            context.fill()
            self.node_positions.append((x, y, node_radius, item))
        occupied = [(x - radius - 2, y - radius - 2, 2 * radius + 4, 2 * radius + 4)
                    for x, y, radius, _item in self.node_positions]
        own_label = self.draw_text(context, "This computer", center_x, center_y, color=colors["text"],
                                   max_width=width - 24, occupied=occupied, bounds=(width, height))
        if own_label:
            occupied.append(own_label)
        for x, y, _radius, item in self.node_positions[:12]:
            rectangle = self.draw_text(context, self.item_text(item), x, y, color=colors["text"],
                                       max_width=min(260, width - 24), occupied=occupied, bounds=(width, height))
            if rectangle:
                occupied.append(rectangle)
        if not ordered:
            self.draw_text(context, "Scan in Wi-Fi or Bluetooth to show nearby devices.",
                           12, height - 26, color=colors["muted"], max_width=width - 24)
        return False
