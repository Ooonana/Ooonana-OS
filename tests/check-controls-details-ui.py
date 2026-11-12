#!/usr/bin/env python3
"""Private GTK/i3 sound/backlight/music checks. No device or playback commands."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1" and os.getuid() != 0
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme
import controls_app as controls

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", int(96 * 1024 * float(os.environ.get("OOONANA_GUI_TEXT_SCALE", "1.0"))))
apply_theme()
jobs, notices, findings = [], [], []
controls.run = controls.launch = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("Unexpected real command"))
controls.run_async_task = lambda task, done: jobs.append((task, done))
controls.run_async = lambda command, done, **kw: jobs.append((command, done))
controls.message = lambda _parent, title, *_a, **_k: notices.append(title)


def check(condition, description):
    if not condition:
        findings.append(description)
        print("CONTROLS_DETAILS_FINDING: " + description, flush=True)


def settle(seconds=.2):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.005)


def capture(window, name):
    settle()
    root = Gdk.get_default_root_window()
    frame = window.get_window().get_frame_extents()
    check(0 <= frame.x and frame.x + frame.width <= root.get_width() and
          0 <= frame.y and frame.y + frame.height <= root.get_height(), f"{name}: frame outside display")
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(out / (name + ".png")), "png", [], [])


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


def apply_button(window):
    return next(w for w in descendants(window) if isinstance(w, Gtk.Button) and w.get_label() == "Apply")


def audio(**changes):
    state = dict(service_rc=0, service_output="", alsa_card_ready=True,
        outputs=[("fixture-output-a", "Fixture speakers · 긴 이름 " * 8), ("fixture-output-b", "Fixture headphones")],
        inputs=[("fixture-input", "Fixture microphone")], default_output="fixture-output-a", default_input="fixture-input",
        volume_rc=0, volume="Volume: front-left: 27525 / 42% / -22 dB", mute_rc=0, mute="Mute: no")
    return dict(state, **changes)


def late_close(window, callback, name):
    before = len(notices)
    window.destroy()
    jobs.clear()
    try:
        callback(1, "Fixture delayed permission denial")
    except Exception as error:
        check(False, name + ": closed callback raises " + type(error).__name__)
    check(len(notices) == before and not jobs, name + ": closed callback creates UI/work")


with tempfile.TemporaryDirectory(prefix="ooonana-controls-details-") as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines() if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < deadline
            time.sleep(.03)
        window = controls.AudioWindow()
        window.show_all()
        check(not window.apply_button.is_sensitive() and not window.mute_button.is_sensitive(), "Sound startup permits unverified actions")
        window.refresh_audio()
        check(len(jobs) == 1, "Sound duplicate refresh queued")
        jobs.clear()
        if hasattr(window, "busy"):
            window.busy = False
        if hasattr(window, "refreshing"):
            window.refreshing = False
        window.apply_audio_state(audio())
        for widget in (window.scale, window.output_combo, window.input_combo):
            check(bool(widget.get_accessible().get_name()), "Sound form control lacks accessible name")
        capture(window, "sound-ready")
        caption_width = window.more_button.create_pango_layout("More").get_pixel_size()[0]
        check(window.more_button.get_allocated_width() <= caption_width + 64, "More control stretches beyond text/icon proportions")
        window.get_window().focus(Gdk.CURRENT_TIME)
        window.more_button.grab_focus()
        settle()
        subprocess.run(["xdotool", "key", "--clearmodifiers", "space"], check=True)
        settle()
        check(window.more_button.get_popover().get_visible(), "Sound More tools not keyboard reachable")
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"], check=True)
        settle()
        check(not window.more_button.get_popover().get_visible(), "Sound More Escape failed")
        window.output_combo.set_active_id("fixture-output-b")
        check(bool(jobs), "Selected output does not load its own volume/mute")
        if jobs:
            jobs.pop()[1](0, audio(volume="Volume: mono: 6554 / 10% / -60 dB"))
        check(int(window.scale.get_value()) == 10, "Selected output shows previous output volume")
        jobs.clear()
        commands = []
        window.audio_command = lambda *args: (commands.append(args), (0, ""))[1]
        window.toggle_mute(window.mute_button)
        if jobs:
            jobs.pop()[0]()
        check(any(args[:2] == ("set-sink-mute", "fixture-output-b") for args in commands), "Mute not bound to selected output identity")
        window.destroy()
        jobs.clear()

        window = controls.AudioWindow()
        window.show_all()
        jobs.pop()[1](0, audio())
        jobs.clear()
        window.scale.set_value(67)
        window.apply(window.apply_button)
        pending = jobs[-1][1]
        window.apply(window.apply_button)
        window.refresh_audio()
        check(len(jobs) == 1, "Sound overlapping write/refresh allowed")
        pending(1, "Fixture permission denied")
        check(int(window.scale.get_value()) == 67, "Sound error erased volume draft")
        check("denied" in window.status.get_text().lower(), "Sound failure lacks persistent inline recovery")
        capture(window, "sound-permission-error")
        jobs.clear()
        window.apply_audio_state(audio(outputs=[], outputs_rc=1, outputs_error="Fixture device-list permission denied", inputs=[]))
        check("permission denied" in window.status.get_text() and not window.apply_button.is_sensitive(), "Device-list denial misreported as missing kernel hardware")
        window.apply_audio_state(audio(service_rc=1, service_output="Fixture service permission denied"))
        check(not window.apply_button.is_sensitive() and "permission denied" in window.status.get_text(), "Failed service presents ready routes")
        window.apply_audio_state(audio())
        window.output_combo.set_active_id("fixture-output-b")
        obsolete = jobs.pop()[1]
        window.output_combo.set_active_id("fixture-output-a")
        obsolete(0, audio(volume="Volume: mono: 6554 / 10% / -60 dB"))
        check(bool(jobs), "Changed output does not schedule fresh query")
        if jobs:
            jobs.pop()[1](0, audio())
        check(int(window.scale.get_value()) == 42, "Stale output response replaced current volume")
        jobs.clear()
        window.apply_audio_state(audio(mute_rc=1, mute=""))
        check(not window.mute_button.is_sensitive(), "Unknown mute state presents verified toggle")
        window.apply_audio_state(audio(outputs=[], inputs=[("fixture-input", "Fixture microphone")], default_output=""))
        check(window.apply_button.is_sensitive() and not window.scale.is_sensitive(), "Input-only audio cannot save microphone route")
        window.apply_audio_state(audio(outputs=[], inputs=[], service_rc=1, service_output="Fixture service unavailable", alsa_card_ready=False))
        check(not window.scale.is_sensitive() and not window.apply_button.is_sensitive(), "No-device Sound has live route controls")
        capture(window, "sound-unavailable")
        window.apply_audio_state(audio(mute_rc=1, mute=""))
        check(not window.mute_button.is_sensitive(), "Unknown mute state presents verified toggle")
        jobs.clear()
        window.refresh_audio()
        late_close(window, jobs[-1][1], "Sound")

        jobs.clear()
        window = controls.BrightnessWindow()
        window.show_all()
        action = apply_button(window)
        check(not action.is_sensitive(), "Brightness startup permits guessed-value Apply")
        check(bool(window.scale.get_accessible().get_name()), "Backlight slider lacks accessible name")
        startup = jobs.pop()[1]
        startup(1, "Fixture backlight unavailable")
        check(not action.is_sensitive(), "Missing backlight permits Apply")
        capture(window, "brightness-unavailable")
        window.refresh()
        jobs.pop()[1](0, "fixture-keyboard,leds,42,42%,100")
        check(not action.is_sensitive(), "Brightness accepts keyboard LED as display backlight")
        window.refresh()
        jobs.pop()[1](0, "fixture,backlight,0,0%,100")
        check("0%" in window.value_label.get_text() and action.is_sensitive(), "Zero backlight observation lost truthful current value/recovery")
        window.destroy()
        jobs.clear()
        window = controls.BrightnessWindow()
        window.show_all()
        jobs.pop()[1](0, "fixture,backlight,75,75%,100")
        action = apply_button(window)
        settle()
        window.get_window().focus(Gdk.CURRENT_TIME)
        window.scale.grab_focus()
        settle()
        before = window.scale.get_value()
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Right"], check=True)
        settle()
        check(window.scale.get_value() > before, "Backlight slider keyboard arrow failed")
        jobs.clear()
        window.apply(action)
        check("--device=fixture" in jobs[-1][0] and "--class=backlight" in jobs[-1][0], "Backlight write not bound to observed display device")
        pending = jobs[-1][1]
        window.apply(action)
        check(len(jobs) == 1, "Brightness duplicate write allowed")
        late_close(window, pending, "Brightness")

        jobs.clear()
        window = controls.MediaWindow()
        window.show_all()
        if window.timer_id:
            controls.GLib.source_remove(window.timer_id)
            window.timer_id = 0
        check(not any(w.is_sensitive() for w in window.playback_actions), "Music startup permits playback before readiness")
        jobs.pop()[1](0, "Fixture player ready")
        jobs.pop()[1](0, dict(current="Artist\tFixture track\t/file.flac", status="[paused] (20%)", volume="volume: 70%"))
        jobs.clear()
        window.refresh_state()
        refresh = jobs[-1][1]
        window.action(window.play_button, "play-pause")
        action_done = jobs[-1][1]
        refresh(0, dict(current="Artist\tFixture track\t/file.flac", status="[paused] (20%)", volume="volume: 70%"))
        check(not window.play_button.is_sensitive(), "Music polling re-enables pending playback")
        action_done(0, "")
        if jobs and callable(jobs[-1][0]):
            jobs[-1][1](0, dict(current="Artist\tFixture track\t/file.flac", status="[paused] (20%)", volume="volume: 70%"))
        window.volume.set_value(33)
        jobs.clear()
        window.refresh_state()
        if jobs:
            jobs[-1][1](0, dict(current="Artist\tFixture track\t/file.flac", status="[paused] (20%)", volume="volume: 70%"))
        check(int(window.volume.get_value()) == 33, "Music polling overwrites uncommitted volume draft")
        capture(window, "music-volume-draft")
        terminal = next(w for w in descendants(window) if isinstance(w, Gtk.Button) and w.get_label() == "Terminal player")
        terminal.grab_focus()
        settle()
        position = terminal.translate_coordinates(window, 0, 0)
        check(position is not None and position[1] >= 0 and position[1] + terminal.get_allocated_height() <= window.get_allocated_height(), "Music footer focus remains clipped")
        jobs.clear()
        window.action(window.play_button, "play-pause")
        late_close(window, jobs[-1][1], "Music")
    finally:
        wm.terminate()
        wm.wait(timeout=5)

if findings:
    raise SystemExit(1)
print("CONTROLS_DETAILS_UI_OK silent fixtures; readiness/identity/drafts; serialized actions; keyboard; closed refusal")
