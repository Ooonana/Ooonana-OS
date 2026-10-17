#!/usr/bin/env python3
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    GLib,
    Gtk,
    Pango,
    apply_theme,
    button,
    flow_row,
    fit_dialog,
    header,
    label,
    launch,
    message,
    more_actions,
    run,
    run_async,
    run_async_task,
)
from ui_preferences import transition_ms  # noqa: E402


class ControlWindowState:
    def init_control_state(self):
        self.closed = False
        self.busy = False

    def add_status(self, root):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.spinner = Gtk.Spinner()
        self.spinner.set_no_show_all(True)
        self.spinner.set_valign(Gtk.Align.START)
        self.status = label("", "muted")
        self.status.set_lines(3)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        self.status.set_selectable(True)
        row.pack_start(self.spinner, False, False, 0)
        row.pack_start(self.status, True, True, 0)
        root.pack_start(row, False, False, 0)

    def feedback(self, text, state="neutral"):
        if self.closed:
            return
        self.status.set_text(text)
        self.status.set_tooltip_text(text)
        self.status.get_accessible().set_description(text)
        context = self.status.get_style_context()
        for name in ("good", "bad", "warn", "neutral"):
            context.remove_class("status-" + name)
        context.add_class("status-" + state)

    def begin(self, text):
        if self.closed or self.busy:
            return False
        self.busy = True
        self.update_controls()
        self.feedback(text, "warn")
        if transition_ms():
            self.spinner.show()
            self.spinner.start()
        return True

    def finish(self):
        if self.closed:
            return
        self.busy = False
        self.spinner.stop()
        self.spinner.hide()
        self.update_controls()

    def on_destroy(self, *_args):
        self.closed = True
        self.spinner.stop()
        if Gtk.main_level():
            Gtk.main_quit()


def control_body(window, width, height):
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    root.set_border_width(18)
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scroll.add(root)
    root.set_focus_vadjustment(scroll.get_vadjustment())
    root.set_focus_hadjustment(scroll.get_hadjustment())
    window.add(scroll)
    fit_dialog(window, width, height)
    return root


class BrightnessWindow(ControlWindowState, Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Brightness")
        self.init_control_state()
        self.ready = False
        self.loading = False
        self.backlight_device = None
        self.set_default_size(540, 220)
        self.set_position(Gtk.WindowPosition.CENTER)
        bar = header(self, "Brightness", "Display backlight", "display-brightness-symbolic")
        self.refresh_button = button("Refresh", "view-refresh-symbolic", lambda *_: self.refresh())
        bar.pack_end(self.refresh_button)
        root = control_body(self, 540, 280)
        self.value_label = label("Backlight unavailable", "card-title")
        root.pack_start(self.value_label, False, False, 0)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        self.scale.set_hexpand(True)
        self.scale.set_draw_value(False)
        self.scale.get_accessible().set_name("Backlight brightness")
        self.scale.connect("value-changed", self.value_changed)
        root.pack_start(self.scale, False, False, 0)
        self.presets = [button(f"{value}%", callback=lambda *_args, value=value: self.scale.set_value(value)) for value in (25, 50, 75, 100)]
        self.apply_button = button("Apply", "object-select-symbolic", self.apply, "suggested-action")
        actions = flow_row([*self.presets, self.apply_button], max_children=5, min_children=1)
        root.pack_start(actions, False, False, 0)
        self.add_status(root)
        self.connect("destroy", self.on_destroy)
        self.refresh()

    def update_controls(self):
        enabled = not (self.busy or self.closed)
        self.refresh_button.set_sensitive(enabled)
        for widget in (self.scale, self.apply_button, *self.presets):
            widget.set_sensitive(enabled and self.ready)

    def refresh(self):
        if not self.begin("Reading backlight…"):
            return

        def loaded(rc, output):
            if self.closed:
                return
            try:
                fields = output.splitlines()[0].split(",") if rc == 0 else []
                value = int(fields[3].rstrip("%")) if fields[1] == "backlight" and fields[0] else None
            except (IndexError, ValueError):
                value = None
            self.ready = value is not None and 0 <= value <= 100
            self.backlight_device = fields[0] if self.ready else None
            self.loading = True
            if self.ready:
                self.scale.set_value(max(1, value))
                self.value_label.set_text(f"Backlight  {value}%" + (" (current)" if value == 0 else ""))
            else:
                self.value_label.set_text("Backlight unavailable")
            self.loading = False
            self.finish()
            self.feedback(("Current backlight is 0%. Select 1–100%, then Apply." if value == 0 else
                           "Backlight ready. Changes apply only when you press Apply.") if self.ready else
                          "Backlight unavailable. Refresh to retry; this display may not expose a backlight device. " + str(output),
                          "neutral" if self.ready else "bad")

        run_async(["brightnessctl", "--class=backlight", "-m"], loaded, timeout=4)

    def value_changed(self, scale):
        self.value_label.set_text(f"Backlight  {int(scale.get_value())}%")
        if self.ready and not self.loading and not self.busy:
            self.feedback("Changes pending. Press Apply to update the backlight.")

    def apply(self, widget):
        if not self.ready or not self.begin("Applying backlight…"):
            return
        value = int(self.scale.get_value())
        device = self.backlight_device

        def done(rc, output):
            if self.closed:
                return
            self.finish()
            if rc != 0:
                self.feedback("Brightness update failed. " + (output or f"Exit status {rc}") + " Draft retained; Refresh to check or retry Apply.", "bad")
            else:
                self.refresh()

        run_async(["brightnessctl", "--class=backlight", "--device=" + device, "set", f"{value}%"], done, admin=True, timeout=15)


class AudioWindow(ControlWindowState, Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Sound")
        self.init_control_state()
        self.rendering = False
        self.service_ready = self.output_ready = self.input_ready = False
        self.volume_known = self.mute_known = False
        self.default_output = ""
        self.muted = None
        self.set_default_size(700, 440)
        self.set_position(Gtk.WindowPosition.CENTER)
        bar = header(self, "Sound", "Outputs, inputs, and volume", "audio-volume-high-symbolic")
        self.refresh_button = button("Refresh", "view-refresh-symbolic", lambda *_: self.refresh_audio())
        bar.pack_end(self.refresh_button)
        root = control_body(self, 700, 440)
        self.value_label = label("Volume unavailable", "card-title")
        root.pack_start(self.value_label, False, False, 0)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        self.scale.set_draw_value(False)
        self.scale.get_accessible().set_name("Output volume")
        self.scale.connect("value-changed", self.value_changed)
        root.pack_start(self.scale, False, False, 0)

        devices = Gtk.Grid(column_spacing=12, row_spacing=10)
        output_prompt = label("Output", wrap=False)
        devices.attach(output_prompt, 0, 0, 1, 1)
        self.output_combo = Gtk.ComboBoxText()
        self.output_combo.set_hexpand(True)
        devices.attach(self.output_combo, 1, 0, 1, 1)
        input_prompt = label("Input", wrap=False)
        devices.attach(input_prompt, 0, 1, 1, 1)
        self.input_combo = Gtk.ComboBoxText()
        self.input_combo.set_hexpand(True)
        devices.attach(self.input_combo, 1, 1, 1, 1)
        for prompt, combo, name in ((output_prompt, self.output_combo, "Output device"),
                                    (input_prompt, self.input_combo, "Input device")):
            prompt.set_mnemonic_widget(combo)
            combo.get_accessible().set_name(name)
        for combo in (self.output_combo, self.input_combo):
            for cell in combo.get_cells():
                if isinstance(cell, Gtk.CellRendererText):
                    cell.set_property("ellipsize", Pango.EllipsizeMode.END)
                    cell.set_property("width-chars", 12)
                    cell.set_property("max-width-chars", 32)
            combo.connect("changed", lambda selected: selected.set_tooltip_text(selected.get_active_text() or ""))
        self.output_combo.connect("changed", self.output_changed)
        root.pack_start(devices, False, False, 0)
        self.hardware_status = label("Detecting ALSA hardware...", "status-warn")
        self.hardware_status.set_line_wrap(True)
        self.hardware_status.set_lines(2)
        self.hardware_status.set_ellipsize(Pango.EllipsizeMode.END)
        root.pack_start(self.hardware_status, False, False, 0)

        self.mute_button = button("Mute", "audio-volume-muted-symbolic", self.toggle_mute)
        self.apply_button = button("Apply", "object-select-symbolic", self.apply, "suggested-action")
        self.apply_button.set_tooltip_text("Use selected devices as defaults and save output volume.")
        self.mute_button.set_tooltip_text("Change mute on selected output without switching default devices.")
        self.repair_button = button("Retry hardware", "view-refresh-symbolic", self.repair_audio)
        self.diagnostics_button = button("Diagnostics", "dialog-information-symbolic", self.show_diagnostics)
        self.more_button = more_actions([
            button("Mixer", "multimedia-volume-control-symbolic", self.open_mixer),
            self.repair_button,
            self.diagnostics_button,
        ], "More sound tools and hardware recovery")
        actions = flow_row([self.apply_button, self.mute_button, self.more_button], max_children=3, min_children=1)
        root.pack_start(actions, False, False, 0)
        self.add_status(root)
        self.update_mute_label()
        self.connect("destroy", self.on_destroy)
        self.refresh_audio()

    def update_controls(self):
        enabled = not (self.closed or self.busy)
        self.refresh_button.set_sensitive(enabled)
        self.repair_button.set_sensitive(enabled)
        self.diagnostics_button.set_sensitive(enabled)
        self.more_button.set_sensitive(enabled)
        self.output_combo.set_sensitive(enabled and self.output_ready)
        self.input_combo.set_sensitive(enabled and self.input_ready)
        self.scale.set_sensitive(enabled and self.output_ready and self.volume_known)
        self.mute_button.set_sensitive(enabled and self.output_ready and self.mute_known)
        self.apply_button.set_sensitive(enabled and (self.output_ready or self.input_ready))

    @staticmethod
    def usable_devices(devices):
        return [item for item in devices if not item[0].startswith("auto_null")]

    def open_mixer(self, *_args):
        if not self.closed and not self.busy and not launch(["pavucontrol"]):
            self.feedback("Mixer could not open. Install pavucontrol or try again.", "bad")

    @staticmethod
    def audio_command(*arguments):
        rc, output = run(["pactl", *arguments], timeout=6)
        if rc == 0:
            return rc, output
        run(["ooonana-audio-start"], timeout=35)
        return run(["pactl", *arguments], timeout=8)

    @staticmethod
    def list_audio_devices(kind, *, report=False):
        rc, output = run(["pactl", "list", "short", kind], timeout=8)
        if rc != 0:
            return (rc, [], output) if report else []
        devices = []
        for line in output.splitlines():
            fields = line.split("\t")
            if len(fields) >= 2 and fields[1]:
                devices.append((fields[1], fields[1].replace("alsa_", "").replace("_", " ")))
        return (0, devices, "") if report else devices

    @staticmethod
    def alsa_card_ready():
        try:
            cards = Path("/proc/asound/cards").read_text(errors="replace")
        except OSError:
            return False
        return bool(cards.strip()) and "--- no soundcards ---" not in cards

    def collect_audio_state(self):
        service_rc, service_output = self.audio_command("info")
        outputs_rc, outputs, outputs_error = self.list_audio_devices("sinks", report=True)
        inputs_rc, inputs, inputs_error = self.list_audio_devices("sources", report=True)
        default_output_rc, default_output = run(["pactl", "get-default-sink"], timeout=5)
        default_input_rc, default_input = run(["pactl", "get-default-source"], timeout=5)
        observed_output = default_output.strip() if default_output_rc == 0 else ""
        volume_rc, volume = self.audio_command("get-sink-volume", observed_output) if observed_output else (1, "")
        mute_rc, mute = run(["pactl", "get-sink-mute", observed_output], timeout=4) if observed_output else (1, "")
        return {
            "service_rc": service_rc,
            "service_output": service_output,
            "alsa_card_ready": self.alsa_card_ready(),
            "outputs": outputs,
            "inputs": inputs,
            "outputs_rc": outputs_rc,
            "outputs_error": outputs_error,
            "inputs_rc": inputs_rc,
            "inputs_error": inputs_error,
            "default_output": default_output.strip() if default_output_rc == 0 else "",
            "default_input": default_input.strip() if default_input_rc == 0 else "",
            "volume_rc": volume_rc,
            "volume": volume,
            "mute_rc": mute_rc,
            "mute": mute,
        }

    def apply_audio_state(self, data):
        if self.closed:
            return
        self.rendering = True
        self.output_combo.remove_all()
        self.input_combo.remove_all()
        outputs = self.usable_devices(data["outputs"]) if data.get("outputs_rc", 0) == 0 else []
        inputs = self.usable_devices(data["inputs"]) if data.get("inputs_rc", 0) == 0 else []
        listing_failed = data.get("outputs_rc", 0) != 0 or data.get("inputs_rc", 0) != 0
        self.service_ready = data["service_rc"] == 0
        self.output_ready = self.service_ready and bool(outputs)
        self.input_ready = self.service_ready and bool(inputs)
        self.default_output = data["default_output"]
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
        current_output = self.output_combo.get_active_id()
        self.apply_output_state(data if current_output == self.default_output else dict(volume_rc=1, mute_rc=1))
        self.rendering = False
        self.finish()
        if not self.service_ready:
            self.hardware_status.set_text("Audio service unavailable" + (" · ALSA card detected" if data["alsa_card_ready"] else ""))
            self.feedback(data["service_output"] or "Audio server is unavailable. Use Refresh or Retry hardware.", "bad")
        elif listing_failed:
            self.hardware_status.set_text("Audio device query incomplete")
            errors = " ".join(value for value in (data.get("outputs_error"), data.get("inputs_error")) if value)
            self.feedback("Some audio devices could not be listed. " + errors + " Refresh to retry.", "bad")
        elif outputs or inputs:
            self.hardware_status.set_text("ALSA hardware detected" if data["alsa_card_ready"] else "Audio device detected")
            self.feedback(f"Audio ready · {len(outputs)} {'output' if len(outputs) == 1 else 'outputs'}"
                          f" · {len(inputs)} {'input' if len(inputs) == 1 else 'inputs'}. Apply saves routing and volume.")
            if self.output_ready and not (self.volume_known and self.mute_known):
                self.feedback("Audio route available; volume or mute state unavailable. Refresh to retry.", "warn")
            elif self.volume_known and self.scale.get_value() > 100:
                self.feedback("Audio ready. Above 100% may distort audio; changes require Apply.", "warn")
        elif data["alsa_card_ready"]:
            self.hardware_status.set_text("ALSA card detected")
            self.feedback("PipeWire has no hardware route. Use Refresh or Retry hardware.", "warn")
        elif data["service_rc"] == 0:
            self.hardware_status.set_text(
                "No ALSA card. Retry hardware. If still missing, reboot into GRUB > Audio compatibility > legacy HDA."
            )
            self.feedback("PipeWire is ready; kernel audio hardware is missing. Use Refresh or Retry hardware.", "warn")
        self.hardware_status.set_tooltip_text(self.hardware_status.get_text())
        hardware_context = self.hardware_status.get_style_context()
        for state in ("good", "warn", "bad"):
            hardware_context.remove_class("status-" + state)
        hardware_context.add_class("status-" + ("bad" if not self.service_ready or listing_failed else "good" if outputs or inputs else "warn"))
        if self.output_ready and current_output != self.default_output:
            self.refresh_selected_output()

    def apply_output_state(self, data):
        match = re.search(r"/\s*(\d+)%", data.get("volume", "")) if data.get("volume_rc") == 0 else None
        self.volume_known = self.output_ready and match is not None
        self.mute_known = self.output_ready and data.get("mute_rc") == 0 and data.get("mute", "").strip() in ("Mute: yes", "Mute: no")
        self.muted = data.get("mute", "").strip() == "Mute: yes" if self.mute_known else None
        self.rendering = True
        if self.volume_known:
            self.scale.set_value(min(150, int(match.group(1))))
        self.rendering = False
        self.value_changed(self.scale)
        self.update_mute_label()

    def output_changed(self, *_args):
        if not self.rendering:
            self.refresh_selected_output()

    def refresh_selected_output(self):
        target = self.output_combo.get_active_id()
        if not target or not self.begin("Reading selected output…"):
            return
        self.volume_known = self.mute_known = False
        self.value_label.set_text("Reading output volume…")

        def task():
            volume_rc, volume = self.audio_command("get-sink-volume", target)
            mute_rc, mute = self.audio_command("get-sink-mute", target)
            return 0, dict(volume_rc=volume_rc, volume=volume, mute_rc=mute_rc, mute=mute)

        def done(rc, data):
            if self.closed:
                return
            if target != self.output_combo.get_active_id():
                self.finish()
                self.refresh_selected_output()
                return
            if rc == 0 and isinstance(data, dict):
                self.apply_output_state(data)
            self.finish()
            self.feedback("Selected output ready. Apply to save routing and volume." if self.volume_known and self.mute_known else
                          "Output volume or mute state unavailable. Refresh to retry.", "neutral" if self.volume_known and self.mute_known else "warn")

        run_async_task(task, done)

    def refresh_audio(self):
        if not self.begin("Checking audio service…"):
            return

        def task():
            return 0, self.collect_audio_state()

        def done(rc, data):
            if self.closed:
                return
            if rc != 0:
                self.service_ready = self.output_ready = self.input_ready = False
                self.volume_known = self.mute_known = False
                self.finish()
                self.feedback("Audio refresh failed. " + str(data) + " Refresh or Retry hardware.", "bad")
                return
            self.apply_audio_state(data)

        run_async_task(task, done)

    def refresh_devices(self):
        self.refresh_audio()

    def repair_audio(self, widget):
        if not self.begin("Retrying audio hardware…"):
            return

        def task():
            probe_rc, probe_output = run(["ooonana-audio-hardware-reprobe"], admin=True, timeout=55)
            audio_rc, audio_output = run(["ooonana-audio-start", "--restart"], timeout=35)
            if audio_rc != 0:
                return audio_rc, audio_output
            return probe_rc, probe_output

        def done(rc, output):
            if self.closed:
                return
            self.finish()
            if rc != 0:
                self.service_ready = self.output_ready = self.input_ready = False
                self.update_controls()
                self.feedback("Audio repair failed. " + (output or "Audio server did not become ready.") + " Refresh to retry.", "bad")
            else:
                self.refresh_audio()

        run_async_task(task, done)

    def show_diagnostics(self, _widget):
        if not self.begin("Collecting audio diagnostics…"):
            return

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
                timeout = 35 if command[0] == "ooonana-audio-hardware-reprobe" else 8
                rc, output = run(command, timeout=timeout)
                sections.append(f"{title}:\n{output or 'unavailable'}" if rc == 0 else f"{title}:\n{output or 'failed'}")
            return 0, "\n\n".join(sections)

        def done(_rc, output):
            if self.closed:
                return
            self.finish()
            self.feedback("Audio diagnostics ready")
            message(self, "Sound diagnostics", output)

        run_async_task(task, done)

    def value_changed(self, scale):
        value = int(scale.get_value())
        self.value_label.set_text(f"Volume  {value}%" if self.volume_known else "Volume unavailable")
        if self.volume_known and not self.rendering and not self.busy:
            self.feedback("Above 100% may distort audio. Apply to save." if value > 100 else "Changes pending. Apply to save routing and volume.", "warn" if value > 100 else "neutral")

    def update_mute_label(self):
        self.mute_button.set_label("Unmute" if self.muted else "Mute" if self.mute_known else "Mute unavailable")

    def toggle_mute(self, _widget):
        target = self.output_combo.get_active_id()
        if not self.output_ready or not self.mute_known or not target or not self.begin("Updating selected output mute…"):
            return
        desired = "no" if self.muted else "yes"

        def task():
            return self.audio_command("set-sink-mute", target, desired)

        def done(rc, output):
            if self.closed:
                return
            self.finish()
            if rc != 0:
                self.feedback("Mute update failed. " + (output or "No usable output") + " Refresh to check or retry.", "bad")
                return
            self.refresh_selected_output()

        run_async_task(task, done)

    def apply(self, widget):
        if not (self.output_ready or self.input_ready) or not self.begin("Applying audio changes…"):
            return
        value = int(self.scale.get_value()) if self.volume_known else None
        output_id = self.output_combo.get_active_id()
        input_id = self.input_combo.get_active_id()

        def done(rc, output):
            if self.closed:
                return
            self.finish()
            if rc != 0:
                self.feedback("Audio update failed. " + (output or f"Exit status {rc}") + " Draft retained; Refresh to check routing or retry Apply.", "bad")
            else:
                self.refresh_audio()

        def task():
            return self.apply_route_changes(output_id, input_id, value)

        run_async_task(task, done)

    def apply_route_changes(self, output_id, input_id, value):
        if output_id:
            rc, output = self.audio_command("set-default-sink", output_id)
            if rc != 0:
                return rc, output
        if input_id:
            rc, output = self.audio_command("set-default-source", input_id)
            if rc != 0:
                return rc, output
        if output_id and value is not None:
            return self.audio_command("set-sink-volume", output_id, f"{value}%")
        return 0, ""


class MediaWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Music")
        self.closed = False
        self.action_busy = False
        self.player_ready = False
        self.state_epoch = 0
        self.volume_dirty = False
        self.volume_known = False
        self.rendering_volume = False
        self.action_error = ""
        self.set_default_size(720, 460)
        self.set_position(Gtk.WindowPosition.CENTER)
        header(self, "Music", "Local library and playback", "multimedia-player-symbolic")
        root = control_body(self, 720, 460)

        now_playing = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        cover = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic", Gtk.IconSize.DIALOG)
        cover.set_size_request(64, 64)
        now_playing.pack_start(cover, False, False, 0)
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.track_label = label("Nothing playing", "page-title", wrap=False)
        self.artist_label = label("Add audio files to Music, then refresh library.", "muted", wrap=False)
        for metadata in (self.track_label, self.artist_label):
            metadata.set_ellipsize(Pango.EllipsizeMode.END)
            metadata.set_max_width_chars(40)
        self.state_label = label("Starting player...", "status-warn")
        self.state_label.set_lines(2)
        self.state_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.state_label.set_selectable(True)
        details.pack_start(self.track_label, False, False, 0)
        details.pack_start(self.artist_label, False, False, 0)
        details.pack_start(self.state_label, False, False, 0)
        now_playing.pack_start(details, True, True, 0)
        root.pack_start(now_playing, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text("Stopped")
        root.pack_start(self.progress, False, False, 0)

        self.play_button = button("Play", "media-playback-start-symbolic", lambda widget: self.action(widget, "play-pause"), "suggested-action")
        self.playback_actions = [
            button("Previous", "media-skip-backward-symbolic", lambda widget: self.action(widget, "previous")),
            self.play_button,
            button("Next", "media-skip-forward-symbolic", lambda widget: self.action(widget, "next")),
            button("Stop", "media-playback-stop-symbolic", lambda widget: self.action(widget, "stop")),
        ]
        playback = flow_row(self.playback_actions, max_children=4, min_children=2)
        root.pack_start(playback, False, False, 0)

        volume_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.volume_label = label("Player volume")
        volume_row.pack_start(self.volume_label, False, False, 0)
        self.volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume.set_hexpand(True)
        self.volume.set_value(70)
        self.volume.set_draw_value(False)
        self.volume.get_accessible().set_name("Player volume")
        self.volume.connect("value-changed", self.volume_changed)
        volume_row.pack_start(self.volume, True, True, 0)
        self.volume_apply_button = button("Apply", "object-select-symbolic", self.apply_volume)
        volume_row.pack_start(self.volume_apply_button, False, False, 0)
        root.pack_start(volume_row, False, False, 0)

        self.library_button = button("Refresh library", "view-refresh-symbolic", self.refresh_library)
        tools = flow_row([
            self.library_button,
            button("Music folder", "folder-music-symbolic", lambda *_: launch(["ooonana-media-control", "open"])),
            button("Terminal player", "utilities-terminal-symbolic", lambda *_: launch(["ooonana-media-control", "terminal"])),
        ], max_children=3, min_children=2)
        root.pack_end(tools, False, False, 0)

        self.refreshing = False
        self.timer_id = GLib.timeout_add_seconds(2, self.periodic_refresh)
        self.connect("destroy", self.destroyed)
        self.update_media_controls()
        run_async(["ooonana-media-control", "status"], self.player_started, timeout=20)

    def destroyed(self, *_args):
        self.closed = True
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = 0
        if Gtk.main_level():
            Gtk.main_quit()

    def update_media_controls(self):
        available = not (self.closed or self.action_busy)
        for action in self.playback_actions:
            action.set_sensitive(available and self.player_ready)
        self.volume.set_sensitive(available and self.player_ready and self.volume_known)
        self.volume_apply_button.set_sensitive(available and self.player_ready and self.volume_known)
        self.library_button.set_sensitive(available)

    def volume_changed(self, *_args):
        if not self.rendering_volume and self.volume_known:
            self.volume_dirty = True
            self.state_label.set_text("Volume change pending · press Apply")

    def begin_media_action(self, text, require_ready=True):
        if self.closed or self.action_busy or (require_ready and not self.player_ready):
            return False
        self.action_busy = True
        self.state_epoch += 1
        self.action_error = ""
        self.state_label.set_text(text)
        self.state_label.set_tooltip_text(text)
        self.state_label.get_style_context().remove_class("status-bad")
        self.state_label.get_style_context().add_class("status-warn")
        self.update_media_controls()
        return True

    def finish_media_action(self, rc, output, title):
        if self.closed:
            return
        self.action_busy = False
        if rc != 0:
            self.action_error = title + ". " + (output or f"Exit status {rc}") + " Retry when ready."
            self.state_label.set_text(self.action_error)
            self.state_label.set_tooltip_text(self.action_error)
            self.state_label.get_style_context().remove_class("status-warn")
            self.state_label.get_style_context().add_class("status-bad")
        self.update_media_controls()
        self.refresh_state()

    def player_started(self, rc, output):
        if self.closed or self.state_epoch or self.player_ready:
            return
        if rc != 0:
            self.player_unavailable(output or "MPD failed to start")
            return
        self.refresh_state()

    def periodic_refresh(self):
        if self.closed:
            return False
        self.refresh_state()
        return True

    def player_unavailable(self, detail):
        self.player_ready = False
        self.state_label.set_text("Player unavailable · Refresh library to retry")
        self.state_label.set_tooltip_text(str(detail))
        self.state_label.get_style_context().remove_class("status-warn")
        self.state_label.get_style_context().add_class("status-bad")
        self.progress.set_fraction(0)
        self.progress.set_text("Unavailable")
        self.update_media_controls()

    @staticmethod
    def collect_state():
        current_rc, current = run(["mpc", "--format", "%artist%\t%title%\t%file%", "current"], timeout=5)
        status_rc, status = run(["mpc", "status"], timeout=5)
        volume_rc, volume = run(["mpc", "volume"], timeout=5)
        if status_rc != 0:
            return status_rc, status or "Music service unavailable"
        return 0, {
            "current": current if current_rc == 0 else "",
            "status": status if status_rc == 0 else "",
            "volume": volume if volume_rc == 0 else "",
        }

    def refresh_state(self):
        if self.closed or self.refreshing or self.action_busy:
            return
        self.refreshing = True
        epoch = self.state_epoch

        def done(rc, data):
            if self.closed:
                return
            self.refreshing = False
            if self.action_busy or epoch != self.state_epoch:
                if not self.action_busy:
                    self.refresh_state()
                return
            if rc != 0 or not isinstance(data, dict):
                self.player_unavailable(data)
                return
            self.player_ready = True
            fields = data["current"].split("\t", 2) if data["current"] else []
            artist = fields[0].strip() if fields else ""
            title = fields[1].strip() if len(fields) > 1 else ""
            filename = fields[2].strip() if len(fields) > 2 else ""
            self.track_label.set_text(title or filename or "Nothing playing")
            self.artist_label.set_text(artist or ("Local music" if title or filename else "Add audio files to Music, then refresh library."))
            for metadata in (self.track_label, self.artist_label):
                metadata.set_tooltip_text(metadata.get_text())

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
            self.play_button.get_image().set_from_icon_name(
                "media-playback-pause-symbolic" if state == "Playing" else "media-playback-start-symbolic",
                Gtk.IconSize.BUTTON)
            percent = re.search(r"\((\d+)%\)", status)
            fraction = min(100, int(percent.group(1))) / 100 if percent else 0
            self.progress.set_fraction(fraction)
            timing = re.search(r"(\d+:\d+)/(\d+:\d+)", status)
            self.progress.set_text(f"{state}  {timing.group(1)} / {timing.group(2)}" if timing else state)
            self.state_label.set_text(self.action_error or ("MPD ready · volume change pending" if self.volume_dirty else
                                      "MPD ready" if status else "Player ready; library empty"))
            self.state_label.set_tooltip_text(self.action_error or None)
            self.state_label.get_style_context().remove_class("status-warn")
            self.state_label.get_style_context().remove_class("status-bad")
            if self.action_error:
                self.state_label.get_style_context().add_class("status-bad")

            volume = re.search(r"volume:\s*(\d+)%", data["volume"])
            self.volume_known = bool(volume)
            self.volume.set_draw_value(self.volume_known)
            if volume and not self.volume_dirty:
                self.rendering_volume = True
                self.volume.set_value(int(volume.group(1)))
                self.rendering_volume = False
            self.update_media_controls()

        run_async_task(self.collect_state, done)

    def action(self, widget, action):
        if not self.begin_media_action("Updating playback…"):
            return

        def done(rc, output):
            self.finish_media_action(rc, output, "Playback update failed")

        run_async(["ooonana-media-control", action], done, timeout=20)

    def apply_volume(self, widget):
        if not self.volume_known or not self.begin_media_action("Updating player volume…"):
            return
        value = int(self.volume.get_value())

        def done(rc, output):
            if self.closed:
                return
            if rc == 0:
                self.volume_dirty = False
            self.finish_media_action(rc, output, "Volume update failed")

        run_async(["ooonana-media-control", "volume", str(value)], done, timeout=10)

    def refresh_library(self, widget):
        if not self.begin_media_action("Refreshing music library…", require_ready=False):
            return

        def done(rc, output):
            self.finish_media_action(rc, output, "Library refresh failed")

        run_async(["ooonana-media-control", "update"], done, timeout=90)


class PowerWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Power")
        self.pending = False
        self.closed = False
        self.actions = []
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
            self.actions.append(widget)
            grid.attach(widget, index % 3, index // 3, 1, 1)
        root.pack_start(grid, True, True, 0)
        self.status = label("", "muted")
        root.pack_start(self.status, False, False, 0)
        self.connect("destroy", self.on_destroy)

    def on_destroy(self, *_args):
        self.closed = True
        if Gtk.main_level():
            Gtk.main_quit()

    def request(self, command, title):
        if self.closed or self.pending:
            return
        self.pending = True
        for widget in self.actions[:-1]:
            widget.set_sensitive(False)
        self.status.set_text(title + " requested...")
        def done(rc, output):
            if self.closed:
                return
            self.pending = False
            for widget in self.actions[:-1]:
                widget.set_sensitive(True)
            self.status.set_text(title + (" failed." if rc else " requested."))
            if rc:
                message(self, title + " failed", output or f"Exit status {rc}", Gtk.MessageType.ERROR)
        run_async(command, done, timeout=20)

    def lock(self, *_args):
        # Display blanking is not authentication and must never replace a lock.
        self.request(["i3lock"], "Lock")

    def logout(self, *_args):
        self.confirm("logout")

    def restart_i3(self, *_args):
        self.request(["i3-msg", "restart"], "Restart i3")

    def confirm(self, action):
        if self.closed or self.pending:
            return
        title, command = {"reboot": ("Reboot", ["bunana", "--restart"]),
                          "shutdown": ("Shut down", ["bunana", "--shutdown"]),
                          "logout": ("Log out", ["i3-msg", "exit"])}[action]
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text=f"{title} Ooonana OS?",
        )
        dialog.format_secondary_text("Unsaved work will be lost.")
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, title, Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        accepted = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if accepted:
            self.request(command, title)


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
