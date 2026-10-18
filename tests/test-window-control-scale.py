#!/usr/bin/env python3
"""Guard i3 device pixels versus GTK application pixels without GTK imports."""
import ast
import math
import re
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
source = ast.parse((root / "packages/ooonana/usr/lib/ooonana/ui/window_controls.py").read_text())
controls = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "Controls")
position = next(node for node in controls.body if isinstance(node, ast.FunctionDef) and node.name == "position")
namespace = {"math": math, "WIDTH": 66}
exec(compile(ast.Module(body=[position], type_ignores=[]), "window-control-scale-fixture", "exec"), namespace)


class Fixture:
    position = namespace["position"]

    def __init__(self, scale):
        self.scale = scale
        self.last_position = self.last_scale = None
        self.updates = 0
        self.shown = 0
        self.scale_provider = SimpleNamespace(load_from_data=self.css)
        self.row = SimpleNamespace(
            set_spacing=lambda value: setattr(self, "spacing", value),
            set_margin_left=lambda value: setattr(self, "left", value),
            set_margin_right=lambda value: setattr(self, "right", value),
            get_children=lambda: [SimpleNamespace(get_image=lambda: SimpleNamespace(
                set_pixel_size=lambda value: setattr(self, "icon", value))) for _ in range(3)])

    def css(self, data):
        self.style = dict((name, float(value)) for name, value in re.findall(
            r"([\w-]+): ([\d.]+)px", data.decode()))
        self.updates += 1

    def get_scale_factor(self):
        return self.scale

    def get_child(self):
        return self.row

    def set_size_request(self, width, height):
        self.size = width, height

    def move(self, x, y):
        self.point = x, y

    def show_all(self):
        self.shown += 1


for scale in (1, 2):
    fixture = Fixture(scale)
    for target in ((818, 217, 22), (-1279, -799, 23), (0, 0, 16)):
        fixture.position(target)
        assert fixture.last_position == target, "Raw i3 target must stay device-based"
        assert fixture.last_scale == scale
        assert fixture.size == (math.ceil(66 / scale), math.ceil(target[2] / scale))
        assert all(0 <= wanted - actual * scale < scale
                   for wanted, actual in zip(target[:2], fixture.point)), "Wrong coordinate units"
        button = fixture.style["min-width"] + 2 * fixture.style["border-width"]
        assert button == fixture.style["min-height"] + 2 * fixture.style["border-width"]
        assert (3 * button + 2 * fixture.spacing + fixture.left + fixture.right) * scale <= 66
        assert fixture.icon * scale == 10
        updates = fixture.updates
        shown = fixture.shown
        fixture.position(target)
        assert fixture.updates == updates, "Unchanged target needlessly restyled"
        assert fixture.shown == shown + 1, "Previously hidden controls did not remap"
    fixture.scale = 3 - scale
    fixture.position(target)
    assert fixture.last_scale == 3 - scale and fixture.updates == updates + 1

print("WINDOW_CONTROL_SCALE_OK 1x/2x, negative origins, titlebar budget, scale changes and remap")
