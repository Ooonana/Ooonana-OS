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
        rc, output = run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], timeout=4)
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
        self.connect("destroy", Gtk.main_quit)

    def value_changed(self, scale):
        self.value_label.set_text(f"Volume  {int(scale.get_value())}%")

    def update_mute_label(self):
        self.mute_button.set_label("Unmute" if self.muted else "Mute")

    def toggle_mute(self, _widget):
        run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], timeout=6)
        self.muted = not self.muted
        self.update_mute_label()

    def apply(self, widget):
        value = int(self.scale.get_value())
        widget.set_sensitive(False)

        def done(rc, output):
            widget.set_sensitive(True)
            if rc != 0:
                message(self, "Sound failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)

        run_async(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{value}%"], done, timeout=15)


class PowerWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Power")
        self.set_default_size(620, 320)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, "Power", "Session and computer", "system-shutdown-symbolic")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_border_width(22)
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
