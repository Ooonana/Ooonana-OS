#!/usr/bin/env python3
"""Default input setup must never replace user profiles or alternate IMEs."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"packages/ooonana/usr/lib/ooonana"))
import input_method as ime


class InputDefaults(unittest.TestCase):
    def test_running_service_with_no_focused_field_is_reused(self):
        with patch.object(ime, 'ensure_profile'), patch.object(ime.subprocess, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout='0\n', stderr='')
            self.assertEqual(ime.start(), 0)
            self.assertFalse(any(call.args[0][0] == 'fcitx5' for call in run.call_args_list))

    def test_start_waits_for_nonactivating_service_readiness(self):
        results = [subprocess.CompletedProcess([], 1, stdout='', stderr=''),
                   subprocess.CompletedProcess([], 0),
                   subprocess.CompletedProcess([], 0, stdout='1\n', stderr='')]
        with patch.object(ime, 'ensure_profile'), patch.object(ime.subprocess, 'run', side_effect=results) as run:
            self.assertEqual(ime.start(), 0)
            self.assertIn('--disable=clipboard', run.call_args_list[1].args[0])
            self.assertIn('--check', run.call_args_list[0].args[0])
            self.assertIn('--check', run.call_args_list[2].args[0])

    def test_fork_success_without_service_is_not_reported_ready(self):
        with patch.object(ime, 'ensure_profile'), patch.object(ime.subprocess, 'run') as run, \
                patch.object(ime.time, 'monotonic', side_effect=[0, 0, 10]), patch.object(ime.time, 'sleep'):
            run.side_effect = lambda args, **kw: subprocess.CompletedProcess(args, 0 if args[0] == 'fcitx5' else 1, stdout='', stderr='')
            with self.assertRaisesRegex(OSError, 'ready'):
                ime.start()

    def test_explicit_alternate_provider_is_respected(self):
        self.assertTrue(ime.selected({}))
        self.assertTrue(ime.selected({"GTK_IM_MODULE": "fcitx"}))
        for values in ({"GTK_IM_MODULE": "ibus"}, {"QT_IM_MODULE": "compose"}, {"XMODIFIERS": "@im=ibus"}):
            self.assertFalse(ime.selected(values))

    def test_atomic_no_clobber_and_profile_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/"default"
            data = b"[Groups/0]\nName=Korean test\n"
            source.write_bytes(data)
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda _: ime.ensure_profile(root/"config", source), range(16)))
            self.assertEqual(sum(results), 1)
            profile = root/"config/fcitx5/profile"
            self.assertEqual(profile.read_bytes(), data)
            self.assertEqual(profile.stat().st_mode & 0o777, 0o600)
            profile.write_text("custom keyboard and shortcuts\n")
            self.assertFalse(ime.ensure_profile(root/"config", source))
            self.assertEqual(profile.read_text(), "custom keyboard and shortcuts\n")
            self.assertEqual(list(profile.parent.glob(".profile-*")), [])

    def test_existing_profile_links_are_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); parent = root/"config/fcitx5"; parent.mkdir(parents=True)
            target = root/"user-profile"; target.write_text("keep user profile")
            profile = parent/"profile"; profile.symlink_to(target)
            self.assertFalse(ime.ensure_profile(root/"config", root/"missing-default"))
            self.assertTrue(profile.is_symlink())
            self.assertEqual(target.read_text(), "keep user profile")


if __name__ == "__main__":
    unittest.main()
