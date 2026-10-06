#!/usr/bin/env python3
"""Fresh directory fixtures only; never mount, signal services or open host disks."""
import ast
import errno
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana"))
import persistence as storage
from storage_health import storage_health


def reject(operation, *args):
    try:
        operation(*args)
    except (OSError, ValueError):
        return
    raise AssertionError("Unsafe operation accepted")


with tempfile.TemporaryDirectory(dir="/dev/shm", prefix="ooonana-source-") as temporary, tempfile.TemporaryDirectory(prefix="ooonana-backup-") as backup_temp:
    mount = Path(temporary)
    upper = mount / "overlay/upper"
    (upper / "home/user").mkdir(parents=True)
    (mount / "overlay/work").mkdir()
    (mount / "overlay/base-id").write_text("old-base\n")
    (upper / "home/user/notes").write_text("saved user data")
    (upper / "etc").mkdir()
    (upper / "etc/old-service").write_text("must not mask new base")
    os.link(upper / "home/user/notes", upper / "home/user/linked")
    os.symlink("/outside/not-read", upper / "home/user/link")
    supports_xattrs = True
    try:
        os.setxattr(upper / "home/user/notes", "user.fixture", b"preserve xattrs")
    except OSError as error:
        if error.errno not in (errno.ENOTSUP, errno.EOPNOTSUPP):
            raise
        supports_xattrs = False
        print("SKIP user-xattr assertion: runner tmpfs lacks user extended attributes; all other checks remain active")
    os.mkfifo(upper / "offline-fifo")
    snapshot = storage.tree_entries(upper)
    output = Path(backup_temp) / "verified"
    backup = storage.export_backup(mount, "abcd-1234", output)
    assert storage.tree_entries(backup / "upper") == snapshot
    assert (backup / "upper/home/user/notes").stat().st_ino == (backup / "upper/home/user/linked").stat().st_ino
    # Identical bytes/metadata do not prove a hardlink relationship survived.
    linked = backup / "upper/home/user/linked"
    parent_entry = next(item for item in snapshot if item["path"] == "home/user")
    linked.unlink()
    shutil.copy2(backup / "upper/home/user/notes", linked)
    os.utime(linked.parent, ns=(parent_entry["mtime_ns"], parent_entry["mtime_ns"]))
    reject(storage.migrate, mount, "abcd-1234", "new-base", backup)
    linked.unlink()
    os.link(backup / "upper/home/user/notes", linked)
    os.utime(linked.parent, ns=(parent_entry["mtime_ns"], parent_entry["mtime_ns"]))
    assert storage.tree_entries(backup / "upper") == snapshot
    reject(storage.export_backup, mount, "abcd-1234", output)
    reject(storage.offline_mount, mount, "abcd-1234")  # Not mounted ext4; never accepts arbitrary dirs.
    reject(storage.real_directory, Path("/"))
    os.symlink(upper, mount / "unsafe")
    reject(storage.real_directory, mount / "unsafe")
    (upper / "home/user/notes").write_text("changed after backup")
    reject(storage.migrate, mount, "abcd-1234", "new-base", backup)
    (upper / "home/user/notes").write_text("saved user data")
    # Restore exact saved metadata to model offline, unchanged backup source.
    entry = next(item for item in snapshot if item["path"] == "home/user/notes")
    os.utime(upper / entry["path"], ns=(entry["mtime_ns"], entry["mtime_ns"]))
    actual_copy = storage.copy_tree
    def damaged_copy(source, target, entries, data_only=False):
        actual_copy(source, target, entries, data_only)
        (target / "user/notes").write_text("corrupt fixture copy")
    with patch.object(storage, "check_space", lambda *_: None), patch.object(storage, "copy_tree", damaged_copy):
        reject(storage.migrate, mount, "abcd-1234", "new-base", backup)
    assert (mount / "overlay/base-id").read_text() == "old-base\n"
    assert storage.tree_entries(upper) == snapshot
    with patch.object(storage, "check_space", lambda *_: None):
        previous = storage.migrate(mount, "abcd-1234", "new-base", backup)
    assert previous.is_dir() and storage.tree_entries(previous / "upper") == snapshot
    assert (upper / "home/user/notes").read_text() == "saved user data"
    assert not (upper / "etc").exists()
    assert (mount / "overlay/base-id").read_text() == "new-base\n"
    assert os.readlink(upper / "home/user/link") == "/outside/not-read"
    if supports_xattrs:
        assert os.getxattr(upper / "home/user/notes", "user.fixture") == b"preserve xattrs"
    # Exercise musl's syscall-only API on glibc hosts too.
    actual_libc = storage.ctypes.CDLL(None, use_errno=True)
    with patch.object(storage.ctypes, "CDLL", lambda *_args, **_kwargs: SimpleNamespace(syscall=actual_libc.syscall)):
        old = mount / "syscall-old"
        new = mount / "syscall-new"
        old.mkdir()
        (old / "identity").write_text("old")
        storage.atomic_rename(old, new, 1)
        assert not old.exists() and (new / "identity").read_text() == "old"
        old.mkdir()
        (old / "identity").write_text("new")
        storage.atomic_rename(old, new, 2)
        assert (old / "identity").read_text() == "old" and (new / "identity").read_text() == "new"
        reject(storage.atomic_rename, old, new, 1)
        with patch.object(storage.platform, "machine", lambda: "unknown-abi"):
            reject(storage.atomic_rename, old, new, 2)
    occupied = mount / "occupied"
    occupied.mkdir()
    reject(storage.atomic_rename, previous, occupied, 1)
    assert previous.is_dir() and occupied.is_dir()
    with patch.object(storage.shutil, "disk_usage", lambda _: SimpleNamespace(free=1)):
        reject(storage.check_space, mount, snapshot)

with tempfile.TemporaryDirectory() as temporary:
    metadata = Path(temporary)
    assert storage_health(metadata)["mode"] == "installed"
    (metadata / "persistence-mode").write_text("usb")
    values = dict(f_bavail=1000000, f_frsize=4096, f_blocks=2000000, f_files=10000, f_favail=9000, f_flag=0)
    check = lambda _: SimpleNamespace(**values)
    assert storage_health(metadata, statvfs=check)["level"] == "ok"
    values["f_bavail"] = 20000
    assert storage_health(metadata, statvfs=check)["level"] == "low"
    values["f_bavail"] = 1000
    assert storage_health(metadata, statvfs=check)["level"] == "critical"
    values["f_bavail"] = 1000000
    values["f_flag"] = os.ST_RDONLY
    assert storage_health(metadata, statvfs=check)["readonly"]
    values["f_flag"], values["f_favail"] = 0, 0
    assert storage_health(metadata, statvfs=check)["level"] == "critical"

# Geometry logic without importing GTK or touching display.
source = (root / "packages/ooonana/usr/lib/ooonana/ui/window_controls.py").read_text()
function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "decoration_targets")
namespace = {"WIDTH": 88}
exec(compile(ast.Module(body=[function], type_ignores=[]), "geometry-fixture", "exec"), namespace)
targets = namespace["decoration_targets"]
def client(identifier, **extra):
    return dict(id=identifier, window=identifier, rect=dict(x=-1200, y=40),
                deco_rect=dict(x=0, y=0, width=500, height=24), **extra)
first, second = client(1), client(2)
tree = dict(nodes=[dict(type="workspace", name="1", nodes=[dict(layout="tabbed", focus=[2, 1], nodes=[first, second])])])
assert set(targets(tree, {"1"})) == {2}
second["fullscreen_mode"] = 1
assert targets(tree, {"1"}) == {}
second["fullscreen_mode"] = 0
assert targets(tree, {"2"}) == {}
assert targets(tree, {"1"})[2] == (-788, 40, 24)
workspace = tree["nodes"][0]
workspace["fullscreen_mode"] = 1  # Normal i3 workspace, not client fullscreen.
assert set(targets(tree, {"1"})) == {2}
workspace["nodes"] = []
workspace["floating_nodes"] = [dict(id=10, rect=dict(x=-1200, y=40, width=500, height=330), nodes=[first]),
                                dict(id=20, rect=dict(x=-1200, y=40, width=500, height=330), nodes=[second])]
workspace["focus"] = [20, 10]
assert set(targets(tree, {"1"})) == {2}
workspace["focus"] = [10, 20]
assert set(targets(tree, {"1"})) == {1}
second["fullscreen_mode"] = 2
tree["nodes"].append(dict(type="workspace", name="2", nodes=[client(3)]))
assert targets(tree, {"1", "2"}) == {}

# Upgrade default action only; never downgrade installed getty or custom hooks.
source = (root / "scripts/build-ooonana-core-package.sh").read_text()
hook = source.split('cat >"$OUT_DIR/hooks/$runtime_id.healthcheck" <<\'CHECK\'\n', 1)[1].split('\nCHECK', 1)[0]
with tempfile.TemporaryDirectory() as temporary:
    prefix = Path(temporary)
    (prefix / "usr/bin").mkdir(parents=True)
    (prefix / "etc").mkdir()
    for helper in ("ooonana", "ooonana-memory", "ooonana-panel-start", "ooonana-window-list", "ooonana-shutdown-cleanup", "ooonana-storage-watch", "ooonana-persistence", "gzip"):
        path = prefix / "usr/bin" / helper
        path.write_text('#!/bin/sh\necho "ooonana 0.9.9"\n')
        path.chmod(0o755)
    environment = {**os.environ, "OOONANA_ROOT": str(prefix), "OOONANA_PKG_VERSION": "0.9.9"}
    auth = "tty1::respawn:/bin/busybox getty 38400 tty1\n"
    for shutdown, changed in (("::shutdown:/bin/umount -a -r\n", True),
                              ("::shutdown:/custom/shutdown\n", False),
                              ("::shutdown:/bin/umount -a -r\n::shutdown:/custom/hook\n", False)):
        inittab = prefix / "etc/inittab"
        inittab.write_text(auth + shutdown)
        subprocess.run(["sh"], input=hook, text=True, env=environment, check=True, capture_output=True)
        assert inittab.read_text().startswith(auth)
        assert ("ooonana-shutdown-cleanup --from-init" in inittab.read_text()) == changed

assert "poweroff -f" not in (root / "packages/ooonana/usr/bin/bunana").read_text()
assert "reboot -f" not in (root / "packages/ooonana/etc/profile.d/ooonana-shell.sh").read_text()
assert "--from-init" in (root / "scripts/build-scratch-rootfs.sh").read_text()
cleanup = (root / "packages/ooonana/usr/bin/ooonana-shutdown-cleanup").read_text()
context = cleanup.split("shutdown_context_allowed() {\n", 1)[1].split("\n}", 1)[0]
predicate = "shutdown_context_allowed() {\n" + context + '\n}\nshutdown_context_allowed "$@"'
for parent, executable, command, hook, allowed in (
        ("1", "/bin/busybox", "/bin/busybox init ", "yes", True),
        ("1", "/bin/busybox", "/sbin/init ", "yes", True),
        ("1", "/bin/busybox", "init ", "yes", True),
        ("1", "/mnt/ooonana-shutdown/bin/busybox", "init ", "yes", True),
        ("1", "/mnt/ooonana-shutdown/lib/ld-musl-x86_64.so.1", "init ", "yes", True),
        ("1", "/mnt/ooonana-shutdown/lib/ld-musl-x86_64.so.1", "/bin/sh ", "yes", False),
        ("1", "/usr/lib/ld-musl-x86_64.so.1", "init ", "yes", False),
        ("1", "/bin/busybox", "/bin/sh ", "yes", False),
        ("1", "/bin/busybox", "/bin/busybox sh ", "yes", False),
        ("1", "/bin/busybox", "init ", "no", False),
        ("2", "/bin/busybox", "init ", "yes", False)):
    result = subprocess.run(["sh", "-c", predicate, "fixture", parent, executable, command, hook])
    assert (result.returncode == 0) == allowed
ram_cleanup = (root / "scripts/lib/live-shutdown.sh").read_text()
steps = ("pivot_root . oldroot", "umount /oldroot", "umount /persist",
         "losetup -d /dev/loop1", "mount -o remount,ro /iso", "umount /iso")
assert [ram_cleanup.index(step) for step in steps] == sorted(ram_cleanup.index(step) for step in steps)
assert "umount -l" not in ram_cleanup and "umount -f" not in ram_cleanup
assert "OOONANA_SHUTDOWN_CLEANUP_FAILED" in ram_cleanup
# Two closed rescue children must leave PID1's shutdown action running.
hold = ram_cleanup.split("shutdown_failed() {\n", 1)[1].split("\n}\n", 1)[0]
assert "exec " not in "\n".join(line for line in hold.splitlines() if not line.lstrip().startswith("#"))
with tempfile.TemporaryDirectory() as temporary:
    fixture = Path(temporary)
    script = fixture / "hold.sh"
    script.write_text("""#!/bin/sh
set -eu
rescue_count=0
sleep() { :; }
ooonana_rescue_child() {
  rescue_count=$((rescue_count + 1))
  echo "RESCUE_CHILD:$rescue_count"
  [ "$rescue_count" -lt 3 ] || exit 73
  return 1
}
shutdown_failed() {
""" + hold.replace("[ -x /mnt/ooonana-shutdown/lib/ld-musl-x86_64.so.1 ]", "true").replace(
    "/mnt/ooonana-shutdown/lib/ld-musl-x86_64.so.1 /mnt/ooonana-shutdown/bin/busybox sh", "ooonana_rescue_child") + "\n}\nshutdown_failed 1\necho UNSAFE_SHUTDOWN_RETURN\n")
    result = subprocess.run(["sh", str(script)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 73 and "RESCUE_CHILD:3" in result.stdout
    assert "UNSAFE_SHUTDOWN_RETURN" not in result.stdout
    assert result.stderr.count("OOONANA_SHUTDOWN_HELD") == 2
print("PERSISTENCE_MAINTENANCE_OK backup/xattrs/hardlinks/tamper/atomic-migration/space/geometry/shutdown-policy")
