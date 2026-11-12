#!/usr/bin/env python3
"""Atomic pinned presentation patch and authentication/input preservation."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("locker_patcher", ROOT / "scripts/patch-i3lock-visuals.py")
patcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(patcher)


class VisualPatch(unittest.TestCase):
    def fixture(self, root):
        values = {}
        for name, changes in patcher.replacements().items():
            text = "\n".join(before * (2 if before.strip() in ("cairo_set_line_width(ctx, 10.0);", "cairo_set_font_size(ctx, 14.0);") else 1)
                             for before, _after in changes)
            (root / name).write_text(text)
            values[name] = text
        return values

    def test_only_clock_redraws_added_to_main(self):
        with tempfile.TemporaryDirectory(prefix="ooonana-lock-patch-") as temporary:
            root = Path(temporary); originals = self.fixture(root)
            patcher.patch(root)
            patched = (root / "i3lock.c").read_text()
            self.assertEqual(patched.replace(patcher.TICK, "").replace(patcher.START, ""), originals["i3lock.c"])
            with self.assertRaises(ValueError): patcher.patch(root)
        timer = patcher.TICK + patcher.START
        for forbidden in ("input_done(", "clear_password_memory(", "pam_", "xcb_grab_", "xcb_ungrab_", "ev_break(", "exit("):
            self.assertNotIn(forbidden, timer)
        self.assertIn('0., 60., NULL', timer)
        self.assertIn('"OOONANA_LOCK_VISUALS"', timer)

    def test_mismatched_late_anchor_writes_nothing(self):
        with tempfile.TemporaryDirectory(prefix="ooonana-lock-patch-") as temporary:
            root = Path(temporary); self.fixture(root)
            path = root / "unlock_indicator.c"
            path.write_text(path.read_text().replace('modifier_string, 28.', 'modifier_string, 29.'))
            originals = {path: path.read_bytes() for path in root.iterdir()}
            with self.assertRaises(ValueError): patcher.patch(root)
            self.assertEqual(originals, {path: path.read_bytes() for path in root.iterdir()})

    def test_header_is_opaque_paint_only_with_readable_palettes(self):
        header = (ROOT / 'packages/i3lock/ooonana_lock_visuals.h').read_text()
        for forbidden in ('pam_', 'input_done(', 'clear_password_memory(', 'xcb_', 'password[', 'system(', 'popen(', 'exit('):
            self.assertNotIn(forbidden, header)
        self.assertIn('localtime_r', header)
        self.assertIn('"%H:%M"', header)
        self.assertIn('xr_resolutions', header)
        self.assertNotIn('cairo_set_source_rgba', header)
        def luminance(color):
            rgb = [(color >> shift & 255) / 255 for shift in (16, 8, 0)]
            return sum((v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4) * w
                       for v, w in zip(rgb, (.2126, .7152, .0722)))
        for foreground, background in ((0x1b1f26, 0xffffff), (0xf5f5f7, 0x1b1f26),
                                      (0x9e2929, 0xfae9e7), (0xff675c, 0x3b2324),
                                      (0x55616e, 0xf5f5f7), (0xb4bdc8, 0x101317)):
            low, high = sorted((luminance(foreground), luminance(background)))
            self.assertGreaterEqual((high + .05) / (low + .05), 4.5)

    def test_release_guard_rejects_legacy_tampered_or_stale_locker(self):
        spec = importlib.util.spec_from_file_location("lock_release", ROOT / "scripts/check-release-repo.py")
        gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
        binary = b"\x7fELF private inert fixture"
        receipt = {"lock_visual_api": 1, "source": json.loads((ROOT / "packages/i3lock/source-pins.json").read_text()),
                   "binary_sha256": hashlib.sha256(binary).hexdigest(), "auth_source_unchanged": True,
                   "auth_source_sha256": "a" * 64, "compile_network": "disabled",
                   "inputs": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                              ("scripts/patch-i3lock-visuals.py", "packages/i3lock/ooonana_lock_visuals.h")}}
        gate.validate_lock_manifest(receipt, binary)
        for bad in (None, [], {**receipt, "auth_source_unchanged": False}, {**receipt, "lock_visual_api": 0},
                    {**receipt, "compile_network": "enabled"}, {**receipt, "inputs": {}},
                    {**receipt, "binary_sha256": "0" * 64}, {**receipt, "source": {}}):
            with self.assertRaises(ValueError): gate.validate_lock_manifest(bad, binary)
        with tempfile.TemporaryDirectory(prefix="ooonana-lock-package-") as temporary:
            repo = Path(temporary); archive = repo / "locker.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                for name, data in (("usr/bin/i3lock", binary),
                                   ("usr/share/doc/i3lock/ooonana-visuals/build-manifest.json", json.dumps(receipt).encode())):
                    item = tarfile.TarInfo(name); item.size = len(data); bundle.addfile(item, io.BytesIO(data))
            package = {"COMPONENTS": "native-lock-visuals-v1", "ARCHIVE": archive.name,
                       "SHA256": hashlib.sha256(archive.read_bytes()).hexdigest()}
            gate.validate_native_lock(repo, package)
            for bad in ({}, {**package, "COMPONENTS": "apk-import"}, {**package, "SHA256": "0" * 64}):
                with self.assertRaises(ValueError): gate.validate_native_lock(repo, bad)


if __name__ == "__main__":
    if "--archive" in sys.argv:
        index = sys.argv.index("--archive"); archive = Path(sys.argv[index + 1]); del sys.argv[index:index+2]
        pins = json.loads((ROOT / 'packages/i3lock/source-pins.json').read_text())
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == pins['source_sha256']
        with tempfile.TemporaryDirectory(prefix="ooonana-real-lock-patch-") as temporary, tarfile.open(archive) as original:
            original.extractall(temporary, filter='data')
            source = Path(temporary) / 'i3lock-2.16'
            main = (source / 'i3lock.c').read_bytes()
            patcher.patch(source)
            assert (source / 'i3lock.c').read_text().replace(patcher.TICK, '').replace(patcher.START, '').encode() == main
            print('PINNED_LOCKER_AUTH_SOURCE_UNCHANGED')
    unittest.main()
