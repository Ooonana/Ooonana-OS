#!/usr/bin/env python3
"""Convert a user-owned Windows pointer for private WSL/ISO builds."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile


THEME = "WindowsCursorConceptPersonal"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--agreement", type=Path)
    parser.add_argument("--size", type=int, help="Preferred pointer size; adds a proportionally scaled frame.")
    args = parser.parse_args()
    if args.size is not None and not 16 <= args.size <= 96:
        parser.error("--size must be between 16 and 96")
    for command in ("convert", "xcursorgen"):
        if not shutil.which(command):
            raise SystemExit(f"Missing host tool: {command}")
    source = args.source.resolve()
    data = source.read_bytes()
    if len(data) < 6:
        raise SystemExit("Invalid CUR header.")
    reserved, kind, count = struct.unpack_from("<HHH", data)
    if reserved or kind != 2 or not 1 <= count <= 64 or len(data) < 6 + count * 16:
        raise SystemExit("Expected a Windows CUR file.")
    output = args.out_dir.resolve() / THEME
    repo_packages = Path(__file__).resolve().parents[1] / "packages"
    if output.is_relative_to(repo_packages):
        raise SystemExit("Personal cursor must stay outside tracked package sources.")
    frames = []
    for index in range(count):
        width, height, _colors, _reserved, xhot, yhot, length, offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + index * 16
        )
        width, height = width or 256, height or 256
        if width != height or xhot >= width or yhot >= height or offset + length > len(data):
            raise SystemExit(f"Invalid CUR frame {index}.")
        frames.append((index, width, xhot, yhot))
    (output / "cursors").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ooonana-personal-cursor-") as temporary:
        work = Path(temporary)
        config = []
        for index, size, xhot, yhot in frames:
            image = work / f"pointer-{size}.png"
            subprocess.run(["convert", f"{source}[{index}]", f"PNG32:{image}"], check=True)
            config.append(f"{size} {xhot} {yhot} {image}")
        if args.size is not None and args.size not in {frame[1] for frame in frames}:
            index, native_size, xhot, yhot = min(
                frames, key=lambda frame: (frame[1] < args.size, abs(frame[1] - args.size))
            )
            image = work / f"pointer-{args.size}.png"
            subprocess.run([
                "convert", f"{source}[{index}]", "-filter", "Lanczos",
                "-resize", f"{args.size}x{args.size}", f"PNG32:{image}",
            ], check=True)
            scaled_xhot = min(args.size - 1, round(xhot * args.size / native_size))
            scaled_yhot = min(args.size - 1, round(yhot * args.size / native_size))
            config.insert(0, f"{args.size} {scaled_xhot} {scaled_yhot} {image}")
        config_path = work / "cursor.in"
        config_path.write_text("\n".join(config) + "\n", encoding="utf-8")
        target = output / "cursors" / "left_ptr"
        subprocess.run(["xcursorgen", str(config_path), str(target)], check=True)
    for alias in ("default", "arrow", "top_left_arrow"):
        shutil.copyfile(target, output / "cursors" / alias)
    (output / "index.theme").write_text(
        "[Icon Theme]\nName=Windows Cursor Concept (personal conversion)\nInherits=Adwaita\n",
        encoding="utf-8",
    )
    (output / "README.txt").write_text(
        "Windows Cursor Concept by Jepri Creations\n"
        "https://www.deviantart.com/jepricreations\n"
        "Personal CUR-to-Xcursor conversion. Native frames preserved; smaller frames scaled proportionally.\n"
        "Do not distribute this theme or an ISO containing it.\n",
        encoding="utf-8",
    )
    if args.agreement:
        shutil.copyfile(args.agreement.resolve(), output / "Agreement.txt")
    preferred_size = args.size or min(frame[1] for frame in frames)
    (output / "cursor-size").write_text(f"{preferred_size}\n", encoding="utf-8")
    print(f"Personal cursor: {output}")
    print(f"Preferred size: {preferred_size}px")
    print("Native sizes/hotspots:", [(size, xhot, yhot) for _, size, xhot, yhot in frames])


if __name__ == "__main__":
    main()
