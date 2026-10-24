#!/usr/bin/env python3
"""QEMU serial login proof using installer account policy; no real disk/audio."""
import argparse
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import tempfile
import time

project = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--kernel", required=True, type=Path)
parser.add_argument("--expired-account", action="store_true", help="Reject an expired disposable account even with correct password")
parser.add_argument("--expired-password", action="store_true", help="Require password change before desktop entry")
parser.add_argument("--login-rootfs", type=Path, help="Use actual candidate PAM login/runtime, not scratch BusyBox login")
args = parser.parse_args()
assert args.kernel.is_file()
assert not (args.expired_account and args.expired_password)
assert not (args.expired_account or args.expired_password) or args.login_rootfs, "Real PAM login required for expiry proof"

with tempfile.TemporaryDirectory(prefix="ooonana-login-proof-") as temporary:
    work = Path(temporary)
    root = work / "root"
    subprocess.run(["bash", str(project / "scripts/build-scratch-rootfs.sh"), "--work-dir", str(work), "--rootfs", str(root), "--no-image"], check=True, capture_output=True)
    installer = (project / "packages/ooonana/usr/sbin/ooonana-install").read_text()
    before_main = installer.split('while [[ $# -gt 0 ]]', 1)[0]
    helper = work / "policy.sh"
    helper.write_text(before_main + '\nUSER_NAME=fixture\nPASSWORD_STDIN=1\nPASSWORD_VALUE=fixture-only-password\napply_install_config "$1"\n')
    subprocess.run(["bash", str(helper), str(root)], check=True, capture_output=True)
    if args.login_rootfs:
        candidate = args.login_rootfs.resolve(strict=True)
        assert candidate.as_posix().startswith("/var/tmp/") and (candidate / "bin/login").is_file()
        assert "ID=ooonana\n" in (candidate / "etc/os-release").read_text()
        copied = set()
        def copy_runtime(relative):
            relative = os.path.normpath("/" + relative).lstrip("/")
            if relative in copied: return
            copied.add(relative)
            source, target = candidate / relative, root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                link = os.readlink(source)
                next_path = link if link.startswith("/") else str(Path(relative).parent / link)
                copy_runtime(next_path)
                target.unlink(missing_ok=True); target.symlink_to(link)
                return
            assert source.is_file(), source
            target.unlink(missing_ok=True)  # Only generated scratch paths; never follow old applet symlinks.
            shutil.copy2(source, target)
            with source.open("rb") as stream: elf = stream.read(4) == b"\x7fELF"
            if not elf: return
            dynamic = subprocess.check_output(["readelf", "-d", str(source)], text=True)
            for library in re.findall(r"\(NEEDED\).*\[([^]]+)\]", dynamic):
                assert "/" not in library
                dependency = next((prefix + library for prefix in ("lib/", "usr/lib/")
                                   if (candidate / (prefix + library)).exists()), None)
                assert dependency, (source, library)
                copy_runtime(dependency)
            program = subprocess.check_output(["readelf", "-l", str(source)], text=True)
            for interpreter in re.findall(r"Requesting program interpreter: ([^]]+)", program): copy_runtime(interpreter)
        copy_runtime("bin/login")
        for helper in ("usr/sbin/unix_chkpwd", "usr/sbin/unix_update"):
            if (candidate / helper).is_file(): copy_runtime(helper)
        for prefix in ("etc/pam.d", "usr/lib/pam.d", "etc/security", "usr/lib/security"):
            directory = candidate / prefix
            if directory.is_dir():
                for source in directory.rglob("*"):
                    if source.is_file(): copy_runtime(source.relative_to(candidate).as_posix())
        for optional in ("etc/login.defs", "etc/environment"):
            if (candidate / optional).is_file(): copy_runtime(optional)
        print("LOGIN_RUNTIME_ACTUAL_OK candidate PAM login and ELF closure; private scratch only", flush=True)
    if args.expired_account or args.expired_password:
        path = root / "etc/shadow"
        records = path.read_text().splitlines()
        for index, record in enumerate(records):
            fields = record.split(":")
            if fields[0] == "fixture":
                assert len(fields) == 9
                if args.expired_account:
                    fields[7] = "1"  # Long expired, independent of host timezone/date.
                else:
                    fields[2], fields[3], fields[4] = "1", "0", "1"
                records[index] = ":".join(fields)
        path.write_text("\n".join(records) + "\n")
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
    startup.write_text('#!/bin/sh\nmount -t proc proc /proc\nmount -t sysfs sysfs /sys\nmount -t devtmpfs devtmpfs /dev\nmkdir -p /dev/pts\nmount -t devpts devpts /dev/pts\n/bin/busybox syslogd -O /dev/ttyS0\ndate -u >/dev/ttyS0\necho OO_LOGIN_INIT_READY >/dev/ttyS0\n')
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
        if args.expired_account:
            expect("account has expired")
            expect("login:")
            assert b"OO_LOGIN_DESKTOP_UID=" not in transcript, "Expired account entered desktop"
            print("INSTALLED_EXPIRED_LOGIN_VM_OK - expired account rejected with correct password")
        elif args.expired_password:
            expect("password expired")
            assert b"OO_LOGIN_DESKTOP_UID=" not in transcript, "Expired password bypassed change requirement"
            print("INSTALLED_PASSWORD_EXPIRY_VM_OK - expired password requires change before desktop")
        else:
            expect("OO_LOGIN_DESKTOP_UID=1000 HOME=/home/fixture")
            print("INSTALLED_LOGIN_VM_OK - wrong password rejected; authenticated nonroot desktop entry")
    finally:
        process.terminate()
        process.wait(timeout=8)
