#!/usr/bin/env python3
"""Render production GRUB menu in disposable EFI VM. No ISO or kernel boot."""
import argparse
import json
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import time

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--geometry", choices=("640x480", "1280x800"), help="Focused geometry regression")
parser.add_argument("--variant", choices=("full", "minimal", "installed"), default="full")
parser.add_argument("--installed-fallback", choices=("missing-font", "missing-mark", "missing-menu-font"),
                    help="Installed-menu recovery fixture; no real installation")
args = parser.parse_args()
work = args.output.resolve()
assert str(work).startswith("/var/tmp/ooonana-grub-ui-") and not work.exists()
work.mkdir(mode=0o755)
source = (ROOT / {"full": "scripts/build-full-i3-iso.sh",
                  "minimal": "scripts/build-scratch-grub-iso.sh",
                  "installed": "packages/ooonana/usr/sbin/ooonana-install"}[args.variant]).read_text()
starts = list(re.finditer(r"^\w+\(\) \{", source, re.MULTILINE))

def function(name):
    index = next(i for i, match in enumerate(starts) if match.group() == name + "() {")
    return source[starts[index].start():starts[index + 1].start()]

dummy = work / "placeholder"
dummy.write_bytes(b"UI fixture; never boot this payload\n")
base = work / "base"
script = f'''set -eu
ROOT={shlex.quote(str(ROOT))}
source "$ROOT/scripts/lib/common.sh"
ISO_TREE={shlex.quote(str(base))}
KERNEL={shlex.quote(str(dummy))}
INITRAMFS="$KERNEL"; LIVE_INITRAMFS="$KERNEL"; LIVE_ROOTFS_IMAGE="$KERNEL"
SMOKE=0; GUI_SMOKE=0; LIVE_SMOKE=0; INSTALL=1; INSTALL_TARGET=auto; DISK_IMAGE_STAGED=unused
DISK_IMAGE=""; ROOTFS_IMAGE="$KERNEL"
'''
if args.variant == "installed":
    # Extract pure config writers only. Never source/execute the installer.
    script += 'run_cmd() { "$@"; }\n' + "\n".join(function(name) for name in ("kernel_append", "write_grub_config"))
    script += '''
mkdir -p "$ISO_TREE/usr/share/ooonana" "$ISO_TREE/boot"
install -m 0644 "$ROOT/packages/ooonana/usr/share/ooonana/grub-logo.txt" "$ISO_TREE/usr/share/ooonana/grub-logo.txt"
install -m 0644 "$ROOT/packages/ooonana/usr/share/ooonana/grub.theme" "$ISO_TREE/usr/share/ooonana/grub.theme"
cp -a "$ROOT/packages/ooonana/usr/share/ooonana/grub-ui" "$ISO_TREE/usr/share/ooonana/"
install -m 0644 "$ROOT/branding/boot-mark.png" "$ISO_TREE/usr/share/ooonana/boot-mark.png"
install -m 0644 "$ROOT/branding/grub-background.png" "$ISO_TREE/usr/share/ooonana/grub-background.png"
install -m 0644 "$KERNEL" "$ISO_TREE/boot/vmlinuz"
'''
    if args.installed_fallback != "missing-font":
        script += 'install -D -m 0644 /usr/share/grub/unicode.pf2 "$ISO_TREE/usr/share/grub/unicode.pf2"\n'
    if args.installed_fallback == "missing-mark":
        # Only this newly created fixture asset is omitted.
        script += 'rm "$ISO_TREE/usr/share/ooonana/boot-mark.png"\n'
    if args.installed_fallback == "missing-menu-font":
        script += 'rm "$ISO_TREE/usr/share/ooonana/grub-ui/menu.pf2"\n'
    script += 'write_grub_config "$ISO_TREE" PARTUUID=FIXTURE_NEVER_BOOT\n'
else:
    script += "\n".join(function(name) for name in ("write_grub_config", "write_rufus_note", "file_size_bytes", "check_iso_mode_file_sizes", "stage_iso_tree")) + "\nstage_iso_tree\n"
stage = subprocess.run(["bash", "-c", script], text=True, capture_output=True)
assert stage.returncode == 0, stage.stderr
fonts = base / "boot/grub/fonts"
if args.variant != "installed":
    fonts.mkdir()
    shutil.copyfile("/usr/share/grub/unicode.pf2", fonts / "unicode.pf2")
results = []
for geometry in (args.geometry,) if args.geometry else ("640x480", "1280x800"):
    case = work / geometry
    volume = case / "volume"
    shutil.copytree(base, volume)
    config = volume / "boot/grub/grub.cfg"
    # QA-only display selection and disabled timer; production config untouched.
    config.write_text(f"set gfxmode={geometry}\n" + config.read_text().replace("set timeout=5", "set timeout=60"))
    bootstrap = case / "bootstrap.cfg"
    bootstrap.write_text("set root=(memdisk)\nconfigfile (memdisk)/boot/grub/main.cfg\n")
    binary = volume / "EFI/BOOT/BOOTX64.EFI"
    binary.parent.mkdir(parents=True)
    embedded = ["boot/grub/grub.cfg=" + str(bootstrap), "boot/grub/main.cfg=" + str(config)]
    for filename in ("theme.txt", "background.png", "boot-mark.png", "ooonana-logo.txt", "fonts/unicode.pf2", "fonts/ooonana.pf2"):
        asset = volume / "boot/grub" / filename
        if asset.is_file():
            embedded.append("boot/grub/" + filename + "=" + str(asset))
    for asset in (volume / "boot/grub/grub-ui").rglob("*"):
        if asset.is_file():
            embedded.append(asset.relative_to(volume).as_posix() + "=" + str(asset))
    subprocess.run(["grub-mkstandalone", "-O", "x86_64-efi", "-o", str(binary), *embedded], check=True, timeout=45)
    variables = case / "OVMF_VARS.fd"
    shutil.copyfile("/usr/share/OVMF/OVMF_VARS_4M.fd", variables)
    qmp = case / "qmp.sock"
    log = (case / "qemu.log").open("w")
    width, height = geometry.split("x")
    process = subprocess.Popen(["qemu-system-x86_64", "-accel", "tcg", "-m", "192", "-display", "none",
        "-vga", "none", "-device", f"VGA,xres={width},yres={height}",
        "-nic", "none", "-audiodev", "none,id=silent", "-no-reboot", "-monitor", "none",
        "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
        "-drive", "if=pflash,format=raw,file=" + str(variables),
        "-drive", "format=raw,file=fat:rw:" + str(volume),
        "-serial", "file:" + str(case / "serial.log"), "-qmp", "unix:" + str(qmp) + ",server=on,wait=off"],
        stdout=log, stderr=subprocess.STDOUT)
    connection = None
    try:
        deadline = time.monotonic() + 10
        while not qmp.exists():
            assert process.poll() is None and time.monotonic() < deadline
            time.sleep(0.1)
        connection = socket.socket(socket.AF_UNIX)
        connection.settimeout(10)
        while True:
            try:
                connection.connect(str(qmp))
                break
            except ConnectionRefusedError:
                assert process.poll() is None and time.monotonic() < deadline
                time.sleep(0.1)
        stream = connection.makefile("rwb")
        json.loads(stream.readline())
        def command(name, arguments=None):
            stream.write((json.dumps({"execute": name, "arguments": arguments or {}}) + "\n").encode())
            stream.flush()
            while True:
                result = json.loads(stream.readline())
                assert "error" not in result, result
                if "return" in result:
                    return result["return"]
        command("qmp_capabilities")
        time.sleep(12)
        def capture(name, modern=True):
            ppm = case / (name + ".ppm")
            command("screendump", {"filename": str(ppm)})
            with Image.open(ppm) as picture:
                assert picture.size == tuple(map(int, geometry.split("x"))), picture.size
                picture.save(case / (name + ".png"))
                if args.variant == "minimal" or not modern:
                    # Both selected and ordinary entries must actually render
                    # with readable roles, not merely appear in theme source.
                    width, height = picture.size
                    menu = picture.convert("RGB").crop((int(width * .16), int(height * .32),
                                                        int(width * .84), int(height * .70)))
                    pixels = list(menu.getdata())
                    for role in ((180, 189, 200), (255, 178, 26)):
                        assert sum(pixel == role for pixel in pixels) >= 40, (name, geometry, role)
                elif not args.installed_fallback:
                    width, height = picture.size
                    left, top = width * 46 // 100 - 40, height * 46 // 100 - 204
                    right = left + width * 28 // 100 + 190
                    menu = picture.convert("RGB").crop((left, top + 66, right, top + 372))
                    pixels = list(menu.getdata())
                    for role in ((228, 230, 233), (255, 220, 154), (64, 52, 41)):
                        assert sum(pixel == role for pixel in pixels) >= 40, (name, geometry, role)
                    if args.variant == "full" and name in ("menu", "persistent"):
                        # All six rows render, including Classic on the shortest framebuffer.
                        selected = 1 if name == "persistent" else 0
                        for row in range(6):
                            text_color = (255, 220, 154) if row == selected else (228, 230, 233)
                            item = menu.crop((70, row * 51, menu.width - 20, row * 51 + 48))
                            assert sum(pixel == text_color for pixel in item.getdata()) >= 16, (name, geometry, row)
                        status_left = width * 74 // 100 + 3
                        status = picture.convert("RGB").crop((status_left, top + 411, status_left + 121, top + 431))
                        status_pixels = sum(pixel == (186, 190, 201) for pixel in status.getdata())
                        assert status_pixels >= 40 if name == "menu" else status_pixels == 0, (name, geometry, "countdown")
            results.append(str(case / (name + ".png")))

        def press(key):
            command("human-monitor-command", {"command-line": "sendkey " + key})
            time.sleep(0.22)

        capture("menu", modern=args.installed_fallback != "missing-menu-font")
        if args.variant == "minimal":
            press("down")
            capture("install-entry")
        elif not args.installed_fallback:
            press("down")
            if args.variant == "full":
                capture("persistent")
                for _ in range(3):
                    press("down")
            # Audio and Classic are config-only choices. Never start a kernel fixture.
            press("ret")
            capture("audio-submenu")
            press("esc")
            press("l")
            time.sleep(1)
            capture("classic", modern=False)
        command("quit")
        process.wait(timeout=5)
    finally:
        if connection:
            connection.close()
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        log.close()
print("GRUB_UI_CAPTURE_OK " + json.dumps(results))
