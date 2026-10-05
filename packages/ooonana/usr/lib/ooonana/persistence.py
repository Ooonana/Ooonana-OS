"""Explicit offline persistence backup/migration. Never mount, format or delete disks."""
import argparse
import base64
import ctypes
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile

UUID = re.compile(r"^[a-zA-Z0-9-]{4,64}$")


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def real_directory(path):
    path = Path(os.path.abspath(path))
    if path == Path("/") or path.is_symlink() or not path.is_dir() or path.resolve() != path:
        raise ValueError("Explicit real directory required; no root/symlink targets")
    return path


def mount_fields():
    def unescape(value):
        return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value)
    result = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        before, after = line.split(" - ", 1)
        left, right = before.split(), after.split()
        result.append({"root": unescape(left[3]), "path": unescape(left[4]),
                       "options": left[5].split(","), "type": right[0],
                       "source": unescape(right[1]), "super": unescape(right[2])})
    return result


def offline_mount(path, expected_uuid, writable=False):
    if os.geteuid() != 0:
        raise ValueError("Root required for ownership/xattr-preserving offline operations")
    if not UUID.fullmatch(expected_uuid):
        raise ValueError("Invalid expected filesystem UUID")
    path = real_directory(path)
    mounts = mount_fields()
    mount = next((item for item in mounts if item["path"] == str(path)), None)
    if not mount or mount["root"] != "/" or mount["type"] != "ext4":
        raise ValueError("Target must be explicit whole ext4 filesystem mount, not bind/subdirectory")
    source = Path(mount["source"])
    if not stat.S_ISBLK(source.stat().st_mode) or source.stat().st_rdev != path.stat().st_dev:
        raise ValueError("Mounted block-device identity could not be verified")
    result = subprocess.run(["blkid", "-s", "UUID", "-s", "LABEL", "-o", "export", str(source)],
                            text=True, capture_output=True, check=True, timeout=5)
    identity = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if identity.get("LABEL") != "OOONANA_PERSIST" or identity.get("UUID", "").lower() != expected_uuid.lower():
        raise ValueError("Label/UUID mismatch; no data changed")
    if ("rw" if writable else "ro") not in mount["options"]:
        raise ValueError("Migration needs rw mount; consistent backup needs ro mount (use ro,noload)")
    for item in mounts:
        if item["type"] != "overlay":
            continue
        for option in item["super"].split(","):
            if option.startswith(("upperdir=", "workdir=")):
                upper = Path(option.split("=", 1)[1])
                if upper == path or path in upper.parents:
                    raise ValueError("Overlay active; boot another Linux system before maintenance")
                try:
                    if upper.stat().st_dev == path.stat().st_dev:
                        raise ValueError("Persistence filesystem used by active overlay")
                except FileNotFoundError:
                    pass
    # initramfs upperdir paths may no longer be visible after switch_root.
    live_device = Path("/mnt/ooonana-live/persistence-device")
    if live_device.is_file():
        device = Path(live_device.read_text().strip())
        if device.exists() and device.stat().st_rdev == source.stat().st_rdev:
            raise ValueError("Current live USB cannot be maintained online; use another Linux system")
    return path


def tree_entries(root):
    root = real_directory(root)
    device = root.stat().st_dev
    entries = []
    links = {}
    for folder, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories + files):
            path = Path(folder) / name
            info = path.lstat()
            if info.st_dev != device:
                raise ValueError("Nested filesystem refused")
            mode = info.st_mode
            if not any(test(mode) for test in (stat.S_ISREG, stat.S_ISDIR, stat.S_ISLNK, stat.S_ISCHR, stat.S_ISBLK, stat.S_ISFIFO)):
                raise ValueError(f"Unsupported saved entry: {path.relative_to(root)}")
            attrs = {key: base64.b64encode(os.getxattr(path, key, follow_symlinks=False)).decode("ascii")
                     for key in sorted(os.listxattr(path, follow_symlinks=False))}
            entry = {"path": str(path.relative_to(root)), "mode": mode, "uid": info.st_uid,
                     "gid": info.st_gid, "mtime_ns": info.st_mtime_ns, "rdev": info.st_rdev, "xattrs": attrs}
            if stat.S_ISREG(mode):
                entry.update(size=info.st_size, sha256=digest(path))
                links.setdefault((info.st_dev, info.st_ino), []).append(entry)
            elif stat.S_ISLNK(mode):
                entry["link"] = os.readlink(path)
            entries.append(entry)
    for group in links.values():
        if len(group) > 1:
            identity = min(entry["path"] for entry in group)
            for entry in group:
                entry["hardlink"] = identity
    return sorted(entries, key=lambda entry: entry["path"])


def copy_tree(source, target, entries, data_only=False):
    target.mkdir(mode=0o700)
    links = {}
    copied = []
    for entry in sorted(entries, key=lambda item: (len(Path(item["path"]).parts), item["path"])):
        src, dst = source / entry["path"], target / entry["path"]
        mode = entry["mode"]
        if data_only and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode) or stat.S_ISLNK(mode)):
            continue  # Overlay whiteouts/device nodes must not enter new base.
        dst.parent.mkdir(parents=True, exist_ok=True)
        if stat.S_ISLNK(mode):
            os.symlink(entry["link"], dst)
        elif stat.S_ISDIR(mode):
            dst.mkdir(exist_ok=True)
        elif stat.S_ISREG(mode):
            key = (src.lstat().st_dev, src.lstat().st_ino)
            if key in links:
                os.link(links[key], dst)
            else:
                shutil.copyfile(src, dst, follow_symlinks=False)
                links[key] = dst
        elif stat.S_ISFIFO(mode):
            os.mkfifo(dst, stat.S_IMODE(mode))
        else:
            os.mknod(dst, mode, entry["rdev"])
        copied.append((entry, dst))
    # Finalize directories last; otherwise adding children changes saved mtimes.
    for entry, dst in reversed(copied):
        os.chown(dst, entry["uid"], entry["gid"], follow_symlinks=False)
        if not dst.is_symlink():
            os.chmod(dst, stat.S_IMODE(entry["mode"]))
        for key, value in entry["xattrs"].items():
            if not data_only or not key.startswith(("trusted.overlay.", "user.overlay.")):
                os.setxattr(dst, key, base64.b64decode(value), follow_symlinks=False)
        os.utime(dst, ns=(entry["mtime_ns"], entry["mtime_ns"]), follow_symlinks=False)
    os.chmod(target, 0o755)


def saved_overlay(mount):
    overlay = real_directory(mount / "overlay")
    upper = real_directory(overlay / "upper")
    marker = overlay / "base-id"
    if marker.is_symlink() or (marker.exists() and not marker.is_file()):
        raise ValueError("Unsafe base identity marker")
    return overlay, upper, marker.read_text().strip() if marker.exists() else "legacy"


def check_space(parent, entries):
    required = sum(entry.get("size", 0) for entry in entries) + 64 * 1024**2
    if shutil.disk_usage(parent).free < required:
        raise ValueError("Insufficient space; source untouched")


def atomic_rename(source, target, flags):
    libc = ctypes.CDLL(None, use_errno=True)
    operation = getattr(libc, "renameat2", None)
    arguments = (-100, os.fsencode(source), -100, os.fsencode(target), flags)
    types = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    if operation is not None:
        operation.argtypes = types
        operation.restype = ctypes.c_int
        result = operation(*arguments)
    else:
        # musl does not export renameat2. Use the identical Linux atomic syscall,
        # never a two-rename approximation. Unknown ABIs refuse before mutation.
        number = {"x86_64": 316, "aarch64": 276, "riscv64": 276}.get(platform.machine())
        operation = getattr(libc, "syscall", None)
        if sys.platform != "linux" or number is None or ctypes.sizeof(ctypes.c_void_p) != 8 or operation is None:
            raise ValueError("Atomic directory rename unavailable; originals unchanged")
        operation.argtypes = [ctypes.c_long, *types]
        operation.restype = ctypes.c_long
        result = operation(number, *arguments)
    if result:
        raise OSError(ctypes.get_errno(), f"Atomic operation refused; originals unchanged; staging at {source}")


def export_backup(mount, uuid, output):
    _, upper, base_id = saved_overlay(mount)
    output = Path(os.path.abspath(output))
    parent = real_directory(output.parent)
    if output.exists() or output.is_symlink() or parent.stat().st_dev == mount.stat().st_dev:
        raise ValueError("Backup needs new directory on different filesystem; no overwrite")
    entries = tree_entries(upper)
    check_space(parent, entries)
    pending = Path(tempfile.mkdtemp(prefix=".ooonana-backup-", dir=parent))
    # Keep failed/incomplete exports private, never promote them as valid backups.
    copy_tree(upper, pending / "upper", entries)
    if tree_entries(upper) != entries or tree_entries(pending / "upper") != entries:
        raise ValueError(f"Backup changed/metadata lost; incomplete export retained at {pending}")
    metadata = {"format": 1, "uuid": uuid.lower(), "base_id": base_id, "entries": entries}
    (pending / "manifest.json").write_text(json.dumps(metadata, sort_keys=True) + "\n")
    os.sync()
    atomic_rename(pending, output, 1)  # RENAME_NOREPLACE: never overwrite existing backup.
    os.sync()
    return output


def migrate(mount, uuid, base_id, backup):
    if not UUID.fullmatch(base_id):
        raise ValueError("New root-image filesystem UUID required")
    overlay, upper, old_base = saved_overlay(mount)
    backup = real_directory(backup)
    metadata = json.loads((backup / "manifest.json").read_text())
    entries = tree_entries(upper)
    if (metadata.get("format") != 1 or metadata.get("uuid") != uuid.lower()
            or metadata.get("base_id") != old_base or metadata.get("entries") != entries
            or tree_entries(backup / "upper") != entries):
        raise ValueError("Verified backup does not match current saved overlay; export again offline")
    home = upper / "home"
    home_entries = tree_entries(home) if home.exists() else []
    check_space(mount, home_entries)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    previous = Path(tempfile.mkdtemp(prefix="overlay.previous-" + stamp + "-", dir=mount))
    (previous / "upper").mkdir(mode=0o755)
    (previous / "work").mkdir(mode=0o755)
    if home.exists():
        copy_tree(home, previous / "upper/home", home_entries, data_only=True)
        expected = [{**entry, "xattrs": {key: value for key, value in entry["xattrs"].items()
                                        if not key.startswith(("trusted.overlay.", "user.overlay."))}}
                    for entry in home_entries
                    if stat.S_ISREG(entry["mode"]) or stat.S_ISDIR(entry["mode"]) or stat.S_ISLNK(entry["mode"])]
        if tree_entries(previous / "upper/home") != expected:
            raise ValueError(f"Migration copy failed verification; originals unchanged; staging at {previous}")
    (previous / "base-id").write_text(base_id.lower() + "\n")
    os.chmod(previous, 0o755)
    os.sync()
    # One atomic exchange: old overlay remains intact at previous, even on crash.
    atomic_rename(previous, overlay, 2)  # RENAME_EXCHANGE
    os.sync()
    return previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("status")
    for action in ("backup", "migrate"):
        command = commands.add_parser(action)
        command.add_argument("--mount", type=Path, required=True)
        command.add_argument("--expect-uuid", required=True)
        if action == "backup":
            command.add_argument("--output", type=Path, required=True)
        else:
            command.add_argument("--base-id", required=True)
            command.add_argument("--backup", type=Path, required=True)
            command.add_argument("--confirm-data-only", required=True, help="Repeat persistence UUID; keep home only, archive everything else")
    args = parser.parse_args()
    try:
        if args.action == "status":
            from storage_health import storage_health
            print(storage_health()["caption"])
            return 0
        mount = offline_mount(args.mount, args.expect_uuid, writable=args.action == "migrate")
        # Cooperating maintenance operations share filesystem lock; no host locks.
        descriptor = os.open(mount, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.action == "backup":
                print("Verified backup:", export_backup(mount, args.expect_uuid, args.output))
            else:
                if args.confirm_data_only.lower() != args.expect_uuid.lower():
                    raise ValueError("Explicit data-only migration confirmation UUID required")
                previous = migrate(mount, args.expect_uuid, args.base_id, args.backup)
                print("Home migrated. Previous overlay preserved:", previous)
                print("Recreate accounts with previous UIDs; reinstall packages/configuration. No automatic restore.")
        finally:
            os.close(descriptor)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print("ooonana-persistence:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
