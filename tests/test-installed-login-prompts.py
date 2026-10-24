#!/usr/bin/env python3
"""Serial login prompt guards without QEMU, credentials or runtime dependencies."""
import ast
from pathlib import Path
import re
import unittest

source = Path(__file__).with_name("test-installed-login.py")
function = next(node for node in ast.parse(source.read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name == "login_prompt")
namespace = {"re": re}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
login_prompt = namespace["login_prompt"]


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


if __name__ == "__main__":
    unittest.main()
