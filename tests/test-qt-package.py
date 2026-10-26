#!/usr/bin/env python3
"""Qt packaging: pinned inputs, reproducibility and refusal before publication."""
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
spec = importlib.util.spec_from_file_location("qt_package", ROOT / "scripts/build-qt-portal-package.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
release = module.release
digest = lambda data: hashlib.sha256(data).hexdigest()


class QtPackage(unittest.TestCase):
    def fixture(self, root):
        base, source, out = (root / name for name in ("base", "source", "out"))
        for path in (base / "archives", source, out): path.mkdir(parents=True)
        inputs = {}
        for name in release.QT_INPUTS:
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("build input " + name); inputs[name] = digest(path.read_bytes())
        pins = {"files": {"vendor.cpp": digest(b"original source")}, "original_plugin_sha256": digest(b"vendor plugin")}
        (root / "scripts/build-qt-portal-package.py").write_bytes((ROOT / "scripts/build-qt-portal-package.py").read_bytes())
        path = root / "packages/qt-portal/source-pins.json"; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(pins)); (source / "vendor.cpp").write_bytes(b"original source")
        binary = root / "native.so"
        data = bytearray(64); data[:6] = b"\x7fELF\x02\x01"; data[16:20] = b"\x03\0\x3e\0"
        binary.write_bytes(data)
        manifest = {"component": "qt-portal-live-palette-v1", "source": pins, "compile_network": "disabled",
                    "binary_sha256": digest(data), "inputs": inputs}
        (root / "build-manifest.json").write_text(json.dumps(manifest))
        archive = base / "archives/vendor.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            item = tarfile.TarInfo(release.QT_PLUGIN); item.size = len(b"vendor plugin")
            bundle.addfile(item, io.BytesIO(b"vendor plugin"))
            item = tarfile.TarInfo("usr/share/vendor-retained"); item.size = 4
            bundle.addfile(item, io.BytesIO(b"keep"))
        upstream = digest(archive.read_bytes())
        package = {"ID": "qt6-qtbase-x11", "SUMMARY": "Qt QA", "VERSION": "6.11.1-r0", "BASE": "alpine-v3.24", "SHA256": upstream,
                   "ARCHIVE": "archives/vendor.tar.gz", "DEPS": "qt6-qtbase qt6-qtbase-wayland", "KIND": "apk"}
        (base / "qt6-qtbase-x11.pkg").write_text("".join(f"OOONANA_PKG_{k}={json.dumps(v)}\n" for k, v in package.items()))
        return base, binary, source, out, upstream

    def build(self, root, values):
        with patch.object(module, "ROOT", root), patch.object(release, "ROOT", root), \
                patch.object(release, "QT_UPSTREAM_SHA", values[4]), \
                patch.object(module.subprocess, "check_output", return_value="libQt6Gui.so.6 libQt6DBus.so.6"):
            module.build(*values[:4])

    def test_reproducible_retains_dependencies_and_vendor_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); values = self.fixture(root); self.build(root, values)
            package = release.metadata(values[3] / "qt6-qtbase-x11.pkg")
            original = (values[3] / package["ARCHIVE"]).read_bytes()
            self.assertEqual(package["DEPS"], "qt6-qtbase qt6-qtbase-wayland")
            with tarfile.open(values[3] / package["ARCHIVE"]) as bundle:
                self.assertEqual(bundle.extractfile("usr/share/vendor-retained").read(), b"keep")
            with self.assertRaisesRegex(ValueError, "existing package"): self.build(root, values)
            second = root / "second"; second.mkdir()
            self.build(root, (*values[:3], second, values[4]))
            self.assertEqual(original, (second / package["ARCHIVE"]).read_bytes())

    def test_source_and_manifest_tamper_refuse_without_output(self):
        for field in ("source", "binary", "inputs", "network", "upstream"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); values = self.fixture(root)
                if field == "source": (values[2] / "vendor.cpp").write_text("changed")
                elif field == "binary": values[1].write_bytes(b"not native")
                elif field == "inputs": (root / release.QT_INPUTS[0]).write_text("changed")
                elif field == "network":
                    path = root / "build-manifest.json"; data = json.loads(path.read_text()); data["compile_network"] = "enabled"; path.write_text(json.dumps(data))
                else: (values[0] / "archives/vendor.tar.gz").write_bytes(b"changed")
                with self.assertRaises(ValueError): self.build(root, values)
                self.assertFalse((values[3] / "qt6-qtbase-x11.pkg").exists())
                self.assertEqual(list(values[3].iterdir()), [])

    def test_publication_output_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); values = self.fixture(root)
            (values[3] / "CURRENT").write_text("existing")
            with self.assertRaisesRegex(ValueError, "unpublished"): self.build(root, values)
            self.assertEqual((values[3] / "CURRENT").read_text(), "existing")


if __name__ == "__main__": unittest.main()
