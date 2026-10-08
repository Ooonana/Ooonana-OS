#!/usr/bin/env python3
"""Generate docs/ooonana-guide.pdf without external PDF packages."""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "ooonana-guide.pdf"
LOGO = ROOT / "docs" / "logo.txt"


def wrap_line(line: str, width: int = 86) -> list[str]:
    if not line:
        return [""]
    if line.startswith("      ") or line.startswith("     ") or line.startswith("   /") or line.startswith("  /"):
        return [line]
    return textwrap.wrap(line, width=width, replace_whitespace=False) or [""]


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


HEADINGS = {"What it is", "Editions", "Package install", "Cloud repo", "Installer",
            "USB live modes", "First boot", "WSL", "AI", "Desktop and hardware",
            "Bootable PDF", "Build proof markers", "Persistence maintenance"}


def page_stream(lines: list[str], page: int = 1, count: int = 1) -> str:
    body = ["0.065 0.075 0.09 rg 0 754 612 38 re f",
            "BT /F2 12 Tf 1 0.70 0.10 rg 54 769 Td (OOONANA / FIELD GUIDE) Tj ET",
            f"BT /F1 9 Tf 0.36 0.39 0.44 rg 54 36 Td (Core 0.10.0 - {page} / {count}) Tj ET",
            "BT", "/F1 9.5 Tf", "13 TL", "54 728 Td"]
    for line in lines:
        body.append("/F2 11 Tf 0.62 0.34 0.01 rg" if line.removesuffix(" (continued)") in HEADINGS else "/F1 9.5 Tf 0.13 0.15 0.18 rg")
        body.append(f"({pdf_escape(line)}) Tj")
        body.append("T*")
    body.append("ET")
    return "\n".join(body)


def paginate(lines: list[str], per_page: int = 48) -> list[list[str]]:
    pages: list[list[str]] = []
    current: list[str] = []
    section = ""
    headings = HEADINGS
    for line in lines:
        if line in headings and len(current) > per_page - 4:
            pages.append(current)
            current = []
        block = wrap_line(line)
        if len(current) + len(block) > per_page:
            pages.append(current)
            current = [section + " (continued)", ""] if section and line not in headings else []
        if line in headings:
            section = line
        current.extend(block)
    if current:
        pages.append(current)
    return pages


def build_lines() -> list[str]:
    logo = LOGO.read_text(encoding="utf-8").rstrip().splitlines()
    return [
        *logo,
        "",
        "Ooonana OS 0.10.0 field guide",
        "",
        "What it is",
        "Ooonana OS is a scratch-built Linux project with its own rootfs, boot flow, installer experiments, WSL export, and custom ooonana package manager.",
        "Debian or Ubuntu are host build tools only. Alpine APKs are imported into Ooonana .pkg repos; the target OS installs Ooonana packages, not live Alpine APKs.",
        "Core 0.10.0 is a supported-base candidate, not a stable release. Imported payloads use one Alpine v3.24 branch. Stable 0.9.9 installations and public update channel remain separate during validation.",
        "Candidate release remains held on Chromium sandbox and compositor visual checks. Installed WSL migration is deferred; no ISO was built in this pass.",
        "",
        "Editions",
        "minimal: BusyBox-style rootfs, kernel, GRUB disk, installer ISO, WSL rootfs, command line AI.",
        "full-i3: minimal plus i3, Xorg, Spotlight-style launcher, movable GTK apps, wallpaper, GUI installer, AI desktop app, and full WSL rootfs.",
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
        "Default cloud path is the GitLab Pages direct repository:",
        "https://ooonana.gitlab.io/ooonana-repo",
        "Run ooonana update && ooonana upgrade. Metadata syncs first; package archives download only when install or upgrade needs them.",
        "GitHub Releases remains a backup tarball repository path.",
        "",
        "Installer",
        "Full-i3 live ISO boots i3. Installer requires explicit target and dry-run preview. Erase-disk mode offers optional swap; custom root, home, swap and EFI must share target disk.",
        "",
        "USB live modes",
        "Normal live mode mounts ISO and rootfs read-only. It uses a cleared temporary overlay on OOONANA_PERSIST when available on the same boot USB, with RAM fallback.",
        "Persistent live mode uses an ext4 OOONANA_PERSIST partition or a configured ext4 persistence file on the same boot USB. Setup previews and requires confirmation; GRUB selection never silently formats storage. Full writable overlay saves files, settings, radio pairings, packages and system changes.",
        "GRUB boot UUID and same-parent checks protect unrelated media. Cloned UUIDs, unsafe paths, missing/unwritable persistence, and mismatched ISO base identity stop in recovery; no silent RAM fallback or automatic repair.",
        "Other disks may be probed read-only. Live mode writes only to matching boot USB persistence. Only the confirmed installer target can be partitioned or formatted.",
        "",
        "First boot",
        "ooonana setup --first-boot --gui can create user, set password, write network config, choose theme, set zram and disk-swap policy, add cloud repo, and mark setup complete.",
        "",
        "WSL",
        "For a new test distro only: scripts/install-wsl-distro.sh --distro OoonanaCandidate --tarball /var/tmp/ooonana-os/release/ooonana-full-i3-wsl-rootfs.tar.gz. Never force-reimport over an existing distro as a migration shortcut.",
        "Launch desktop with: wsl.exe -d Ooonana -u ooonana --exec start-ooonana-i3",
        "WSL GUI needs WSLg and Xephyr, or an X server with DISPLAY set. Nested mode keeps i3 panel and dock together in one window.",
        "Same-base maintenance: ooonana update && ooonana upgrade. Cross-base migration requires verified backup and whole-world upgrade --allow-major from an independent host against an offline target root. Live libc replacement is refused; old saved USB overlays need separate explicit data migration.",
        "",
        "AI",
        "Ooonana AI runs as ooonana ai ... or ooonana-ai. It supports cloud providers, offline Intel OpenVINO, ask/chat, tools, tasks, audit, history, status, and a native GUI.",
        "The full-i3 desktop includes a ChatGPT-style AI workspace, Settings, Wi-Fi, Bluetooth, Packages, and Spotlight-style application launcher.",
        "",
        "Desktop and hardware",
        "The i3 desktop uses solid graphite and orange styling, rounded controls, a top music/window bar, and a centered opaque dock with running dots, click-to-restore apps, and right-click window actions.",
        "Core 0.10.0 retains matching native icons, focus-neutral dock previews, responsive panel spacing, AI loading/RAM/storage indicators, and compact third-party controls that exclude hidden tabs and fullscreen-covered windows. Alt+F4 closes; Alt+F10 toggles fullscreen.",
        "Ctrl+Shift+Esc opens native Task Manager with processes, performance, and available temperature and fan sensors. Unavailable hardware counters are labeled, not guessed.",
        "Live USB starts compressed zram swap. OpenVINO setup requires persistent USB storage or an installed system; RAM-only live storage cannot hold its runtime and models.",
        "Ooonana OpenVINO Chat 0.2.1 has a browser GUI through an authenticated loopback bridge. Windows-only computer-control tools are unavailable on Linux.",
        "Wi-Fi supports personal and enterprise profiles. NetworkManager, BlueZ, D-Bus, Intel Wi-Fi/Bluetooth firmware, Chromium, Python 3, sudo, su, and doas are included in full-i3.",
        "Installed password-login handoff passed diskless VM tests as UID 1000. Physical Xorg, wireless, audio, sensors and inference remain hardware checks; no sound was played.",
        "OpenVINO Linux dependencies use exact wheel hashes and a pinned Ubuntu image/APT snapshot. Signing private key stays local; public CI signing is deferred.",
        "",
        "Bootable PDF",
        "docs/ooonana.pdf uses native RISC-V64 Linux 6.18.37 and BusyBox 1.37.0. Embedded VM boot, stable input, native/virtual Backspace, version and package sync passed. Actual Chromium PDF interaction remains a manual gate.",
        "RV64 JavaScript emulator clock is scaled down 16x for CPU progress. Guest time is slower than real time. This terminal PDF is not the x86 i3 desktop.",
        "Boot status updates after kernel warnings. A sequential RAM seed replaces per-file boot copying; the interactive shell and package backend use RAM. Keep the PDF tab visible. Slow viewers may need several minutes; wait for ooonana# before typing.",
        "docs/ooonana-lite.pdf is a legacy artifact, not the current optimized runtime.",
        "",
        "Persistence maintenance",
        "bunana --shutdown and --restart request orderly init shutdown, stopping writers before sync, swapoff and unmount/remount read-only. No forced fallback. Live storage warnings are silent; no files are deleted automatically.",
        "ooonana-persistence backup requires explicit read-only ext4 mount, matching UUID and a new destination on another filesystem. Ownership, hardlinks and xattrs are verified. Active live overlay operations are refused.",
        "ooonana-persistence migrate requires matching verified backup and explicit data-only confirmation. It atomically switches to a fresh base, keeps home data, and preserves the complete old overlay. Accounts, packages and system configuration must be recreated; see docs/persistent-usb-safety.md.",
        "",
        "Build proof markers",
        "OOONANA_CLI_OK",
        "OOONANA_BOOT_OK",
        "OOONANA_INSTALL_OK",
        "OOONANA_FULL_I3_OK",
        "More detail lives in README.md, docs/ooonana-ai.md, and docs/jarvis-agi-research.md.",
    ]


def write_pdf(pages: list[list[str]], out: Path) -> None:
    objects: list[str] = ["", "", "<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
                          "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"]
    page_ids: list[int] = []
    for number, lines in enumerate(pages, 1):
        stream = page_stream(lines, number, len(pages))
        content_id = len(objects) + 1
        objects.append(f"<< /Length {len(stream.encode('latin-1', 'replace'))} >>\nstream\n{stream}\nendstream")
        page_id = len(objects) + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_id} 0 R >>"
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
    parser = argparse.ArgumentParser(description="Generate the Ooonana OS field guide PDF")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    output = args.output.expanduser().resolve()
    write_pdf(paginate(build_lines()), output)
    print(output)


if __name__ == "__main__":
    main()
