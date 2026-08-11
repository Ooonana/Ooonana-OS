#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
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

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.mute_button = button("Mute", "audio-volume-muted-symbolic", self.toggle_mute)
        actions.pack_start(self.mute_button, False, False, 0)
        actions.pack_start(button("Mixer", "multimedia-volume-control-symbolic", lambda *_: launch(["pavucontrol"])), False, False, 0)
        actions.pack_start(button("Repair audio", "view-refresh-symbolic", self.repair_audio), False, False, 0)
        actions.pack_start(button("Diagnostics", "dialog-information-symbolic", self.show_diagnostics), False, False, 0)
        actions.pack_end(button("Apply", "object-select-symbolic", self.apply, "suggested-action"), False, False, 0)
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
        outputs = data["outputs"]
        inputs = data["inputs"]
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
        self.status.set_text(
            f"Audio service ready | {len(outputs)} output(s) | {len(inputs)} input(s)"
            if outputs or inputs
            else data["service_output"] or "Audio service runs, but no output or input is exposed. Open Diagnostics."
        )

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

        def done(rc, output):
            widget.set_sensitive(True)
            self.refresh_audio()
            if rc != 0:
                message(self, "Audio repair failed", output or "Audio server did not become ready.", Gtk.MessageType.ERROR)

        run_async(["ooonana-audio-start", "--restart"], done, timeout=25)

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
        print("modes: brightness audio power")
        print("OOONANA_CONTROLS_NATIVE_OK")
        return 0
    apply_theme()
    if mode == "brightness":
        window = BrightnessWindow()
    elif mode in ("audio", "sound", "volume"):
        window = AudioWindow()
    elif mode == "power":
        window = PowerWindow()
    else:
        print("usage: controls_app.py brightness|audio|power", file=sys.stderr)
        return 2
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
