#!/usr/bin/env python3
"""Boot mount policy with owned files and an inert mount command only."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstalledMountTests(unittest.TestCase):
    def run_policy(self, mode="installed", status=0, custom=None, fstab=True):
        with tempfile.TemporaryDirectory(prefix="ooonana-installed-mounts-") as directory:
            work = Path(directory)
            tools = work / "bin"
            tools.mkdir()
            files = {name: work / name for name in ("mode", "fstab", "log", "nologin", "calls")}
            files["mode"].write_text(mode)
            if fstab:
                files["fstab"].write_text("UUID=qa-only /home ext4 defaults 0 2\n")
            if custom is not None:
                files["nologin"].write_text(custom)
            mount = tools / "mount"
            mount.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\nexit "$MOUNT_RESULT"\n')
            mount.chmod(0o755)
            source = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
            body = source.split("start_installed_mounts() {", 1)[1].split("\n}\n", 1)[0]
            for original, key in (("/etc/ooonana/system-mode", "mode"),
                                  ("/etc/fstab", "fstab"),
                                  ("/var/log/ooonana-mounts.log", "log"),
                                  ("/run/nologin", "nologin")):
                body = body.replace(original, str(files[key]))
            result = subprocess.run(["sh", "-c", "start_installed_mounts() {" + body +
                                     "\n}\nstart_installed_mounts\n"], capture_output=True,
                env={**os.environ, "PATH": str(tools) + ":" + os.environ["PATH"],
                     "CALLS": str(files["calls"]), "MOUNT_RESULT": str(status)}, timeout=5)
            return result.returncode, {key: path.read_text() if path.exists() else None
                                       for key, path in files.items()}

    def test_live_boot_never_mounts_installed_storage(self):
        rc, files = self.run_policy(mode="live", status=32)
        self.assertEqual(rc, 0)
        self.assertIsNone(files["calls"])
        self.assertIsNone(files["nologin"])

    def test_installed_mounts_skip_network_and_preserve_admin_login_policy(self):
        rc, files = self.run_policy(custom="administrator maintenance")
        self.assertEqual(rc, 0)
        self.assertEqual(files["calls"], "-a -O no_netdev\n")
        self.assertEqual(files["nologin"], "administrator maintenance")

    def test_failed_or_timed_out_mount_blocks_login(self):
        for status in (32, 124):
            with self.subTest(status=status):
                rc, files = self.run_policy(status=status)
                self.assertEqual(rc, 1)
                self.assertIn("Configured storage failed", files["nologin"])

    def test_failed_mount_preserves_existing_nologin(self):
        rc, files = self.run_policy(status=32, custom="administrator maintenance")
        self.assertEqual(rc, 1)
        self.assertEqual(files["nologin"], "administrator maintenance")

    def test_missing_fstab_blocks_login_without_mounting(self):
        rc, files = self.run_policy(fstab=False)
        self.assertEqual(rc, 1)
        self.assertIsNone(files["calls"])
        self.assertIn("Configured storage failed", files["nologin"])

    def test_builder_retains_native_mount_tools_and_restores_init_links(self):
        with tempfile.TemporaryDirectory(prefix="ooonana-mount-links-") as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            for name in ("busybox", "mount", "umount"):
                path = root / "bin" / name
                path.write_text("owned native fixture " + name)
                path.chmod(0o755)
            source = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
            body = source.split("restore_busybox_init_links() {", 1)[1].split("\n}\n", 1)[0]
            subprocess.run(["bash", "-c", "restore_busybox_init_links() {" + body +
                            "\n}\nrestore_busybox_init_links\n"],
                           env={**os.environ, "ROOTFS": str(root)}, check=True)
            for name in ("mount", "umount"):
                self.assertFalse((root / "bin" / name).is_symlink())
                self.assertEqual((root / "bin" / name).read_text(), "owned native fixture " + name)
            self.assertTrue((root / "sbin/init").is_symlink())


if __name__ == "__main__":
    unittest.main()
