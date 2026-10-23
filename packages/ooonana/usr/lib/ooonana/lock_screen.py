"""Small launch policy; actual keyboard grab/password verification stay i3lock/PAM."""
import os
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


def main():
    if len(sys.argv) != 1:
        print("usage: ooonana-lock", file=sys.stderr)
        return 2
    status = live_account_status()
    if status != READY:
        return refuse_lock(status)
    try:
        os.execvpe("i3lock", command(), {**os.environ, "OOONANA_LOCK_VISUALS": "1"})
    except OSError:
        print("Lock unavailable: i3lock could not start. Screen has not been secured.", file=sys.stderr)
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
