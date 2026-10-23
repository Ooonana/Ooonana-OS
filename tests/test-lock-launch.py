#!/usr/bin/env python3
"""Lock launch arguments/failure paths only; never grabs real display."""
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana"))
import lock_screen


class LockLaunch(unittest.TestCase):
    def test_saved_appearance_and_real_feedback_flags(self):
        with tempfile.TemporaryDirectory(prefix="ooonana-lock-launch-") as temporary:
            preference = Path(temporary) / "ooonana/theme"
            preference.parent.mkdir()
            for theme, color in (("dark", "101317"), ("light", "f5f5f7")):
                preference.write_text(theme + "\n")
                with patch.dict(os.environ, {"XDG_CONFIG_HOME": temporary, "OOONANA_THEME": "dark", "OOONANA_THEME_INHERITED": "dark"}, clear=True):
                    command = lock_screen.command()
                self.assertEqual(command, ["i3lock", "--color", color, "--show-keyboard-layout", "--show-failed-attempts"])
                self.assertNotIn("--debug", command)
                self.assertNotIn("--beep", command)
                self.assertNotIn("--ignore-empty-password", command)
                self.assertNotIn("--no-unlock-indicator", command)

    def test_direct_exec_preserves_locker_exit_and_grab_contract(self):
        with patch.object(sys, "argv", ["ooonana-lock"]), patch.object(lock_screen.os, "execvp") as execute:
            lock_screen.main()
            self.assertEqual(execute.call_args.args, ("i3lock", lock_screen.command()))

    def test_missing_backend_and_debug_injection_fail_without_blanking(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            with patch.object(sys, "argv", ["ooonana-lock", "--debug"]), patch.object(lock_screen.os, "execvp") as execute:
                self.assertEqual(lock_screen.main(), 2)
                execute.assert_not_called()
            with patch.object(sys, "argv", ["ooonana-lock"]), patch.object(lock_screen.os, "execvp", side_effect=FileNotFoundError):
                self.assertEqual(lock_screen.main(), 127)
        self.assertIn("has not been secured", errors.getvalue())

    def test_all_owned_actions_share_launcher(self):
        builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
        controls = (ROOT / "packages/ooonana/usr/lib/ooonana/ui/controls_app.py").read_text()
        self.assertIn('Lock) exec ooonana-lock ;;', builder)
        self.assertIn('click-right = ooonana-lock', builder)
        self.assertIn('self.request(["ooonana-lock"], "Lock")', controls)


if __name__ == "__main__":
    unittest.main()
