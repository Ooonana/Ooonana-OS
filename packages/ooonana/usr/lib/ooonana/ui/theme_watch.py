"""Debounced preference notifications; no polling, writes or process signals."""
from pathlib import Path


class AppearanceWatch:
    def __init__(self, gio, glib, paths, state, changed):
        self.gio, self.glib = gio, glib
        self.state, self.changed = state, changed
        self.paths, self.monitors, self.pending = (), {}, 0
        self.previous = state()
        self.set_paths(paths)

    def set_paths(self, paths):
        paths = tuple(Path(path).absolute() for path in paths)
        if paths != self.paths:
            self.paths = paths
            self.arm()

    def arm(self):
        directories = set()
        for path in self.paths:
            parent = path.parent
            while parent != parent.parent:
                try:
                    if parent.is_dir():
                        break
                except OSError:
                    pass  # Watch readable ancestor; never fail app startup.
                parent = parent.parent
            directories.add(parent)
        for path in set(self.monitors) - directories:
            monitor, handler = self.monitors.pop(path)
            monitor.disconnect(handler)
            monitor.cancel()
        for path in directories - set(self.monitors):
            try:
                monitor = self.gio.File.new_for_path(str(path)).monitor_directory(
                    self.gio.FileMonitorFlags.WATCH_MOVES, None)
                self.monitors[path] = (monitor, monitor.connect("changed", self.event))
            except self.glib.Error:
                # Keep existing appearance if this environment cannot monitor.
                # Never create directories or start a retry/polling loop.
                continue

    def event(self, _monitor, file, other, _kind):
        candidates = [Path(item.get_path()).absolute() for item in (file, other)
                      if item is not None and item.get_path()]
        if any(candidate == target or candidate in target.parents
               for candidate in candidates for target in self.paths):
            if not self.pending:
                self.pending = self.glib.timeout_add(80, self.refresh)

    def refresh(self):
        self.pending = 0
        self.arm()  # Rebind after missing directories appear or are replaced.
        current = self.state()
        if current != self.previous:
            self.previous = current
            self.changed()
        return False

    def close(self):
        if self.pending:
            self.glib.source_remove(self.pending)
            self.pending = 0
        for monitor, handler in self.monitors.values():
            monitor.disconnect(handler)
            monitor.cancel()
        self.monitors.clear()
