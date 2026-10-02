#!/usr/bin/env python3
"""Check compiled cursor sizes, dimensions, hotspots, and aliases."""

import argparse
from pathlib import Path
import struct


def frames(path):
    data = path.read_bytes()
    magic, header_size, _version, count = struct.unpack_from("<4sIII", data)
    assert magic == b"Xcur" and header_size >= 16
    result = {}
    for index in range(count):
        kind, size, offset = struct.unpack_from("<III", data, header_size + index * 12)
        if kind != 0xFFFD0002:
            continue
        _header, _kind, _size, _version, width, height, xhot, yhot, _delay = struct.unpack_from("<9I", data, offset)
        assert width == height == size
        assert xhot < width and yhot < height
        result[size] = (xhot, yhot)
    assert result
    for alias in ("default", "arrow", "top_left_arrow"):
        assert (path.parent / alias).read_bytes() == data
    return result


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--personal-dir", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
public = frames(root / "packages/ooonana/usr/share/icons/OoonanaTailless/cursors/left_ptr")
assert public[17] == (2, 2), public
assert "gtk-cursor-theme-size=17" in (root / "packages/ooonana/etc/gtk-3.0/settings.ini").read_text()
if args.personal_dir:
    personal = frames(args.personal_dir / "cursors/left_ptr")
    assert personal[19] == (2, 5), personal
    assert personal[32] == (3, 9), personal
    assert (args.personal_dir / "cursor-size").read_text().strip() == "19"
print("ok cursor-theme")
