#!/usr/bin/env python3
"""Exercise embedded theme merge against private files, never installed settings."""
import configparser
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "scripts/build-full-i3-rootfs.sh").read_text()
MERGE = SOURCE.split("<<'PY_GTK_SETTINGS'\n", 1)[1].split("\nPY_GTK_SETTINGS", 1)[0]


class ThemePreferences(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ooonana-theme-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.ini = self.base / "gtk-3.0/settings.ini"
        self.xconfig = self.base / "ooonana/xsettingsd.conf"
        for path in (self.ini, self.xconfig):
            path.parent.mkdir(parents=True, exist_ok=True)

    def merge(self, prefix="", success=True):
        result = subprocess.run([sys.executable, "-c", prefix + MERGE, str(self.base),
                                 "true", "Adwaita-dark", "OoonanaTailless", "19"],
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        self.assertFalse(list(self.base.rglob(".settings.ini.*")))
        self.assertFalse(list(self.base.rglob(".xsettingsd.conf.*")))
        return result

    def settings(self):
        parser = configparser.RawConfigParser(strict=False, delimiters=("=",))
        parser.read(self.ini)
        return parser["Settings"]

    def test_defaults_and_idempotency(self):
        self.merge()
        self.assertEqual(self.settings()["gtk-font-name"], "Sans 10")
        self.assertEqual(self.settings()["gtk-cursor-theme-size"], "19")
        before = (self.ini.read_bytes(), self.xconfig.read_bytes())
        self.merge()
        self.assertEqual(before, (self.ini.read_bytes(), self.xconfig.read_bytes()))

    def test_preserve_preferences_comments_sections_modes(self):
        self.ini.write_text("# retain comment\n[Settings]\ngtk-font-name=Serif 11\n"
                            "gtk-xft-dpi=196608\ngtk-icon-theme-name=Custom Icons\n"
                            "gtk-enable-animations=false\ngtk-custom=value:with=punctuation\n"
                            "[Application]\nsecret=fixture-only\n")
        self.ini.chmod(0o600)
        self.xconfig.write_text('# retain xsettings\nXft/Antialias 1\nGtk/FontName "Old 9"\n')
        self.xconfig.chmod(0o640)
        self.merge()
        values = self.settings()
        self.assertEqual(values["gtk-font-name"], "Serif 11")
        self.assertEqual(values["gtk-xft-dpi"], "196608")
        self.assertEqual(values["gtk-enable-animations"], "false")
        self.assertIn("# retain comment", self.ini.read_text())
        self.assertIn("[Application]\nsecret=fixture-only", self.ini.read_text())
        self.assertIn("gtk-custom=value:with=punctuation", self.ini.read_text())
        self.assertIn('Gtk/FontName "Serif 11"', self.xconfig.read_text())
        self.assertIn("Xft/DPI 196608", self.xconfig.read_text())
        self.assertIn("Xft/Antialias 1", self.xconfig.read_text())
        self.assertEqual(stat.S_IMODE(self.ini.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.xconfig.stat().st_mode), 0o640)

    def test_existing_xsettings_font_and_icon_seed_defaults(self):
        self.xconfig.write_text('Gtk/FontName "Serif 12"\nNet/IconThemeName "Custom Icons"\n')
        self.merge()
        self.assertEqual(self.settings()["gtk-font-name"], "Serif 12")
        self.assertEqual(self.settings()["gtk-icon-theme-name"], "Custom Icons")

    def test_duplicate_keys_and_missing_final_newline(self):
        self.ini.write_text("[Settings]\ngtk-font-name=Sans 9\ngtk-font-name=Serif 12")
        self.merge()
        self.assertEqual(self.settings()["gtk-font-name"], "Serif 12")
        self.assertEqual(self.settings()["gtk-theme-name"], "Adwaita")

    def test_reduced_motion_bridge(self):
        ui = self.base / "ooonana/ui.json"
        for reduced in (True, False):
            ui.write_text(json.dumps({"reduce_motion": reduced}))
            self.merge()
            self.assertEqual(self.settings()["gtk-enable-animations"], str(not reduced).lower())
            self.assertIn("Gtk/EnableAnimations " + ("0" if reduced else "1"), self.xconfig.read_text())

    def test_invalid_preferences_retain_both_without_echoing_secret(self):
        for text in ("fixture-secret-no-section", "[Settings]\ngtk-xft-dpi=invalid-secret"):
            self.ini.write_text(text)
            self.xconfig.write_text("# unchanged\n")
            before = (self.ini.read_bytes(), self.xconfig.read_bytes())
            result = self.merge(success=False)
            self.assertNotIn("secret", result.stderr)
            self.assertEqual(before, (self.ini.read_bytes(), self.xconfig.read_bytes()))

    def test_linked_settings_never_replaced(self):
        target = self.base / "managed.ini"
        target.write_text("[Settings]\ngtk-font-name=Managed 12\n")
        self.ini.symlink_to(target)
        self.merge(success=False)
        self.assertTrue(self.ini.is_symlink())
        self.assertIn("Managed 12", target.read_text())
        self.assertFalse(self.xconfig.exists())

    def test_prepare_failure_preserves_both_and_cleans_temps(self):
        self.ini.write_text("[Settings]\ngtk-font-name=Serif 11\n")
        self.xconfig.write_text("# unchanged\n")
        before = (self.ini.read_bytes(), self.xconfig.read_bytes())
        self.merge(prefix="import os\n"
                   "_fsync = os.fsync\n_count = 0\n"
                   "def _fail_second(fd):\n"
                   "    global _count\n    _count += 1\n"
                   "    if _count == 2: raise OSError('fixture disk full')\n"
                   "    return _fsync(fd)\nos.fsync = _fail_second\n", success=False)
        self.assertEqual(before, (self.ini.read_bytes(), self.xconfig.read_bytes()))


if __name__ == "__main__":
    unittest.main()
