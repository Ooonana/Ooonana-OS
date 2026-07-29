#!/usr/bin/env python3
"""Audit a built full-i3 rootfs for runtime closure."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys


PATH_DIRS = (
    "usr/local/sbin",
    "usr/local/bin",
    "usr/sbin",
    "usr/bin",
    "sbin",
    "bin",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("rootfs", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.rootfs.resolve()
    errors: list[str] = []
    checked_elf = 0
    checked_scripts = 0

    def fail(message: str) -> None:
        errors.append(message)

    def rooted(path: str | Path) -> Path:
        return root / str(path).lstrip("/")

    def command_path(command: str) -> Path | None:
        if command.startswith("/"):
            candidate = rooted(command)
            return candidate if candidate.exists() else None
        for directory in PATH_DIRS:
            candidate = root / directory / command
            if candidate.exists():
                return candidate
        return None

    def check_command(command: str) -> None:
        candidate = command_path(command)
        if candidate is None:
            fail(f"missing command: {command}")
        elif not os.access(candidate, os.X_OK):
            fail(f"command not executable: {command}")

    if not root.is_dir():
        print(f"not a rootfs: {root}", file=sys.stderr)
        return 2

    required_commands = (
        "init",
        "dbus-run-session",
        "start-ooonana-i3",
        "startx",
        "Xorg",
        "i3",
        "i3-msg",
        "i3-nagbar",
        "rofi",
        "polybar",
        "xterm",
        "alacritty",
        "chromium",
        "nemo",
        "python3",
        "nmcli",
        "NetworkManager",
        "bluetoothctl",
        "pulseaudio",
        "pactl",
        "pavucontrol",
        "sudo",
        "doas",
        "su",
        "ooonana",
        "oonana",
        "bunana",
        "ooonana-wifi",
        "ooonana-bluetooth",
        "ooonana-audio-panel",
        "ooonana-power-menu",
        "ooonana-settings-launch",
        "ooonana-ai-launch",
        "ooonana-hardware-reprobe",
        "ooonana-service-repair",
        "ooonana-run-admin",
        "ooonana-apps",
        "ooonana-files",
        "ooonana-browser",
        "ooonana-packages-app",
        "ooonana-gui-installer",
        "ooonana-wallpaper",
        "ooonana-screenshot",
        "ooonana-editor",
        "ooonana-music",
        "ooonana-processes",
        "ooonana-ranger",
        "ooonana-touchpad",
        "nm-applet",
        "blueman-applet",
        "picom",
        "dunst",
        "xsettingsd",
        "xsetroot",
        "xset",
        "xauth",
        "i3lock",
        "iw",
        "wpa_supplicant",
        "rfkill",
        "ip",
        "brightnessctl",
        "grub-install",
    )
    for command in required_commands:
        check_command(command)

    if not any(
        rooted(path).exists()
        for path in (
            "/usr/lib/bluetooth/bluetoothd",
            "/usr/libexec/bluetooth/bluetoothd",
            "/usr/sbin/bluetoothd",
        )
    ):
        fail("missing bluetoothd")

    required_files = (
        "/etc/init.d/rcS",
        "/etc/os-release",
        "/etc/passwd",
        "/etc/group",
        "/etc/shadow",
        "/etc/NetworkManager/NetworkManager.conf",
        "/etc/bluetooth/main.conf",
        "/etc/i3/config",
        "/etc/ooonana/polybar.ini",
        "/etc/ooonana/rofi.rasi",
        "/etc/doas.conf",
        "/etc/sudoers.d/ooonana",
        "/etc/machine-id",
        "/var/lib/dbus/machine-id",
        "/usr/share/ooonana/logo.png",
        "/usr/share/ooonana/wallpapers/ooonana-wallpaper.png",
    )
    for path in required_files:
        if not rooted(path).exists():
            fail(f"missing runtime file: {path}")

    for grub_target in ("i386-pc", "x86_64-efi"):
        directory = rooted(f"/usr/lib/grub/{grub_target}")
        if not directory.is_dir() or not any(directory.iterdir()):
            fail(f"missing GRUB target modules: {grub_target}")

    os_release = rooted("/etc/os-release").read_text(errors="replace")
    if not re.search(r"^ID=ooonana$", os_release, re.MULTILINE):
        fail("rootfs os-release ID is not ooonana")

    passwd_lines = rooted("/etc/passwd").read_text(errors="replace").splitlines()
    group_lines = rooted("/etc/group").read_text(errors="replace").splitlines()
    user_line = next((line for line in passwd_lines if line.startswith("ooonana:")), "")
    if not user_line:
        fail("missing non-root desktop user")
    else:
        fields = user_line.split(":")
        if len(fields) != 7 or fields[2] == "0" or fields[5] != "/home/ooonana":
            fail(f"invalid desktop user: {user_line}")

    for group in ("wheel", "audio", "video", "input", "netdev", "plugdev"):
        line = next((item for item in group_lines if item.startswith(group + ":")), "")
        members = line.split(":")[-1].split(",") if line else []
        if "ooonana" not in members:
            fail(f"desktop user missing group: {group}")

    for path in ("/usr/bin/doas", "/usr/bin/sudo", "/bin/su"):
        candidate = rooted(path)
        if candidate.exists() and not candidate.stat().st_mode & stat.S_ISUID:
            fail(f"setuid bit missing: {path}")

    mode_expectations = {
        "/etc/shadow": 0o600,
        "/etc/doas.conf": 0o400,
        "/etc/sudoers.d/ooonana": 0o440,
    }
    for path, expected in mode_expectations.items():
        candidate = rooted(path)
        if candidate.exists() and stat.S_IMODE(candidate.stat().st_mode) != expected:
            fail(
                f"wrong mode: {path} "
                f"{stat.S_IMODE(candidate.stat().st_mode):04o}, expected {expected:04o}"
            )

    # Check links as they would resolve inside the rootfs, not on the host.
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        current = path
        seen: set[Path] = set()
        for _ in range(64):
            if current in seen:
                fail(f"symlink loop: /{path.relative_to(root)}")
                break
            seen.add(current)
            if not current.is_symlink():
                if not current.exists():
                    fail(f"broken symlink: /{path.relative_to(root)} -> {os.readlink(path)}")
                break
            target = os.readlink(current)
            if target.startswith(("/proc/", "/sys/", "/dev/", "/run/")):
                break
            if target.startswith("/"):
                current = rooted(target)
            else:
                current = Path(os.path.normpath(current.parent / target))
        else:
            fail(f"symlink depth exceeded: /{path.relative_to(root)}")

    # Every desktop launcher must point to an installed executable.
    for desktop in rooted("/usr/share/applications").glob("*.desktop"):
        for line in desktop.read_text(errors="replace").splitlines():
            if not line.startswith("Exec="):
                continue
            value = line.removeprefix("Exec=").strip()
            try:
                words = shlex.split(value)
            except ValueError as exc:
                fail(f"{desktop.name}: invalid Exec line: {exc}")
                continue
            words = [word for word in words if not re.fullmatch(r"%[fFuUdDnNickvm]", word)]
            index = 0
            if words and words[0] == "env":
                index = 1
                while index < len(words) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[index]):
                    index += 1
            if index >= len(words):
                fail(f"{desktop.name}: empty Exec line")
            elif command_path(words[index]) is None:
                fail(f"{desktop.name}: missing Exec target: {words[index]}")

    # Panel actions and status commands must exist.
    panel = rooted("/etc/ooonana/polybar.ini")
    if panel.exists():
        for line in panel.read_text(errors="replace").splitlines():
            match = re.match(r"^(?:click-(?:left|middle|right)|scroll-(?:up|down)|exec)\s*=\s*(.+)$", line)
            if not match:
                continue
            try:
                words = shlex.split(match.group(1))
            except ValueError as exc:
                fail(f"polybar invalid command: {exc}")
                continue
            if words and words[0] not in ("true", "false") and command_path(words[0]) is None:
                fail(f"polybar command missing: {words[0]}")

    firmware = rooted("/lib/firmware")
    firmware_families = {
        "Intel Wi-Fi": ("iwlwifi-*.ucode",),
        "Realtek Wi-Fi": ("rtw88/*", "rtw89/*"),
        "MediaTek Wi-Fi": ("mediatek/*",),
        "Qualcomm Wi-Fi": ("ath10k/*", "ath11k/*", "ath12k/*"),
        "Bluetooth": ("intel/ibt-*", "rtl_bt/*", "mediatek/BT_*"),
        "Intel audio": ("intel/sof*",),
    }
    for family, patterns in firmware_families.items():
        if not any(any(firmware.glob(pattern)) for pattern in patterns):
            fail(f"missing firmware family: {family}")

    if not any(rooted("/usr/lib/NetworkManager").rglob("*wifi*")):
        fail("NetworkManager Wi-Fi plugin missing")
    if not any(rooted("/usr/share/alsa/ucm2").rglob("*")):
        fail("ALSA UCM profiles missing")
    if not any(rooted("/usr/share/fonts").rglob("*.ttf")):
        fail("TrueType fonts missing")
    if not any(rooted("/usr/share/icons/Adwaita").rglob("*.svg")):
        fail("Adwaita application icons missing")

    chromium_sandbox = rooted("/usr/lib/chromium/chrome-sandbox")
    if chromium_sandbox.exists() and not chromium_sandbox.stat().st_mode & stat.S_ISUID:
        fail("Chromium sandbox lacks setuid bit")

    text_roots = (
        rooted("/bin"),
        rooted("/sbin"),
        rooted("/usr/bin"),
        rooted("/usr/sbin"),
        rooted("/etc/init.d"),
        rooted("/etc/NetworkManager"),
        rooted("/etc/dbus-1"),
    )
    for base in text_roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if b"\r\n" in data and (
                data.startswith(b"#!") or path.suffix in (".conf", ".sh", ".pkg", ".desktop")
            ):
                fail(f"CRLF runtime file: /{path.relative_to(root)}")
            if (
                (str(path.relative_to(root)).startswith("etc/") or str(path.relative_to(root)).startswith("usr/"))
                and path.stat().st_mode & stat.S_IWOTH
            ):
                fail(f"world-writable critical file: /{path.relative_to(root)}")

    for package in rooted("/var/lib/ooonana/packages/installed").glob("*.pkg"):
        data = package.read_text(errors="replace")
        if "\r" in data:
            fail(f"CRLF package metadata: {package.name}")
        if not re.search(r"^OOONANA_PKG_ID=", data, re.MULTILINE):
            fail(f"package ID missing: {package.name}")
        if not re.search(r"^OOONANA_PKG_VERSION=", data, re.MULTILINE):
            fail(f"package version missing: {package.name}")

    sof_package = rooted("/var/lib/ooonana/packages/installed/sof-firmware.pkg")
    if not sof_package.exists():
        fail("SOF firmware package marker missing")
    else:
        sof_data = sof_package.read_text(errors="replace")
        match = re.search(r'^OOONANA_PKG_VERSION="?(\d+)\.(\d+)\.(\d+)', sof_data, re.MULTILINE)
        if not match or tuple(map(int, match.groups())) < (2025, 12, 1):
            fail("SOF firmware is too old for Galaxy Book4 Meteor Lake audio")

    # Python syntax closure without creating pycache.
    for path in rooted("/usr/lib/ooonana").rglob("*.py"):
        try:
            compile(path.read_bytes(), str(path), "exec")
        except (OSError, SyntaxError) as exc:
            fail(f"Python syntax failed: /{path.relative_to(root)}: {exc}")

    # Shebang interpreters and shell syntax.
    for base in (rooted("/bin"), rooted("/sbin"), rooted("/usr/bin"), rooted("/usr/sbin")):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                first = path.open("rb").readline(512)
            except OSError:
                continue
            if not first.startswith(b"#!"):
                continue
            checked_scripts += 1
            shebang = first[2:].decode("utf-8", "replace").strip().split()
            if not shebang:
                fail(f"empty shebang: /{path.relative_to(root)}")
                continue
            interpreter = shebang[0]
            if interpreter == "/usr/bin/env" and len(shebang) > 1:
                if command_path(shebang[1]) is None:
                    fail(f"missing shebang command {shebang[1]}: /{path.relative_to(root)}")
            elif interpreter.startswith("/") and not rooted(interpreter).exists():
                fail(f"missing shebang interpreter {interpreter}: /{path.relative_to(root)}")
            logical = "/" + str(path.relative_to(root))
            if interpreter.endswith(("/sh", "/bash")):
                result = subprocess.run(
                    ["chroot", str(root), interpreter, "-n", logical],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                )
                if result.returncode:
                    fail(f"shell syntax failed: {logical}: {result.stdout.strip()}")

    # Scan all command ELFs, plus Chromium, through musl's dependency lister.
    loader = rooted("/lib/ld-musl-x86_64.so.1")
    elf_roots = [rooted(path) for path in ("/bin", "/sbin", "/usr/bin", "/usr/sbin", "/usr/libexec")]
    chromium_binary = rooted("/usr/lib/chromium/chromium")
    elf_paths: set[Path] = {chromium_binary} if chromium_binary.exists() else set()
    for base in elf_roots:
        if not base.exists():
            continue
        elf_paths.update(path for path in base.rglob("*") if path.is_file() and not path.is_symlink())
    if not loader.exists():
        fail("musl dynamic loader missing")
    else:
        for path in sorted(elf_paths):
            try:
                header = path.open("rb").read(4)
            except OSError:
                continue
            if header != b"\x7fELF":
                continue
            checked_elf += 1
            logical = "/" + str(path.relative_to(root))
            result = subprocess.run(
                ["chroot", str(root), "/lib/ld-musl-x86_64.so.1", "--list", logical],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            output = result.stdout.strip()
            if result.returncode or "not found" in output.lower():
                fail(f"ELF dependency failure: {logical}: {output}")

    print(f"runtime audit: scripts={checked_scripts} elf={checked_elf} errors={len(errors)}")
    for error in errors:
        print(f"FAIL: {error}")
    if errors:
        return 1
    print("OOONANA_RUNTIME_CLOSURE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
