#!/usr/bin/env python3
"""Run actual session prefix only: no display, bus, audio or system writes."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text(encoding="utf-8")
session = builder.split('"$ROOTFS/usr/bin/ooonana-i3-session" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
# Stop before bus, theme, state directories or child daemons. No --user argument
# means the account migration/authority-copy branch cannot run in this fixture.
prefix = session.split("\nexport XDG_CURRENT_DESKTOP=", 1)[0]


class SessionDirectory(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ooonana-session-cwd-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.launch = self.base / "Launch folder"
        self.launch.mkdir()

    def execute(self, home):
        environment = {**os.environ, "CDPATH": str(self.launch)}
        if home is None:
            environment.pop("HOME", None)
        else:
            environment["HOME"] = str(home)
        return subprocess.run(["/bin/sh", "-c", prefix + '\nprintf "%s\\n%s\\n" "$PWD" "$HOME"\n'],
                              cwd=self.launch, env=environment, capture_output=True, text=True, timeout=5)

    def test_home_not_inherited_launch_directory(self):
        for name in ("Home", "Home 한글 with spaces", "Home ; literal $(not-a-command)"):
            with self.subTest(name=name):
                home = self.base / name
                home.mkdir()
                result = self.execute(home)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), [str(home), str(home)])
                self.assertEqual(result.stderr, "")

    def test_unavailable_home_refuses_before_startup(self):
        regular_file = self.base / "Not a directory"
        regular_file.write_text("Owned fixture only\n", encoding="utf-8")
        for home in (None, "", self.base / "Missing", regular_file):
            with self.subTest(home=home):
                result = self.execute(home)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("desktop home unavailable", result.stderr)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
