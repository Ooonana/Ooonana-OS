#!/usr/bin/env python3
"""Stub setters only; never alter user's desktop or wallpaper preference."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temporary:
    work = Path(temporary)
    binaries = work / 'bin'
    binaries.mkdir()
    image = work / 'Original wallpaper.jpg'
    image.write_bytes(b'fixture')
    for name in ('ooonana-wallpaper-fit', 'feh', 'hsetroot'):
        path = binaries / name
        path.write_text('#!/bin/sh\nprintf "%s\\n" "$0" "$@" > "$CALLS"\nexit "${SETTER_EXIT:-0}"\n')
        path.chmod(0o755)
    log = work / 'calls'
    home = work / 'home'
    env = {**os.environ, 'HOME': str(home), 'PATH': str(binaries) + ':' + os.environ['PATH'], 'CALLS': str(log)}
    command = ['sh', str(ROOT / 'packages/ooonana/usr/bin/ooonana-wallpaper')]
    result = subprocess.run(command + [str(image)], env=env, capture_output=True)
    assert result.returncode == 0
    assert 'ooonana-wallpaper-fit' in log.read_text()
    config = home / '.config/ooonana'
    assert (config / 'wallpaper').read_text().strip() == str(image)
    before = (config / 'wallpaper').read_bytes()
    result = subprocess.run(command + ['--mode', 'fill', str(image)], env={**env, 'SETTER_EXIT': '1'}, capture_output=True)
    assert result.returncode and (config / 'wallpaper').read_bytes() == before
    assert (config / 'wallpaper-mode').read_text().strip() == 'fit'
    result = subprocess.run(command + ['--apply-saved'], env=env, capture_output=True)
    assert result.returncode == 0 and (config / 'wallpaper').read_bytes() == before
    assert not list(config.glob('*.??????'))
print('ok wallpaper: canonical fit, spaces, success-only save, saved preference preserved')
