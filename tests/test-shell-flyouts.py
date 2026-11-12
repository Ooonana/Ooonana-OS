#!/usr/bin/env python3
"""Flyout bounds, focus identity, worker completion and task-list contracts."""
import ast
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from types import SimpleNamespace
from contextlib import redirect_stderr
import io
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT / "packages/ooonana/usr/lib/ooonana/ui/shell_flyout.py").read_text())
methods = [node for node in tree.body if isinstance(node, ast.FunctionDef)
           and node.name in ("anchor_geometry", "focused_client", "visible_client", "operation_group", "external_child")]
scope = {}
exec(compile(ast.Module(body=methods, type_ignores=[]), "flyout-contracts", "exec"), scope)
for area in ((0, 0, 1280, 800), (-1280, -100, 1280, 800), (0, 0, 640, 480), (0, 0, 10, 10)):
    for size in ((440, 520), (560, 320), (3000, 3000)):
        for anchor in ("left", "right", "bottom"):
            x, y, width, height = scope["anchor_geometry"](area, size, anchor)
            assert area[0] <= x and x + width <= area[0] + area[2]
            assert area[1] <= y and y + height <= area[1] + area[3]
            assert min(width, height) > 0

parent = dict(id=1, window=10, name="Editor", focused=True, window_properties={"class": "Geany"})
flyout = dict(id=2, window=20, name="Notifications", focused=True, window_properties={"class": "OoonanaFlyout"})
dialog = dict(id=3, window=30, name="Child", window_properties={"class": "OoonanaApp", "transient_for": 20})
nested = dict(id=4, window=40, name="Nested", window_properties={"class": "GtkDialog", "transient_for": 30})
other = dict(id=5, window=50, name="Other dialog", window_properties={"class": "GtkDialog", "transient_for": 10})
snapshot = {"nodes": [{"type": "workspace", "name": "1", "nodes": [parent, flyout, dialog, nested, other]}]}
assert scope["focused_client"](snapshot) == (1, 10)
assert scope["focused_client"](flyout) is None
assert scope["visible_client"](snapshot, (1, 10), {"1"})
assert not scope["visible_client"](snapshot, (1, 99), {"1"})
assert not scope["visible_client"](snapshot, (1, 10), {"2"})
assert scope["operation_group"]("controls") == scope["operation_group"]("audio") == scope["operation_group"]("brightness")
assert scope["operation_group"]("wifi") != scope["operation_group"]("audio")
assert scope["external_child"](snapshot, 20)
assert not scope["external_child"](snapshot, 999)
assert not scope["external_child"]({"type": "workspace", "name": "__i3_scratch", "nodes": [dialog]}, 20)
loader = SourceFileLoader("shell_task_list", str(ROOT / "packages/ooonana/usr/bin/ooonana-window-list"))
windows = module_from_spec(spec_from_loader(loader.name, loader))
loader.exec_module(windows)
assert [item[0] for item in windows.windows(snapshot)] == [1, 5], "Flyouts and nested dialogs must not create task sessions"

common = ast.parse((ROOT / "packages/ooonana/usr/lib/ooonana/ui/common.py").read_text())
callback = next(node for node in common.body if isinstance(node, ast.FunctionDef) and node.name == "operation_callback")
events = []
app = SimpleNamespace(begin_operation=lambda: (events.append("hold"), lambda: events.append("release"))[1])
scope["Gtk"] = SimpleNamespace(Application=SimpleNamespace(get_default=lambda: app))
exec(compile(ast.Module(body=[callback], type_ignores=[]), "worker-lifetime", "exec"), scope)
deliver = scope["operation_callback"](lambda *_: events.append("done"))
assert deliver(0, "") is False and events == ["hold", "done", "release"]
events.clear()
def failure(*_args):
    raise RuntimeError("Owned callback failure")
try:
    scope["operation_callback"](failure)(1, "")
except RuntimeError:
    pass
assert events == ["hold", "release"], "Failed callback leaks application hold"
scope["Gtk"].Application.get_default = lambda: None
assert scope["operation_callback"](failure) is failure, "Standalone apps must retain their existing callback behavior"

loader = SourceFileLoader("shell_client_contract", str(ROOT / "packages/ooonana/usr/lib/ooonana/ui/shell_client.py"))
client = module_from_spec(spec_from_loader(loader.name, loader)); loader.exec_module(client)
replayed = []
with patch.dict(sys.modules, {"shell_flyout": SimpleNamespace(run_shell=lambda *args: replayed.append(args) or 0)}):
    with patch.object(client.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as call:
        assert client.main("apps", panel=True) == 0
        assert call.call_args.args[0][-2:] == ["[<('apps', 'left')>]", "{}"]
        assert client.main("apps'; touch /tmp/nope") == 2 and call.call_count == 1
    with redirect_stderr(io.StringIO()):
        with patch.object(client.subprocess, "run", side_effect=subprocess.TimeoutExpired("gdbus", 2)):
            assert client.main("apps") == 1 and not replayed, "Ambiguous IPC timeout replayed toggle"
        with patch.object(client.subprocess, "run", return_value=SimpleNamespace(returncode=1, stderr="org.freedesktop.DBus.Error.AccessDenied")):
            assert client.main("apps") == 1 and not replayed, "IPC refusal replayed toggle"
    with patch.object(client.subprocess, "run", return_value=SimpleNamespace(returncode=1, stderr="org.freedesktop.DBus.Error.ServiceUnknown")):
        assert client.main("notifications") == 0 and replayed == [("notifications", False)]
print("SHELL_FLYOUT_CONTRACTS_OK bounds/negative origins, exact visible focus, nested task exclusion, background worker lifetime")
