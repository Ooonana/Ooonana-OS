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
        **{name: (lambda *_args, **_kwargs: None) for name in (
            "apply_theme", "button", "flow_row", "header", "label", "launch",
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
    widget = Widget()
    controls_app.AudioWindow.apply(target(output, source), widget)
    assert commands == expected, commands
    assert widget.sensitive
    assert not errors

commands.clear()
controls_app.AudioWindow.apply(target("speaker", "usb_mic", "set-default-sink"), Widget())
assert commands == [("set-default-sink", "speaker")]
assert len(errors) == 1

data = dict(outputs=[("bluez_output.headset", "Headset")], inputs=[],
            default_output="", default_input="", volume_rc=1, volume="",
            mute_rc=1, mute="", alsa_card_ready=False, service_rc=0, service_output="")
value = target()
controls_app.AudioWindow.apply_audio_state(value, data)
assert value.hardware_status.text == "Audio device detected"
assert value.apply_button.sensitive
data.update(outputs=[], inputs=[("usb_mic", "Microphone")], alsa_card_ready=True)
controls_app.AudioWindow.apply_audio_state(value, data)
assert value.hardware_status.text == "ALSA hardware detected"
assert value.apply_button.sensitive and not value.mute_button.sensitive
data.update(inputs=[], outputs=[("auto_null", "Dummy output")], alsa_card_ready=False)
controls_app.AudioWindow.apply_audio_state(value, data)
assert not value.apply_button.sensitive
print("ok audio-actions")
