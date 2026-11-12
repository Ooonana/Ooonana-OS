"""Small launch policy; actual keyboard grab/password verification stay i3lock/PAM."""
import os
import hashlib
import re
import stat
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).parent / "ui"))
from ui_preferences import resolved_theme
from lock_readiness import READY, NO_SECRET, UNKNOWN, account_status


def live_account_status():
    try:
        if Path("/etc/ooonana/system-mode").read_text()[:32].strip() == "installed":
            return READY  # Installed/custom PAM remains authoritative, no shadow precheck.
    except OSError:
        pass
    uid = os.getuid()
    if uid == 0:
        import pwd
        return account_status(Path("/etc/shadow"), pwd.getpwuid(uid).pw_name)
    check = ["/usr/bin/python3", "-I", "/usr/lib/ooonana/lock_readiness.py", str(uid)]
    for authority in (["sudo", "-n", "--"], ["doas", "-n"]):
        try:
            result = subprocess.run(authority + check, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3).returncode
            if result in (READY, NO_SECRET):
                return result
        except (OSError, subprocess.SubprocessError):
            pass
    return UNKNOWN


def refuse_lock(status):
    detail = ("Live account has no usable local password. Set account password through Ooonana Setup before locking."
              if status == NO_SECRET else "Cannot confirm live account can unlock. Check account password and administrator access before locking.")
    print(detail + " Screen has not been secured.", file=sys.stderr)
    try:
        subprocess.run(["notify-send", "--app-name=Ooonana", "--urgency=critical", "--", "Lock unavailable", detail],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    except (OSError, subprocess.SubprocessError):
        pass
    return 1


def command():
    return ["i3lock", "--color", "f5f5f7" if resolved_theme() == "light" else "101317",
            "--show-keyboard-layout", "--show-failed-attempts"]


def quiet_background_streams():
    # The ready parent exits after grabs, but its daemon keeps inherited pipes
    # open. GUI/suspend callers must receive EOF without waiting for unlock.
    sys.stdout.flush()
    sys.stderr.flush()
    with open(os.devnull, "wb") as sink:
        for descriptor in (1, 2):
            if not os.isatty(descriptor):
                os.dup2(sink.fileno(), descriptor)


def claim_display():
    import fcntl
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", str(Path.home() / ".local/state"))) / "ooonana"
    runtime.mkdir(parents=True, exist_ok=True)
    if runtime.is_symlink() or runtime.stat().st_uid != os.getuid():
        raise OSError("Unsafe session lock directory")
    display = re.sub(r"\.0$", "", os.environ.get("DISPLAY", "default"))
    name = hashlib.sha256(display.encode()).hexdigest()[:16]
    descriptor = os.open(runtime / f"screen-lock-{name}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise OSError("Unsafe session lock file")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Keep ownership in vendor's forked/foreground locker until it exits.
        os.set_inheritable(descriptor, True)
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def main():
    if sys.argv[1:] not in ([], ["--foreground"]):
        print("usage: ooonana-lock [--foreground]", file=sys.stderr)
        return 2
    status = live_account_status()
    if status != READY:
        return refuse_lock(status)
    try:
        descriptor = claim_display()
    except BlockingIOError:
        print("Another lock request is active; no new locker submitted.", file=sys.stderr)
        return 75
    except OSError:
        print("Lock unavailable: session ownership could not be secured.", file=sys.stderr)
        return 1
    try:
        args = command() + (["--nofork"] if sys.argv[1:] else [])
        if not sys.argv[1:]:
            quiet_background_streams()
        os.execvpe("i3lock", args, {**os.environ, "OOONANA_LOCK_VISUALS": "1"})
    except OSError:
        print("Lock unavailable: i3lock could not start. Screen has not been secured.", file=sys.stderr)
        return 127
    finally:
        # Real exec never returns; this also closes descriptors on launch errors.
        if descriptor is not None:
            os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
