#!/usr/bin/env python3
"""Application identity, overflow and exact-session policy without GTK/X11."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import sys
import json
import tempfile
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana/ui"))
from dock_model import PinStore, app_groups, click_target, visible_groups

loader = SourceFileLoader("dock_windows_test", str(root / "packages/ooonana/usr/bin/ooonana-window-list"))
windows = module_from_spec(spec_from_loader(loader.name, loader))
loader.exec_module(windows)
items = [(1, "First terminal", False, False, "xterm"),
         (2, "Second terminal", False, True, "xterm"),
         (3, "Browser", False, False, "chromium"),
         (4, "Different browser", False, False, "firefox"),
         (5, "Ooonana Settings", False, False, "ooonanaapp"),
         (6, "Ooonana Packages", False, False, "ooonanaapp"),
         (7, "File chooser", True, False, "other-dialog-class"),
         (8, "Ooonana Settings", False, True, "ooonanaapp"),
         (9, "Unidentified window", False, False, "")]
nodes = {item[0]: {"window": item[0] * 100, "window_properties": {"class": item[4]}} for item in items}
nodes[5]["window_properties"]["window_role"] = "ooonana-settings"
nodes[7]["window_properties"]["transient_for"] = 500
groups, hints = app_groups(items, nodes, windows.pin_for)
assert groups["terminal"] == items[:2]
assert groups["browser"] == [items[2]]
assert groups["class:firefox"] == [items[3]]
assert groups["ooonana-settings"] == [items[4], items[6], items[7]]
assert groups["ooonana-packages"] == [items[5]]
assert groups["window:9"] == [items[8]]
assert sum(map(len, groups.values())) == len(items)
assert click_target(groups["ooonana-settings"], [8, 5, 7]) == items[6]
assert click_target(groups["terminal"], [2, 1]) == items[0], "App click must not revive hidden siblings"
hidden = [(1, "One", False, True, "xterm"), (2, "Two", False, True, "xterm")]
assert click_target(hidden, [2, 1]) == hidden[1]
assert click_target(hidden, []) == hidden[0]
assert click_target([], []) is None
focused = [(1, "One", True, False, "xterm"), hidden[1]]
assert click_target(focused, [2]) == focused[0], "Focused app click must not minimize it"
# Dialog cycles and missing parents cannot hang/discard windows.
nodes[5]["window_properties"]["transient_for"] = 700
cyclic, _ = app_groups(items, nodes, windows.pin_for)
assert sum(map(len, cyclic.values())) == len(items)
nodes[5]["window_properties"]["transient_for"] = 999999
assert sum(map(len, app_groups(items, nodes, windows.pin_for)[0].values())) == len(items)
pins = [pin[0] for pin in windows.PINS]
for width in (320, 480, 640, 1280):
    many = {"terminal": items[:2], **{f"class:app{index}": [items[3]] for index in range(60)}}
    keys, overflow = visible_groups(many, pins, width)
    assert len(keys) <= max(2, (width - 44) // 52)
    assert "apps" in keys and "other" in keys and "terminal" in keys
    assert set(many) <= set(keys) | set(overflow), "Every running app must remain reachable"
    assert not (set(keys) & set(overflow))
keys, overflow = visible_groups(groups, pins, 1280)
assert "class:firefox" in keys and "ooonana-settings" in keys and not overflow
keys, overflow = visible_groups({"class:one": [items[3]], "class:two": [items[5]]}, pins, 320)
assert "class:one" in keys and "class:two" in keys, "Idle launchers must yield to running apps"
assert set(pins) <= set(keys) | set(overflow), "Hidden idle pins need More apps access too"
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / "dock.json"
    defaults = [{"key": "terminal"}, {"key": "browser"}]
    state = PinStore(path, defaults)
    assert state.records == defaults and not state.error and not path.exists()
    records = [{"key": "class:firefox", "desktop": "org.mozilla.firefox.desktop"}, *defaults]
    assert state.save(records, ["ooonana-settings", "class:qterminal"])
    assert PinStore(path, defaults).records == records
    assert PinStore(path, defaults).order == ["ooonana-settings", "class:qterminal"]
    before = path.read_bytes()
    with patch("dock_model.write_json", side_effect=PermissionError("Owned readonly fixture")):
        assert not state.save(defaults)
    assert state.records == records and path.read_bytes() == before and state.error
    bad_layouts = [([{"key": "window:12345", "desktop": "foo.desktop"}], []),
                   ([{"key": "class:foo", "desktop": "../escape.desktop"}], []),
                   ([{"key": "class:foo"}], []),
                   ([{"key": "terminal"}, {"key": "terminal"}], []),
                   (defaults, ["class:foo", "class:foo"]),
                   (defaults, ["window:12345"]),
                   ([{"key": "terminal"}] * 65, [])]
    for records_bad, order_bad in bad_layouts:
        assert not state.save(records_bad, order_bad)
        assert path.read_bytes() == before
    path.write_text('{invalid JSON')
    corrupt = PinStore(path, defaults)
    assert corrupt.load_failed and not corrupt.save(defaults)
    assert path.read_text() == '{invalid JSON', "Never overwrite unreadable user preferences"
    path.write_text(json.dumps({"version": 99, "pins": [], "order": []}))
    assert PinStore(path, defaults).load_failed
    path.write_text('x' * 65537)
    assert PinStore(path, defaults).load_failed
print("DOCK_MODEL_OK distinct apps, native roles/dialogs, stable capacity and exact-session click")
