#!/usr/bin/env python3
"""Preserve empty MPD columns through common.run's whitespace trimming."""
import ast
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
source = ast.parse((root / "packages/ooonana/usr/lib/ooonana/ui/controls_app.py").read_text(encoding="utf-8"))
media = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "MediaWindow")
collect = next(node for node in media.body if isinstance(node, ast.FunctionDef) and node.name == "collect_state")
collect.decorator_list = []
namespace = {}
exec(compile(ast.Module(body=[collect], type_ignores=[]), "media-metadata-fixture", "exec"), namespace)
filename = "한글-untagged%{F#fff}.wav"
for artist, title in (("", ""), ("", "Title"), ("Artist", ""), ("Artist", "Title")):
    def run(command, **options):
        if command[-1] == "current":
            assert options.get("utf8") is True, "Human metadata must opt in to Unicode"
            raw = command[2].replace("%artist%", artist).replace("%title%", title).replace("%file%", filename)
            return 0, (raw + "\n").strip()
        return 0, "volume: 61%"
    namespace["run"] = run
    rc, state = namespace["collect_state"]()
    assert rc == 0 and state["current"].split("\t", 2) == [artist, title, filename], state

namespace["run"] = lambda command, **options: (0, "")
assert namespace["collect_state"]()[1]["current"] == ""
namespace["run"] = lambda command, **options: (1, "MPD unavailable")
assert namespace["collect_state"]() == (1, "MPD unavailable")

common = ast.parse((root / "packages/ooonana/usr/lib/ooonana/ui/common.py").read_text(encoding="utf-8"))
runner = next(node for node in common.body if isinstance(node, ast.FunctionDef) and node.name == "run")
calls = []


class Process:
    returncode = 0

    def __init__(self, _command, **options):
        calls.append(options)

    def communicate(self, **_options):
        return "한글 metadata\n", None


scope = {"os": SimpleNamespace(environ={"TASK_EXAMPLE": "retained"}),
         "subprocess": SimpleNamespace(Popen=Process, PIPE=-1, STDOUT=-2)}
exec(compile(ast.Module(body=[runner], type_ignores=[]), "metadata-command-fixture", "exec"), scope)
for utf8, expected in ((False, "C"), (True, "C.UTF-8")):
    assert scope["run"](["owned-fixture"], utf8=utf8) == (0, "한글 metadata")
    assert calls[-1]["env"]["LC_ALL"] == calls[-1]["env"]["LANG"] == expected
    assert calls[-1]["env"]["TASK_EXAMPLE"] == "retained"
print("MEDIA_METADATA_OK empty tags, filename, failures, Unicode opt-in and unchanged parser locale")

body = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "control_body")


class Widget:
    def __init__(self, *arguments, **options):
        pass

    def __getattr__(self, name):
        return lambda *arguments: None


sizes = []
scope = {"Gtk": SimpleNamespace(Box=Widget, ScrolledWindow=Widget,
                               Orientation=SimpleNamespace(VERTICAL=0), PolicyType=SimpleNamespace(AUTOMATIC=0)),
         "fit_dialog": lambda window, width, height: sizes.append((width, height))}
exec(compile(ast.Module(body=[body], type_ignores=[]), "control-body-fixture", "exec"), scope)
for bounded, expected in (((576, 376), (576, 376)), ((720, 460), (720, 460)), ((-1, -1), (720, 460))):
    window = SimpleNamespace(get_default_size=lambda: bounded, add=lambda root: None)
    scope["control_body"](window, 720, 460)
    assert sizes[-1] == expected, sizes[-1]
print("CONTROL_BODY_BOUNDS_OK preserve header limits without changing desktop defaults")
