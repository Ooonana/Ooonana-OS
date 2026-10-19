#!/usr/bin/env python3
"""Owned real MPD/mpc/UI/panel state flow; null output only, no audio device."""
import configparser
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme
from controls_app import MediaWindow

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
events = []
findings = []


def settle(seconds=0.15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


def wait(predicate, message, seconds=16):
    end = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < end, message
        settle(0.04)
    settle()


def mpc(*arguments):
    return subprocess.run(["mpc", *arguments], capture_output=True, text=True, timeout=6)


def check(condition, message):
    if not condition:
        findings.append(message)
        print("MEDIA_RUNTIME_FINDING", message, flush=True)


def capture(name):
    settle()
    root = Gdk.get_default_root_window()
    for suffix, height in (("", root.get_height()), ("-bar", min(72, root.get_height()))):
        Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), height).savev(
            str(output / (name + suffix + ".png")), "png", [], [])


def stop(process, group=False):
    if process is not None and process.poll() is None:
        if group:
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=5)


loader = SourceFileLoader("media_panel_windows", str(ROOT / "packages/ooonana/usr/bin/ooonana-window-list"))
windows = module_from_spec(spec_from_loader(loader.name, loader))
loader.exec_module(windows)
with tempfile.TemporaryDirectory(prefix="ooonana-media-session-") as temporary:
    fixture = Path(temporary)
    music = fixture / "Music"
    music.mkdir()
    configuration = fixture / "config/mpd/mpd.conf"
    configuration.parent.mkdir(parents=True)
    socket = fixture / "mpd.sock"
    os.environ.update(MPD_HOST=str(socket), XDG_CONFIG_HOME=str(fixture / "config"),
                      XDG_STATE_HOME=str(fixture / "state"), XDG_MUSIC_DIR=str(music))
    configuration.write_text(
        'music_directory "%s"\ndb_file "%s"\nstate_file "%s"\n'
        'bind_to_address "%s"\nzeroconf_enabled "no"\nauto_update "no"\nrestore_paused "yes"\n'
        'audio_output {\n type "null"\n name "Ooonana QA Null"\n sync "yes"\n mixer_type "software"\n}\n'
        % (music, fixture / "database", fixture / "player-state", socket))
    assert configuration.read_text().count('type "null"') == 1
    assert all(token not in configuration.read_text() for token in ('"pulse"', '"alsa"', '"pipewire"'))
    wm_config = fixture / "i3.conf"
    wm_config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                                  if not line.startswith("exec")) + "\n")
    log = (output / "services.log").open("w")
    wm = subprocess.Popen(["i3", "-c", str(wm_config)], stdout=log, stderr=log)
    daemon = panel = watcher = window = watch_log = reader = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0,
             "Owned window manager unavailable")

        def start_player():
            process = subprocess.Popen(["mpd", "--no-daemon", str(configuration)], stdout=log, stderr=log)
            wait(lambda: process.poll() is None and mpc("status").returncode == 0, "Private MPD unavailable")
            outputs = mpc("outputs").stdout.splitlines()
            assert len(outputs) == 1 and "Ooonana QA Null" in outputs[0] and "enabled" in outputs[0], outputs
            return process

        daemon = start_player()
        width = Gdk.get_default_root_window().get_width()
        left, right, gap, limit, wifi_limit = windows.panel_layout(width)
        os.environ.update(OOONANA_PANEL_LEFT=left, OOONANA_PANEL_RIGHT=right, OOONANA_PANEL_GAP=str(gap),
                          OOONANA_MEDIA_MAX_CHARS=str(limit), OOONANA_WIFI_MAX_CHARS=str(wifi_limit))
        watch_log = (output / "watch.log").open("w")
        watcher = subprocess.Popen(["ooonana-media-status", "--watch"], stdout=subprocess.PIPE,
                                   stderr=log, text=True, start_new_session=True)

        def read_events():
            for line in watcher.stdout:
                events.append(line.strip())
                watch_log.write(line)
                watch_log.flush()
        reader = threading.Thread(target=read_events, daemon=True)
        reader.start()
        builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
        text = builder.split('"$ROOTFS/etc/ooonana/polybar.ini" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
        bar = configparser.RawConfigParser(strict=False)
        bar.read_string(text)
        samples = {"memory": "RAM 42%", "wifi": "Connected", "audio": "70%", "battery": "85%", "notifications": "0"}
        for section in bar.sections():
            for key in list(bar[section]):
                if key.startswith(("click-", "scroll-")):
                    bar.remove_option(section, key)
            if bar[section].get("type") == "custom/script" and section != "module/media":
                sample = samples.get(section.removeprefix("module/"), "")
                bar[section]["exec"] = "printf '%s\\\\n' " + shlex.quote(sample)
                bar[section]["tail"] = "false"
                bar[section]["interval"] = "60"
        bar_path = fixture / "polybar.ini"
        with bar_path.open("w") as stream:
            bar.write(stream)
        panel = subprocess.Popen(["polybar", "-l", "info", "-c", str(bar_path), "ooonana"], stdout=log, stderr=log)
        apply_theme()
        window = MediaWindow()
        window.show_all()
        wait(lambda: window.player_ready and not window.refreshing and bool(events), "Empty music UI unavailable")
        frame = window.get_window().get_frame_extents()
        bar_bottom = (int(bar["bar/ooonana"]["offset-y"]) + int(bar["bar/ooonana"]["height"])
                      + 2 * int(bar["bar/ooonana"]["border-size"]))
        print("MEDIA_INITIAL_FRAME", frame.x, frame.y, frame.width, frame.height, "bar-bottom", bar_bottom, flush=True)
        check(frame.y >= bar_bottom, "Initial Music window covers panel")
        check(window.track_label.get_text() == "Nothing playing", "Empty library has stale track")
        check(events[-1].endswith(" Music"), "Empty panel label is not Music")
        capture("empty")
        names = ("01-한글긴제목%{F#ff0000}-음악상태검사.wav", "02-Next-owned-track.wav")
        for name in names:
            with wave.open(str(music / name), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(8000)
                audio.writeframes(b"\0\0" * 8000 * 120)
        window.library_button.clicked()
        wait(lambda: not window.action_busy and len(mpc("playlist").stdout.splitlines()) == 2,
             "Real library refresh did not load owned tracks")
        mark = len(events)
        window.play_button.clicked()
        wait(lambda: window.play_button.get_label() == "Pause" and "[playing]" in mpc("status").stdout,
             "Real Play action did not reach MPD")
        wait(lambda: any("\uf04b" in line for line in events[mark:]), "Panel watch missed playing transition")
        check(window.track_label.get_tooltip_text() == names[0], "Full filename tooltip lost Unicode/percent text")
        latest = events[-1]
        check("%{F" not in latest and len(latest.split("%{T-} ", 1)[-1]) <= limit,
              "Real panel filename escaped its text/style budget")
        capture("playing")
        mark = len(events)
        window.play_button.clicked()
        wait(lambda: window.play_button.get_label() == "Play" and window.progress.get_text().startswith("Paused"),
             "Real Pause action not reflected in UI")
        wait(lambda: any("\uf04c" in line for line in events[mark:]), "Panel watch missed pause transition")
        capture("paused")
        wait(lambda: window.volume_known and not window.action_busy, "MPD software volume unavailable")
        window.volume.set_value(61)
        window.volume_apply_button.clicked()
        wait(lambda: not window.action_busy and not window.volume_dirty and "61%" in mpc("volume").stdout,
             "Private player volume Apply did not persist")
        window.playback_actions[2].clicked()
        wait(lambda: window.track_label.get_text() == names[1] and not window.action_busy, "Real Next did not change track")
        window.playback_actions[3].clicked()
        wait(lambda: window.progress.get_text() == "Stopped" and not window.action_busy, "Real Stop did not settle")
        capture("stopped")
        mark = len(events)
        stop(daemon)
        wait(lambda: not window.player_ready and window.progress.get_text() == "Unavailable", "Timer missed MPD loss")
        check(not any(control.get_sensitive() for control in window.playback_actions), "Unavailable player actions remain active")
        capture("unavailable")
        wait(lambda: any(line.endswith(" Music") for line in events[mark:]), "Panel watch retained stale track after MPD loss")
        mark = len(events)
        daemon = start_player()
        wait(lambda: window.player_ready and not window.refreshing, "Timer failed to recover restarted MPD")
        wait(lambda: len(events) > mark, "Panel watch produced no fresh state after restart")
        check(panel.poll() is None and watcher.poll() is None, "Actual panel/watch exited during service restart")
        capture("recovered")
        print("MEDIA_RUNTIME_RESULTS", json.dumps(findings), flush=True)
        assert not findings, "; ".join(findings)
        print("MEDIA_RUNTIME_OK real MPD/mpc/null output, UI controls, watch transitions and timer recovery", flush=True)
    finally:
        if window is not None:
            window.destroy()
        stop(panel, group=False)
        stop(watcher, group=True)
        if reader is not None:
            reader.join(timeout=2)
        if watch_log is not None:
            watch_log.close()
        stop(daemon)
        stop(wm)
        log.close()
