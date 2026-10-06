#!/usr/bin/env python3
"""Native, read-only-by-default Ooonana Task Manager."""

from __future__ import annotations

import os
import pwd
import signal
import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Gdk, GLib, Gtk, Pango, apply_theme, button, header, label, message  # noqa: E402


def read_text(path: Path, limit: int = 65536) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            return stream.read(limit)
    except (OSError, ValueError):
        return ""


def read_number(path: Path) -> int | None:
    try:
        return int(read_text(path).strip())
    except ValueError:
        return None


def meminfo_values(text: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        key, _, raw = line.partition(":")
        if not raw:
            continue
        try:
            values[key] = int(raw.strip().split()[0])
        except (IndexError, ValueError):
            continue
    return values


def zram_consumption(base=Path("/sys/block")):
    original = compressed = physical = 0
    for device in base.glob("zram*"):
        try:
            values = list(map(int, read_text(device / "mm_stat").split()))
            original += values[0]
            compressed += values[1]
            physical += values[2]
        except (IndexError, ValueError):
            continue
    return original, compressed, physical


def cpu_totals(text: str) -> tuple[int, int] | None:
    first = text.splitlines()[0] if text else ""
    fields = first.split()
    if not fields or fields[0] != "cpu" or len(fields) < 6:
        return None
    try:
        counters = [int(value) for value in fields[1:]]
    except ValueError:
        return None
    if any(counter < 0 for counter in counters):
        return None
    # Guest/guest-nice already contribute to user/nice; count them once.
    return sum(counters[:8]), counters[3] + counters[4]


def parse_process_stat(text: str) -> tuple[str, int, int] | None:
    end = text.rfind(")")
    if end < 0:
        return None
    fields = text[end + 1 :].split()
    if len(fields) < 20:
        return None
    try:
        return fields[0], int(fields[11]) + int(fields[12]), int(fields[19])
    except ValueError:
        return None


def human_rate(value: float) -> str:
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MiB/s"
    if value >= 1024:
        return f"{value / 1024:.0f} KiB/s"
    return f"{value:.0f} B/s"


def disk_bytes() -> tuple[int, int]:
    reads = writes = 0
    for device in Path("/sys/block").glob("*"):
        if device.name.startswith(("loop", "ram", "zram", "dm-", "md", "sr")):
            continue
        fields = read_text(device / "stat").split()
        if len(fields) < 7:
            continue
        try:
            reads += int(fields[2]) * 512
            writes += int(fields[6]) * 512
        except ValueError:
            continue
    return reads, writes


def network_bytes(base: Path = Path("/sys/class/net")) -> tuple[str, int, int] | None:
    devices = []
    for device in base.glob("*"):
        if device.name == "lo":
            continue
        state = read_text(device / "operstate").strip()
        carrier = read_number(device / "carrier")
        if state in {"down", "lowerlayerdown", "notpresent", "dormant", "testing"} or carrier == 0:
            continue
        devices.append((state == "up" or carrier == 1, device))
    devices.sort(key=lambda item: (not item[0], not (item[1] / "wireless").exists(), item[1].name))
    for _active, device in devices:
        rx = read_number(device / "statistics/rx_bytes")
        tx = read_number(device / "statistics/tx_bytes")
        if rx is not None and tx is not None and rx >= 0 and tx >= 0:
            return device.name, rx, tx
    return None


def gpu_busy() -> tuple[str, float | None]:
    for card in sorted(Path("/sys/class/drm").glob("card[0-9]*")):
        vendor = read_text(card / "device/vendor").strip().lower()
        name = {"0x8086": "Intel GPU", "0x1002": "AMD GPU", "0x10de": "NVIDIA GPU"}.get(vendor, card.name)
        busy = read_number(card / "device/gpu_busy_percent")
        if busy is not None:
            return name, float(max(0, min(100, busy)))
        if vendor:
            return name, None
    return "GPU", None


def root_storage() -> tuple[int, int] | None:
    try:
        stat = os.statvfs("/")
    except OSError:
        return None
    total = stat.f_blocks * stat.f_frsize
    available = stat.f_bavail * stat.f_frsize
    return total, available


def thermal_fan_snapshot(
    hwmon_root: Path = Path("/sys/class/hwmon"),
    thermal_root: Path = Path("/sys/class/thermal"),
) -> tuple[str, str]:
    """Read exposed sensors only; never touch fan control or PWM nodes."""
    temperatures: list[tuple[int, str, float]] = []
    fans: list[tuple[str, int]] = []
    for chip in sorted(hwmon_root.glob("hwmon*")):
        chip_name = read_text(chip / "name").strip()
        for sensor in chip.glob("temp*_input"):
            raw = read_number(sensor)
            if raw is None or not -50000 <= raw <= 200000:
                continue
            label_text = read_text(sensor.with_name(sensor.name.replace("_input", "_label"))).strip()
            title = label_text or chip_name or sensor.stem
            priority = 0 if any(word in title.casefold() for word in ("package", "tctl", "cpu")) else 1
            temperatures.append((priority, title, raw / 1000))
        for sensor in chip.glob("fan*_input"):
            rpm = read_number(sensor)
            if rpm is None or rpm < 0:
                continue
            label_text = read_text(sensor.with_name(sensor.name.replace("_input", "_label"))).strip()
            fans.append((label_text or chip_name or sensor.stem, rpm))
    if not temperatures:
        for zone in sorted(thermal_root.glob("thermal_zone*")):
            title = read_text(zone / "type").strip()
            if "cpu" not in title.casefold() and "x86_pkg_temp" not in title.casefold():
                continue
            raw = read_number(zone / "temp")
            if raw is not None and -50000 <= raw <= 200000:
                temperatures.append((0, title, raw / 1000))
    temperatures.sort(key=lambda item: (item[0], item[1]))
    fans.sort(key=lambda item: item[0])
    temp_text = f"{temperatures[0][1]} {temperatures[0][2]:.0f}°C" if temperatures else "Temp unavailable"
    fan_text = f"{fans[0][0]} {fans[0][1]} RPM" if fans else "Fan unavailable"
    return temp_text, fan_text


class MetricCard(Gtk.Box):
    def __init__(self, title: str, percent_scale: bool = True):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.get_style_context().add_class("card")
        self.set_hexpand(True)
        self.percent_scale = percent_scale
        self.history: deque[float] = deque(maxlen=60)
        self.pack_start(label(title, "card-title"), False, False, 0)
        self.value = label("Checking...", "muted")
        self.pack_start(self.value, False, False, 0)
        self.progress = Gtk.ProgressBar()
        self.pack_start(self.progress, False, False, 0)
        self.chart = Gtk.DrawingArea()
        display = Gdk.Display.get_default()
        monitor = (display.get_primary_monitor() or display.get_monitor(0)) if display else None
        self.chart.set_size_request(-1, 40 if monitor and monitor.get_geometry().height <= 800 else 54)
        self.chart.connect("draw", self.draw_chart)
        self.pack_start(self.chart, True, True, 0)

    def update(self, text: str, sample: float | None) -> None:
        self.value.set_text(text)
        if sample is not None:
            self.history.append(max(0.0, sample))
        peak = 100.0 if self.percent_scale else max(1.0, max(self.history, default=0.0))
        self.progress.set_fraction(min(1.0, max(0.0, (sample or 0.0) / peak)))
        self.chart.queue_draw()

    def draw_chart(self, area: Gtk.DrawingArea, cr) -> bool:
        width = area.get_allocated_width()
        height = area.get_allocated_height()
        cr.set_source_rgb(0.10, 0.12, 0.15)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        cr.set_source_rgb(0.22, 0.25, 0.29)
        for fraction in (0.25, 0.5, 0.75):
            y = height * fraction
            cr.move_to(0, y)
            cr.line_to(width, y)
        cr.set_line_width(1)
        cr.stroke()
        if len(self.history) < 2:
            return False
        peak = 100.0 if self.percent_scale else max(1.0, max(self.history))
        cr.set_source_rgb(1.0, 0.70, 0.10)
        cr.set_line_width(2)
        values = list(self.history)
        for index, value in enumerate(values):
            x = index * max(1, width - 2) / max(1, len(values) - 1) + 1
            y = height - 2 - min(1.0, value / peak) * max(1, height - 4)
            if index == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()
        return False


class TaskManagerWindow(Gtk.Window):
    COLUMNS = (("Name", 0), ("PID", 1), ("CPU %", 2), ("RAM MiB", 3), ("User", 4), ("State", 5), ("Command", 6))

    def __init__(self):
        super().__init__(title="Ooonana Task Manager")
        self.set_default_size(1000, 620)
        self.set_size_request(800, 500)
        header(self, "Task Manager", "Processes and performance", "utilities-system-monitor-symbolic")
        self.previous_cpu: tuple[int, int] | None = None
        self.previous_process_ticks: dict[tuple[int, int], int] = {}
        self.previous_disk: tuple[int, int, float] | None = None
        self.previous_network: tuple[str, int, int, float] | None = None
        self.users: dict[int, str] = {}
        self.closed = False

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(root)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(220)
        sidebar = Gtk.StackSidebar()
        sidebar.set_stack(self.stack)
        sidebar.set_size_request(175, -1)
        sidebar.get_style_context().add_class("sidebar")
        root.pack_start(sidebar, False, False, 0)
        root.pack_start(self.stack, True, True, 0)
        self.stack.add_titled(self.build_processes(), "processes", "Processes")
        self.stack.add_titled(self.build_performance(), "performance", "Performance")
        self.stack.set_visible_child_name("processes")
        self.connect("destroy", self.on_destroy)
        self.refresh()
        GLib.timeout_add_seconds(2, self.refresh)

    def build_processes(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_border_width(18)
        page.pack_start(label("Running tasks", "page-title"), False, False, 0)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search name, PID, user, command")
        self.search.connect("search-changed", lambda *_: self.filtered.refilter())
        toolbar.pack_start(self.search, True, True, 0)
        toolbar.pack_start(button("Refresh", "view-refresh-symbolic", lambda *_: self.refresh()), False, False, 0)
        self.end_button = button("End task", "window-close-symbolic", self.end_selected, "destructive-action")
        self.end_button.set_sensitive(False)
        toolbar.pack_start(self.end_button, False, False, 0)
        page.pack_start(toolbar, False, False, 0)

        self.store = Gtk.ListStore(str, int, float, float, str, str, str, int, int)
        self.filtered = self.store.filter_new()
        self.filtered.set_visible_func(self.visible_process)
        self.sorted = Gtk.TreeModelSort(model=self.filtered)
        self.sorted.set_sort_column_id(2, Gtk.SortType.DESCENDING)
        self.tree = Gtk.TreeView(model=self.sorted)
        self.tree.set_headers_clickable(True)
        self.tree.set_enable_search(False)
        self.tree.get_selection().connect("changed", self.selection_changed)
        for title, column_id in self.COLUMNS:
            renderer = Gtk.CellRendererText()
            if column_id == 6:
                renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
            if column_id in (2, 3):
                renderer.set_property("xalign", 1.0)
                column = Gtk.TreeViewColumn(title, renderer)
                column.set_cell_data_func(renderer, self.render_numeric, column_id)
            else:
                column = Gtk.TreeViewColumn(title, renderer, text=column_id)
            column.set_sort_column_id(column_id)
            column.set_resizable(True)
            column.set_min_width(56 if column_id != 6 else 180)
            if column_id == 6:
                column.set_expand(True)
            self.tree.append_column(column)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.tree)
        page.pack_start(scroll, True, True, 0)
        self.process_summary = label("Reading processes...", "muted")
        page.pack_start(self.process_summary, False, False, 0)
        return page

    def render_numeric(self, _column, renderer, model, row_iter, column_id) -> None:
        renderer.set_property("text", f"{model[row_iter][column_id]:.1f}")

    def build_performance(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_border_width(18)
        page.pack_start(label("Performance", "page-title"), False, False, 0)
        page.pack_start(label("Two-second history. Rates are measured throughput, not link speed.", "muted"), False, False, 0)
        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_column_homogeneous(True)
        self.metrics = {
            "cpu": MetricCard("CPU"),
            "ram": MetricCard("RAM"),
            "gpu": MetricCard("GPU"),
            "disk": MetricCard("Disk read / write", False),
            "network": MetricCard("Wi-Fi / network", False),
            "storage": MetricCard("Root storage"),
        }
        for index, widget in enumerate(self.metrics.values()):
            grid.attach(widget, index % 2, index // 2, 1, 1)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(grid)
        page.pack_start(scroll, True, True, 0)
        return page

    def visible_process(self, model, row_iter, _data=None) -> bool:
        query = self.search.get_text().strip().casefold()
        if not query:
            return True
        row = model[row_iter]
        return query in " ".join((row[0], str(row[1]), row[4], row[6])).casefold()

    def selection_changed(self, selection) -> None:
        model, row_iter = selection.get_selected()
        allowed = bool(row_iter and os.getuid() != 0 and model[row_iter][8] == os.getuid() and model[row_iter][1] not in (1, os.getpid()))
        self.end_button.set_sensitive(allowed)

    def selected_identity(self) -> tuple[int, int, str, int] | None:
        model, row_iter = self.tree.get_selection().get_selected()
        if row_iter is None:
            return None
        row = model[row_iter]
        return int(row[1]), int(row[7]), str(row[0]), int(row[8])

    def end_selected(self, *_args) -> None:
        selected = self.selected_identity()
        if selected is None:
            return
        pid, starttime, name, owner = selected
        if os.getuid() == 0 or owner != os.getuid() or pid in (1, os.getpid()):
            message(self, "End task refused", "Only your own tasks can be stopped.", Gtk.MessageType.WARNING)
            return
        dialog = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE, text=f"End {name} (PID {pid})?",
        )
        dialog.format_secondary_text("Unsaved work in this task may be lost.")
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("End task", Gtk.ResponseType.OK)
        accepted = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if not accepted:
            return
        current = parse_process_stat(read_text(Path(f"/proc/{pid}/stat")))
        uid_text = read_text(Path(f"/proc/{pid}/status"))
        current_owner = next((line.split()[1] for line in uid_text.splitlines() if line.startswith("Uid:")), "")
        if current is None or current[2] != starttime or current_owner != str(owner):
            message(self, "Task changed", "Process exited or PID was reused.", Gtk.MessageType.WARNING)
            self.refresh()
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as error:
            message(self, "End task failed", str(error), Gtk.MessageType.ERROR)
        self.refresh()

    def process_rows(self, total_delta: int) -> list[tuple]:
        rows = []
        next_ticks: dict[tuple[int, int], int] = {}
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            parsed = parse_process_stat(read_text(entry / "stat"))
            if parsed is None:
                continue
            state, ticks, starttime = parsed
            info = read_text(entry / "status")
            name = next((line.split(":", 1)[1].strip() for line in info.splitlines() if line.startswith("Name:")), entry.name)
            uid_text = next((line.split()[1] for line in info.splitlines() if line.startswith("Uid:")), "")
            rss_text = next((line.split()[1] for line in info.splitlines() if line.startswith("VmRSS:")), "0")
            try:
                uid = int(uid_text)
                rss_mib = int(rss_text) / 1024
            except ValueError:
                continue
            if uid not in self.users:
                try:
                    self.users[uid] = pwd.getpwuid(uid).pw_name
                except KeyError:
                    self.users[uid] = str(uid)
            try:
                command = (entry / "cmdline").read_bytes()[:512].replace(b"\0", b" ").decode("utf-8", "replace").strip()
            except OSError:
                command = ""
            key = pid, starttime
            prior = self.previous_process_ticks.get(key, ticks)
            cpu = 100.0 * max(0, ticks - prior) / total_delta if total_delta > 0 else 0.0
            next_ticks[key] = ticks
            rows.append((name, pid, round(cpu, 1), round(rss_mib, 1), self.users[uid], state, command or name, starttime, uid))
        self.previous_process_ticks = next_ticks
        return rows

    def refresh(self) -> bool:
        if self.closed:
            return False
        now = time.monotonic()
        temperature, fan = thermal_fan_snapshot()
        cpu = cpu_totals(read_text(Path("/proc/stat")))
        total_delta = 0
        if cpu and self.previous_cpu:
            total_delta = max(0, cpu[0] - self.previous_cpu[0])
            idle_delta = max(0, cpu[1] - self.previous_cpu[1])
            cpu_percent = 100.0 * max(0, total_delta - idle_delta) / total_delta if total_delta else 0.0
            self.metrics["cpu"].update(f"{cpu_percent:.0f}% total • {temperature} • {fan}", cpu_percent)
        self.previous_cpu = cpu

        selected = self.selected_identity() if hasattr(self, "tree") else None
        rows = self.process_rows(total_delta)
        self.store.clear()
        for row in rows:
            self.store.append(row)
        if selected:
            def restore(model, path, row_iter, _data):
                row = model[row_iter]
                if row[1] == selected[0] and row[7] == selected[1]:
                    self.tree.get_selection().select_path(path)
                    return True
                return False
            self.sorted.foreach(restore, None)
        self.process_summary.set_text(f"{len(rows)} tasks  •  Click column header to sort  •  End task affects your processes only")

        memory = meminfo_values(read_text(Path("/proc/meminfo")))
        total = memory.get("MemTotal", 0)
        available = memory.get("MemAvailable", memory.get("MemFree", 0))
        if total > 0:
            percent = 100.0 * max(0, total - available) / total
            swap_total = memory.get("SwapTotal", 0)
            swap_used = max(0, swap_total - memory.get("SwapFree", 0))
            original, _compressed, physical = zram_consumption()
            zram = f" • zram physical {physical / 1048576:.0f} MiB ({original / physical:.1f}x effective)" if physical else ""
            self.metrics["ram"].update(f"{percent:.0f}% used • {available / 1048576:.1f} GiB available • swap {swap_used / 1048576:.1f}/{swap_total / 1048576:.1f} GiB" + zram, percent)
        gpu_name, busy = gpu_busy()
        self.metrics["gpu"].update(f"{gpu_name}: {busy:.0f}%" if busy is not None else f"{gpu_name}: counter unavailable", busy)

        read_bytes, write_bytes = disk_bytes()
        if self.previous_disk:
            prior_read, prior_write, prior_time = self.previous_disk
            elapsed = max(0.1, now - prior_time)
            read_rate = max(0, read_bytes - prior_read) / elapsed
            write_rate = max(0, write_bytes - prior_write) / elapsed
            self.metrics["disk"].update(f"Read {human_rate(read_rate)}  •  Write {human_rate(write_rate)}", read_rate + write_rate)
        self.previous_disk = read_bytes, write_bytes, now

        network = network_bytes()
        if network:
            interface, rx, tx = network
            if self.previous_network and self.previous_network[0] == interface:
                _, prior_rx, prior_tx, prior_time = self.previous_network
                elapsed = max(0.1, now - prior_time)
                down = max(0, rx - prior_rx) / elapsed
                up = max(0, tx - prior_tx) / elapsed
                self.metrics["network"].update(f"{interface}: ↓ {human_rate(down)}  ↑ {human_rate(up)}", down + up)
            else:
                self.metrics["network"].update(f"{interface}: sampling...", 0.0)
            self.previous_network = interface, rx, tx, now
        else:
            self.metrics["network"].update("No active interface counter", None)
            self.previous_network = None

        storage = root_storage()
        if storage and storage[0] > 0:
            capacity, free = storage
            percent = 100.0 * max(0, capacity - free) / capacity
            self.metrics["storage"].update(f"{percent:.0f}% used • {free / (1024 ** 3):.1f} GiB available", percent)
        return True

    def on_destroy(self, *_args) -> None:
        self.closed = True
        Gtk.main_quit()


def main() -> None:
    if "--dry-run" in sys.argv:
        print("Ooonana Task Manager: processes search sort end-task CPU GPU RAM disk Wi-Fi")
        print("OOONANA_TASK_MANAGER_OK")
        return
    apply_theme()
    window = TaskManagerWindow()
    window.show_all()
    if "--performance" in sys.argv:
        window.stack.set_visible_child_name("performance")
    Gtk.main()


if __name__ == "__main__":
    main()
