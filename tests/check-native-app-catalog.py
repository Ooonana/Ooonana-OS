#!/usr/bin/env python3
"""Batch every native window/page on private UID1000 display, no backend writes."""
import os
from pathlib import Path
import subprocess
import sys

if os.environ.get("OOONANA_GUI_TEST_DISPLAY") != "1" or os.getuid() == 0:
    raise SystemExit("Dedicated test display and nonroot test user required")
root = Path(__file__).resolve().parents[1]
cases = [(app, None) for app in ("launcher", "wifi", "bluetooth", "packages", "ai", "setup",
                               "music", "sound", "brightness", "power", "notifications", "health", "updates",
                               "wifi-map", "bluetooth-map", "wifi-credentials", "bluetooth-pair")]
cases += [("settings", page) for page in ("overview", "network", "hardware", "appearance", "apps", "system")]
cases += [("tasks", page) for page in ("processes", "performance")]
failed = []
for app, page in cases:
    name = f"{app}-{page}" if page else app
    command = [sys.executable, str(root / "tests/capture-native-ui.py"), app, f"/qa/{name}.png",
               "--sample-data", "--require-fit", "--delay-ms", "800"]
    if page:
        command += ["--page", page]
    result = subprocess.run(command, timeout=8)
    if result.returncode:
        failed.append(name)
assert not failed, failed
print(f"NATIVE_APP_CATALOG_OK {len(cases)} native windows/pages; bounds and accessible window controls; mocked backends")
