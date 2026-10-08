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
    env = {**os.environ, "PATH": str(work) + ":" + os.environ['PATH'], "CALLS": str(log)}
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
    repo = work / 'repo'
    subprocess.run(['bash', str(ROOT / 'scripts/build-firefox-package.sh'), '--out-dir', str(repo)], check=True)
    archive = repo / 'archives/firefox-1.0.0.tar.gz'
    original = archive.read_bytes()
    subprocess.run(['bash', str(ROOT / 'scripts/build-firefox-package.sh'), '--out-dir', str(repo)], check=True)
    assert archive.read_bytes() == original
print('ok firefox launcher: explicit user setup, remote guard, argv, missing runtime, reproducible package')
