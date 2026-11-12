#!/usr/bin/env python3
"""Private shell/PTY tests. Never execute installer or host power commands."""
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import termios
import time
import unittest

BUILDER = (Path(__file__).resolve().parents[1] / "scripts/build-full-i3-rootfs.sh").read_text()
WIZARD = BUILDER.split('"$ROOTFS/usr/bin/ooonana-install-wizard" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]


def function(name):
    return name + "() {" + WIZARD.split(name + "() {", 1)[1].split("\n}\n", 1)[0] + "\n}\n"


class WizardInput(unittest.TestCase):
    def test_hidden_pipe_preserves_spaces_without_extra_newline(self):
        result = subprocess.run(["sh", "-c", function("read_hidden") +
                                 'password="$(read_hidden "Fixture password: ")" || exit $?\nprintf %s "$password"'],
                                input=" fixture|password \\ ", text=True,
                                capture_output=True, timeout=4)
        # A terminal entry is one newline-terminated line.
        self.assertNotEqual(result.returncode, 0)
        result = subprocess.run(["sh", "-c", function("read_hidden") +
                                 'password="$(read_hidden "Fixture password: ")"\nprintf %s "$password"'],
                                input=" fixture|password \\ \n", text=True,
                                capture_output=True, timeout=4)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, " fixture|password \\ ")
        self.assertNotIn("fixture|password", result.stderr)

    def test_hidden_pty_backspace_and_echo_restore(self):
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        original = termios.tcgetattr(slave)
        process = subprocess.Popen(["sh", "-c", function("read_hidden") +
                                    'password="$(read_hidden "Fixture password: ")"\nprintf %s "$password"'],
                                   stdin=slave, stderr=slave, stdout=subprocess.PIPE)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        deadline = time.monotonic() + 4
        while termios.tcgetattr(slave)[3] & termios.ECHO:
            self.assertIsNone(process.poll())
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.01)
        os.write(master, b" fixture-z\x7fx \n")
        stdout, _ = process.communicate(timeout=4)
        self.assertEqual(stdout, b" fixture-x ")
        self.assertEqual(termios.tcgetattr(slave), original)
        terminal = b""
        while select.select([master], [], [], .05)[0]:
            terminal += os.read(master, 4096)
        self.assertNotIn(b"fixture-x", terminal)

    def test_hidden_pty_interruption_restores_echo(self):
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        original = termios.tcgetattr(slave)
        process = subprocess.Popen(["sh", "-c", function("read_hidden") +
                                    'password="$(read_hidden "Fixture password: ")"'],
                                   stdin=slave, stderr=slave, stdout=subprocess.PIPE,
                                   start_new_session=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        deadline = time.monotonic() + 4
        while termios.tcgetattr(slave)[3] & termios.ECHO:
            self.assertIsNone(process.poll())
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.01)
        # Only this explicitly created child session receives the signal.
        os.killpg(process.pid, signal.SIGTERM)
        process.communicate(timeout=4)
        while termios.tcgetattr(slave) != original:
            self.assertLess(time.monotonic(), deadline, "TTY state not restored after interruption")
            time.sleep(.01)


class WizardCompletion(unittest.TestCase):
    def invoke(self, text, fail=False):
        # All possible legacy/current power commands are shell mocks. No host
        # command can be reached even while reproducing the original defect.
        mocks = """sync() { :; }
reboot() { printf 'FORBIDDEN forced reboot\\n'; return 1; }
poweroff() { printf 'FORBIDDEN forced poweroff\\n'; return 1; }
bunana() { printf 'ORDERLY %s\\n' "$*"; return "$failure"; }
"""
        return subprocess.run(["sh", "-c", mocks + function("finish_prompt") +
                               f"YES=0; failure={int(fail)}; finish_prompt"],
                              input=text, text=True, capture_output=True, timeout=4)

    def test_eof_never_reboots(self):
        result = self.invoke("")
        self.assertNotIn("ORDERLY", result.stdout)
        self.assertNotIn("FORBIDDEN", result.stdout)

    def test_stay_and_unknown_never_reboot(self):
        for answer in ("stay\n", "shell\n", "no\n", "typo\n"):
            with self.subTest(answer=answer):
                result = self.invoke(answer)
                self.assertNotIn("ORDERLY", result.stdout)
                self.assertNotIn("FORBIDDEN", result.stdout)

    def test_enter_uses_orderly_reboot_only(self):
        result = self.invoke("\n")
        self.assertEqual(result.returncode, 0)
        self.assertIn("ORDERLY --restart", result.stdout)
        self.assertNotIn("FORBIDDEN", result.stdout)

    def test_failed_reboot_is_reported_without_force_or_poweroff(self):
        result = self.invoke("\n", fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("FORBIDDEN", result.stdout)
        self.assertIn("failed", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
