#!/usr/bin/env python3
"""Pure installed-GRUB writer tests; no installer, mount, disk or reboot calls."""
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "packages/ooonana/usr/sbin/ooonana-install").read_text()


def function(name):
    starts = list(re.finditer(r"^\w+\(\) \{", SOURCE, re.MULTILINE))
    index = next(i for i, match in enumerate(starts) if match.group() == name + "() {")
    return SOURCE[starts[index].start():starts[index + 1].start()]


class InstalledGrub(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ooonana-grub-writer-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.assets = self.root / "usr/share/ooonana"
        self.assets.mkdir(parents=True)
        for name in ("grub.theme", "grub-logo.txt"):
            (self.assets / name).write_bytes((ROOT / "packages/ooonana/usr/share/ooonana" / name).read_bytes())
        for source, name in (("boot-mark.png", "boot-mark.png"), ("grub-background.png", "grub-background.png")):
            (self.assets / name).write_bytes((ROOT / "branding" / source).read_bytes())
        self.font = self.root / "usr/share/grub/unicode.pf2"
        self.font.parent.mkdir()
        self.font.write_bytes(b"fixture font; never loaded or booted")

    def write(self):
        # Only these two pure functions execute. Every install destination is
        # under this test's new temporary root. Full installer never runs.
        script = 'set -eu\nSMOKE=0; GUI_SMOKE=0\nrun_cmd() { "$@"; }\n'
        script += function("kernel_append") + function("write_grub_config")
        script += "write_grub_config " + shlex.quote(str(self.root)) + " PARTUUID=FIXTURE_NEVER_BOOT\n"
        result = subprocess.run(["bash", "-c", script], text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return (self.root / "boot/grub/grub.cfg").read_text()

    def test_complete_target_uses_shared_theme_and_copies_target_font(self):
        config = self.write()
        self.assertIn("set ooonana_theme_ready=1", config)
        self.assertEqual((self.root / "boot/grub/theme.txt").read_bytes(), (self.assets / "grub.theme").read_bytes())
        self.assertEqual((self.root / "boot/grub/fonts/ooonana.pf2").read_bytes(), self.font.read_bytes())
        self.assertEqual((self.root / "boot/grub/boot-mark.png").read_bytes(), (ROOT / "branding/boot-mark.png").read_bytes())
        self.assertIn('if [ "$ooonana_theme_ready" = 1 ]; then', config)
        self.assertLess(config.index("if loadfont"), config.index("set theme=/boot/grub/theme.txt"))
        self.assertIn('if [ -z "$theme" ]; then', config)

    def test_missing_assets_keep_console_and_serial_fallback(self):
        for missing in (self.font, self.assets / "boot-mark.png", self.assets / "grub.theme"):
            with self.subTest(missing=missing.name):
                original = missing.read_bytes()
                missing.unlink()
                try:
                    config = self.write()
                    self.assertIn("set ooonana_theme_ready=0", config)
                    self.assertIn("terminal_input console serial", config)
                    self.assertIn("terminal_output console serial", config)
                    self.assertIn("set color_normal=yellow/black", config)
                    self.assertFalse((self.root / "boot/grub/theme.txt").exists())
                finally:
                    missing.write_bytes(original)

    def test_existing_boot_font_is_preserved(self):
        boot_font = self.root / "boot/grub/fonts/unicode.pf2"
        boot_font.parent.mkdir(parents=True)
        boot_font.write_bytes(b"existing target font")
        before = boot_font.stat().st_mtime_ns
        self.write()
        self.assertEqual(boot_font.read_bytes(), b"existing target font")
        self.assertEqual(boot_font.stat().st_mtime_ns, before)
        self.assertEqual((self.root / "boot/grub/fonts/ooonana.pf2").read_bytes(), self.font.read_bytes())

    def test_boot_arguments_and_default_remain_unchanged(self):
        config = self.write()
        expected = "root=PARTUUID=FIXTURE_NEVER_BOOT rw console=ttyS0 console=tty0 panic=1 init=/sbin/init ooonana.edition=full-i3"
        self.assertEqual(config.count("linux /boot/vmlinuz " + expected), 3)
        self.assertIn("snd_intel_dspcfg.dsp_driver=3", config)
        self.assertIn("snd_intel_dspcfg.dsp_driver=1", config)
        self.assertIn("set timeout=5\nset default=0", config)


if __name__ == "__main__":
    unittest.main()
