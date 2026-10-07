#!/usr/bin/env python3
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import os
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
os.environ["OOONANA_WINDOW_MENU"] = "rofi"
loader = SourceFileLoader("window_list", str(root / "packages/ooonana/usr/bin/ooonana-window-list"))
module = module_from_spec(spec_from_loader(loader.name, loader))
loader.exec_module(module)


def window(identifier, name, **kwargs):
    return dict(id=identifier, window=identifier, name=name, **kwargs)


tree = dict(nodes=[
    dict(type="dockarea", nodes=[window(1, "Panel")]),
    window(2, "polybar", window_properties={"class": "Polybar"}),
    dict(name="1", floating_nodes=[window(3, "Terminal", scratchpad_state="changed", focused=True, window_properties={"class": "XTerm"})]),
    dict(name="__i3_scratch", floating_nodes=[window(4, "Browser", scratchpad_state="fresh", window_properties={"class": "Chromium"})]),
])
module.tree = lambda: tree
items = module.windows()
assert items == [(3, "Terminal", True, False, "xterm"), (4, "Browser", False, True, "chromium")], items
assert module.compact(items) == "* Terminal +1 (1 hidden)"
bar = module.bar(items)
assert "ooonana-window-list --focus 3" in bar
assert "ooonana-window-list --actions 3" in bar
assert "ooonana-window-list --focus 4" in bar
assert module.bar([]) == "desktop"
dock = module.dock(items)
assert "ooonana-window-list --dock-open terminal" in dock
assert "ooonana-window-list --dock-actions browser" in dock
assert "•" in dock
assert module.pin_for(items[0]) == "terminal"
assert module.pin_for(items[1]) == "browser"
assert module.pin_for((8, "Music", False, False, "ooonanaapp")) == "music"
assert module.pin_for((8, "Ooonana Music", False, False, "ooonanaapp")) == "music"
assert module.pin_for((8, "Ooonana Music", False, False, "chromium")) == "browser"
assert module.pin_for((9, "Task Manager", False, False, "ooonanaapp")) == "tasks"
for title in ("Music", "Task Manager - Chromium", "Spotlight documentation", "Processes"):
    assert module.pin_for((9, title, False, False, "chromium")) == "browser", title
assert module.pin_for((9, "Task Manager notes", False, False, "geany")) == "editor"
assert module.pin_for((9, "OpenVINO / Quack", False, False, "pywebview")) == "openvino"
assert module.pin_for((9, "OpenVINO / Quack - Approval needed", False, False, "pywebview")) == "openvino"
openvino_window = (6, "OpenVINO Chat", False, False, "chromium")
assert module.pin_for(openvino_window) == "openvino"
original_which = module.shutil.which
module.shutil.which = lambda command: "/usr/bin/" + command
assert "ooonana-window-list --dock-open openvino" in module.dock(items + [openvino_window])
module.shutil.which = original_which
commands = []
launches = []
selection = "0"


menu_inputs = []


def run(command, **kwargs):
    commands.append(command)
    if command[0] == "rofi":
        menu_inputs.append(kwargs["input"])
    return SimpleNamespace(stdout=selection)


module.subprocess.run = run
module.subprocess.Popen = lambda command, **_kwargs: launches.append(command)
module.menu(items)
assert commands[-1] == ["i3-msg", "[con_id=3] focus"]
selection = "1"
module.menu(items)
assert commands[-1] == ["i3-msg", "[con_id=4] scratchpad show; [con_id=4] focus"]
module.menu(items, close=True)
assert commands[-1] == ["i3-msg", "[con_id=4] kill"]
selection = "1"
module.actions_menu(items, 3)
assert commands[-1] == ["i3-msg", "[con_id=3] move scratchpad"]
selection = "0"
module.actions_menu(items, 4)
assert commands[-1] == ["i3-msg", "[con_id=4] scratchpad show; [con_id=4] focus"]
selection = "2"
module.actions_menu(items, 4)
assert commands[-1] == ["i3-msg", "[con_id=4] fullscreen toggle"]
selection = "3"
module.actions_menu(items, 3)
assert commands[-1] == ["i3-msg", "[con_id=3] kill"]
module.sys.argv = ["ooonana-window-list", "--focus", "4"]
module.main()
assert commands[-1] == ["i3-msg", "[con_id=4] scratchpad show; [con_id=4] focus"]
module.sys.argv = ["ooonana-window-list", "--actions"]
selection = "1"
module.main()
assert commands[-1] == ["i3-msg", "[con_id=4] move scratchpad"]
module.sys.argv = ["ooonana-window-list", "--focused-actions"]
module.main()
assert commands[-1] == ["i3-msg", "[con_id=3] move scratchpad"]
module.sys.argv = ["ooonana-window-list", "--window-action", "show", "4"]
module.main()
assert commands[-1] == ["i3-msg", "[con_id=4] scratchpad show; [con_id=4] focus"]
module.sys.argv = ["ooonana-window-list", "--window-action", "close", "invalid"]
before = len(commands)
module.main()
assert len(commands) == before
module.dock_open(items, "browser")
assert commands[-1] == ["i3-msg", "[con_id=4] scratchpad show; [con_id=4] focus"]
module.dock_open(items, "music")
assert launches[-1] == ("ooonana-music",)
other = (10, "Ooonana Settings", False, True, "ooonanaapp")
assert module.other_windows(items + [other]) == [other]
module.dock_open(items + [other], "other")
assert commands[-1] == ["i3-msg", "[con_id=10] scratchpad show; [con_id=10] focus"]
selection = "0"
module.dock_actions(items + [other], "other")
assert commands[-1] == ["i3-msg", "[con_id=10] scratchpad show; [con_id=10] focus"]
selection = "1"
module.dock_open(items + [other, (11, "Unpinned app", False, False, "thirdparty")], "other")
assert commands[-1] == ["i3-msg", "[con_id=11] focus"]
assert "Terminal" not in menu_inputs[-1] and "Browser" not in menu_inputs[-1], menu_inputs[-1]
assert "Ooonana Settings" in menu_inputs[-1] and "Unpinned app" in menu_inputs[-1]
before_other = len(commands)
module.dock_open(items, "other")
module.dock_actions(items, "other")
assert len(commands) == before_other
before_launch = len(launches)
module.dock_open(items + [(8, "Ooonana Music", False, True, "ooonanaapp")], "music")
assert len(launches) == before_launch
assert commands[-1] == ["i3-msg", "[con_id=8] scratchpad show; [con_id=8] focus"]
selection = "1"
module.dock_actions(items, "terminal")
assert commands[-1] == ["i3-msg", "[con_id=3] move scratchpad"]
selection = "0"
module.dock_actions(items, "music")
assert launches[-1] == ("ooonana-music",)
tree["nodes"].append(window(5, "100%{A1:bad:} CPU"))
assert "%{A1:bad:}" not in module.bar(module.windows())
assert "ooonana-window-list --focus 5" in module.dock(module.windows())
tree["nodes"].append(window(7, "Spreadsheet"))
assert " +1 " in module.dock(module.windows())
print("ok window-list")
