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
args = parser.parse_args()
work = args.output.resolve()
assert str(work).startswith("/var/tmp/ooonana-grub-ui-") and not work.exists()
work.mkdir(mode=0o755)
source = (ROOT / "scripts/build-full-i3-iso.sh").read_text()
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
SMOKE=0; LIVE_SMOKE=0; INSTALL_TARGET=auto; DISK_IMAGE_STAGED=unused
''' + "\n".join(function(name) for name in ("write_grub_config", "write_rufus_note", "file_size_bytes", "check_iso_mode_file_sizes", "stage_iso_tree")) + "\nstage_iso_tree\n"
stage = subprocess.run(["bash", "-c", script], text=True, capture_output=True)
assert stage.returncode == 0, stage.stderr
fonts = base / "boot/grub/fonts"
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
    for filename in ("theme.txt", "background.png", "boot-mark.png", "ooonana-logo.txt", "fonts/unicode.pf2"):
        embedded.append("boot/grub/" + filename + "=" + str(volume / "boot/grub" / filename))
    subprocess.run(["grub-mkstandalone", "-O", "x86_64-efi", "-o", str(binary), *embedded], check=True, timeout=45)
    variables = case / "OVMF_VARS.fd"
    shutil.copyfile("/usr/share/OVMF/OVMF_VARS_4M.fd", variables)
    qmp = case / "qmp.sock"
    log = (case / "qemu.log").open("w")
    process = subprocess.Popen(["qemu-system-x86_64", "-accel", "tcg", "-m", "192", "-display", "none",
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
        def capture(name):
            ppm = case / (name + ".ppm")
            command("screendump", {"filename": str(ppm)})
            with Image.open(ppm) as picture:
                assert picture.size == tuple(map(int, geometry.split("x"))), picture.size
                picture.save(case / (name + ".png"))
            results.append(str(case / (name + ".png")))
        capture("menu")
        for _ in range(4):
            command("human-monitor-command", {"command-line": "sendkey down"})
            time.sleep(0.15)
        command("human-monitor-command", {"command-line": "sendkey ret"})
        time.sleep(1)
        capture("audio-submenu")
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
