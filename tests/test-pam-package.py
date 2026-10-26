#!/usr/bin/env python3
"""PAM repair preserves authentication bytes/policy and refuses unknown layouts."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pam_package", ROOT / "scripts/build-pam-helper-package.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class PamPackage(unittest.TestCase):
    def fixture(self, root, mode=0o2755):
        base = root / "base"; base.mkdir(); out = root / "out"; out.mkdir()
        archive = base / "pam.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for name, data in ((module.HELPER, b"unchanged helper"), ("usr/lib/pam.d/base-auth", b"unchanged policy")):
                item = tarfile.TarInfo(name); item.mode = mode if name == module.HELPER else 0o644; item.size = len(data)
                bundle.addfile(item, io.BytesIO(data))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        values = {"ID": "linux-pam", "VERSION": "1.7.1-r2", "BASE": "alpine-v3.24", "SUMMARY": "PAM QA",
                  "DEPS": "musl utmps-libs", "SHA256": digest, "ARCHIVE": archive.name}
        (base / "linux-pam.pkg").write_text("".join(f"OOONANA_PKG_{k}={json.dumps(v)}\n" for k, v in values.items()))
        return base, out, digest

    def test_authentication_bytes_policy_and_dependencies_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            base, out, digest = self.fixture(Path(directory))
            with patch.object(module, "UPSTREAM_SHA", digest): module.build(base, out)
            package = module.release.metadata(out / "linux-pam.pkg")
            self.assertEqual(package["DEPS"], "musl utmps-libs")
            with tarfile.open(base / "pam.tar.gz") as original, tarfile.open(out / package["ARCHIVE"]) as updated:
                for member in original:
                    value = updated.getmember(member.name)
                    self.assertEqual(original.extractfile(member).read(), updated.extractfile(value).read())
                    self.assertEqual(value.mode, 0o4755 if member.name == module.HELPER else member.mode)
                    self.assertEqual((member.uid, member.gid), (value.uid, value.gid))
            with patch.object(module, "UPSTREAM_SHA", digest), self.assertRaisesRegex(ValueError, "existing"):
                module.build(base, out)

    def test_unknown_mode_and_damaged_archive_refuse(self):
        for mode in (0o755, 0o4755):
            with tempfile.TemporaryDirectory() as directory:
                base, out, digest = self.fixture(Path(directory), mode)
                with patch.object(module, "UPSTREAM_SHA", digest), self.assertRaisesRegex(ValueError, "known root-owned"):
                    module.build(base, out)
                self.assertEqual(list(out.iterdir()), [])
        with tempfile.TemporaryDirectory() as directory:
            base, out, digest = self.fixture(Path(directory)); (base / "pam.tar.gz").write_bytes(b"changed")
            with patch.object(module, "UPSTREAM_SHA", digest), self.assertRaisesRegex(ValueError, "checksum"):
                module.build(base, out)
            self.assertEqual(list(out.iterdir()), [])


if __name__ == "__main__": unittest.main()
