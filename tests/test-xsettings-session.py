#!/usr/bin/env python3
"""Pure Xsettings protocol/parser and exact legacy CSS ownership regressions."""
import hashlib
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana"))
import xsettings_session as settings
import legacy_gtk_style as legacy


class Protocol(unittest.TestCase):
    def test_types_comments_and_utf8(self):
        value = settings.parse('# retained comment\nNet/ThemeName "Paper"\nGtk/FontName "한글 10" # tail\n'
                               'Xft/DPI 98304\nTest/Color (1, 2, 3, 65535)\n')
        self.assertEqual(value, {"Net/ThemeName": "Paper", "Gtk/FontName": "한글 10", "Xft/DPI": 98304,
                                 "Test/Color": (1, 2, 3, 65535)})
        wire = settings.encode({"A": "한", "B": -1, "C": (1, 2, 3, 4)}, 7)
        self.assertEqual(wire, (b'\0\0\0\0' + struct.pack('<II', 7, 3) +
            b'\1\0\1\0A\0\0\0' + struct.pack('<II', 7, 3) + '한'.encode() + b'\0' +
            b'\0\0\1\0B\0\0\0' + struct.pack('<Ii', 7, -1) +
            b'\2\0\1\0C\0\0\0' + struct.pack('<I4H', 7, 1, 2, 3, 4)))

    def test_malformed_config_never_becomes_partial_settings(self):
        for text in ('A "unterminated', 'A value', 'A 1\nA 2', 'A 2147483648', 'A -2147483649',
                     'A (1, 2, 3, 65536)', 'A "text" garbage', 'A "text"junk', 'A "nul\0"', 'A "\\u0000"', '../bad 1',
                     'A-B 1', 'A/1key 1', 'A//B 1', 'A/ 1',
                     'A "' + 'x' * settings.LIMIT + '"', '\n'.join(f'Key{i} 0' for i in range(257))):
            with self.subTest(text=text[:35]), self.assertRaises(ValueError):
                settings.parse(text)

    def test_named_palettes_and_opaque_shared_styles(self):
        for name, background in (("OoonanaGraphite", "#101317"), ("OoonanaPaper", "#f5f5f7")):
            source = (ROOT / f"packages/ooonana/usr/share/themes/{name}/gtk-3.0/gtk.css").read_text()
            self.assertIn('@define-color ooonana_bg ' + background, source)
            self.assertIn('Ooonana/gtk-3.0/common.css', source)
            self.assertNotIn('$OOONANA_', source)


@unittest.skipIf(sys.platform == "win32", "POSIX CSS ownership")
class Migration(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ooonana-css-ownership-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.path = self.base / "gtk.css"
        self.content = b'/* private exact generated fixture */\n'
        self.digest = hashlib.sha256(self.content).hexdigest()
        self.path.write_bytes(self.content)

    def test_exact_generated_css_has_backup_then_idempotent_marker(self):
        self.path.chmod(0o640)
        with patch.object(legacy, "LEGACY_HASHES", {self.digest}):
            legacy.retire(self.path)
            self.assertEqual(self.path.read_bytes(), legacy.MARKER)
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
            backup = self.path.with_name('gtk.css.ooonana-legacy-' + self.digest[:12])
            self.assertEqual(backup.read_bytes(), self.content)
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
            legacy.retire(self.path)
            self.assertEqual(len(list(self.base.iterdir())), 2)

    def test_custom_symlink_and_hardlink_retained(self):
        legacy.retire(self.path)
        self.assertEqual(self.path.read_bytes(), self.content)
        target = self.base / "custom"
        self.path.rename(target)
        self.path.symlink_to(target)
        with patch.object(legacy, "LEGACY_HASHES", {self.digest}), self.assertRaises(OSError):
            legacy.retire(self.path)
        self.path.unlink()
        os.link(target, self.path)
        with patch.object(legacy, "LEGACY_HASHES", {self.digest}):
            legacy.retire(self.path)
        self.assertEqual(self.path.read_bytes(), self.content)

    def test_backup_conflict_and_concurrent_edit_keep_original(self):
        with patch.object(legacy, "LEGACY_HASHES", {self.digest}):
            backup = self.path.with_name('gtk.css.ooonana-legacy-' + self.digest[:12])
            backup.write_text('unrelated user file')
            with self.assertRaises(ValueError):
                legacy.retire(self.path)
            self.assertEqual(self.path.read_bytes(), self.content)
            backup.unlink()
            fsync = os.fsync
            def race(descriptor):
                fsync(descriptor)
                self.path.write_text('concurrent user edit')
            with patch.object(legacy.os, 'fsync', side_effect=race), self.assertRaises(ValueError):
                legacy.retire(self.path)
            self.assertEqual(self.path.read_text(), 'concurrent user edit')
            self.assertFalse(list(self.base.glob('.gtk.css.*')))


if __name__ == "__main__":
    unittest.main()
