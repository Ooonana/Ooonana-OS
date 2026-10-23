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
import lock_readiness


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
        with patch.object(lock_screen, "live_account_status", return_value=0), patch.object(sys, "argv", ["ooonana-lock"]), patch.object(lock_screen.os, "execvpe") as execute:
            lock_screen.main()
            self.assertEqual(execute.call_args.args[:2], ("i3lock", lock_screen.command()))
            self.assertEqual(execute.call_args.args[2]["OOONANA_LOCK_VISUALS"], "1")

    def test_missing_backend_and_debug_injection_fail_without_blanking(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            with patch.object(sys, "argv", ["ooonana-lock", "--debug"]), patch.object(lock_screen.os, "execvpe") as execute:
                self.assertEqual(lock_screen.main(), 2)
                execute.assert_not_called()
            with patch.object(lock_screen, "live_account_status", return_value=0), patch.object(sys, "argv", ["ooonana-lock"]), patch.object(lock_screen.os, "execvpe", side_effect=FileNotFoundError):
                self.assertEqual(lock_screen.main(), 127)
        self.assertIn("has not been secured", errors.getvalue())

    def test_live_locked_empty_unknown_refuse_before_any_grab(self):
        with tempfile.TemporaryDirectory(prefix="ooonana-lock-status-") as temporary:
            shadow = Path(temporary) / "shadow"
            for secret, expected in (("!", 3), ("*", 3), ("", 3), ("!$6$locked", 3), ("$6$fixture$hash", 0)):
                shadow.write_text(f"ooonana:{secret}:20000:0:99999:7:::\n")
                self.assertEqual(lock_readiness.account_status(shadow, "ooonana"), expected)
            shadow.write_text("bad data\n")
            self.assertEqual(lock_readiness.account_status(shadow, "ooonana"), 4)
            shadow.write_text("ooonana:$6$a:20000:0:99999:7:::\n" * 2)
            self.assertEqual(lock_readiness.account_status(shadow, "ooonana"), 4)
            link = shadow.with_name("link"); link.symlink_to(shadow)
            self.assertEqual(lock_readiness.account_status(link, "ooonana"), 4)
        for status in (3, 4):
            with patch.object(lock_screen, "live_account_status", return_value=status), patch.object(sys, "argv", ["ooonana-lock"]), \
                    patch.object(lock_screen.os, "execvpe") as execute, patch.object(lock_screen.subprocess, "run"), \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(lock_screen.main(), 1)
                execute.assert_not_called()
                self.assertIn("has not been secured", errors.getvalue())

    def test_noninteractive_live_authority_and_installed_custom_pam(self):
        from types import SimpleNamespace
        with patch.object(lock_screen.Path, "read_text", return_value="installed\n"), patch.object(lock_screen.subprocess, "run") as run:
            self.assertEqual(lock_screen.live_account_status(), 0)
            run.assert_not_called()
        with patch.object(lock_screen.Path, "read_text", side_effect=FileNotFoundError), patch.object(lock_screen.os, "getuid", return_value=1000), \
                patch.object(lock_screen.subprocess, "run", return_value=SimpleNamespace(returncode=3)) as run:
            self.assertEqual(lock_screen.live_account_status(), 3)
            self.assertEqual(run.call_args.args[0], ["sudo", "-n", "--", "/usr/bin/python3", "-I", "/usr/lib/ooonana/lock_readiness.py", "1000"])
        with patch.object(lock_screen.Path, "read_text", side_effect=FileNotFoundError), patch.object(lock_screen.os, "getuid", return_value=1000), \
                patch.object(lock_screen.subprocess, "run", side_effect=PermissionError):
            self.assertEqual(lock_screen.live_account_status(), 4)

    def test_all_owned_actions_share_launcher(self):
        builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
        controls = (ROOT / "packages/ooonana/usr/lib/ooonana/ui/controls_app.py").read_text()
        self.assertIn('Lock) exec ooonana-lock ;;', builder)
        self.assertIn('click-right = ooonana-lock', builder)
        self.assertIn('self.request(["ooonana-lock"], "Lock")', controls)


if __name__ == "__main__":
    unittest.main()
