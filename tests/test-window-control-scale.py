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
        self.last_control_scale = 0
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

for scale in (1, 2, 4):
    fixture = Fixture(scale)
    target = (-1279, -799, 32 * scale)
    fixture.position(target, scale)
    assert fixture.size == (82, 32) and fixture.spacing == 5 and fixture.left == fixture.right == 0
    assert fixture.style["min-width"] + 2 * fixture.style["border-width"] == 24
    assert fixture.icon == 12
    fixture.position(target, 0)
    assert fixture.last_control_scale == 0 and fixture.icon * scale <= 10

capability = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "native_control_scale")
exec(compile(ast.Module(body=[capability], type_ignores=[]), "control-capability-fixture", "exec"), namespace)
negotiate = namespace["native_control_scale"]
for reply in (None, [], {}, {"ooonana_control_api": True, "ooonana_control_scale": 1},
              {"ooonana_control_api": 2, "ooonana_control_scale": 1},
              {"ooonana_control_api": 1, "ooonana_control_scale": True},
              {"ooonana_control_api": 1, "ooonana_control_scale": 0},
              {"ooonana_control_api": 1, "ooonana_control_scale": 5}):
    assert negotiate(reply) == 0, reply
for scale in (1, 2, 4):
    assert negotiate({"ooonana_control_api": 1, "ooonana_control_scale": scale}) == scale

geometry = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "decoration_targets")
exec(compile(ast.Module(body=[geometry], type_ignores=[]), "native-decoration-fixture", "exec"), namespace)
for scale in (1, 2, 4):
    node = {"id": 42, "window": 101, "rect": {"x": -1280, "y": 58},
            "deco_rect": {"x": 0, "y": 0, "width": 500, "height": 32 * scale}}
    tree = {"nodes": [{"type": "workspace", "name": "1", "nodes": [node]}]}
    assert namespace["decoration_targets"](tree, {"1"}, scale) == {42: (-1280 + 14 * scale, 58, 32 * scale)}
    node["deco_rect"]["width"] = 96 * scale - 1
    assert namespace["decoration_targets"](tree, {"1"}, scale) == {}, "Narrow tab must not overlap neighbour"
    node["deco_rect"].update(width=500, height=22)
    assert namespace["decoration_targets"](tree, {"1"}, scale) == {}, "Never clip native controls into old WM frame"

manager = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "Manager")
methods = [node for node in manager.body if isinstance(node, ast.FunctionDef) and node.name in ("refresh", "clear")]
exec(compile(ast.Module(body=methods, type_ignores=[]), "wm-capability-cache-fixture", "exec"), namespace)
requests = []
socket_name = ["first"]
def request(path, kind):
    requests.append((path, kind))
    return ({"ooonana_control_api": 1, "ooonana_control_scale": 2} if kind == 7 else {} if kind == 4 else [])
namespace.update(i3_events=SimpleNamespace(socket_path=lambda: socket_name[0], request=request),
                 initial_dialog_targets=lambda *_: {}, initial_app_targets=lambda *_: {})
owner = SimpleNamespace(controls={}, placement_seen=None, capability_path=None, control_scale=0)
owner.clear = lambda: namespace["clear"](owner)
for _ in range(2):
    namespace["refresh"](owner)
assert requests.count(("first", 7)) == 1 and owner.control_scale == 2
owner.clear()
namespace["refresh"](owner)
assert requests.count(("first", 7)) == 2
socket_name[0] = "replacement"
namespace["refresh"](owner)
assert requests.count(("replacement", 7)) == 1
activate = next(node for node in controls.body if isinstance(node, ast.FunctionDef) and node.name == "activate")
exec(compile(ast.Module(body=[activate], type_ignores=[]), "control-action-xid-fixture", "exec"), namespace)
actions = []
namespace["run_async"] = lambda command, _done: actions.append(command)
namespace["activate"](SimpleNamespace(identifier=42, target_xid=101), "close")
assert actions == [["ooonana-window-list", "--window-action", "close", "42", "--expect-xid", "101"]]
namespace["activate"](SimpleNamespace(identifier=42, target_xid=None), "close")
assert len(actions) == 1
print("WINDOW_CONTROL_SCALE_OK legacy/native, 1x/2x/4x, origins, capability guards, scale changes and remap")
