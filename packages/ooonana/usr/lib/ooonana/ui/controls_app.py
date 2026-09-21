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
    read_file,
    run,
    run_async,
    run_async_task,
)


class BrightnessWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Brightness")
        self.set_default_size(540, 220)
        self.set_resizable(False)
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
        rc, output = run(["brightnessctl", "-m"], timeout=4)
        current = 75
        if rc == 0:
            try:
                current = int(output.split(",")[3].rstrip("%"))
            except (IndexError, ValueError):
                pass
        self.scale.set_value(current)
        if rc != 0:
            self.value_label.set_text("No controllable backlight detected")
            self.scale.set_sensitive(False)
            for child in actions.get_children():
                child.set_sensitive(False)
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
        self.set_default_size(560, 260)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, "Sound", "Default audio output", "audio-volume-high-symbolic")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_border_width(22)
        self.add(root)
        output_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        output_row.pack_start(label("Output"), False, False, 0)
        self.output_combo = Gtk.ComboBoxText()
        self.output_combo.set_hexpand(True)
        output_row.pack_start(self.output_combo, True, True, 0)
        output_row.pack_start(button("Refresh", "view-refresh-symbolic", self.refresh_outputs), False, False, 0)
        root.pack_start(output_row, False, False, 0)

        self.value_label = label("Volume", "card-title")
        root.pack_start(self.value_label, False, False, 0)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        self.scale.set_draw_value(False)
        self.scale.connect("value-changed", self.value_changed)
        root.pack_start(self.scale, False, False, 0)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.mute_button = button("Mute", "audio-volume-muted-symbolic", self.toggle_mute)
        actions.pack_start(self.mute_button, False, False, 0)
        actions.pack_start(button("Mixer", "multimedia-volume-control-symbolic", lambda *_: launch(["pavucontrol"])), False, False, 0)
        actions.pack_end(button("Apply", "object-select-symbolic", self.apply, "suggested-action"), False, False, 0)
        root.pack_start(actions, False, False, 0)
        self.status = label("Checking audio service...", "muted")
        root.pack_start(self.status, False, False, 0)
        self.refresh_outputs()
        rc, output = self.audio_command("get-sink-volume", "@DEFAULT_SINK@")
        current = 50
        if rc == 0 and "/" in output:
            try:
                current = int(output.split("/")[1].strip().rstrip("%"))
            except (IndexError, ValueError):
                pass
        self.scale.set_value(current)
        mute_rc, mute = run(["pactl", "get-sink-mute", "@DEFAULT_SINK@"], timeout=4)
        self.muted = mute_rc == 0 and mute.endswith("yes")
        self.update_mute_label()
        self.status.set_text("Audio ready" if rc == 0 else (output or "No audio output detected"))
        self.connect("destroy", Gtk.main_quit)

    def refresh_outputs(self, *_args):
        self.output_combo.remove_all()
        rc, output = self.audio_command("list", "short", "sinks")
        default_rc, default_sink = self.audio_command("get-default-sink")
        active_index = 0
        count = 0
        if rc == 0:
            for line in output.splitlines():
                fields = line.split("\t")
                if len(fields) < 2:
                    continue
                sink = fields[1]
                state = fields[4] if len(fields) > 4 else ""
                self.output_combo.append(sink, f"{sink}  {state}".strip())
                if default_rc == 0 and sink == default_sink.strip():
                    active_index = count
                count += 1
        if count:
            self.output_combo.set_sensitive(True)
            self.output_combo.set_active(active_index)
            if hasattr(self, "status"):
                self.status.set_text(f"{count} output device(s) ready")
        else:
            self.output_combo.append("", "No audio output detected")
            self.output_combo.set_active(0)
            self.output_combo.set_sensitive(False)
            if hasattr(self, "status"):
                self.status.set_text("No audio output detected")

    @staticmethod
    def audio_command(*arguments):
        rc, output = run(["pactl", *arguments], timeout=6)
        if rc == 0:
            return rc, output
        run(["pulseaudio", "--start", "--exit-idle-time=-1"], timeout=8)
        return run(["pactl", *arguments], timeout=8)

    def value_changed(self, scale):
        self.value_label.set_text(f"Volume  {int(scale.get_value())}%")

    def update_mute_label(self):
        self.mute_button.set_label("Unmute" if self.muted else "Mute")

    def toggle_mute(self, _widget):
        rc, output = self.audio_command("set-sink-mute", "@DEFAULT_SINK@", "toggle")
        if rc != 0:
            message(self, "Sound failed", output or "PulseAudio has no usable output", Gtk.MessageType.ERROR)
            return
        self.muted = not self.muted
        self.update_mute_label()

    def apply(self, widget):
        value = int(self.scale.get_value())
        sink = self.output_combo.get_active_id() or "@DEFAULT_SINK@"
        widget.set_sensitive(False)

        def done(rc, output):
            widget.set_sensitive(True)
            if rc != 0:
                message(self, "Sound failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)

        def task():
            if sink != "@DEFAULT_SINK@":
                rc, output = self.audio_command("set-default-sink", sink)
                if rc != 0:
                    return rc, output
                inputs_rc, inputs = self.audio_command("list", "short", "sink-inputs")
                if inputs_rc == 0:
                    for line in inputs.splitlines():
                        input_id = line.split("\t", 1)[0]
                        if input_id.isdigit():
                            self.audio_command("move-sink-input", input_id, sink)
            return self.audio_command("set-sink-volume", sink, f"{value}%")

        run_async_task(task, done)


class KeyboardWindow(Gtk.Window):
    LAYOUTS = (
        ("us", "English (US)"),
        ("us,kr", "English + Korean (Alt+Shift)"),
        ("kr", "Korean"),
        ("gb", "English (UK)"),
        ("de", "German"),
        ("fr", "French"),
        ("jp", "Japanese"),
    )

    def __init__(self):
        super().__init__(title="Ooonana Keyboard")
        self.set_default_size(580, 260)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, "Keyboard", "Layout and media keys", "input-keyboard-symbolic")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_border_width(22)
        self.add(root)
        root.pack_start(label("Keyboard layout", "card-title"), False, False, 0)
        self.layout_combo = Gtk.ComboBoxText()
        for layout_id, title in self.LAYOUTS:
            self.layout_combo.append(layout_id, title)
        current = read_file(Path.home() / ".config/ooonana/keyboard-layout", "")
        if not current:
            rc, output = run(["setxkbmap", "-query"], timeout=4)
            if rc == 0:
                current = next(
                    (line.split(":", 1)[1].strip() for line in output.splitlines() if line.startswith("layout:")),
                    "us",
                )
        valid = {item[0] for item in self.LAYOUTS}
        self.layout_combo.set_active_id(current if current in valid else "us")
        root.pack_start(self.layout_combo, False, False, 0)
        root.pack_start(
            label("Brightness, volume, mute, touchpad, and Print Screen keys follow standard XF86 bindings.", "muted"),
            False,
            False,
            0,
        )
        root.pack_end(button("Apply", "object-select-symbolic", self.apply, "suggested-action"), False, False, 0)
        self.connect("destroy", Gtk.main_quit)

    def apply(self, widget):
        layout = self.layout_combo.get_active_id() or "us"
        widget.set_sensitive(False)

        def done(rc, output):
            widget.set_sensitive(True)
            if rc != 0:
                message(self, "Keyboard layout failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)

        run_async(["ooonana-keyboard", "set", layout], done, timeout=15)


class ThermalWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Thermal and Fan")
        self.set_default_size(660, 420)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, "Thermal and Fan", "Safe firmware-backed control", "weather-clear-symbolic")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_border_width(22)
        self.add(root)

        profile_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        profile_row.pack_start(label("Performance profile"), False, False, 0)
        self.profile_combo = Gtk.ComboBoxText()
        self.profile_combo.set_hexpand(True)
        profile_row.pack_start(self.profile_combo, True, True, 0)
        self.apply_button = button("Apply", "object-select-symbolic", self.apply, "suggested-action")
        profile_row.pack_start(self.apply_button, False, False, 0)
        root.pack_start(profile_row, False, False, 0)

        self.summary = Gtk.TextView()
        self.summary.set_editable(False)
        self.summary.set_cursor_visible(False)
        self.summary.set_monospace(True)
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(240)
        scroll.add(self.summary)
        root.pack_start(scroll, True, True, 0)
        root.pack_start(
            label("Direct PWM writes are disabled. Firmware platform profiles control cooling safely when supported.", "muted"),
            False,
            False,
            0,
        )
        root.pack_end(button("Refresh", "view-refresh-symbolic", self.refresh), False, False, 0)
        self.connect("destroy", Gtk.main_quit)
        self.refresh()

    @staticmethod
    def thermal_summary():
        lines = []
        for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
            kind = read_file(zone / "type", zone.name)
            raw = read_file(zone / "temp", "")
            try:
                value = float(raw) / 1000 if abs(float(raw)) >= 1000 else float(raw)
            except ValueError:
                continue
            lines.append(f"{kind}: {value:.1f} C")
        for device in sorted(Path("/sys/class/thermal").glob("cooling_device*")):
            kind = read_file(device / "type", device.name)
            state = read_file(device / "cur_state", "?")
            maximum = read_file(device / "max_state", "?")
            lines.append(f"{kind}: cooling {state}/{maximum}")
        for fan_input in sorted(Path("/sys/class/hwmon").glob("hwmon*/fan*_input")):
            chip = read_file(fan_input.parent / "name", fan_input.parent.name)
            rpm = read_file(fan_input, "?")
            lines.append(f"{chip} {fan_input.stem}: {rpm} RPM")
        if not lines and Path("/usr/bin/sensors").exists():
            rc, output = run(["sensors"], timeout=8)
            if rc == 0:
                lines.extend(output.splitlines())
        return "\n".join(lines) or "No thermal or cooling telemetry exposed by firmware."

    def refresh(self, *_args):
        choices = read_file("/sys/firmware/acpi/platform_profile_choices", "").split()
        current = read_file("/sys/firmware/acpi/platform_profile", "")
        self.profile_combo.remove_all()
        for choice in choices:
            self.profile_combo.append(choice, choice.replace("-", " ").title())
        if choices:
            self.profile_combo.set_active_id(current if current in choices else choices[0])
            self.profile_combo.set_sensitive(True)
            self.apply_button.set_sensitive(True)
        else:
            self.profile_combo.append("", "Firmware profile control unavailable")
            self.profile_combo.set_active(0)
            self.profile_combo.set_sensitive(False)
            self.apply_button.set_sensitive(False)
        self.summary.get_buffer().set_text(self.thermal_summary())

    def apply(self, widget):
        profile = self.profile_combo.get_active_id() or ""
        if not profile:
            return
        widget.set_sensitive(False)

        def done(rc, output):
            widget.set_sensitive(True)
            if rc != 0:
                message(self, "Thermal profile failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
            self.refresh()

        run_async(["ooonana-hardware-profile", profile], done, admin=True, timeout=15)


class PowerWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Power")
        self.set_default_size(620, 320)
        self.set_resizable(False)
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
        print("modes: brightness audio keyboard thermal power")
        print("OOONANA_CONTROLS_NATIVE_OK")
        return 0
    apply_theme()
    if mode == "brightness":
        window = BrightnessWindow()
    elif mode in ("audio", "sound", "volume"):
        window = AudioWindow()
    elif mode == "keyboard":
        window = KeyboardWindow()
    elif mode in ("thermal", "fan", "performance"):
        window = ThermalWindow()
    elif mode == "power":
        window = PowerWindow()
    else:
        print("usage: controls_app.py brightness|audio|keyboard|thermal|power", file=sys.stderr)
        return 2
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
