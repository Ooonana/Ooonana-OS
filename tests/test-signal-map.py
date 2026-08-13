#!/usr/bin/env python3
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))


class DummyWindow:
    pass


sys.modules.setdefault("cairo", SimpleNamespace())
sys.modules["common"] = SimpleNamespace(
    Gtk=SimpleNamespace(Window=DummyWindow),
    Pango=SimpleNamespace(FontDescription=lambda *_args: None),
    PangoCairo=SimpleNamespace(),
    header=lambda *_args, **_kwargs: None,
    label=lambda *_args, **_kwargs: None,
)

from signal_map import SignalMapWindow  # noqa: E402


class Toggle:
    def __init__(self, active):
        self.active = active

    def get_active(self):
        return self.active


def check(condition, detail):
    if not condition:
        raise AssertionError(detail)


window = object.__new__(SignalMapWindow)
window.items = [
    {"name": "router", "category": "router", "signal": 80},
    {"name": "device", "category": "device", "signal": 35},
]
window.router_toggle = Toggle(True)
window.device_toggle = Toggle(True)
check(len(window.filtered_items()) == 2, "both map categories visible")

window.router_toggle.active = False
check([item["name"] for item in window.filtered_items()] == ["device"], "router toggle hides routers")

window.router_toggle.active = True
window.device_toggle.active = False
check([item["name"] for item in window.filtered_items()] == ["router"], "device toggle hides devices")

print("ok signal-map")
