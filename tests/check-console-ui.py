#!/usr/bin/env python3
"""Render console UI in private Xvfb/xterm PTY. Never boot/shut down host."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
work = parser.parse_args().output.resolve()
assert str(work).startswith("/var/tmp/ooonana-console-ui-") and not work.exists()
assert os.environ.get("DISPLAY"), "Run under xvfb-run with a private display"
assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1", "Private test display opt-in required"
work.mkdir(mode=0o755)
helper = work / "console-ui.sh"
helper.write_text((ROOT / "packages/ooonana/usr/lib/ooonana/console-ui.sh").read_text().replace(
    "ooonana_ui_device=/dev/tty1", "ooonana_ui_device=/dev/tty"))
fixture = work / "fixture.sh"
fixture.write_text(f"""set -eu
. {shlex.quote(str(helper))}
cat() {{ :; }} # Only the kernel command line read; never inspect host boot.
ooonana_console_begin {shlex.quote(str(ROOT / 'packages/ooonana/usr/share/ooonana/boot-logo.txt'))}
ooonana_console_stage 'Finding boot media'
printf boot >{shlex.quote(str(work / 'state'))}
sleep 3
ooonana_console_begin {shlex.quote(str(ROOT / 'packages/ooonana/usr/share/ooonana/boot-logo.txt'))}
ooonana_console_stage 'Closing session'
printf shutdown >{shlex.quote(str(work / 'state'))}
ooonana_console_wait 2
ooonana_console_stage 'Saving changes'
printf saved >{shlex.quote(str(work / 'state'))}
sleep 3
ooonana_console_end
""")
process = subprocess.Popen(["xterm", "-geometry", "80x25+0+0", "-fa", "DejaVu Sans Mono", "-fs", "12",
                            "-bg", "#101317", "-fg", "#f5f5f7", "-e", "sh", str(fixture)])
try:
    for state in ("boot", "shutdown", "saved"):
        deadline = time.monotonic() + 10
        while not (work / "state").exists() or (work / "state").read_text() != state:
            assert process.poll() is None and time.monotonic() < deadline, state
            time.sleep(0.05)
        time.sleep(0.15)
        subprocess.run(["import", "-window", "root", str(work / (state + ".png"))], check=True, timeout=5)
    process.wait(timeout=5)
finally:
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=5)
print("CONSOLE_UI_CAPTURE_OK", work)
