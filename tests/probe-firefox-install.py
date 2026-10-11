#!/usr/bin/env python3
"""Explicit network opt-in: actual nonroot wrapper install/update, private home."""
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import time

if os.getuid() != 1000 or os.environ.get("OOONANA_FIREFOX_DOWNLOAD") != "1" or os.environ.get("HOME") != "/home/ooonana":
    raise SystemExit("Require disposable UID1000 Firefox download runner")
assert Path("/source/tests/run-candidate-gui.sh").is_file()
assert not Path("/home/ooonana/.local/share/flatpak").exists(), "Require fresh private home"
for operation in ("setup", "status", "update"):
    # Flatpak intentionally declines prompts on non-TTY stdin. Exercise the
    # actual interactive launcher, without changing its production defaults.
    pid, terminal = pty.fork()
    if pid == 0:
        os.execvp("ooonana-firefox", ["ooonana-firefox", operation])
    deadline, pending, status = time.monotonic() + 1100, b"", None
    try:
        while status is None:
            assert time.monotonic() < deadline, "Firefox operation timed out"
            if select.select([terminal], [], [], 0.2)[0]:
                try:
                    data = os.read(terminal, 65536)
                except OSError:
                    data = b""
                if data:
                    sys.stdout.buffer.write(data)
                    sys.stdout.flush()
                    pending = (pending + data)[-8192:]
                    if b"[y/n]" in pending.lower():
                        os.write(terminal, b"y\n")
                        pending = b""
            finished, child_status = os.waitpid(pid, os.WNOHANG)
            if finished:
                status = child_status
        assert os.waitstatus_to_exitcode(status) == 0, (operation, status)
    finally:
        os.close(terminal)
        if status is None:
            os.killpg(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
    print("REAL_FIREFOX_WRAPPER", operation, "passed", flush=True)
location = subprocess.check_output(["flatpak", "--user", "info", "--show-location", "org.mozilla.firefox"], text=True).strip()
assert Path(location).resolve().is_relative_to(Path("/home/ooonana/.local/share/flatpak"))
print(json.dumps({"nonroot": True, "setup": "passed", "update": "passed", "private_install": location}), flush=True)
