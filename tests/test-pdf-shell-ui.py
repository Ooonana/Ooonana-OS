#!/usr/bin/env python3
"""Reopen interactive PDF: canonical fields, appearances, actions and geometry."""
import importlib.util
from pathlib import Path
import tempfile

from pdfrw import PdfReader

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pdf_shell", root / "scripts/generate-ooonana-pdf-shell.py")
shell = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shell)
with tempfile.TemporaryDirectory() as temporary:
    compiled, output = Path(temporary) / "vm.js", Path(temporary) / "shell.pdf"
    compiled.write_text("var vm_fixture = true;\n//" + "x" * 10000 + "\n")
    shell.build(compiled, output)
    assert output.stat().st_size < 180000 + 2 * compiled.stat().st_size, "Duplicated page/script content"
    document = PdfReader(str(output))
    page = document.pages[0]
    canonical = document.Root.AcroForm.Fields
    assert str(document.Root.AcroForm.NeedAppearances) == "false"
    widgets = page.Annots
    names = [field.T.to_unicode() for field in canonical]
    assert len(names) == len(set(names)) == 116
    assert not any(name.startswith("console_") for name in names)
    assert "Type command" not in page.Contents.stream
    assert {field.indirect for field in canonical} == {field.indirect for field in widgets}
    assert {f"field_{index}" for index in range(30)} <= set(names)
    assert {"key_input", "key_status", "speed_indicator", "command_enter", "button_Enter"} <= set(names)
    visible = []
    for field in widgets:
        assert field.AP.N.stream
        assert field.AP.N.Resources.Font.FUI and field.AP.N.Resources.Font.FMono
        assert field.V == next(item.V for item in canonical if item.T == field.T)
        x1, y1, x2, y2 = map(float, field.Rect)
        if x2 <= 0 or y2 <= 0:
            assert field.T.to_unicode().startswith("console_")
            continue
        assert 0 <= x1 < x2 <= 760 and 0 <= y1 < y2 <= 820
        visible.append((field.T.to_unicode(), (x1, y1, x2, y2)))
    for index, (name, rectangle) in enumerate(visible):
        for other, second in visible[index + 1:]:
            overlap = min(rectangle[2], second[2]) - max(rectangle[0], second[0])
            height = min(rectangle[3], second[3]) - max(rectangle[1], second[1])
            assert overlap <= 0.001 or height <= 0.001, (name, other)
    by_name = {field.T.to_unicode(): field for field in widgets}
    assert by_name["key_input"].V.to_unicode() == ""
    assert "pdf_key_input(event)" in by_name["key_input"].AA.K.JS.to_unicode()
    assert 'button_down("Backspace")' in by_name["button_Backspace"].AA.D.JS.to_unicode()
    assert 'button_up("Backspace")' in by_name["button_Backspace"].AA.U.JS.to_unicode()
    assert "queue_console_text" in by_name["command_enter"].AA.U.JS.to_unicode()
    assert "button_toggle" in by_name["button_Ctrl"].AA.D.JS.to_unicode()
    assert "button_up" in by_name["button_Enter"].AA.U.JS.to_unicode()
    assert "vm_fixture" in page.AA.O.JS.to_unicode()
print("ok pdf-shell-ui: 116 canonical widgets, empty input, appearances, actions, layout")
