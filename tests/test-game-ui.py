#!/usr/bin/env python3
"""Owned PTY only: small/restore state, controls, cleanup and launcher fallback."""
import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packages/ooonana/usr/lib/ooonana/oonana_game.py"
spec = importlib.util.spec_from_file_location("game", SCRIPT)
game = importlib.util.module_from_spec(spec); spec.loader.exec_module(game)
board = game.Game(width=80, height=28)
board.score, board.lives, board.paused = 123, 2, True
before = copy.deepcopy(vars(board))
for columns, rows in ((0, 0), (1, 1), (20, 6), (40, 12), (79, 30)):
    notice = game.viewport_message(board, columns, rows)
    assert notice is not None and len(notice) <= max(0, rows - 1)
    assert all(len(line) < max(1, columns) for line in notice)
assert game.viewport_message(board, 80, 30) is None
assert vars(board) == before, "Viewport change must not reset progress/pause"

master, slave = pty.openpty()
def resize(columns, rows):
    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
resize(80, 30)
child = subprocess.Popen([sys.executable, "-B", str(SCRIPT)], stdin=slave, stdout=slave, stderr=slave,
    env={**os.environ, "NO_COLOR": "1", "PYTHONDONTWRITEBYTECODE": "1"})
os.close(slave)
transcript = bytearray()
def expect(value):
    deadline = time.monotonic() + 8
    while value.encode() not in transcript:
        assert child.poll() is None and time.monotonic() < deadline, transcript[-2000:]
        if select.select([master], [], [], .05)[0]: transcript.extend(os.read(master, 32768))
def send(value):
    transcript.clear(); os.write(master, value.encode())
try:
    expect("PLAY")
    send("p"); expect("PAUSED")
    transcript.clear(); resize(20, 6); expect("Terminal too small")
    transcript.clear(); resize(80, 30); expect("PAUSED")
    assert b"Score:0" in transcript and b"Lives:3" in transcript
    send("p"); expect("PLAY")
    send("q"); child.wait(timeout=5)
    assert child.returncode == 0
    while select.select([master], [], [], .05)[0]:
        try: transcript.extend(os.read(master, 32768))
        except OSError: break  # PTY slave closed normally.
    assert b"\x1b[?25h\x1b[0m\x1b[?1049l" in transcript
finally:
    if child.poll() is None: child.terminate(); child.wait(timeout=5)
    os.close(master)

with tempfile.TemporaryDirectory() as temporary:
    work = Path(temporary)
    log = work / "calls"
    stub = '#!/usr/bin/python3\nimport json,os,sys\nopen(os.environ["GAME_QA_CALLS"],"w").write(json.dumps(sys.argv))\n'
    for name in ("xterm", "alacritty"):
        (work / name).write_text(stub); (work / name).chmod(0o755)
    env = {**os.environ, "PATH": str(work), "GAME_QA_CALLS": str(log)}
    launcher = ROOT / "packages/ooonana/usr/bin/ooonana-game-launch"
    assert subprocess.run(["/bin/sh", str(launcher)], env=env).returncode == 0
    arguments = json.loads(log.read_text())
    assert arguments[0].endswith("/xterm") and arguments[-2:] == ["-e", "oonana"]
    assert arguments[arguments.index("-fs") + 1] == "11"
    (work / "xterm").unlink()
    assert subprocess.run(["/bin/sh", str(launcher)], env=env).returncode == 0
    assert json.loads(log.read_text())[0].endswith("/alacritty")
    (work / "alacritty").unlink()
    refused = subprocess.run(["/bin/sh", str(launcher)], env=env, input="", text=True, capture_output=True)
    assert refused.returncode == 127 and "terminal unavailable" in refused.stderr
print("GAME_UI_OK bounded small viewport, preserved pause/progress, resize recovery, quit/TTY cleanup, terminal fallback")
