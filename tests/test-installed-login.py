#!/usr/bin/env python3
"""QEMU serial login proof using installer account policy; no real disk/audio."""
import argparse
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time

project = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--kernel", required=True, type=Path)
args = parser.parse_args()
assert args.kernel.is_file()

with tempfile.TemporaryDirectory(prefix="ooonana-login-proof-") as temporary:
    work = Path(temporary)
    root = work / "root"
    subprocess.run(["bash", str(project / "scripts/build-scratch-rootfs.sh"), "--work-dir", str(work), "--rootfs", str(root), "--no-image"], check=True, capture_output=True)
    installer = (project / "packages/ooonana/usr/sbin/ooonana-install").read_text()
    before_main = installer.split('while [[ $# -gt 0 ]]', 1)[0]
    helper = work / "policy.sh"
    helper.write_text(before_main + '\nUSER_NAME=fixture\nPASSWORD_STDIN=1\nPASSWORD_VALUE=fixture-only-password\napply_install_config "$1"\n')
    subprocess.run(["bash", str(helper), str(root)], check=True, capture_output=True)
    assert "NOPASSWD" not in (root / "etc/sudoers.d/ooonana").read_text()
    assert "/bin/busybox getty" in (root / "etc/inittab").read_text()
    assert (root / "etc/X11/Xwrapper.config").read_text() == "allowed_users=console\nneeds_root_rights=yes\n"
    assert (root / "etc/shadow").read_text().splitlines()[0].startswith("root:!")
    # Serial fixture replaces console number only. Real getty/login/shell remain.
    (root / "etc/inittab").write_text('::sysinit:/etc/init.d/rcS\nttyS0::respawn:/usr/bin/login-fixture-getty\n::shutdown:/bin/umount -a -r\n')
    getty = root / "usr/bin/login-fixture-getty"
    getty.write_text('#!/bin/sh\necho OO_GETTY_START >/dev/ttyS0\nexec /bin/busybox getty -L 115200 ttyS0 vt100\n')
    getty.chmod(0o755)
    startup = root / "etc/init.d/rcS"
    startup.write_text('#!/bin/sh\nmount -t proc proc /proc\nmount -t sysfs sysfs /sys\nmount -t devtmpfs devtmpfs /dev\nmkdir -p /dev/pts\nmount -t devpts devpts /dev/pts\necho OO_LOGIN_INIT_READY >/dev/ttyS0\n')
    startup.chmod(0o755)
    desktop = root / "usr/bin/start-ooonana-i3"
    desktop.write_text('#!/bin/sh\nprintf "OO_LOGIN_DESKTOP_UID=%s HOME=%s\\n" "$(id -u)" "$HOME"\n')
    desktop.chmod(0o755)
    profile = root / "home/fixture/.profile"
    profile.write_text('/usr/bin/start-ooonana-i3\n')
    os.chown(profile, 1000, 1000)
    initramfs = work / "login.cpio"
    with initramfs.open("wb") as output:
        subprocess.run(["bash", "-c", "find . -print0 | cpio --null -o --format=newc --quiet"], cwd=root, stdout=output, check=True)
    command = ["qemu-system-x86_64", "-accel", "tcg,thread=multi", "-m", "256", "-kernel", str(args.kernel), "-initrd", str(initramfs), "-append", "console=ttyS0 rdinit=/sbin/init panic=-1", "-display", "none", "-serial", "stdio", "-monitor", "none", "-nic", "none", "-no-reboot"]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    transcript = bytearray()

    def expect(needle, timeout=35):
        deadline = time.monotonic() + timeout
        while needle.encode() not in transcript:
            if time.monotonic() >= deadline or process.poll() is not None:
                raise AssertionError(bytes(transcript[-4000:]).decode(errors="replace"))
            if select.select([process.stdout], [], [], 0.2)[0]:
                transcript.extend(os.read(process.stdout.fileno(), 8192))

    def send(text):
        transcript.clear()
        process.stdin.write(text.encode() + b"\n")
        process.stdin.flush()

    try:
        expect("login:")
        send("fixture")
        expect("Password:")
        send("wrong-fixture-password")
        expect("Login incorrect")
        expect("login:")
        send("fixture")
        expect("Password:")
        send("fixture-only-password")
        expect("OO_LOGIN_DESKTOP_UID=1000 HOME=/home/fixture")
        print("INSTALLED_LOGIN_VM_OK - wrong password rejected; authenticated nonroot desktop entry")
    finally:
        process.terminate()
        process.wait(timeout=8)
