#!/usr/bin/env python3
"""Actual Sound UI/PulseAudio routing; private server, null modules, no playback."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme
from controls_app import AudioWindow
from shell_flyout import QuickControls
from types import SimpleNamespace

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode
assert not Path("/dev/snd").exists(), "Refuse any exposed audio hardware"
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", round(96 * 1024 * float(os.environ["OOONANA_GUI_TEXT_SCALE"])))
apply_theme()


def wait(predicate, detail):
    deadline = time.monotonic() + 15
    while not predicate():
        assert time.monotonic() < deadline, detail
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.02)


def pactl(*args):
    return subprocess.check_output(["pactl", *args], text=True, stderr=subprocess.STDOUT, timeout=5)


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        process.wait(timeout=5)


with tempfile.TemporaryDirectory(prefix="ooonana-null-audio-") as temporary:
    fixture = Path(temporary)
    config = fixture / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                               if not line.startswith("exec")) + "\n")
    socket = fixture / "native"
    pulse_config = fixture / "pulse.pa"
    pulse_config.write_text(
        f"load-module module-native-protocol-unix socket={socket} auth-anonymous=1\n"
        "load-module module-null-sink sink_name=qa_speaker_a\n"
        "load-module module-null-sink sink_name=qa_speaker_b\n"
        "load-module module-null-source source_name=qa_microphone\n")
    assert all(name not in pulse_config.read_text() for name in ("alsa", "udev", "pipewire", "tcp"))
    client_config = fixture / "client.conf"
    client_config.write_text("autospawn = no\n")
    os.environ.update(PULSE_SERVER="unix:" + str(socket), PULSE_CLIENTCONFIG=str(client_config))
    log = (output / "services.log").open("w")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=log, stderr=log)
    server = window = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0,
             "Private window manager unavailable")
        server = subprocess.Popen(["pulseaudio", "-n", "--daemonize=no", "--exit-idle-time=-1",
            "--use-pid-file=no", "--file=" + str(pulse_config)], stdout=log, stderr=log)
        wait(lambda: server.poll() is None and socket.exists(), "Private null audio server unavailable")
        pactl("set-default-sink", "qa_speaker_a")
        pactl("set-default-source", "qa_microphone")
        pactl("set-sink-volume", "qa_speaker_a", "21%")
        pactl("set-sink-volume", "qa_speaker_b", "67%")
        window = AudioWindow()
        window.show_all()
        wait(lambda: not window.busy and window.service_ready and window.volume_known, "Sound readiness stalled")
        assert window.output_combo.get_active_id() == "qa_speaker_a" and int(window.scale.get_value()) == 21
        window.output_combo.set_active_id("qa_speaker_b")
        wait(lambda: not window.busy and int(window.scale.get_value()) == 67, "Selected sink volume not loaded")
        assert pactl("get-default-sink").strip() == "qa_speaker_a", "Selection changed default before Apply"
        window.scale.set_value(44)
        window.apply_button.clicked()
        wait(lambda: not window.busy and pactl("get-default-sink").strip() == "qa_speaker_b", "Route Apply failed")
        assert "44%" in pactl("get-sink-volume", "qa_speaker_b")
        assert "21%" in pactl("get-sink-volume", "qa_speaker_a")
        assert pactl("get-default-source").strip() == "qa_microphone"
        for muted in (True, False):
            window.mute_button.clicked()
            wait(lambda: not window.busy and window.muted is muted, "Mute state failed to settle")
            assert ("yes" in pactl("get-sink-mute", "qa_speaker_b")) == muted
            assert "no" in pactl("get-sink-mute", "qa_speaker_a")
        module_names = [line.split()[1] for line in pactl("list", "short", "modules").splitlines()]
        assert sorted(module_names) == sorted(["module-native-protocol-unix", "module-null-sink",
                                             "module-null-sink", "module-null-source"]), module_names
        assert not pactl("list", "short", "sink-inputs").strip(), "Unexpected playback stream"
        # GTK state callbacks can precede frame-clock paint. Capture settled UI.
        deadline = time.monotonic() + .25
        while time.monotonic() < deadline:
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            time.sleep(.01)
        assert not window.busy and "44%" in window.value_label.get_text()
        root = Gdk.get_default_root_window()
        frame = window.get_window().get_frame_extents()
        assert 0 <= frame.x and frame.x + frame.width <= root.get_width()
        assert 0 <= frame.y and frame.y + frame.height <= root.get_height()
        Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
            str(output / "sound-null-routing.png"), "png", [], [])
        print("AUDIO_RUNTIME_OK actual private PulseAudio, selected sink/default route, volume, mute, source; no playback streams or hardware modules", flush=True)
        window.destroy()
        window = QuickControls(SimpleNamespace(show_surface=lambda *_: None, dismiss=lambda *_: None))
        window.show_all()
        audio = window.audio
        wait(lambda: not audio.busy and audio.volume_known, "Control Center audio not ready")
        assert audio.output_combo.get_active_id() == "qa_speaker_b"
        # Another client changes defaults after the center opens. Its volume
        # slider must never silently restore hidden output/input selections.
        pactl("set-default-sink", "qa_speaker_a")
        pactl("set-default-source", "qa_speaker_a.monitor")
        audio.scale.set_value(33)
        audio.apply_button.clicked()
        wait(lambda: not audio.busy, "Control Center volume request stalled")
        assert "33%" in pactl("get-sink-volume", "qa_speaker_b")
        assert pactl("get-default-sink").strip() == "qa_speaker_a", "Control Center changed hidden default output"
        assert pactl("get-default-source").strip() == "qa_speaker_a.monitor", "Control Center changed hidden default input"
        print("CONTROL_CENTER_VOLUME_OK exact output volume; external default output/input preserved; no playback", flush=True)
    finally:
        if window is not None:
            window.destroy()
        stop(server)
        stop(wm)
        log.close()
