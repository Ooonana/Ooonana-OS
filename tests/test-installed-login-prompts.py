#!/usr/bin/env python3
"""Login prompt and graphical sign-in configuration checks without QEMU."""
import ast
import configparser
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

source = Path(__file__).with_name("test-installed-login.py")
function = next(node for node in ast.parse(source.read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name == "login_prompt")
namespace = {"re": re}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
login_prompt = namespace["login_prompt"]
overlay = source.parent.parent / "packages/ooonana"


class LoginPrompts(unittest.TestCase):
    def test_complete_prompts(self):
        for prefix in (b"", b"banner\n", b"banner\r", b"banner\r\n"):
            for hostname in (b"(none)", b"ooonana", b"host.example"):
                with self.subTest(prefix=prefix, hostname=hostname):
                    self.assertTrue(login_prompt(prefix + hostname + b" login: "))

    def test_pam_and_syslog_are_not_prompts(self):
        for transcript in (
            b"pam_unix(login:session): session closed for user fixture\r\n",
            b"pam_unix(login:auth): authentication failure\n",
            b"Oct 24 14:38:48 (none) daemon.info login: session closed\r\n",
            b"init: process '/usr/bin/login-fixture-getty' exited\r\n",
        ):
            with self.subTest(transcript=transcript):
                self.assertFalse(login_prompt(transcript))

    def test_fragments_do_not_release_input(self):
        transcript = bytearray(b"pam_unix(login:session): session closed\r\n")
        prompt = b"(none) login: "
        for value in prompt[:-1]:
            transcript.append(value)
            self.assertFalse(login_prompt(transcript))
        transcript.append(prompt[-1])
        self.assertTrue(login_prompt(transcript))


class GraphicalSignIn(unittest.TestCase):
    def test_local_password_authenticated_session(self):
        config = configparser.ConfigParser(interpolation=None)
        config.read(overlay / "etc/lightdm/lightdm.conf.d/90-ooonana.conf")
        seat = config["Seat:*"]
        policy = overlay / "etc/pam.d" / seat["pam-service"]
        rules = [line.split() for line in policy.read_text().splitlines() if line and not line.startswith("#")]
        for phase in ("auth", "account", "password", "session"):
            self.assertIn([phase, "include", "login"], rules)
        self.assertIn(["auth", "requisite", "pam_succeed_if.so", "uid", ">=", "1000", "quiet"], rules)
        self.assertFalse(seat.getboolean("allow-guest"))
        self.assertFalse(seat.getboolean("autologin-guest"))
        self.assertFalse(seat["autologin-user"])
        self.assertFalse(seat.getboolean("xserver-allow-tcp"))
        self.assertFalse(config["XDMCPServer"].getboolean("enabled"))
        self.assertFalse(config["VNCServer"].getboolean("enabled"))
        session = overlay / "usr/share/xsessions" / (seat["user-session"] + ".desktop")
        self.assertIn("Exec=/usr/bin/ooonana-i3-session --user-session", session.read_text().splitlines())

    def test_installer_selects_graphical_login_and_preserves_console_choice(self):
        installer = (overlay / "usr/sbin/ooonana-install").read_text()
        definitions = installer.split('while [[ $# -gt 0 ]]', 1)[0]
        for account_step in ("create_user", "write_password", "write_hostname", "write_theme",
                             "write_cloud_repo", "lock_installed_root"):
            definitions += f"\n{account_step}() {{ :; }}\n"
        with tempfile.TemporaryDirectory(prefix="ooonana-login-mode-") as folder:
            for prior, expected in ((None, "graphical"), ("console", "console")):
                root = Path(folder) / expected
                (root / "etc/ooonana").mkdir(parents=True)
                mode = root / "etc/ooonana/login-mode"
                if prior:
                    mode.write_text(prior + "\n")
                result = subprocess.run(["bash", "-c", definitions + '\napply_install_config "$1"',
                                         "owned-login-fixture", str(root)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(mode.read_text().strip(), expected)
                self.assertIn("tty2::respawn:/bin/busybox getty 38400 tty2",
                              (root / "etc/inittab").read_text().splitlines())


if __name__ == "__main__":
    unittest.main()
