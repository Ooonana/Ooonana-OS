"""Read-only live-account lockout guard; never verifies a password or edits auth."""
import os
from pathlib import Path
import pwd
import stat
import sys

READY, NO_SECRET, UNKNOWN = 0, 3, 4


def account_status(path, name):
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024:
            return UNKNOWN
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            data = stream.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            return UNKNOWN
        records = [line.split(b":") for line in data.splitlines() if line.partition(b":")[0] == name.encode()]
        if len(records) != 1 or len(records[0]) != 9:
            return UNKNOWN
        secret = records[0][1]
        return READY if secret and not secret.startswith((b"!", b"*")) else NO_SECRET
    except (OSError, UnicodeError, ValueError):
        return UNKNOWN
    finally:
        if descriptor is not None:
            os.close(descriptor)


def main():
    # Existing live sudo/doas authorization only; no new setuid executable.
    if os.getuid() != 0 or len(sys.argv) != 2 or not sys.argv[1].isascii() or not sys.argv[1].isdecimal():
        return UNKNOWN
    try:
        uid = int(sys.argv[1])
        if not 0 <= uid < 2**31:
            return UNKNOWN
        # Sudo caller may ask only about its own account. Direct root is trusted.
        if os.environ.get("SUDO_UID", str(uid)) != str(uid):
            return UNKNOWN
        return account_status(Path("/etc/shadow"), pwd.getpwuid(uid).pw_name)
    except (KeyError, ValueError):
        return UNKNOWN


if __name__ == "__main__":
    raise SystemExit(main())
