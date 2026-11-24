#!/usr/bin/env python3
import hashlib
import math

import cairo  # Registers PyGObject's cairo.Context converter.

from common import Gdk, Gtk, Pango, chart_colors, header, label


class SignalMapWindow(Gtk.Window):
    def __init__(self, title, kind="wireless"):
        super().__init__(title=title)
        self.kind = kind
        self.items = []
        self.rows = {}
        self.node_positions = []
        self.router_toggle = None
        self.device_toggle = None
        self.set_default_size(752, 428)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, title, "", "find-location-symbolic")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_border_width(12)
        self.add(root)
        if kind == "wireless":
            self.router_toggle = Gtk.CheckButton.new_with_label("Access points")
            self.device_toggle = Gtk.CheckButton.new_with_label("LAN peers")
            filters = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
            for toggle in (self.router_toggle, self.device_toggle):
                toggle.set_active(True)
                toggle.connect("toggled", self.filter_changed)
                filters.pack_start(toggle, False, False, 0)
            root.pack_start(filters, False, False, 0)

        self.layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.pack_start(self.layout, True, True, 0)
        self.plot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.layout.pack_start(self.plot, False, True, 0)
        self.area = Gtk.DrawingArea()
        self.area.set_size_request(220, 150)
        self.area.set_has_tooltip(True)
        self.area.get_accessible().set_name("Signal plot")
        self.area.connect("query-tooltip", self.query_tooltip)
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.area.connect("button-press-event", self.select_node)
        self.area.connect("draw", self.draw)
        self.plot.pack_start(self.area, True, True, 0)
        self.plot_hint = label("", "muted")
        self.plot.pack_start(self.plot_hint, False, False, 0)

        readings = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.layout.pack_start(readings, True, True, 0)
        readings.pack_start(label("Nearby devices" if kind == "bluetooth" else "Scan results",
                                  "card-title"), False, False, 0)
        self.legend = label("", "muted")
        readings.pack_start(self.legend, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_overlay_scrolling(False)
        scroll.set_min_content_height(92)
        scroll.set_min_content_width(248)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        self.list = Gtk.ListBox()
        self.list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list.set_activate_on_single_click(False)
        self.list.get_accessible().set_name("Signal readings")
        self.list.connect("row-selected", lambda *_: self.area.queue_draw())
        placeholder = label("No results", "muted", xalign=0.5)
        placeholder.set_margin_top(10)
        placeholder.show()
        self.list.set_placeholder(placeholder)
        scroll.add(self.list)
        readings.pack_start(scroll, True, True, 0)
        self.connect("size-allocate", self.resize_layout)
        self.update_readings()

    def resize_layout(self, _window, allocation):
        spread = allocation.width >= 610
        orientation = Gtk.Orientation.HORIZONTAL if spread else Gtk.Orientation.VERTICAL
        if self.layout.get_orientation() != orientation:
            self.layout.set_orientation(orientation)
            self.layout.set_homogeneous(spread)
            self.layout.set_child_packing(self.plot, spread, True, 0, Gtk.PackType.START)

    def update_items(self, items):
        self.items = [dict(item, key=item.get("key") or item.get("name") or "signal") for item in items]
        self.update_readings()

    def filter_changed(self, _toggle):
        self.update_readings()

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

    @staticmethod
    def strength(item):
        if not item.get("signal_known", True) or item.get("signal") is None:
            return None
        return max(0, min(100, int(item["signal"])))

    @classmethod
    def signal_text(cls, item):
        strength = cls.strength(item)
        if item.get("lan_peer"):
            return "LAN peer"
        if strength is None:
            return "No reading"
        if item.get("rssi") is not None:
            return f"{item['rssi']} dBm"
        return f"{strength}%"

    @classmethod
    def item_text(cls, item):
        name = item.get("name") or item.get("key") or "Device"
        return " · ".join(part for part in (name, item.get("detail"), cls.signal_text(item)) if part)

    @classmethod
    def reading_order(cls, item):
        strength = cls.strength(item)
        return (not item.get("connected"), strength is None, -(strength or 0),
                (item.get("name") or "").casefold())

    def update_readings(self):
        selected = self.list.get_selected_row()
        key = selected.key if selected else None
        items = sorted(self.filtered_items(), key=self.reading_order)
        self.measured = [item for item in items if self.strength(item) is not None]
        for row in self.rows.values():
            self.list.remove(row)
        self.rows.clear()
        for item in items:
            self.add_reading(item)
        if key in self.rows:
            self.list.select_row(self.rows[key])

        if self.kind == "wireless":
            routers = sum(item.get("category", "router") == "router" for item in items)
            peers = len(items) - routers
            count = f"{routers} {'access point' if routers == 1 else 'access points'} · {peers} LAN {'peer' if peers == 1 else 'peers'}"
        else:
            count = f"{len(items)} {'device' if len(items) == 1 else 'devices'} · {len(self.measured)} with signal readings"
        self.legend.set_text(count)
        if self.measured:
            hint = "Stronger signals sit inward. Angles are illustrative."
        elif items:
            hint = "No radio readings for these devices."
        elif self.items:
            hint = "Choose a filter to show results."
        else:
            hint = "Scan for nearby devices and networks."
        self.plot_hint.set_text(hint)
        self.area.get_accessible().set_description(hint)
        self.area.queue_draw()

    def add_reading(self, item):
        key = item["key"]
        row = Gtk.ListBoxRow()
        row.key = key
        row.set_tooltip_text(self.item_text(item))
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        line.set_border_width(5)
        line.set_margin_start(3)
        line.set_margin_end(3)
        identity = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        line.pack_start(identity, True, True, 0)
        name = label(item.get("name") or key, wrap=False)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        identity.pack_start(name, False, False, 0)
        if item.get("detail"):
            detail = label(item["detail"], "muted", wrap=False)
            detail.set_ellipsize(Pango.EllipsizeMode.END)
            identity.pack_start(detail, False, False, 0)
        reading = label(self.signal_text(item), "status-good" if item.get("connected") else "muted",
                        xalign=1, wrap=False)
        line.pack_end(reading, False, False, 0)
        row.add(line)
        self.rows[key] = row
        self.list.add(row)
        row.show_all()

    def node_at(self, x, y):
        return next((item for px, py, radius, item in reversed(self.node_positions)
                     if (x - px) ** 2 + (y - py) ** 2 <= (radius + 5) ** 2), None)

    def query_tooltip(self, _area, x, y, keyboard, tooltip):
        node = None if keyboard else self.node_at(x, y)
        if node:
            tooltip.set_text(self.item_text(node))
        return node is not None

    def select_node(self, _area, event):
        item = self.node_at(event.x, event.y) if event.button == 1 else None
        if not item:
            return False
        row = self.rows[item["key"]]
        self.list.select_row(row)
        row.grab_focus()
        return True

    @staticmethod
    def angle_for(key):
        digest = hashlib.sha256(key.encode("utf-8", errors="replace")).digest()
        return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF * math.tau

    @staticmethod
    def draw_card(context, width, height):
        radius = 10
        for x, y, start in ((width - radius, radius, -0.25),
                            (width - radius, height - radius, 0),
                            (radius, height - radius, 0.25),
                            (radius, radius, 0.5)):
            context.arc(x, y, radius - 0.5, start * math.tau, (start + 0.25) * math.tau)
        context.close_path()

    def draw(self, widget, context):
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        cx, cy = width / 2, height / 2
        radius = max(1, min(cx, cy) - 18)
        colors = chart_colors()
        self.draw_card(context, width, height)
        context.set_source_rgb(*colors["background"])
        context.fill_preserve()
        context.set_source_rgb(*colors["grid"])
        context.set_line_width(1)
        context.stroke()
        if self.measured:
            for fraction in (0.3, 0.6, 0.9):
                context.arc(cx, cy, radius * fraction, 0, math.tau)
                context.stroke()
        context.set_source_rgb(*colors["muted"])
        context.arc(cx, cy, 3, 0, math.tau)
        context.fill()

        selected = self.list.get_selected_row()
        self.node_positions = []
        selected_key = selected.key if selected else None
        for item in sorted(self.measured, key=lambda candidate: candidate["key"] == selected_key):
            key = item["key"]
            angle = self.angle_for(key)
            distance = radius * (0.16 + 0.79 * (1 - self.strength(item) / 100))
            x, y = cx + math.cos(angle) * distance, cy + math.sin(angle) * distance
            color = colors["blue" if self.kind == "bluetooth" else "accent"]
            if selected and selected.key == key:
                context.set_source_rgb(*colors["text"])
                context.arc(x, y, 9, 0, math.tau)
                context.stroke()
            elif item.get("connected"):
                context.set_source_rgb(*colors["green"])
                context.arc(x, y, 8, 0, math.tau)
                context.stroke()
            context.set_source_rgb(*color)
            context.arc(x, y, 4.5, 0, math.tau)
            context.fill()
            self.node_positions.append((x, y, 4.5, item))
        return False
