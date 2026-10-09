#!/usr/bin/env python3
"""Opt-in diagnostic refuses ordinary execution before any mount/state writes."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
runner = root / "tests/run-openvino-transport.sh"
probe = root / "tests/probe-openvino-transport.py"
ast.parse(probe.read_text())
subprocess.run(["bash", "-n", str(runner)], check=True)
environment = {**os.environ, "OOONANA_TRANSPORT_ISOLATED": "0", "OOONANA_TRANSPORT_WORKER": "0"}
with tempfile.TemporaryDirectory() as temporary:
    sentinel = Path(temporary) / "keep"
    sentinel.write_text("unchanged")
    for command, expected in (
        (["bash", str(runner)], "Usage"),
        (["bash", str(runner), "--worker", temporary, temporary, temporary, temporary], "private namespace"),
        ([sys.executable, "-B", str(probe), "--source", str(root), "--qa", temporary], "disposable Linux"),
    ):
        call = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=10)
        assert call.returncode and expected in call.stderr, (command, call.stdout, call.stderr)
        assert list(Path(temporary).iterdir()) == [sentinel] and sentinel.read_text() == "unchanged"
    invalid = subprocess.run(["bash", str(runner)],
                             env={**environment, "OOONANA_TRANSPORT_INSTALL_APP": "invalid"},
                             capture_output=True, text=True, timeout=10)
    assert invalid.returncode and "Invalid app-install opt-in" in invalid.stderr
    assert list(Path(temporary).iterdir()) == [sentinel] and sentinel.read_text() == "unchanged"
print("ok openvino-transport diagnostic: syntax, opt-in/worker refusal, unrelated state preserved")
