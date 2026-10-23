"""Small launch policy; actual keyboard grab/password verification stay i3lock/PAM."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "ui"))
from ui_preferences import resolved_theme


def command():
    return ["i3lock", "--color", "f5f5f7" if resolved_theme() == "light" else "101317",
            "--show-keyboard-layout", "--show-failed-attempts"]


def main():
    if len(sys.argv) != 1:
        print("usage: ooonana-lock", file=sys.stderr)
        return 2
    try:
        os.execvp("i3lock", command())
    except OSError:
        print("Lock unavailable: i3lock could not start. Screen has not been secured.", file=sys.stderr)
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
