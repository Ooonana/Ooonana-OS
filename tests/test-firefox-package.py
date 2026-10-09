#!/usr/bin/env python3
"""No downloads: launcher commands isolated behind fixture Flatpak/id."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
launcher = ROOT / "packages/firefox/rootfs/usr/bin/ooonana-firefox"
with tempfile.TemporaryDirectory() as temporary:
    work = Path(temporary)
    log = work / "calls"
    mock = work / "flatpak"
    mock.write_text('''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['CALLS'], 'a') as output:
    output.write(json.dumps(sys.argv[1:]) + '\\n')
if 'remotes' in sys.argv:
    print('flathub\\t' + os.environ.get('REMOTE_URL', 'https://dl.flathub.org/repo/'))
if 'info' in sys.argv and os.environ.get('MISSING') == '1':
    sys.exit(1)
''')
    mock.chmod(0o755)
    (work / "id").write_text('#!/bin/sh\nprintf "%s\\n" "${FIXTURE_UID:-1000}"\n')
    (work / "id").chmod(0o755)
    (work / "notify-send").write_text('#!/bin/sh\nexit 0\n')
    (work / "notify-send").chmod(0o755)
    mode_file = work / 'persistence-mode'
    env = {**os.environ, "PATH": str(work) + ":" + os.environ['PATH'], "CALLS": str(log),
           "OOONANA_LIVE_MODE_FILE": str(mode_file), "OOONANA_FIREFOX_ALLOW_VOLATILE": '0'}
    def run(*args, **overrides):
        log.write_text('')
        result = subprocess.run(['sh', str(launcher), *args], env={**env, **overrides}, capture_output=True, text=True)
        return result, [json.loads(line) for line in log.read_text().splitlines()]
    result, calls = run('setup')
    assert result.returncode == 0 and calls[-1] == ['--user', 'install', 'flathub', 'org.mozilla.firefox']
    for overrides in ({'FIXTURE_UID': '0'}, {'REMOTE_URL': 'https://bad.example.invalid/repo/'}):
        result, calls = run('setup', **overrides)
        assert result.returncode and not any('install' in call or 'remote-add' in call for call in calls)
    result, calls = run('run', 'https://example.invalid/a?x=1&y=2', '--private-window')
    assert result.returncode == 0 and calls[-1][-2:] == ['https://example.invalid/a?x=1&y=2', '--private-window']
    result, calls = run('run', MISSING='1')
    assert result.returncode and not any('run' in call for call in calls)
    assert run('status', 'unexpected')[0].returncode == 2
    assert run('update')[1][-1] == ['--user', 'update', 'org.mozilla.firefox']
    for mode in ('ram', 'usb-temporary', '', 'invalid'):
        mode_file.write_text(mode + '\n')
        for operation in ('setup', 'update'):
            result, calls = run(operation)
            assert result.returncode and not calls, (mode, operation, calls)
        # Queries and already installed browser launches do not download.
        assert run('status')[0].returncode == 0
        assert run('run')[0].returncode == 0
    for mode in ('ram', 'usb-temporary'):
        mode_file.write_text(mode + '\n')
        for operation in ('setup', 'update'):
            result, calls = run(operation, OOONANA_FIREFOX_ALLOW_VOLATILE='1')
            assert result.returncode == 0 and 'WARNING' in result.stderr
    mode_file.write_text('usb\n')
    assert run('setup')[0].returncode == 0
    assert run('update')[0].returncode == 0
    mode_file.unlink()
    mode_file.mkdir()  # Present but unreadable as a mode file: fail closed.
    for operation in ('setup', 'update'):
        result, calls = run(operation)
        assert result.returncode and not calls
    mode_file.rmdir()
    mode_file.symlink_to(work / 'missing-mode')
    for operation in ('setup', 'update'):
        result, calls = run(operation)
        assert result.returncode and not calls
    repo = work / 'repo'
    subprocess.run(['bash', str(ROOT / 'scripts/build-firefox-package.sh'), '--out-dir', str(repo)], check=True)
    archive = repo / 'archives/firefox-1.0.0.tar.gz'
    original = archive.read_bytes()
    subprocess.run(['bash', str(ROOT / 'scripts/build-firefox-package.sh'), '--out-dir', str(repo)], check=True)
    assert archive.read_bytes() == original
print('ok firefox launcher: user setup, live-storage guard, remote guard, argv, reproducible package')
