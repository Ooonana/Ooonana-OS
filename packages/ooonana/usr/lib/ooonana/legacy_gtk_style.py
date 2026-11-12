"""Retire only byte-exact old generated CSS; retain backup and custom edits."""
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile

LEGACY_HASHES = {
    "e5b6b74469030a7e4a215808a86b6deaf59e9ed1f519a2639cdb6d54cdbfb868",
    "79fb26d685536ec2b4ed377f1bc319fba8340752d0f031a704cae6b83069fc7b",
    "f927f7cacdb1e0627995184046c920a1439a4c987f439e4f9c0f16c91e9015c9",
}
MARKER = b"/* Ooonana appearance now follows named GTK themes; custom CSS belongs here. */\n"


def retire(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 131072:
            return
        content = stream.read(131073)
    if content == MARKER:
        return
    digest = hashlib.sha256(content).hexdigest()
    if digest not in LEGACY_HASHES:
        if b"@define-color ooonana_bg" in content:
            print("Theme: customized GTK CSS retained; it may override live appearance.", file=sys.stderr)
        return
    backup = path.with_name("gtk.css.ooonana-legacy-" + digest[:12])
    try:
        descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        descriptor = os.open(backup, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode) or stream.read(len(content) + 1) != content:
                raise ValueError("Legacy CSS backup differs; original retained")
    else:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    descriptor, temporary = tempfile.mkstemp(prefix=".gtk.css.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), stat.S_IMODE(before.st_mode))
            stream.write(MARKER)
            stream.flush()
            os.fsync(stream.fileno())
        after = path.stat(follow_symlinks=False)
        if (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size) != (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size):
            raise ValueError("GTK CSS changed during migration; original retained")
        os.replace(temporary, path)
        print("Theme: legacy GTK style migrated with backup; reopen older apps once to follow live appearance.", file=sys.stderr)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        retire(Path(sys.argv[1]) / "gtk-3.0/gtk.css")
    except (OSError, ValueError) as error:
        print("Theme: custom GTK CSS retained; " + str(error), file=sys.stderr)
