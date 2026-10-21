#!/usr/bin/env python3
"""Candidate-only i3 source guards and native-sized metrics, no desktop changes."""
import importlib.util
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("i3_patch", root / "scripts/patch-i3-controls.py")
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)
pins = json.loads((root / "packages/i3wm/source-pins.json").read_text(encoding="utf-8"))
assert pins["version"] == "4.24" and pins["mode"] == "candidate-only"
assert pins["source_sha256"] == "5baefd0e5e78f1bafb7ac85deea42bcd3cbfe65f1279aa96f7e49661637ac981"

with tempfile.TemporaryDirectory(prefix="ooonana-i3-controls-") as temporary:
    work = Path(temporary)
    source = work / "i3-4.24"
    (source / "include").mkdir(parents=True)
    originals = {}
    for name, edits in patcher.replacements().items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "/* UTF-8 guard: ‘source’ */\n" + "\n".join(before for before, _after in edits)
        path.write_text(text, encoding="utf-8")
        originals[path] = path.read_bytes()
    assert patcher.patch(source, check=True) == 5
    assert all(path.read_bytes() == data for path, data in originals.items())
    last = source / "src/handlers.c"
    last.write_text("unknown upstream source", encoding="utf-8")
    try:
        patcher.patch(source)
        raise AssertionError("Changed source must be refused")
    except ValueError:
        pass
    assert all(path.read_bytes() == data for path, data in originals.items() if path != last), "No partial patch before final hunk validates"
    last.write_bytes(originals[last])
    assert patcher.patch(source) == 5
    assert (source / "include/ooonana_controls.h").read_bytes() == (root / "packages/i3wm/ooonana_controls.h").read_bytes()
    frozen = {path: path.read_bytes() for path in originals}
    try:
        patcher.patch(source)
        raise AssertionError("Already modified source must be refused")
    except ValueError:
        pass
    assert all(path.read_bytes() == data for path, data in frozen.items())
    compiler = shutil.which("cc") or shutil.which("gcc")
    if compiler:
        unit = work / "metrics.c"
        unit.write_text('''#include <assert.h>
#include <stdio.h>
#include "ooonana_controls.h"
int main(void) {
    int scale = ooonana_control_scale();
    printf("%d %d %d %d %d\\n", scale, ooonana_titlebar_height(),
           ooonana_titlebar_left(10000), ooonana_titlebar_left(10), OOONANA_CONTROL_ICON);
    assert(OOONANA_CONTROL_SIZE == 24 && OOONANA_CONTROL_GAP == 5 && OOONANA_CONTROL_INSET == 14);
    assert(ooonana_font_dpi(192.0) == (scale > 2 ? 96.0 * scale : 192.0));
    assert(ooonana_font_dpi(96.0) == (scale > 1 ? 96.0 * scale : 96.0));
    return 0;
}
''', encoding="utf-8")
        binary = work / "metrics"
        subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(root / "packages/i3wm"),
                        str(unit), "-o", str(binary)], check=True, capture_output=True)
        for mode, raw, expected in [(None, "2", (0, 0, 0)), ("right", "2", (0, 0, 0)),
                                    ("left", "1", (1, 32, 108)), ("left", "2", (2, 64, 216)),
                                    ("left", "4", (4, 128, 432)), ("left", "0", (1, 32, 108)),
                                    ("left", "2junk", (1, 32, 108)), ("left", "-1", (1, 32, 108))]:
            env = {key: value for key, value in os.environ.items() if key not in ("OOONANA_WINDOW_CONTROLS", "GDK_SCALE")}
            env["GDK_SCALE"] = raw
            if mode is not None:
                env["OOONANA_WINDOW_CONTROLS"] = mode
            values = tuple(map(int, subprocess.check_output([str(binary)], text=True, env=env).split()))
            assert values[:3] == expected and values[3:] == (0, 12), (mode, raw, values)
        print("I3_CONTROL_METRICS_C_OK opt-in/off, 1x/2x/4x, narrow frames, invalid-scale guards")
    else:
        print("SKIP C metrics: compiler unavailable")
print("I3_CONTROLS_PATCH_GUARDS_OK exact hunks, UTF-8, no partial/version/double patch; not built/GUI-certified")

gate_spec = importlib.util.spec_from_file_location("i3_release_gate", root / "scripts/check-release-repo.py")
gate = importlib.util.module_from_spec(gate_spec)
gate_spec.loader.exec_module(gate)
with tempfile.TemporaryDirectory(prefix="ooonana-i3-provenance-") as temporary:
    repo = Path(temporary)
    binary = b"\x7fELF private non-executable fixture"
    receipt = {"control_api": 1, "source": pins,
               "binary_sha256": hashlib.sha256(binary).hexdigest(),
               "inputs": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in
                          ("scripts/patch-i3-controls.py", "packages/i3wm/ooonana_controls.h")}}
    archive = repo / "i3.tar.gz"
    def payload(manifest):
        with tarfile.open(archive, "w:gz") as stream:
            for name, data in (("./usr/bin/i3", binary),
                               ("./usr/share/doc/i3/ooonana-controls/build-manifest.json", json.dumps(manifest).encode())):
                item = tarfile.TarInfo(name)
                item.size = len(data)
                stream.addfile(item, io.BytesIO(data))
        return {"COMPONENTS": "native-controls-v1", "ARCHIVE": archive.name,
                "SHA256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    valid = payload(receipt)
    gate.validate_native_controls(repo, valid)
    broken = json.loads(json.dumps(receipt))
    broken["inputs"]["scripts/patch-i3-controls.py"] = "0" * 64
    for manifest in (None, [], {**receipt, "binary_sha256": "0" * 64}, broken):
        metadata = payload(manifest)
        try:
            gate.validate_native_controls(repo, metadata)
            raise AssertionError("Stale/bad native provenance accepted")
        except ValueError:
            pass
    for metadata in ({}, {**valid, "COMPONENTS": "apk-import"}, {**valid, "SHA256": "0" * 64}):
        try:
            gate.validate_native_controls(repo, metadata)
            raise AssertionError("Legacy/tampered native package accepted")
        except ValueError:
            pass
print("I3_CONTROLS_RELEASE_GUARDS_OK missing/legacy, archive tamper, binary/source/input provenance")
