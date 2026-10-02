#!/usr/bin/env python3
"""Isolated native GTK rendering with explicit sample data and no backend actions."""

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("app", choices=("appearance", "notifications", "offline-ai", "chat", "setup", "setup-review", "health"))
parser.add_argument("output", type=Path)
parser.add_argument("--size", default="1080x680")
args = parser.parse_args()

with tempfile.TemporaryDirectory(prefix="ooonana-gui-fixture-") as temporary:
    fixture = Path(temporary)
    os.environ["XDG_CONFIG_HOME"] = str(fixture / "config")
    os.environ["XDG_STATE_HOME"] = str(fixture / "state")
    os.environ["XDG_DATA_HOME"] = str(fixture / "data")
    os.environ["OOONANA_OPENVINO_HOME"] = str(fixture / "models-home")
    now = int(time.monotonic() * 1_000_000)
    records = [
        dict(id=1, timestamp=now, app="Updates", summary="GUI preview", body="Grouped notifications with unread tracking. Sample data only."),
        dict(id=2, timestamp=now - 60_000_000, app="Music", summary="Library ready", body="No sound played during this preview."),
    ]

    def sample(command, **_kwargs):
        if command == ["ooonana-ai", "provider"]:
            return 0, "active: openvino\nlabel: Offline Intel\nkey: not required"
        if command == ["ooonana-ai", "model"]:
            return 0, "active: Choose model"
        if command[:2] == ["openvino", "doctor"]:
            return 0, "Runtime setup needed. This is sample UI state."
        if command[:3] == ["openvino", "api", "status"]:
            return 0, "API stopped"
        if command[:2] == ["dunstctl", "is-paused"]:
            return 0, "false"
        return 0, "Sample preview data"

    def async_run(command, done, **kwargs):
        GLib.idle_add(done, *sample(command, **kwargs))

    apply_theme()
    selected = {"appearance": ("settings_app", "SettingsWindow"), "notifications": ("notifications_app", "NotificationsWindow"), "offline-ai": ("ai_app", "AiWindow"), "chat": ("ai_app", "AiWindow"), "health": ("health_app", "HealthWindow"), "setup": ("setup_app", "SetupWindow"), "setup-review": ("setup_app", "SetupWindow")}
    module_name, class_name = selected[args.app]
    module = importlib.import_module(module_name)
    module.run = sample
    module.run_async = async_run
    if args.app == "notifications":
        module.read_history = lambda: (0, json.dumps([[{**record, "appname": record["app"]} for record in records]]))
    if args.app == "offline-ai":
        module.AiWindow.load_transcript = lambda _self: None
        module.AiWindow.save_transcript = lambda _self: None
        module.command_exists = lambda _name: True
    window = getattr(module, class_name)()
    if args.app == "chat":
        window.current["title"] = "USB installation checks"
        window.store.append(window.current, "user", "What should we check before installing?", "You")
        window.store.append(window.current, "assistant", "Check the selected disk, available memory, and a verified package repository.\n\n```shell\nooonana-memory status\n```", "Ooonana")
        other = window.store.new()
        other["title"] = "Model memory planning"
        other["updated"] = 0
        window.refresh_chats()
        window.render_messages()
        window.set_default_size(*map(int, args.size.split("x")))
    if args.app in ("setup", "setup-review"):
        window.user_entry.set_text("ooonana")
    if args.app == "appearance":
        window.headerbar.set_subtitle("Native GTK preview · sample data")
    window.show_all()
    window.move(0 if args.app == "chat" else 110, 0 if args.app == "chat" else 65)
    if args.app == "appearance":
        window.sidebar.select_row(window.sidebar.get_row_at_index(3))
    if args.app == "offline-ai":
        GLib.timeout_add(200, lambda: (window.offline_dialog(), False)[1])
    if args.app == "setup-review":
        GLib.timeout_add(200, lambda: (window.apply(Gtk.Button()), False)[1])

    def capture():
        native_root = Gdk.get_default_root_window()
        pixels = Gdk.pixbuf_get_from_window(native_root, 0, 0, native_root.get_width(), native_root.get_height())
        assert pixels is not None
        args.output.parent.mkdir(parents=True, exist_ok=True)
        pixels.savev(str(args.output), "png", [], [])
        print(f"GTK_GUI_PREVIEW_OK {args.app}: {args.output}", flush=True)
        for item in Gtk.Window.list_toplevels():
            if isinstance(item, Gtk.Dialog):
                item.response(Gtk.ResponseType.CLOSE)
            item.destroy()
        Gtk.main_quit()
        return False

    GLib.timeout_add(2200, capture)
    Gtk.main()
