#!/usr/bin/env python3
from pathlib import Path
import hashlib
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
icons = root / "packages/ooonana/usr/share/icons/hicolor/scalable/apps"
digests = set()
for path in icons.glob("ooonana-*.svg"):
    svg = ET.parse(path).getroot()
    assert svg.attrib["viewBox"] == "0 0 64 64"
    text = path.read_text()
    assert "gradient" not in text and "filter=" not in text
    digests.add(hashlib.sha256(path.read_bytes()).hexdigest())
assert len(digests) == 19
for directory in (root / "packages/ooonana/usr/share/applications", root / "packages/openvino-chat/rootfs/usr/share/applications"):
    for desktop in directory.glob("*.desktop"):
        icon = next(line.split("=", 1)[1] for line in desktop.read_text().splitlines() if line.startswith("Icon="))
        assert icon.startswith("ooonana-") and (icons / f"{icon}.svg").is_file(), (desktop, icon)
print("ok native-icons")
