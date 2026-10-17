#!/usr/bin/env python3
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))

try:
    import gi  # noqa: F401
except ImportError:
    sys.modules["common"] = SimpleNamespace(
        Gtk=SimpleNamespace(Window=object, MessageType=SimpleNamespace(ERROR=1)),
        GLib=SimpleNamespace(),
        Pango=SimpleNamespace(),
        **{name: (lambda *_args, **_kwargs: None) for name in (
            "apply_theme", "button", "flow_row", "fit_dialog", "header", "label", "launch", "more_actions",
            "message", "run", "run_async", "run_async_task",
        )},
    )

import controls_app  # noqa: E402


class Widget:
    def __init__(self, active=None):
        self.active = active
        self.sensitive = True
        self.text = ""

    def get_active_id(self):
        return self.active

    def set_sensitive(self, value):
        self.sensitive = value

    def set_text(self, value):
        self.text = value

    def remove_all(self):
        pass

    def append(self, *_args):
        pass

    def set_active(self, _index):
        pass


commands, errors = [], []
controls_app.run_async_task = lambda task, done: done(*task())
controls_app.message = lambda *_args: errors.append(_args)


def target(output=None, source=None, fail=None):
    def command(*args):
        commands.append(args)
        return (1, "device unavailable") if args[0] == fail else (0, "")

    return SimpleNamespace(
        output_combo=Widget(output), input_combo=Widget(source),
        scale=SimpleNamespace(get_value=lambda: 42, set_sensitive=lambda _value: None),
        audio_command=command, hardware_status=Widget(), status=Widget(),
        mute_button=Widget(), apply_button=Widget(), update_mute_label=lambda: None,
    )


for output, source, expected in (
    (None, "usb_mic", [("set-default-source", "usb_mic")]),
    ("speaker", None, [("set-default-sink", "speaker"), ("set-sink-volume", "speaker", "42%")]),
    (None, None, []),
):
    commands.clear()
    rc, _output = controls_app.AudioWindow.apply_route_changes(target(output, source), output, source, 42)
    assert commands == expected, commands
    assert rc == 0

commands.clear()
rc, _output = controls_app.AudioWindow.apply_route_changes(target("speaker", "usb_mic", "set-default-sink"), "speaker", "usb_mic", 42)
assert commands == [("set-default-sink", "speaker")]
assert rc == 1

data = dict(outputs=[("bluez_output.headset", "Headset")], inputs=[],
            default_output="", default_input="", volume_rc=1, volume="",
            mute_rc=1, mute="", alsa_card_ready=False, service_rc=0, service_output="")
assert controls_app.AudioWindow.usable_devices(data['outputs']) == data['outputs']
data.update(outputs=[], inputs=[("usb_mic", "Microphone")], alsa_card_ready=True)
commands.clear()
controls_app.AudioWindow.apply_route_changes(target("speaker", "usb_mic"), "speaker", "usb_mic", None)
assert commands == [("set-default-sink", "speaker"), ("set-default-source", "usb_mic")]
data.update(inputs=[], outputs=[("auto_null", "Dummy output")], alsa_card_ready=False)
assert controls_app.AudioWindow.usable_devices(data['outputs']) == []
observed = []
def read_audio(command, **_kwargs):
    observed.append(tuple(command))
    if command == ["pactl", "list", "short", "sinks"]:
        return 1, "Fixture permission denied"
    if command == ["pactl", "list", "short", "sources"]:
        return 0, "0\tusb_mic\tmodule-fixture\tfloat32le\tIDLE"
    if command == ["pactl", "get-default-sink"]:
        return 0, "observed-speaker"
    if command == ["pactl", "get-default-source"]:
        return 0, "usb_mic"
    return 0, "Mute: no"
controls_app.run = read_audio
reader = SimpleNamespace(audio_command=lambda *args: read_audio(["pactl", *args]),
                         list_audio_devices=controls_app.AudioWindow.list_audio_devices,
                         alsa_card_ready=lambda: True)
snapshot = controls_app.AudioWindow.collect_audio_state(reader)
assert snapshot['outputs_rc'] == 1 and 'permission denied' in snapshot['outputs_error']
assert ("pactl", "get-sink-volume", "observed-speaker") in observed
assert ("pactl", "get-sink-mute", "observed-speaker") in observed
assert not any('@DEFAULT_SINK@' in command for command in observed)
print("ok audio-actions")
