#!/usr/bin/env python3
"""Wallpaper action argument safety and silent failure feedback; no real desktop."""
import ast
import configparser
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / 'packages/ooonana'
actions = OVERLAY / 'usr/share/nemo/actions'
wallpaper = configparser.ConfigParser(interpolation=None)
wallpaper.read(actions / 'ooonana-wallpaper.nemo_action')
assert wallpaper['Nemo Action']['Exec'] == 'ooonana-nemo-wallpaper %F'
assert wallpaper['Nemo Action']['Selection'] == 's'
assert wallpaper['Nemo Action']['UriScheme'] == 'file'
assert wallpaper['Nemo Action']['Quote'] == 'double'
appearance = configparser.ConfigParser(interpolation=None)
appearance.read(actions / 'ooonana-appearance.nemo_action')
assert appearance['Nemo Action']['Exec'] == 'ooonana-settings --page appearance'
defaults = configparser.ConfigParser(interpolation=None)
defaults.read(OVERLAY / 'usr/share/glib-2.0/schemas/20_ooonana-nemo.gschema.override')
assert defaults['org.cinnamon.desktop.media-handling']['automount'] == 'false'
assert defaults['org.cinnamon.desktop.media-handling']['automount-open'] == 'false'
assert defaults['org.cinnamon.desktop.media-handling']['autorun-never'] == 'true'
assert 'change-background.nemo_action' in ast.literal_eval(defaults['org.nemo.plugins']['disabled-actions'])

with tempfile.TemporaryDirectory(prefix='ooonana-nemo-action-') as folder:
    work = Path(folder)
    backend = work / 'ooonana-wallpaper'
    backend.write_text('#!/bin/sh\nprintf "%s\\0" "$@" >"$CAPTURE"\nexit "${FAILURE:-0}"\n')
    backend.chmod(0o755)
    notify = work / 'notify-send'
    notify.write_text('#!/bin/sh\nprintf "%s\\0" "$@" >"$NOTICE"\n')
    notify.chmod(0o755)
    image = work / 'QA "image" $(touch unexpected) 한글.png'
    image.write_bytes(b'owned fixture; image decoding belongs to wallpaper backend')
    env = dict(os.environ, PATH=str(work) + ':' + os.environ['PATH'],
               CAPTURE=str(work / 'args'), NOTICE=str(work / 'notice'))
    command = ['sh', str(OVERLAY / 'usr/bin/ooonana-nemo-wallpaper'), str(image)]
    result = subprocess.run(command, env=env, cwd=work, capture_output=True)
    assert result.returncode == 0
    assert (work / 'args').read_bytes() == str(image).encode() + b'\0'
    assert not (work / 'unexpected').exists()
    assert not (work / 'notice').exists()
    result = subprocess.run(command, env={**env, 'FAILURE': '1'}, cwd=work, capture_output=True)
    assert result.returncode == 1
    notice = (work / 'notice').read_bytes()
    assert b'boolean:suppress-sound:true' in notice
    assert b'Wallpaper unchanged' in notice
    assert image.name.encode() not in notice

print('NEMO_ACTION_SAFETY_OK')
