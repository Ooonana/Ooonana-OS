#!/usr/bin/env python3
"""Initial Qt placement guards without importing a display toolkit."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
source = ast.parse((root / "packages/ooonana/usr/lib/ooonana/ui/window_controls.py").read_text())
function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "initial_dialog_targets")
manager = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "Manager")
callback = next(node for node in manager.body if isinstance(node, ast.FunctionDef) and node.name == "place_initial_dialog")
namespace = {}
exec(compile(ast.Module(body=[function, callback], type_ignores=[]), "placement-fixture", "exec"), namespace)
targets = namespace["initial_dialog_targets"]

dialog = {"id": 42, "window": 123, "window_type": "dialog", "floating": "auto_on",
          "window_properties": {"class": "qterminal"}, "rect": {"x": 0, "y": -13, "width": 640, "height": 600}}
workspace = {"type": "workspace", "name": "1", "floating_nodes": [dialog]}
output = {"type": "output", "rect": {"x": 0, "y": 0, "width": 640, "height": 600}, "nodes": [workspace]}
tree = {"type": "root", "nodes": [output]}
expected = {42: ((0, 0), (0, -13, 640, 600))}
assert targets(tree, {"1"}) == expected
assert targets(tree, {"2"}) == {}
assert targets({"nodes": [workspace]}, {"1"}) == {}
for field, value in (("window_type", "normal"), ("floating", "auto_off"), ("fullscreen_mode", 1),
                     ("window_properties", {"class": "OoonanaApp"}), ("window_properties", {"class": "Geany"})):
    candidate = deepcopy(tree)
    candidate["nodes"][0]["nodes"][0]["floating_nodes"][0][field] = value
    assert targets(candidate, {"1"}) == {}, (field, value)
for rectangle in ({"x": 0, "y": 0, "width": 640, "height": 600},
                  {"x": 0, "y": -13, "width": 641, "height": 600},
                  {"x": 0, "y": -13, "width": 640, "height": 601}):
    candidate = deepcopy(tree)
    candidate["nodes"][0]["nodes"][0]["floating_nodes"][0]["rect"] = rectangle
    assert targets(candidate, {"1"}) == {}, rectangle
negative = deepcopy(tree)
negative["nodes"][0]["rect"]["x"] = -640
negative["nodes"][0]["nodes"][0]["floating_nodes"][0]["rect"]["x"] = -650
assert targets(negative, {"1"}) == {42: ((-640, 0), (-650, -13, 640, 600))}

commands = []
namespace["i3_events"] = SimpleNamespace(socket_path=lambda: "fixture", request=lambda path, kind:
    tree if kind == 4 else [{"name": "1", "visible": True}])
namespace["run_async"] = lambda command, _done: commands.append(command)
place = namespace["place_initial_dialog"]
owner = SimpleNamespace(placement_seen={42})
assert place(owner, 42, expected[42][1]) is False
assert commands == [["i3-msg", "[con_id=42] move absolute position 0 px 0 px"]]
commands.clear()
assert place(owner, 42, (0, -6, 640, 600)) is False
assert commands == [], "Changed user geometry must not be corrected"
for seen in (None, set()):
    owner.placement_seen = seen
    assert place(owner, 42, expected[42][1]) is False
    assert commands == [], "Closed/restarted session must not move windows"
print("ok initial-dialog-placement: scoped Qt, bounds, hidden/negative outputs, no resize, changed/closed refusal")

app_function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "initial_app_targets")
app_callback = next(node for node in manager.body if isinstance(node, ast.FunctionDef) and node.name == "fit_initial_app")
exec(compile(ast.Module(body=[app_function, app_callback], type_ignores=[]), "app-fit-fixture", "exec"), namespace)
app_targets = namespace["initial_app_targets"]
app_tree = deepcopy(tree)
app = app_tree["nodes"][0]["nodes"][0]["floating_nodes"][0]
app.update(window_type="normal", window_properties={"class": "Geany"},
           rect={"x": -131, "y": -24, "width": 902, "height": 623},
           window_rect={"width": 900, "height": 600})
original = (-131, -24, 902, 623)
assert app_targets(app_tree, {"1"}) == {42: ((12, 58, 616, 458), original, 123)}
assert app_targets(app_tree, {"2"}) == {}
for field, value in (("window_type", "dialog"), ("floating", "auto_off"), ("fullscreen_mode", 1),
                     ("window_properties", {"class": "OoonanaApp"}), ("window_properties", {"class": "XTerm"})):
    candidate = deepcopy(app_tree)
    candidate["nodes"][0]["nodes"][0]["floating_nodes"][0][field] = value
    assert app_targets(candidate, {"1"}) == {}, (field, value)
fitting = deepcopy(app_tree)
fitting["nodes"][0]["nodes"][0]["floating_nodes"][0]["rect"] = {"x": 20, "y": 60, "width": 500, "height": 400}
assert app_targets(fitting, {"1"}) == {}, "Already fitting app geometry must stay unchanged"
negative = deepcopy(app_tree)
negative["nodes"][0]["rect"].update(x=-640, y=-600)
negative["nodes"][0]["nodes"][0]["floating_nodes"][0]["rect"].update(x=-771, y=-624)
assert app_targets(negative, {"1"})[42][0] == (-628, -542, 616, 458)
files = deepcopy(app_tree)
files["nodes"][0]["nodes"][0]["floating_nodes"][0]["window_properties"] = {"class": "Nemo"}
assert app_targets(files, {"1"}) == app_targets(app_tree, {"1"})
namespace["i3_events"] = SimpleNamespace(socket_path=lambda: "fixture", request=lambda path, kind:
    app_tree if kind == 4 else [{"name": "1", "visible": True}])
commands.clear()
owner.placement_seen = {42}
fit = namespace["fit_initial_app"]
assert fit(owner, 42, original, 123) is False
assert commands == [["i3-msg", "[con_id=42 id=123] resize set 616 px 458 px; [con_id=42 id=123] move absolute position 12 px 58 px"]]
commands.clear()
assert fit(owner, 42, original, 999) is False and not commands, "Reused ID must not resize another client"
assert fit(owner, 42, (0, 0, 902, 623), 123) is False and not commands, "Later user geometry must stay unchanged"
owner.placement_seen = set()
assert fit(owner, 42, original, 123) is False and not commands, "Closed client must stay untouched"
print("ok initial-app-fit: scoped new Geany/Nemo, frame clearances, fitting defaults, hidden/negative outputs, user move and reused/closed refusal")
