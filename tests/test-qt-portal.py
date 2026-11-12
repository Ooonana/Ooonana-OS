#!/usr/bin/env python3
"""Pinned one-line palette fix is reversible; late source mismatch writes nothing."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("qt_portal_patch", ROOT / "scripts/patch-qt-portal.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class QtPortalPatch(unittest.TestCase):
    def fixture(self, root):
        source = root / "source"; source.mkdir()
        values = {"qxdgdesktopportaltheme.cpp": "before\n" + module.BEFORE + "\nafter\n", "last.h": "unchanged header\n"}
        for name, text in values.items(): (source / name).write_text(text)
        pins = root / "packages/qt-portal/source-pins.json"; pins.parent.mkdir(parents=True)
        pins.write_text(json.dumps({"files": {name: hashlib.sha256(text.encode()).hexdigest() for name, text in values.items()}}))
        return source, values

    def test_only_palette_cache_invalidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source, before = self.fixture(root)
            with patch.object(module, "ROOT", root):
                module.patch(source)
                self.assertEqual((source / "qxdgdesktopportaltheme.cpp").read_text().replace(module.AFTER, module.BEFORE), before["qxdgdesktopportaltheme.cpp"])
                self.assertEqual((source / "last.h").read_text(), before["last.h"])
                with self.assertRaises(ValueError): module.patch(source)
        self.assertEqual(module.AFTER.replace(module.BEFORE.splitlines()[0], "").count("baseTheme->requestColorScheme(colorScheme);"), 1)

    def test_late_hash_mismatch_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source, before = self.fixture(root)
            (source / "last.h").write_text("changed\n")
            with patch.object(module, "ROOT", root), self.assertRaises(ValueError): module.patch(source)
            self.assertEqual((source / "qxdgdesktopportaltheme.cpp").read_text(), before["qxdgdesktopportaltheme.cpp"])

    def test_unpinned_local_moc_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source, before = self.fixture(root)
            (source / "main.moc").write_text("unexpected input")
            with patch.object(module, "ROOT", root), self.assertRaises(ValueError): module.patch(source)
            self.assertEqual((source / "qxdgdesktopportaltheme.cpp").read_text(), before["qxdgdesktopportaltheme.cpp"])


if __name__ == "__main__": unittest.main()
