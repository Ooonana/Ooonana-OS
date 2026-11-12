#!/usr/bin/env python3
"""Event coalescing and missing/atomic preference paths; no GTK or desktop."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from theme_watch import AppearanceWatch


class Monitor:
    def connect(self, _name, callback):
        self.callback, self.cancelled = callback, False
        return 1
    def disconnect(self, _handler):
        self.callback = None
    def cancel(self):
        self.cancelled = True


class Loop:
    Error = OSError
    def __init__(self):
        self.callbacks, self.sequence = {}, 0
    def timeout_add(self, delay, callback):
        assert delay == 80
        self.sequence += 1
        self.callbacks[self.sequence] = callback
        return self.sequence
    def source_remove(self, identifier):
        self.callbacks.pop(identifier)
    def drain(self):
        callbacks, self.callbacks = self.callbacks, {}
        for callback in callbacks.values():
            assert callback() is False


class ThemeWatch(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ooonana-theme-watch-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.target = self.base / "config/ooonana/theme"
        self.state, self.changes, self.created = "dark", [], []
        self.loop = Loop()
        class File:
            def __init__(file, path):
                file.path = path
            def monitor_directory(file, _flags, _cancel):
                monitor = Monitor()
                self.created.append((Path(file.path), monitor))
                return monitor
        self.gio = SimpleNamespace(File=SimpleNamespace(new_for_path=File),
                                   FileMonitorFlags=SimpleNamespace(WATCH_MOVES=1))
        self.watch = AppearanceWatch(self.gio, self.loop, [self.target],
                                    lambda: self.state, lambda: self.changes.append(self.state))
        self.addCleanup(self.watch.close)

    def event(self, path, other=None):
        def file(value):
            return SimpleNamespace(get_path=lambda: str(value)) if value else None
        self.watch.event(None, file(path), file(other), None)

    def test_atomic_rename_coalesces_without_polling_or_unrelated_events(self):
        self.event(self.base / "unrelated")
        self.assertFalse(self.loop.callbacks)
        self.state = "light"
        for _ in range(8):
            self.event(self.target.with_name(".theme.temporary"), self.target)
        self.assertEqual(len(self.loop.callbacks), 1)
        self.loop.drain()
        self.assertEqual(self.changes, ["light"])
        self.assertFalse(self.loop.callbacks)
        self.event(self.target)
        self.loop.drain()
        self.assertEqual(self.changes, ["light"], "Unchanged preferences must not reload CSS")

    def test_missing_parent_creation_and_replacement_rebind(self):
        self.assertEqual(set(self.watch.monitors), {self.base})
        first = self.created[-1][1]
        self.target.parent.mkdir(parents=True)
        self.event(self.base / "config")
        self.loop.drain()
        self.assertEqual(set(self.watch.monitors), {self.target.parent})
        self.assertTrue(first.cancelled)
        self.target.parent.rmdir()
        self.event(self.target.parent)
        self.loop.drain()
        self.assertEqual(set(self.watch.monitors), {self.base / "config"})
        self.assertFalse(self.changes)

    def test_close_cancels_pending_work_and_monitors(self):
        self.event(self.target)
        monitors = [monitor for _path, monitor in self.created]
        self.watch.close()
        self.assertFalse(self.loop.callbacks or self.watch.monitors)
        self.assertTrue(all(item.cancelled and item.callback is None for item in monitors))

    def test_same_paths_keep_monitors_and_changed_paths_release_old_ones(self):
        count = len(self.created)
        self.watch.set_paths([self.target])
        self.assertEqual(len(self.created), count)
        self.watch.set_paths([self.base / "other/theme"])
        self.assertEqual(set(self.watch.monitors), {self.base})

    def test_monitor_failure_has_no_retry_timer_or_directory_write(self):
        self.watch.close()
        def fail(*_args):
            raise OSError("fixture permission denial")
        self.gio.File.new_for_path = fail
        self.watch.arm()
        self.assertFalse(self.watch.monitors or self.loop.callbacks)
        self.assertFalse(self.target.parent.exists())

    def test_unreadable_parent_does_not_break_startup(self):
        original = Path.is_dir
        def check(path):
            if path == self.target.parent:
                raise PermissionError("owned denied fixture")
            return original(path)
        with patch.object(Path, "is_dir", check):
            self.watch.arm()
        self.assertEqual(set(self.watch.monitors), {self.base})
        self.assertFalse(self.loop.callbacks)


if __name__ == "__main__":
    unittest.main()
