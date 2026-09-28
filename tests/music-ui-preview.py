#!/usr/bin/env python3
"""Show music window for visual QA without starting MPD or playing audio."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana/ui"))
import controls_app  # noqa: E402

controls_app.run_async = lambda *_args, **_kwargs: None
controls_app.GLib.timeout_add_seconds = lambda *_args, **_kwargs: 0
controls_app.apply_theme()
window = controls_app.MediaWindow()
window.state_label.set_text("Preview only - audio disabled")
window.show_all()
controls_app.Gtk.main()
