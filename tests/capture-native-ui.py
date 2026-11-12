#!/usr/bin/env python3
"""Render one real native app for visual QA without activating its actions."""

import argparse
import importlib
import json
import os
import shutil
from pathlib import Path
import sys
import tempfile

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
    "sound": ("controls_app", "AudioWindow"),
    "brightness": ("controls_app", "BrightnessWindow"),
    "power": ("controls_app", "PowerWindow"),
    "notifications": ("notifications_app", "NotificationsWindow"),
    "health": ("health_app", "HealthWindow"),
    "updates": ("health_app", "HealthWindow"),
    "wifi-map": ("signal_map", "SignalMapWindow"),
    "bluetooth-map": ("signal_map", "SignalMapWindow"),
    "wifi-credentials": ("wifi_app", "WifiCredentialsDialog"),
    "bluetooth-pair": ("bluetooth_app", "PairDialog"),
}


def sample_backend(module, app):
    """Block every external action; representative state only, never hardware QA."""
    def sample(command, **_kwargs):
        if command == ["ooonana-ai", "provider"]:
            return 0, "active: nim\nlabel: Fixture NVIDIA NIM\nkey: configured"
        if command == ["ooonana-ai", "model"]:
            return 0, "active: Choose model"
        if command == ["dunstctl", "is-paused"]:
            return 0, "false"
        if command[0] in ("ooonana-health", "ooonana"):
            return 0, "Isolated UI sample. No update or hardware operation executed."
        return 1, "Unavailable in isolated UI sample"

    module.run = sample
    module.run_async = lambda command, done, **kwargs: GLib.idle_add(done, *sample(command, **kwargs))
    module.run_async_task = lambda task, done: GLib.idle_add(lambda: (done(*task()), False)[1])
    if app == "wifi":
        def initial(window):
            window.service_label.set_text("Service: unavailable in UI fixture")
            window.radio_label.set_text("Radio: unavailable")
            window.active_label.set_text("Connection: offline")
            window.toolbar.set_sensitive(False)
            window.actions.set_sensitive(False)
        module.WifiWindow.initial_refresh = initial
    if app == "bluetooth":
        def initial(window):
            window.service_status.set_text("Service: unavailable in UI fixture")
            window.adapter_status.set_text("Adapter: unavailable")
            window.power_status.set_text("Power: unavailable")
            window.toolbar.set_sensitive(False)
            window.actions.set_sensitive(False)
        module.BluetoothWindow.initial_refresh = initial
    if app == "sound":
        module.AudioWindow.collect_audio_state = lambda _self: dict(
            service_rc=1, service_output="No hardware exposed to UI fixture.",
            alsa_card_ready=False, outputs=[], inputs=[], default_output="",
            default_input="", volume_rc=1, volume="", mute_rc=1, mute="")
    if app == "notifications":
        record = dict(id=1, timestamp=0, appname="Updates", summary="UI sample notification",
                      body="Layout preview only. No update executed.")
        module.read_history = lambda: (0, json.dumps([[record]]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", choices=APPS)
    parser.add_argument("output", type=Path)
    parser.add_argument("--delay-ms", type=int, default=2500)
    parser.add_argument("--require-fit", action="store_true", help="Reject windows extending outside isolated display")
    parser.add_argument("--sample-data", action="store_true", help="Private state and mocked backend; no hardware actions")
    parser.add_argument("--page", help="Settings or Task Manager page")
    parser.add_argument("--text-scale", type=float, choices=(1.0, 1.25, 1.5), help="Private GTK DPI regression")
    args = parser.parse_args()
    fixture = None
    if args.sample_data:
        if os.environ.get("OOONANA_GUI_TEST_DISPLAY") != "1" or os.getuid() == 0:
            raise SystemExit("Dedicated test display and nonroot test user required")
        fixture = tempfile.TemporaryDirectory(prefix="ooonana-native-catalog-")
        # Keep the selected presentation while isolating writable app state.
        # Dropping these files silently turned light-theme QA into dark/default.
        gtk_source = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "gtk-3.0"
        gtk_target = Path(fixture.name) / "config/gtk-3.0"
        gtk_target.mkdir(parents=True)
        for name in ("gtk.css", "settings.ini"):
            if (gtk_source / name).is_file():
                shutil.copyfile(gtk_source / name, gtk_target / name)
        for key, directory in (("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state"),
                               ("XDG_DATA_HOME", "data"), ("OOONANA_OPENVINO_HOME", "models")):
            os.environ[key] = str(Path(fixture.name) / directory)
    module_name, class_name = APPS[args.app]
    module = importlib.import_module(module_name)
    if args.sample_data:
        sample_backend(module, args.app)
    elif args.app == "music":
        module.run_async = lambda *_args, **_kwargs: None
    apply_theme()
    if args.text_scale is not None:
        Gtk.Settings.get_default().set_property("gtk-xft-dpi", round(96 * 1024 * args.text_scale))
    Gtk.IconTheme.get_default().append_search_path(str(ROOT / "packages/ooonana/usr/share/icons/hicolor/scalable/apps"))
    factory = getattr(module, class_name)
    if args.app == "updates":
        window = factory(updates=True)
    elif args.app in ("wifi-map", "bluetooth-map"):
        window = factory("Signal map · isolated UI sample", "bluetooth" if args.app == "bluetooth-map" else "wireless")
        window.connect("destroy", Gtk.main_quit)
        window.update_items([dict(name="UI sample device", key="qa", signal=65, category="device")])
    elif args.app == "wifi-credentials":
        window = factory(None, dict(ssid="UI sample enterprise network", security_label="Enterprise",
                                    security_kind="enterprise", security="WPA2-EAP"))
        window.connect("destroy", Gtk.main_quit)
    elif args.app == "bluetooth-pair":
        window = factory(None, dict(name="UI sample device"))
        window.connect("destroy", Gtk.main_quit)
    else:
        window = factory()
    window.show_all()
    if args.app in ("appearance", "settings") and (args.page or args.app == "appearance"):
        selected = args.page or "appearance"
        index = next(i for i, page in enumerate(window.PAGES) if page[0] == selected)
        window.sidebar.select_row(window.sidebar.get_row_at_index(index))
    if args.app == "tasks":
        window.stack.set_visible_child_name(args.page or "performance")
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
        if not isinstance(window, Gtk.Dialog):
            controls = next(child for child in window.get_titlebar().get_children() if isinstance(child, Gtk.Box))
            assert [child.get_accessible().get_name() for child in controls.get_children()] == [
                "Close window", "Minimize window", "Toggle fullscreen"]
        else:
            assert window.get_widget_for_response(Gtk.ResponseType.CANCEL)
            assert window.get_widget_for_response(Gtk.ResponseType.OK)
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
    if fixture:
        fixture.cleanup()
    if failures:
        raise SystemExit(f"Window exceeds display: {failures}")


if __name__ == "__main__":
    main()
