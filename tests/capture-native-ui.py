#!/usr/bin/env python3
"""Render one real native app for visual QA without activating its actions."""

import argparse
import importlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme  # noqa: E402


APPS = {
    "settings": ("settings_app", "SettingsWindow"),
    "appearance": ("settings_app", "SettingsWindow"),
    "tasks": ("task_manager_app", "TaskManagerWindow"),
    "launcher": ("launcher_app", "LauncherWindow"),
    "wifi": ("wifi_app", "WifiWindow"),
    "bluetooth": ("bluetooth_app", "BluetoothWindow"),
    "packages": ("packages_app", "PackagesWindow"),
    "ai": ("ai_app", "AiWindow"),
    "setup": ("setup_app", "SetupWindow"),
    "music": ("controls_app", "MediaWindow"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", choices=APPS)
    parser.add_argument("output", type=Path)
    parser.add_argument("--delay-ms", type=int, default=2500)
    parser.add_argument("--require-fit", action="store_true", help="Reject windows extending outside isolated display")
    args = parser.parse_args()
    module_name, class_name = APPS[args.app]
    module = importlib.import_module(module_name)
    if args.app == "music":
        module.run_async = lambda *_args, **_kwargs: None
        module.GLib.timeout_add_seconds = lambda *_args, **_kwargs: 0
    apply_theme()
    window = getattr(module, class_name)()
    window.show_all()
    if args.app == "appearance":
        window.sidebar.select_row(window.sidebar.get_row_at_index(3))
    if args.app == "tasks":
        window.stack.set_visible_child_name("performance")
    if args.app == "music":
        window.state_label.set_text("UI preview - playback untested")

    failures = []

    def capture():
        root = Gdk.get_default_root_window()
        pixels = Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())
        if pixels is None:
            raise RuntimeError("Screenshot unavailable")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        pixels.savev(str(args.output), "png", [], [])
        bounds = window.get_window().get_frame_extents()
        if args.require_fit and (bounds.x < 0 or bounds.y < 0 or
                                 bounds.x + bounds.width > root.get_width() or
                                 bounds.y + bounds.height > root.get_height()):
            failures.append((args.app, bounds.x, bounds.y, bounds.width, bounds.height,
                             root.get_width(), root.get_height()))
        print(f"{args.app}: {bounds.x},{bounds.y} {bounds.width}x{bounds.height} -> {args.output}", flush=True)
        window.destroy()
        return False

    GLib.timeout_add(max(500, args.delay_ms), capture)
    Gtk.main()
    if failures:
        raise SystemExit(f"Window exceeds display: {failures}")


if __name__ == "__main__":
    main()
