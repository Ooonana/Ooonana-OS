#!/usr/bin/env python3
"""Pinned Qt portal cache invalidation; no app/WM/stylesheet replacement."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEFORE = "                colorScheme = colorSchemeFromXdgPref(static_cast<XdgColorschemePref>(value.variant().toUInt()));\n                QWindowSystemInterface::handleThemeChange();"
AFTER = BEFORE.replace("                QWindowSystemInterface", "                baseTheme->requestColorScheme(colorScheme);\n                QWindowSystemInterface")


def patch(source):
    pins = json.loads((ROOT / "packages/qt-portal/source-pins.json").read_text())
    if any(path.name not in set(pins["files"]) | {"CMakeLists.txt"} or path.is_symlink()
           for path in source.iterdir()):
        raise ValueError("Unpinned or linked Qt build input")
    for name, expected in pins["files"].items():
        path = source / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Pinned Qt source mismatch: " + name)
    path = source / "qxdgdesktopportaltheme.cpp"
    text = path.read_text()
    if text.count(BEFORE) != 1:
        raise ValueError("Qt portal update anchor changed")
    updated = text.replace(BEFORE, AFTER)
    assert updated.replace(AFTER, BEFORE) == text
    path.write_text(updated)
    print("QT_PORTAL_SOURCE_OK one cache invalidation; remaining vendor source unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    patch(parser.parse_args().source)
