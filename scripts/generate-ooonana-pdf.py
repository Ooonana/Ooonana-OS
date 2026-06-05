#!/usr/bin/env python3
"""Generate docs/ooonana.pdf without external PDF packages."""

from __future__ import annotations

import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "ooonana.pdf"
LOGO = ROOT / "docs" / "logo.txt"


def wrap_line(line: str, width: int = 86) -> list[str]:
    if not line:
        return [""]
    if line.startswith("      ") or line.startswith("     ") or line.startswith("   /") or line.startswith("  /"):
        return [line]
    return textwrap.wrap(line, width=width, replace_whitespace=False) or [""]


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def page_stream(lines: list[str]) -> str:
    body = ["BT", "/F1 10 Tf", "13 TL", "54 744 Td"]
    for line in lines:
        body.append(f"({pdf_escape(line)}) Tj")
        body.append("T*")
    body.append("ET")
    return "\n".join(body)


def paginate(lines: list[str], per_page: int = 52) -> list[list[str]]:
    pages: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        for wrapped in wrap_line(line):
            current.append(wrapped)
            if len(current) >= per_page:
                pages.append(current)
                current = []
    if current:
        pages.append(current)
    return pages


def build_lines() -> list[str]:
    logo = LOGO.read_text(encoding="utf-8").rstrip().splitlines()
    return [
        *logo,
        "",
        "Ooonana OS v1 field guide",
        "",
        "What it is",
        "Ooonana OS is a scratch-built Linux project with its own rootfs, boot flow, installer experiments, WSL export, and custom ooonana package manager.",
        "Debian or Ubuntu are host build tools only. Alpine APKs are imported into Ooonana .pkg repos; the target OS installs Ooonana packages, not live Alpine APKs.",
        "",
        "Editions",
        "minimal: BusyBox-style rootfs, kernel, GRUB disk, installer ISO, WSL rootfs, command line AI.",
        "full-i3: minimal plus i3, Xorg package set, wallpaper, logo assets, GUI installer wizard, AI desktop app, full WSL rootfs.",
        "",
        "Package install",
        "ooonana update",
        "ooonana search nano",
        "ooonana show nano",
        "ooonana get nano --dry-run",
        "ooonana get nano",
        "ooonana files nano",
        "ooonana verify nano",
        "ooonana upgrade",
        "ooonana remove nano",
        "ooonana purge nano",
        "ooonana fix nano --reinstall",
        "",
        "Cloud repo",
        "Default cloud path is GitHub Releases:",
        "ooonana-package-repo.tar.gz",
        "https://github.com/Ooonana/Ooonana-OS/releases/download/packages-latest/ooonana-package-repo.tar.gz",
        "A repo tarball contains index.tsv, SHA256SUMS, *.pkg files, and archives/. ooonana update extracts it into /var/cache/ooonana/repos/NAME.",
        "Private GitHub repos need OOONANA_REPO_TOKEN or OOONANA_GITHUB_TOKEN for release tarball sync.",
        "",
        "Installer",
        "Full-i3 live ISO boots i3 by default. The installer wizard has disk picker, user/password, hostname, theme picker, package repo picker, progress log, failure shell, and reboot prompt.",
        "",
        "First boot",
        "ooonana setup --first-boot --gui can create user, set password, write network config, choose theme, add cloud repo, and mark setup complete.",
        "",
        "WSL",
        "Import full-i3 with scripts/install-wsl-distro.sh --distro Ooonana --tarball /var/tmp/ooonana-os/release/ooonana-full-i3-wsl-rootfs.tar.gz --force",
        "Launch with: wsl.exe -d Ooonana -- /usr/bin/start-ooonana-i3",
        "WSL GUI needs WSLg or an X server with DISPLAY set.",
        "",
        "AI",
        "Ooonana AI runs as ooonana ai ... or ooonana-ai. It supports provider setup, model aliases, ask/chat, tools, tasks, audit, history, status, and the full-i3 ooonana-ai-app launcher.",
        "ooonana-ai-app is now a native terminal dashboard with quick actions for chat, ask, tools, tasks, sessions, setup, and shell fallback.",
        "",
        "Build proof markers",
        "OOONANA_CLI_OK",
        "OOONANA_BOOT_OK",
        "OOONANA_INSTALL_OK",
        "OOONANA_FULL_I3_OK",
        "",
        "More detail lives in README.md, docs/ooonana-ai.md, and docs/jarvis-agi-research.md.",
    ]


def write_pdf(pages: list[list[str]], out: Path) -> None:
    objects: list[str] = ["", "", "<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"]
    page_ids: list[int] = []
    for lines in pages:
        stream = page_stream(lines)
        content_id = len(objects) + 1
        objects.append(f"<< /Length {len(stream.encode('latin-1', 'replace'))} >>\nstream\n{stream}\nendstream")
        page_id = len(objects) + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[0] = "<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"

    out.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode("ascii"))
        data.extend(obj.encode("latin-1", "replace"))
        data.extend(b"\nendobj\n")
    xref_at = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    data.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode("ascii")
    )
    out.write_bytes(data)


def main() -> None:
    write_pdf(paginate(build_lines()), OUT)
    print(OUT)


if __name__ == "__main__":
    main()
