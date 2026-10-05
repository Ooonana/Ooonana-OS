#!/usr/bin/env python3
"""Fixture-only GTK phase/memory UI, no API calls or real history."""
import os
from pathlib import Path
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana/ui"))
import ai_app
from common import Gdk, Gtk, apply_theme

with tempfile.TemporaryDirectory() as temporary:
    os.environ["XDG_STATE_HOME"] = temporary
    ai_app.run_async_task = lambda _task, done: done(0, ("active: openvino\nlabel: Offline Intel\nkey: not needed", "active: qwen3.5-9b-int4-ov"))
    ai_app.available_ram = lambda: {"available": 512 * 1024**2, "total": 8 * 1024**3, "low": True}
    ai_app.storage_health = lambda: {"mode": "usb", "level": "low", "free": 100 * 1024**2, "caption": "Persistent USB · 0.1 GiB free · low space"}
    apply_theme()
    window = ai_app.AiWindow()
    window.show_all()
    window.set_phase("Loading model")
    window.phase_started -= 7
    window.phase_tick()
    assert "7s" in window.phase_label.get_text()
    assert "0.5 GiB RAM available" in window.memory_label.get_text()
    assert "low" in window.memory_label.get_text() and window.memory_label.get_visible()
    assert window.memory_label.get_style_context().has_class("status-warn")
    assert window.storage_label.get_visible() and "low space" in window.storage_label.get_text()
    assert window.phase_timer
    for _ in range(50):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.02)
    if len(sys.argv) > 1:
        root_window = Gdk.get_default_root_window()
        image = Gdk.pixbuf_get_from_window(root_window, 0, 0, root_window.get_width(), root_window.get_height())
        image.savev(sys.argv[1], "png", [], [])
    window.set_phase()
    assert window.phase_label.get_text() == "Ready" and not window.phase_timer
    window.destroy()
print("AI_INDICATORS_OK phase lifecycle; low RAM; no API calls")
