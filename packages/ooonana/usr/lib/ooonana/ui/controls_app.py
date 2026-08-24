#!/usr/bin/env python3
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    GLib,
    Gtk,
    apply_theme,
    button,
    header,
    label,
    launch,
    message,
    run,
    run_async,
    run_async_task,
)


class BrightnessWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Brightness")
        self.set_default_size(540, 220)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, "Brightness", "Display backlight", "display-brightness-symbolic")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_border_width(22)
        self.add(root)
        self.value_label = label("Backlight", "card-title")
        root.pack_start(self.value_label, False, False, 0)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        self.scale.set_hexpand(True)
        self.scale.set_draw_value(False)
        self.scale.connect("value-changed", self.value_changed)
        root.pack_start(self.scale, False, False, 0)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.pack_start(button("25%", callback=lambda *_: self.scale.set_value(25)), False, False, 0)
        actions.pack_start(button("50%", callback=lambda *_: self.scale.set_value(50)), False, False, 0)
        actions.pack_start(button("75%", callback=lambda *_: self.scale.set_value(75)), False, False, 0)
        actions.pack_start(button("100%", callback=lambda *_: self.scale.set_value(100)), False, False, 0)
        actions.pack_end(button("Apply", "object-select-symbolic", self.apply, "suggested-action"), False, False, 0)
        root.pack_start(actions, False, False, 0)
        self.scale.set_value(75)

        def loaded(rc, output):
            if rc != 0:
                return
            try:
                self.scale.set_value(int(output.split(",")[3].rstrip("%")))
            except (IndexError, ValueError):
                pass

        run_async(["brightnessctl", "-m"], loaded, timeout=4)
        self.connect("destroy", Gtk.main_quit)

    def value_changed(self, scale):
        self.value_label.set_text(f"Backlight  {int(scale.get_value())}%")

    def apply(self, widget):
        value = int(self.scale.get_value())
        widget.set_sensitive(False)

        def done(rc, output):
            widget.set_sensitive(True)
            if rc != 0:
                message(self, "Brightness failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)

        run_async(["brightnessctl", "set", f"{value}%"], done, admin=True, timeout=15)


class AudioWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Sound")
        self.set_default_size(700, 440)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, "Sound", "Outputs, inputs, and volume", "audio-volume-high-symbolic")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_border_width(22)
        self.add(root)
        self.value_label = label("Volume", "card-title")
        root.pack_start(self.value_label, False, False, 0)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        self.scale.set_draw_value(False)
        self.scale.connect("value-changed", self.value_changed)
        root.pack_start(self.scale, False, False, 0)

        devices = Gtk.Grid(column_spacing=12, row_spacing=10)
        devices.attach(label("Output"), 0, 0, 1, 1)
        self.output_combo = Gtk.ComboBoxText()
        self.output_combo.set_hexpand(True)
        devices.attach(self.output_combo, 1, 0, 1, 1)
        devices.attach(label("Input"), 0, 1, 1, 1)
        self.input_combo = Gtk.ComboBoxText()
        self.input_combo.set_hexpand(True)
        devices.attach(self.input_combo, 1, 1, 1, 1)
        root.pack_start(devices, False, False, 0)
        self.hardware_status = label("Detecting ALSA hardware...", "status-warn")
        self.hardware_status.set_line_wrap(True)
        root.pack_start(self.hardware_status, False, False, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.mute_button = button("Mute", "audio-volume-muted-symbolic", self.toggle_mute)
        actions.pack_start(self.mute_button, False, False, 0)
        actions.pack_start(button("Mixer", "multimedia-volume-control-symbolic", lambda *_: launch(["pavucontrol"])), False, False, 0)
        actions.pack_start(button("Retry hardware", "view-refresh-symbolic", self.repair_audio), False, False, 0)
        actions.pack_start(button("Diagnostics", "dialog-information-symbolic", self.show_diagnostics), False, False, 0)
        self.apply_button = button("Apply", "object-select-symbolic", self.apply, "suggested-action")
        actions.pack_end(self.apply_button, False, False, 0)
        root.pack_start(actions, False, False, 0)
        self.status = label("Checking audio service...", "muted")
        root.pack_start(self.status, False, False, 0)
        self.scale.set_value(50)
        self.muted = False
        self.update_mute_label()
        self.connect("destroy", Gtk.main_quit)
        self.refresh_audio()

    @staticmethod
    def audio_command(*arguments):
        rc, output = run(["pactl", *arguments], timeout=6)
        if rc == 0:
            return rc, output
        run(["ooonana-audio-start"], timeout=18)
        return run(["pactl", *arguments], timeout=8)

    @staticmethod
    def list_audio_devices(kind):
        rc, output = run(["pactl", "list", "short", kind], timeout=8)
        if rc != 0:
            return []
        devices = []
        for line in output.splitlines():
            fields = line.split("\t")
            if len(fields) >= 2 and fields[1]:
                devices.append((fields[1], fields[1].replace("alsa_", "").replace("_", " ")))
        return devices

    def collect_audio_state(self):
        service_rc, service_output = self.audio_command("info")
        outputs = self.list_audio_devices("sinks")
        inputs = self.list_audio_devices("sources")
        default_output_rc, default_output = run(["pactl", "get-default-sink"], timeout=5)
        default_input_rc, default_input = run(["pactl", "get-default-source"], timeout=5)
        volume_rc, volume = self.audio_command("get-sink-volume", "@DEFAULT_SINK@")
        mute_rc, mute = run(["pactl", "get-sink-mute", "@DEFAULT_SINK@"], timeout=4)
        return {
            "service_rc": service_rc,
            "service_output": service_output,
            "outputs": outputs,
            "inputs": inputs,
            "default_output": default_output.strip() if default_output_rc == 0 else "",
            "default_input": default_input.strip() if default_input_rc == 0 else "",
            "volume_rc": volume_rc,
            "volume": volume,
            "mute_rc": mute_rc,
            "mute": mute,
        }

    def apply_audio_state(self, data):
        self.output_combo.remove_all()
        self.input_combo.remove_all()
        outputs = [item for item in data["outputs"] if not item[0].startswith("auto_null")]
        inputs = [item for item in data["inputs"] if not item[0].startswith("auto_null")]
        for device_id, title in outputs:
            self.output_combo.append(device_id, title)
        for device_id, title in inputs:
            self.input_combo.append(device_id, title)
        if outputs:
            if not data["default_output"] or not self.output_combo.set_active_id(data["default_output"]):
                self.output_combo.set_active(0)
        if inputs:
            if not data["default_input"] or not self.input_combo.set_active_id(data["default_input"]):
                self.input_combo.set_active(0)
        if data["volume_rc"] == 0 and "/" in data["volume"]:
            try:
                self.scale.set_value(int(data["volume"].split("/")[1].strip().rstrip("%")))
            except (IndexError, ValueError):
                pass
        self.muted = data["mute_rc"] == 0 and data["mute"].endswith("yes")
        self.update_mute_label()
        self.scale.set_sensitive(bool(outputs))
        self.output_combo.set_sensitive(bool(outputs))
        self.input_combo.set_sensitive(bool(inputs))
        self.mute_button.set_sensitive(bool(outputs))
        self.apply_button.set_sensitive(bool(outputs or inputs))
        if outputs or inputs:
            self.hardware_status.set_text("ALSA hardware detected")
            self.status.set_text(f"Audio ready | {len(outputs)} output(s) | {len(inputs)} input(s)")
        elif data["service_rc"] == 0:
            self.hardware_status.set_text(
                "No ALSA card. Retry hardware. If still missing, reboot into GRUB > Audio compatibility > legacy HDA."
            )
            self.status.set_text("PipeWire is ready; kernel audio hardware is missing.")
        else:
            self.hardware_status.set_text("Audio service unavailable")
            self.status.set_text(data["service_output"] or "Audio server is unavailable. Use Repair audio.")

    def refresh_audio(self):
        self.status.set_text("Checking audio service...")

        def task():
            return 0, self.collect_audio_state()

        def done(rc, data):
            if rc != 0:
                self.status.set_text(str(data))
                return
            self.apply_audio_state(data)

        run_async_task(task, done)

    def refresh_devices(self):
        self.refresh_audio()

    def repair_audio(self, widget):
        widget.set_sensitive(False)

        def task():
            probe_rc, probe_output = run(["ooonana-audio-hardware-reprobe"], admin=True, timeout=35)
            audio_rc, audio_output = run(["ooonana-audio-start", "--restart"], timeout=25)
            if audio_rc != 0:
                return audio_rc, audio_output
            return probe_rc, probe_output

        def done(rc, output):
            widget.set_sensitive(True)
            self.refresh_audio()
            if rc != 0:
                message(self, "Audio repair failed", output or "Audio server did not become ready.", Gtk.MessageType.ERROR)

        run_async_task(task, done)

    def show_diagnostics(self, _widget):
        self.status.set_text("Collecting audio diagnostics...")

        def task():
            sections = []
            for title, command in (
                ("Audio server", ["pactl", "info"]),
                ("Outputs", ["pactl", "list", "short", "sinks"]),
                ("Inputs", ["pactl", "list", "short", "sources"]),
                ("ALSA playback", ["aplay", "-l"]),
                ("ALSA capture", ["arecord", "-l"]),
                ("Hardware probe", ["ooonana-audio-hardware-reprobe", "--report"]),
            ):
                rc, output = run(command, timeout=8)
                sections.append(f"{title}:\n{output or 'unavailable'}" if rc == 0 else f"{title}:\n{output or 'failed'}")
            return 0, "\n\n".join(sections)

        def done(_rc, output):
            self.status.set_text("Audio diagnostics ready")
            message(self, "Sound diagnostics", output)

        run_async_task(task, done)

    def value_changed(self, scale):
        self.value_label.set_text(f"Volume  {int(scale.get_value())}%")

    def update_mute_label(self):
        self.mute_button.set_label("Unmute" if self.muted else "Mute")

    def toggle_mute(self, _widget):
        self.mute_button.set_sensitive(False)

        def task():
            return self.audio_command("set-sink-mute", "@DEFAULT_SINK@", "toggle")

        def done(rc, output):
            self.mute_button.set_sensitive(True)
            if rc != 0:
                message(self, "Sound failed", output or "PulseAudio has no usable output", Gtk.MessageType.ERROR)
                return
            self.muted = not self.muted
            self.update_mute_label()

        run_async_task(task, done)

    def apply(self, widget):
        value = int(self.scale.get_value())
        output_id = self.output_combo.get_active_id()
        input_id = self.input_combo.get_active_id()
        widget.set_sensitive(False)

        def done(rc, output):
            widget.set_sensitive(True)
            if rc != 0:
                message(self, "Sound failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)

        def task():
            if output_id:
                rc, output = self.audio_command("set-default-sink", output_id)
                if rc != 0:
                    return rc, output
            if input_id:
                rc, output = self.audio_command("set-default-source", input_id)
                if rc != 0:
                    return rc, output
            return self.audio_command("set-sink-volume", "@DEFAULT_SINK@", f"{value}%")

        run_async_task(task, done)


class MediaWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Music")
        self.set_default_size(720, 460)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, "Music", "Local library and playback", "multimedia-player-symbolic")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_border_width(22)
        self.add(root)

        now_playing = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        cover = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic", Gtk.IconSize.DIALOG)
        cover.set_size_request(96, 96)
        now_playing.pack_start(cover, False, False, 0)
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.track_label = label("Nothing playing", "page-title")
        self.artist_label = label("Add audio files to Music, then refresh library.", "muted")
        self.state_label = label("Starting player...", "status-warn")
        details.pack_start(self.track_label, False, False, 0)
        details.pack_start(self.artist_label, False, False, 0)
        details.pack_start(self.state_label, False, False, 0)
        now_playing.pack_start(details, True, True, 0)
        root.pack_start(now_playing, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text("Stopped")
        root.pack_start(self.progress, False, False, 0)

        playback = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        playback.set_halign(Gtk.Align.CENTER)
        playback.pack_start(button("Previous", "media-skip-backward-symbolic", lambda widget: self.action(widget, "previous")), False, False, 0)
        self.play_button = button("Play", "media-playback-start-symbolic", lambda widget: self.action(widget, "play-pause"), "suggested-action")
        playback.pack_start(self.play_button, False, False, 0)
        playback.pack_start(button("Next", "media-skip-forward-symbolic", lambda widget: self.action(widget, "next")), False, False, 0)
        playback.pack_start(button("Stop", "media-playback-stop-symbolic", lambda widget: self.action(widget, "stop")), False, False, 0)
        root.pack_start(playback, False, False, 0)

        volume_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        volume_row.pack_start(label("Player volume"), False, False, 0)
        self.volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume.set_hexpand(True)
        self.volume.set_value(70)
        volume_row.pack_start(self.volume, True, True, 0)
        volume_row.pack_start(button("Apply", "object-select-symbolic", self.apply_volume), False, False, 0)
        root.pack_start(volume_row, False, False, 0)

        tools = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tools.pack_start(button("Refresh library", "view-refresh-symbolic", self.refresh_library), False, False, 0)
        tools.pack_start(button("Music folder", "folder-music-symbolic", lambda *_: launch(["ooonana-media-control", "open"])), False, False, 0)
        tools.pack_start(button("Terminal player", "utilities-terminal-symbolic", lambda *_: launch(["ooonana-media-control", "terminal"])), False, False, 0)
        root.pack_end(tools, False, False, 0)

        self.refreshing = False
        self.timer_id = GLib.timeout_add_seconds(2, self.periodic_refresh)
        self.connect("destroy", self.destroyed)
        run_async(["ooonana-media-control", "status"], self.player_started, timeout=20)

    def destroyed(self, *_args):
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = 0
        Gtk.main_quit()

    def player_started(self, rc, output):
        if rc != 0:
            self.state_label.set_text(output or "MPD failed to start")
            return
        self.refresh_state()

    def periodic_refresh(self):
        self.refresh_state()
        return True

    @staticmethod
    def collect_state():
        current_rc, current = run(["mpc", "--format", "%artist%\t%title%\t%file%", "current"], timeout=5)
        status_rc, status = run(["mpc", "status"], timeout=5)
        volume_rc, volume = run(["mpc", "volume"], timeout=5)
        return 0, {
            "current": current if current_rc == 0 else "",
            "status": status if status_rc == 0 else "",
            "volume": volume if volume_rc == 0 else "",
        }

    def refresh_state(self):
        if self.refreshing:
            return
        self.refreshing = True

        def done(_rc, data):
            self.refreshing = False
            fields = data["current"].split("\t", 2) if data["current"] else []
            artist = fields[0].strip() if fields else ""
            title = fields[1].strip() if len(fields) > 1 else ""
            filename = fields[2].strip() if len(fields) > 2 else ""
            self.track_label.set_text(title or filename or "Nothing playing")
            self.artist_label.set_text(artist or ("Local music" if title or filename else "Add audio files to Music, then refresh library."))

            status = data["status"]
            if "[playing]" in status:
                state = "Playing"
                self.play_button.set_label("Pause")
            elif "[paused]" in status:
                state = "Paused"
                self.play_button.set_label("Play")
            else:
                state = "Stopped"
                self.play_button.set_label("Play")
            percent = re.search(r"\((\d+)%\)", status)
            fraction = min(100, int(percent.group(1))) / 100 if percent else 0
            self.progress.set_fraction(fraction)
            timing = re.search(r"(\d+:\d+)/(\d+:\d+)", status)
            self.progress.set_text(f"{state}  {timing.group(1)} / {timing.group(2)}" if timing else state)
            self.state_label.set_text("MPD ready" if status else "Player ready; library empty")

            volume = re.search(r"volume:\s*(\d+)%", data["volume"])
            if volume:
                self.volume.set_value(int(volume.group(1)))

        run_async_task(self.collect_state, done)

    def action(self, widget, action):
        widget.set_sensitive(False)

        def done(rc, output):
            widget.set_sensitive(True)
            if rc != 0:
                message(self, "Playback failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh_state()

        run_async(["ooonana-media-control", action], done, timeout=20)

    def apply_volume(self, widget):
        value = int(self.volume.get_value())
        widget.set_sensitive(False)

        def done(rc, output):
            widget.set_sensitive(True)
            if rc != 0:
                message(self, "Volume failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh_state()

        run_async(["ooonana-media-control", "volume", str(value)], done, timeout=10)

    def refresh_library(self, widget):
        widget.set_sensitive(False)
        self.state_label.set_text("Refreshing music library...")

        def done(rc, output):
            widget.set_sensitive(True)
            if rc != 0:
                message(self, "Library refresh failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh_state()

        run_async(["ooonana-media-control", "update"], done, timeout=90)


class PowerWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Power")
        self.set_default_size(620, 320)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, "Power", "Session and computer", "system-shutdown-symbolic")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_border_width(22)
        self.add(root)
        root.pack_start(label("What should Ooonana do?", "page-title"), False, False, 0)
        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_column_homogeneous(True)
        actions = [
            ("Lock", "system-lock-screen-symbolic", self.lock, None),
            ("Log out", "system-log-out-symbolic", self.logout, None),
            ("Restart i3", "view-refresh-symbolic", self.restart_i3, None),
            ("Reboot", "system-reboot-symbolic", lambda *_: self.confirm("reboot"), None),
            ("Shut down", "system-shutdown-symbolic", lambda *_: self.confirm("shutdown"), "destructive-action"),
            ("Cancel", "window-close-symbolic", lambda *_: self.destroy(), None),
        ]
        for index, (title, icon_name, callback, style) in enumerate(actions):
            widget = button(title, icon_name, callback, style)
            widget.set_size_request(170, 70)
            grid.attach(widget, index % 3, index // 3, 1, 1)
        root.pack_start(grid, True, True, 0)
        self.connect("destroy", Gtk.main_quit)

    @staticmethod
    def lock(*_args):
        if not launch(["i3lock"]):
            launch(["xset", "dpms", "force", "off"])

    @staticmethod
    def logout(*_args):
        launch(["i3-msg", "exit"])

    @staticmethod
    def restart_i3(*_args):
        launch(["i3-msg", "restart"])

    def confirm(self, action):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text=f"{action.title()} Ooonana OS?",
        )
        dialog.format_secondary_text("Unsaved work will be lost.")
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, action.title(), Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            dialog.destroy()
            command = ["bunana", "--restart" if action == "reboot" else "--shutdown"]

            def done(rc, output):
                if rc != 0:
                    message(
                        self,
                        f"{action.title()} failed",
                        output or f"Exit status {rc}",
                        Gtk.MessageType.ERROR,
                    )

            run_async(command, done, timeout=20)
            return
        dialog.destroy()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "brightness"
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana quick controls")
        print("modes: brightness audio media power")
        print("OOONANA_CONTROLS_NATIVE_OK")
        return 0
    apply_theme()
    if mode == "brightness":
        window = BrightnessWindow()
    elif mode in ("audio", "sound", "volume"):
        window = AudioWindow()
    elif mode in ("media", "music", "player"):
        window = MediaWindow()
    elif mode == "power":
        window = PowerWindow()
    else:
        print("usage: controls_app.py brightness|audio|media|power", file=sys.stderr)
        return 2
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
