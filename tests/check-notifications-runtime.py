#!/usr/bin/env python3
"""Check notification actions on an isolated D-Bus session with test messages."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme, run  # noqa: E402
from notifications_app import NotificationsWindow  # noqa: E402
from notification_utils import read_history  # noqa: E402


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path)
parser.add_argument("--config", type=Path, default=Path("/etc/ooonana/dunstrc"))
args = parser.parse_args()
if not os.environ.get("OOONANA_NOTIFICATION_TEST_SESSION"):
    raise SystemExit("Run through a dedicated dbus-run-session with OOONANA_NOTIFICATION_TEST_SESSION=1.")
if not args.config.is_file():
    raise SystemExit(f"Notification configuration missing: {args.config}")

with tempfile.TemporaryFile() as log:
    daemon = subprocess.Popen(["dunst", "-config", str(args.config)], stdout=log, stderr=log)
    window = None
    passed = False
    try:
        time.sleep(0.5)
        for _attempt in range(30):
            rc, _text = run(["dunstctl", "is-paused"], timeout=2)
            if rc == 0:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Isolated Dunst did not start")
        subprocess.run(["notify-send", "-a", "Ooonana test", "Notification center ready", "History, clear, and Do Not Disturb controls.", "-t", "1000"], check=True)
        apply_theme()
        window = NotificationsWindow()
        window.show_all()
        stage = 0
        capture_ready_at = 0
        deadline = time.monotonic() + 20

        def verify():
            global passed, stage, capture_ready_at
            try:
                if time.monotonic() > deadline:
                    raise AssertionError(f"Notification stage {stage} did not settle")
                if window.refreshing:
                    return True
                if stage == 0 and len(window.records) == 1:
                    assert window.records[0]["summary"] == "Notification center ready"
                    if args.output:
                        capture_ready_at = time.monotonic() + 0.6
                        stage = 6
                        return True
                    window.pause.set_active(True)
                    stage = 1
                elif stage == 6 and time.monotonic() >= capture_ready_at:
                    root = Gdk.get_default_root_window()
                    pixels = Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    pixels.savev(str(args.output), "png", [], [])
                    window.pause.set_active(True)
                    stage = 1
                elif stage == 1 and run(["dunstctl", "is-paused"], timeout=2)[1].strip() == "true" and window.pause.get_sensitive():
                    window.pause.set_active(False)
                    stage = 2
                elif stage == 2 and run(["dunstctl", "is-paused"], timeout=2)[1].strip() == "false":
                    window.perform(["history-rm", str(window.records[0]["id"])])
                    stage = 3
                elif stage == 3 and not window.records:
                    assert run(["dunstctl", "count", "history"], timeout=2)[1].strip() == "0"
                    subprocess.run(["notify-send", "-a", "Ooonana test", "Clear test", "Second test notification."], check=True)
                    run(["dunstctl", "close-all"], timeout=2)
                    window.refresh()
                    stage = 4
                elif stage == 4 and len(window.records) == 1:
                    window.perform(["history-clear"])
                    stage = 5
                elif stage == 5 and not window.records:
                    assert run(["dunstctl", "count", "history"], timeout=2)[1].strip() == "0"
                    passed = True
                    print("NOTIFICATION_CENTER_RUNTIME_OK", flush=True)
                    window.destroy()
                    return False
                return True
            except Exception:
                traceback.print_exc()
                print("History diagnostic:", read_history(), flush=True)
                print("Window records:", window.records, flush=True)
                log.seek(0)
                print("Dunst diagnostic:", log.read().decode(errors="replace"), flush=True)
                window.destroy()
                return False

        GLib.timeout_add(150, verify)
        Gtk.main()
    finally:
        if daemon.poll() is None:
            daemon.terminate()
            try:
                daemon.wait(timeout=3)
            except subprocess.TimeoutExpired:
                daemon.kill()
                daemon.wait()
    raise SystemExit(0 if passed else 1)
