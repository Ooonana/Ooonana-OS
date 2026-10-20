#!/usr/bin/env python3
"""Private GTK long-content/empty-state checks. No playback or device actions."""
import argparse
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1" and os.getuid() != 0
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
import common
import controls_app as controls
import launcher_app as launcher
import setup_app as setup
from common import Gdk, GLib, Gtk, Pango, apply_theme
from gi.repository import Gio

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--baseline", action="store_true", help="Capture findings before a repair")
parser.add_argument("--text-scale", type=float, choices=(1.0, 1.25, 1.5, 2.0), default=1.0)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
apply_theme()
Gtk.Settings.get_default().set_property("gtk-xft-dpi", round(96 * 1024 * args.text_scale))
print("CONTENT_TEST_XFT_DPI", Gtk.Settings.get_default().get_property("gtk-xft-dpi"), flush=True)
Gtk.main_quit = lambda *_args: None
failures = []


def check(condition, description):
    if not condition:
        failures.append(description)


def settle(seconds=0.12):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.005)


def capture(window, name):
    window.show_all()
    settle()
    root = Gdk.get_default_root_window()
    bounds = window.get_window().get_frame_extents()
    check(0 <= bounds.x and bounds.x + bounds.width <= root.get_width() and
          0 <= bounds.y and bounds.y + bounds.height <= root.get_height(),
          f"{name}: window outside {root.get_width()}x{root.get_height()} ({bounds.width}x{bounds.height})")
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
        str(args.output / (name + ".png")), "png", [], [])


def labels(widget):
    if isinstance(widget, Gtk.Label):
        yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from labels(child)


window = launcher.LauncherWindow()
for row in window.results.get_children():
    row.destroy()
long_name = "Ooonana multilingual application · 긴 이름 " * 6
app = Gio.AppInfo.create_from_commandline("true", long_name, Gio.AppInfoCreateFlags.NONE)
window.add_app(app)
window.show_all()
window.search_changed()
settle()
capture(window, "launcher-long")
name_label = next(item for item in labels(window.results) if item.get_text() == long_name)
check(name_label.get_mapped(), "Filtered application content did not map")
check(name_label.get_ellipsize() == Pango.EllipsizeMode.END, "Launcher name needs bounded ellipsis")
check(name_label.get_tooltip_text() == long_name, "Launcher full name missing from tooltip")
window.search.set_text("no-such-qa-application")
window.search_changed()
settle()
capture(window, "launcher-no-match")
check(not window.visible_rows(), "No-match search still has launchable rows")
empty = getattr(window, "empty_state", None)
check(empty is not None and empty.get_visible() and empty.get_child_visible(), "Search has no visible recovery state")
window.search.set_text("")
window.search_changed()
settle()
check(len(window.visible_rows()) == 1, "Clearing search did not restore application")
if empty is not None:
    check(not empty.get_visible(), "Empty search state stayed visible after recovery")
check(name_label.get_mapped(), "Restored application content did not map")
messages = []
launcher.launch = lambda *_args, **_kwargs: False
launcher.message = lambda _parent, title, *_args: messages.append(title)
window.launch_app(SimpleNamespace(get_id=lambda: "geany.desktop"))
check(messages == ["Application failed"] and window.get_visible(), "Launch failure lost launcher/retry path")
for row in window.results.get_children():
    row.destroy()
window.search_changed()
settle()
check(empty is not None and empty.get_visible(), "Empty application catalog has no guidance")
window.destroy()

jobs = []
controls.run_async = lambda command, done, **kwargs: jobs.append((command, done))
controls.run_async_task = lambda task, done: jobs.append((task, done))
controls.launch = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Unexpected launch"))
controls.message = lambda *_args, **_kwargs: None
window = controls.MediaWindow()
window.show_all()
startup = jobs.pop()[1]
startup(1, "MPD unavailable in isolated fixture")
check(not window.play_button.get_sensitive(), "Failed player start leaves Play enabled")
jobs.clear()
window.refresh_state()
window.refresh_state()
check(len(jobs) == 1, "Duplicate media refresh queued")
title = ("Long music title · 아주 긴 노래 제목 " * 6).strip()
artist = "Long artist and album name " * 8
jobs.pop()[1](0, dict(current=f"{artist}\t{title}\t/fixture/music.flac",
                     status="[paused] #1/1 1:23/4:56 (28%)", volume="volume: 70%"))
capture(window, "music-long-paused")
check(window.track_label.get_text() == title, "Music title lost full text")
check(window.track_label.get_tooltip_text() == title, "Music full title missing from tooltip")
check(window.play_button.get_label() == "Play", "Paused music does not offer Play")
jobs.clear()
window.refresh_state()
try:
    jobs.pop()[1](1, "Offline fixture: MPD is unavailable")
except (TypeError, KeyError) as exc:
    check(False, "Player error callback crashed: " + type(exc).__name__)
capture(window, "music-offline")
check("unavailable" in window.state_label.get_text().lower(), "Player failure masquerades as empty library")
check(all(not item.get_sensitive() for item in window.playback_actions), "Offline playback buttons remain enabled")
window.refresh_state()
jobs.pop()[1](0, dict(current="Artist\tRecovery fixture\t/file.flac", status="[playing] (10%)", volume=""))
check(window.play_button.get_label() == "Pause", "Recovered player does not offer Pause")
check(window.play_button.get_image().get_icon_name()[0] == "media-playback-pause-symbolic", "Pause icon contradicts action")
check(all(item.get_sensitive() for item in window.playback_actions), "Playback recovery stayed disabled")
controls.run = lambda command, **kwargs: (1, "Offline fixture") if command == ["mpc", "status"] else (0, "")
check(controls.MediaWindow.collect_state() == (1, "Offline fixture"), "MPD command failure discarded")
window.refresh_state()
late = jobs.pop()[1]
window.destroy()
late(1, "Late failure after close")
check(window.closed and not window.timer_id, "Closed player retained refresh timer")

jobs.clear()
window = controls.AudioWindow()
device = "alsa_output.pci-0000_00_1f.3.analog-stereo"
device_title = "External digital audio interface · 장치 " * 8
window.apply_audio_state(dict(service_rc=0, service_output="", alsa_card_ready=True,
    outputs=[(device, device_title)], inputs=[("fixture.input", device_title)],
    default_output=device, default_input="fixture.input", volume_rc=0,
    volume="Volume: front-left: 32768 / 50% / -18.00 dB", mute_rc=0, mute="Mute: no"))
capture(window, "sound-long-devices")
for combo in (window.output_combo, window.input_combo):
    cell = next(cell for cell in combo.get_cells() if isinstance(cell, Gtk.CellRendererText))
    check(cell.get_property("ellipsize") == Pango.EllipsizeMode.END, "Audio device text is unbounded")
    check(combo.get_tooltip_text() == device_title, "Full selected device name missing from tooltip")
window.destroy()

setup.message = lambda _parent, title, *_args: messages.append(title)
setup.run = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Unexpected setup command"))
setup.load_preferences = lambda: {"reduce_motion": True}
workers = []
original_thread = setup.threading.Thread


class DeferredWorker:
    def __init__(self, *, target, daemon):
        self.target = target

    def start(self):
        workers.append(self.target)


setup.threading.Thread = DeferredWorker
window = setup.SetupWindow()
window.show_all()
window.user_entry.set_text("Bad user!")
window.apply(window.apply_button)
check(window.get_focus() is window.user_entry and not workers and window.status.get_text(), "Invalid setup lost field focus/inline feedback or dispatched work")
window.user_entry.set_text("ooonana")
window.network_combo.set_active_id("static")
window.address_entry.set_text("192.0.2.10/24")
window.gateway_entry.set_text("192.0.2.1")
window.dns_entry.set_text("192.0.2.53")
for entry in (window.address_entry, window.gateway_entry, window.dns_entry):
    check(bool(entry.get_accessible().get_name()), "Static network entry has no accessible name")
capture(window, "setup-static")


def setup_response(response):
    def respond():
        dialog = next(item for item in Gtk.Window.list_toplevels() if isinstance(item, Gtk.Dialog) and item.get_title() == "Review setup")
        check(dialog.get_default_widget() == dialog.get_widget_for_response(Gtk.ResponseType.CANCEL),
              "Setup review does not default to Back")
        if response == Gtk.ResponseType.CANCEL:
            capture(dialog, "setup-review")
        dialog.response(response)
        return False
    GLib.timeout_add(100, respond)


setup_response(Gtk.ResponseType.CANCEL)
window.apply(window.apply_button)
check(not workers and not window.pending, "Back submitted setup changes")
setup_response(Gtk.ResponseType.OK)
window.apply(window.apply_button)
check(len(workers) == 1 and window.pending, "Setup confirmation did not dispatch one worker")
check(not window.content.get_sensitive() and not window.cancel_button.get_sensitive(), "Pending setup controls remain editable")
check(not window.spinner.get_property("active"), "Setup ignores Reduce Motion")
window.apply(window.apply_button)
check(len(workers) == 1 and window.before_close(), "Pending setup allowed duplicate action/close")
window.finished(window.apply_button, 1, "Failure fixture; no command executed")
check(not window.pending and window.content.get_sensitive() and window.cancel_button.get_sensitive(), "Setup failure has no retry path")
window.destroy()
window.finished(window.apply_button, 0, "Late completion")
check(window.closed, "Late setup completion changed destroyed window")
setup.threading.Thread = original_thread

parent = Gtk.Window(title="Dialog fixture")
parent.set_default_size(420, 220)
parent.show_all()
settle()
for name, text in (("message-unbroken", "x" * 580),
                   ("message-diagnostics", "Long diagnostic line " * 50 + "\n" + "Detail\n" * 60)):
    dialog = common.message_dialog(parent, "Operation unavailable", text, Gtk.MessageType.ERROR)
    capture(dialog, name)
    dialog.destroy()


def cancel_prompt():
    dialog = next(item for item in Gtk.Window.list_toplevels()
                  if isinstance(item, Gtk.Dialog) and item.get_transient_for() is parent)
    entries = [child for child in dialog.get_content_area().get_children() if isinstance(child, Gtk.Entry)]
    check(len(entries) == 1, "Prompt input missing")
    entry = entries[0]
    capture(dialog, "secret-prompt")
    check(bool(entry.get_accessible().get_name()), "Secret prompt input has no accessible label")
    check(not entry.get_visibility(), "Secret prompt reveals text")
    check(dialog.get_focus() is entry, "Prompt starts without input focus")
    dialog.response(Gtk.ResponseType.CANCEL)
    return False


GLib.timeout_add(100, cancel_prompt)
check(common.ask_text(parent, "Connect to network", "Network password · 네트워크 암호", secret=True) == "",
      "Cancel returned a secret")


def accept_secret():
    dialog = next(item for item in Gtk.Window.list_toplevels()
                  if isinstance(item, Gtk.Dialog) and item.get_transient_for() is parent)
    entry = next(child for child in dialog.get_content_area().get_children() if isinstance(child, Gtk.Entry))
    check(entry.get_input_purpose() == Gtk.InputPurpose.PASSWORD, "Secret prompt has nonsecret input purpose")
    entry.set_text("  fixture password  ")
    dialog.response(Gtk.ResponseType.OK)
    return False


GLib.timeout_add(100, accept_secret)
check(common.ask_text(parent, "Connect to network", "Network password", secret=True) == "  fixture password  ",
      "Secret prompt trimmed password whitespace")
parent.destroy()
if failures:
    for failure in failures:
        print("CONTENT_FINDING: " + failure, flush=True)
    if not args.baseline:
        raise SystemExit(1)
else:
    print("UI_CONTENT_RUNTIME_OK long names; empty search recovery; silent media error; device labels; dialogs/prompts")
