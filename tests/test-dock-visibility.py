#!/usr/bin/env python3
"""Pure fullscreen/output/workspace guards without importing GTK."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
source = ast.parse((root / "packages/ooonana/usr/lib/ooonana/ui/dock_app.py").read_text())
function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "fullscreen_on_monitor")
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), "dock-visibility-fixture", "exec"), namespace)
hidden = namespace["fullscreen_on_monitor"]
area = SimpleNamespace(x=0, y=0, width=640, height=600)
client = dict(id=10, type="con", fullscreen_mode=1, rect=dict(x=0, y=0, width=640, height=600))
workspace = dict(id=1, type="workspace", name="1", fullscreen_mode=1, nodes=[client])
other = dict(id=2, type="workspace", name="2", fullscreen_mode=1, nodes=[])
content = dict(id=3, type="con", name="content", focus=[1, 2], nodes=[workspace, other])
tree = dict(type="root", nodes=[dict(type="output", name="screen", nodes=[content])])
assert hidden(tree, area)
for mode in (0, None):
    candidate = deepcopy(tree)
    candidate["nodes"][0]["nodes"][0]["nodes"][0]["nodes"][0]["fullscreen_mode"] = mode
    assert not hidden(candidate, area), "Normal workspace fullscreen flag hid dock"
candidate = deepcopy(tree)
candidate["nodes"][0]["nodes"][0]["focus"] = [2, 1]
assert not hidden(candidate, area), "Inactive workspace hid dock"
assert not hidden(tree, SimpleNamespace(x=640, y=0, width=640, height=600)), "Other output hid dock"
assert not hidden(tree, SimpleNamespace(x=-640, y=0, width=640, height=600)), "Touching output edge overlaps"
assert hidden(tree, SimpleNamespace(x=-10, y=0, width=640, height=600))
candidate = deepcopy(tree)
candidate["nodes"][0]["nodes"][0]["nodes"][0]["nodes"][0]["fullscreen_mode"] = 2
assert hidden(candidate, SimpleNamespace(x=2000, y=-800, width=640, height=600)), "Global fullscreen did not hide dock"
candidate["nodes"][0]["name"] = "__i3"
assert not hidden(candidate, area), "Scratchpad fullscreen hid dock"
assert not hidden({}, area)
candidate = deepcopy(tree)
split = dict(id=20, type="con", layout="tabbed", focus=[11, 10], nodes=[client, dict(id=11, type="con")])
candidate["nodes"][0]["nodes"][0]["nodes"][0]["nodes"] = [split]
assert not hidden(candidate, area), "Hidden tab hid dock"
split["focus"] = [10, 11]
assert hidden(candidate, area)
candidate = deepcopy(tree)
workspace = candidate["nodes"][0]["nodes"][0]["nodes"][0]
workspace["nodes"], workspace["floating_nodes"] = [], [dict(type="floating_con", nodes=[client])]
assert hidden(candidate, area)
second = deepcopy(tree["nodes"][0])
second["name"] = "secondary"
second["nodes"][0]["nodes"][0]["nodes"][0]["rect"]["x"] = 640
normal = deepcopy(tree["nodes"][0])
normal["nodes"][0]["nodes"][0]["nodes"][0]["fullscreen_mode"] = 0
multi = dict(type="root", nodes=[normal, second])
assert not hidden(multi, area), "Secondary output fullscreen hid primary dock"
assert hidden(multi, SimpleNamespace(x=640, y=0, width=640, height=600))
second["nodes"][0]["nodes"][0]["nodes"][0]["fullscreen_mode"] = 2
assert hidden(multi, area), "Global fullscreen on secondary did not hide primary dock"
scaled = SimpleNamespace(x=320, y=0, width=320, height=300)
local = dict(type="con", fullscreen_mode=1, rect=dict(x=640, y=0, width=640, height=600))
assert hidden(local, scaled, scale=2), "Offset logical monitor was not converted to device pixels"
assert not hidden(local, SimpleNamespace(x=0, y=0, width=320, height=300), scale=2)
print("DOCK_VISIBILITY_OK visible workspaces/tabs, output edges, scratchpad, floating and global fullscreen")
