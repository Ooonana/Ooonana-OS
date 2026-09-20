#!/usr/bin/env python3
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
loader = SourceFileLoader("window_list", str(root / "packages/ooonana/usr/bin/ooonana-window-list"))
module = module_from_spec(spec_from_loader(loader.name, loader))
loader.exec_module(module)


def window(identifier, name, **kwargs):
    return dict(id=identifier, window=identifier, name=name, **kwargs)


tree = dict(nodes=[
    dict(type="dockarea", nodes=[window(1, "Panel")]),
    window(2, "polybar", window_properties={"class": "Polybar"}),
    dict(name="1", floating_nodes=[window(3, "Terminal", scratchpad_state="changed", focused=True)]),
    dict(name="__i3_scratch", floating_nodes=[window(4, "Browser", scratchpad_state="fresh")]),
])
module.tree = lambda: tree
items = module.windows()
assert items == [(3, "Terminal", True, False), (4, "Browser", False, True)], items
assert module.compact(items) == "* Terminal +1 (1 hidden)"
commands = []
selection = "0"


def run(command, **kwargs):
    commands.append(command)
    return SimpleNamespace(stdout=selection)


module.subprocess.run = run
module.menu(items)
assert commands[-1] == ["i3-msg", "[con_id=3] focus"]
selection = "1"
module.menu(items)
assert commands[-1] == ["i3-msg", "[con_id=4] scratchpad show; [con_id=4] focus"]
module.menu(items, close=True)
assert commands[-1] == ["i3-msg", "[con_id=4] kill"]
print("ok window-list")
