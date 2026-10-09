#!/usr/bin/env python3
"""Real setup state/lock/rename/fault paths; fake downloads and inner installer.

Only disposable fixtures. No runtime/network installation or inference claim.
"""
import hashlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tarfile
import tempfile
import time

root = Path(__file__).resolve().parents[1]
source = root / "packages/openvino-chat/rootfs/usr/bin"
with tempfile.TemporaryDirectory() as temporary:
    work = Path(temporary)
    tools = work / "tools"
    tools.mkdir()
    project = work / "project"
    (project / "src/openvino_chat").mkdir(parents=True)
    (project / "pyproject.toml").write_text('fixture app snapshot\n')
    fingerprint = hashlib.sha256((project / "pyproject.toml").read_bytes()).hexdigest()
    seed = work / "seed"
    (seed / "etc").mkdir(parents=True)
    (seed / "etc/resolv.conf").write_text('nameserver 127.0.0.1\n')
    archive = work / "seed.tar.xz"
    with tarfile.open(archive, 'w:xz') as output:
        output.add(seed, arcname='.')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    installer = tools / "bwrap"
    installer.write_text('''#!/usr/bin/env python3
import hashlib, os, pathlib, sys, time
try:
    os.fstat(9)
except OSError:
    pass
else:
    raise AssertionError("inner installer inherited writer lock")
target = pathlib.Path(sys.argv[sys.argv.index('--bind') + 1])
assert target.parent.name.startswith('.setup.')
with open(os.environ['CALLS'], 'a') as output:
    output.write(str(target) + '\\n')
(target / 'payload').write_text('new runtime')
if os.environ.get('HOLD_INSTALLER') == '1':
    pathlib.Path(os.environ['HOLD_MARKER']).touch()
    while not pathlib.Path(os.environ['RELEASE']).exists():
        time.sleep(0.02)
if os.environ.get('FAIL_INSTALLER') == '1':
    sys.exit(7)
if os.environ.get('BAD_READY') != 'missing':
    project = pathlib.Path(os.environ['OOONANA_OPENVINO_PROJECT'])
    digest = hashlib.sha256((project / 'pyproject.toml').read_bytes()).hexdigest()
    if os.environ.get('BAD_READY') == 'wrong':
        digest = 'wrong'
    (target / '.ooonana-openvino-ready').write_text(digest + '\\n')
''')
    installer.chmod(0o755)
    (tools / "curl").write_text('''#!/usr/bin/env python3
import os, pathlib, shutil, sys
destination = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])
if destination.name == 'SHA256SUMS':
    destination.write_text(os.environ['SEED_SHA'] + ' *ubuntu-24.04-minimal-cloudimg-amd64-root.tar.xz\\n')
else:
    shutil.copyfile(os.environ['SEED_ARCHIVE'], destination)
''')
    (tools / "curl").chmod(0o755)
    (tools / "df").write_text('''#!/usr/bin/env python3
import os
print('Filesystem 1024-blocks Used Available Capacity Mounted on')
print('/fixture 1000000000 1 ' + os.environ.get('FREE_KB', '900000000') + ' 1% /fixture')
''')
    (tools / "df").chmod(0o755)
    real_awk = shutil.which('awk')
    (tools / "awk").write_text('''#!/usr/bin/env python3
import os, sys
program = sys.argv[1]
if 'MemAvailable:' in program and 'FIXTURE_RAM_KB' in os.environ:
    print(os.environ['FIXTURE_RAM_KB'])
elif 'SwapFree:' in program and 'FIXTURE_SWAP_KB' in os.environ:
    print(os.environ['FIXTURE_SWAP_KB'])
else:
    os.execv(os.environ['REAL_AWK'], [os.environ['REAL_AWK'], *sys.argv[1:]])
''')
    (tools / "awk").chmod(0o755)
    real_mv = shutil.which('mv')
    (tools / "mv").write_text('''#!/usr/bin/env python3
import os, pathlib, subprocess, sys, time
args = sys.argv[1:]
if os.environ.get('FAIL_PROMOTE') == '1' and pathlib.Path(args[-2]).name == 'rootfs.next':
    sys.exit(28)
subprocess.run([os.environ['REAL_MV'], *args], check=True)
phase = os.environ.get('HOLD_PROMOTE', '')
old_moved = args[-2] == os.environ['OOONANA_OPENVINO_STATE_DIR'] + '/rootfs'
pointer_moved = pathlib.Path(args[-2]).name == 'rootfs.next'
journal_moved = pathlib.Path(args[-1]).name == '.runtime-promotion'
if (phase == 'journal' and journal_moved) or (phase == 'directory' and old_moved) or (phase == 'pointer' and pointer_moved):
    pathlib.Path(os.environ['HOLD_MARKER']).touch()
    while True:
        time.sleep(0.02)
''')
    (tools / "mv").chmod(0o755)
    # Replace only the absolute binary in disposable script copies, never /usr/bin.
    setup = work / "setup.sh"
    setup.write_text((source / 'ooonana-openvino-setup').read_text().replace('/usr/bin/bwrap', str(installer)))
    launcher = work / "openvino.sh"
    launcher.write_text((source / 'openvino').read_text().replace('/usr/bin/bwrap', str(installer)))
    calls = work / "calls"
    calls.touch()
    history = work / "history/keep.json"
    history.parent.mkdir()
    history.write_text('user history remains')
    environment = {**os.environ, 'PATH': str(tools) + ':' + os.environ['PATH'],
                   'OOONANA_OPENVINO_PROJECT': str(project), 'OOONANA_LIVE_MODE_FILE': str(work / 'not-live'),
                   'OOONANA_OPENVINO_ROOTFS_SHA256': digest, 'SEED_SHA': digest,
                   'SEED_ARCHIVE': str(archive), 'CALLS': str(calls), 'REAL_MV': real_mv,
                   'REAL_AWK': real_awk,
                   'HOLD_MARKER': str(work / 'held'), 'RELEASE': str(work / 'release')}

    def seed_state(name):
        state = work / name
        (state / 'rootfs/etc').mkdir(parents=True)
        (state / 'rootfs/.ooonana-openvino-ready').write_text(fingerprint + '\n')
        (state / 'rootfs/payload').write_text('old runtime')
        (state / 'rootfs/etc/custom.conf').write_text('custom settings')
        return state

    def snapshot(path):
        return {str(file.relative_to(path)): file.read_bytes() for file in path.rglob('*') if file.is_file()}

    def run(state, *args, **overrides):
        call = subprocess.run(['sh', str(setup), *args], env={**environment,
                              'OOONANA_OPENVINO_STATE_DIR': str(state), **overrides},
                              capture_output=True, text=True, timeout=15)
        assert history.read_text() == 'user history remains'
        return call

    state = seed_state('state')
    baseline = snapshot(state / 'rootfs')
    low_ram = run(state, FIXTURE_RAM_KB='1024', FIXTURE_SWAP_KB='9000000', FAIL_INSTALLER='1')
    assert low_ram.returncode and 'less than 4 GiB available physical RAM' in low_ram.stderr
    assert 'not extra physical RAM' in low_ram.stderr and snapshot(state / 'rootfs') == baseline
    for free in ('0', 'bad'):
        before = calls.read_text()
        result = run(state, FREE_KB=free)
        assert result.returncode and 'storage' in result.stderr
        assert snapshot(state / 'rootfs') == baseline and calls.read_text() == before
    for overrides in ({'FAIL_INSTALLER': '1'}, {'BAD_READY': 'wrong'}, {'BAD_READY': 'missing'}):
        result = run(state, **overrides)
        assert result.returncode and snapshot(state / 'rootfs') == baseline
        assert not [path for path in state.glob('.setup.*') if path.is_dir()]
        assert not (state / '.runtime-promotion').exists()
    result = run(state)
    assert result.returncode == 0, result.stderr
    assert (state / 'rootfs').is_symlink()
    first = (state / 'rootfs').resolve()
    assert snapshot(first.parent / 'previous') == baseline
    assert (first / 'etc/custom.conf').read_text() == 'custom settings'
    first_snapshot = snapshot(first)
    assert run(state).returncode == 0
    second = (state / 'rootfs').resolve()
    assert second != first and snapshot(first) == first_snapshot
    for arguments, overrides in (((), {'FAIL_INSTALLER': '1'}),
                                 (('--force',), {'OOONANA_OPENVINO_ROOTFS_SHA256': 'wrong'}),
                                 (('--force',), {'FAIL_INSTALLER': '1'})):
        result = run(state, *arguments, **overrides)
        assert result.returncode and (state / 'rootfs').resolve() == second
        assert snapshot(first) == first_snapshot
    assert run(state, '--force').returncode == 0
    assert second.exists() and (first.parent / 'previous').exists()

    def wait_held(process):
        deadline = time.monotonic() + 8
        while not (work / 'held').exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        if not (work / 'held').exists():
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            raise AssertionError((stdout, stderr))

    # Actual kernel writer lock, closed in the installer child.
    pending = subprocess.Popen(['sh', str(setup)], env={**environment, 'OOONANA_OPENVINO_STATE_DIR': str(state),
                               'HOLD_INSTALLER': '1'}, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        wait_held(pending)
        assert 'another setup' in run(state).stderr
        (work / 'release').touch()
        stdout, stderr = pending.communicate(timeout=10)
        assert pending.returncode == 0, (stdout, stderr)
    finally:
        if pending.poll() is None:
            os.killpg(pending.pid, signal.SIGKILL)
            pending.wait()
    (work / 'held').unlink()

    for phase in ('journal', 'directory', 'pointer'):
        fault = seed_state('fault-' + phase)
        original = snapshot(fault / 'rootfs')
        process = subprocess.Popen(['sh', str(setup)], env={**environment,
                                   'OOONANA_OPENVINO_STATE_DIR': str(fault), 'HOLD_PROMOTE': phase},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            wait_held(process)
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=5)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        assert (fault / '.runtime-promotion').exists()
        guard = subprocess.run(['sh', str(launcher), 'api', 'status'], env={**environment,
                               'OOONANA_OPENVINO_STATE_DIR': str(fault)}, capture_output=True, text=True, timeout=5)
        assert guard.returncode and 'interrupted runtime promotion' in guard.stderr
        recovery = run(fault, FAIL_INSTALLER='1')
        assert recovery.returncode and 'recovered previous runtime' in recovery.stderr
        assert not (fault / '.runtime-promotion').exists()
        assert snapshot(fault / 'rootfs') == original and not (fault / 'rootfs').is_symlink()
        (work / 'held').unlink()

    failure = seed_state('rename-failure')
    original = snapshot(failure / 'rootfs')
    assert run(failure, FAIL_PROMOTE='1').returncode
    assert snapshot(failure / 'rootfs') == original and not (failure / '.runtime-promotion').exists()
    (failure / '.runtime-promotion').write_text('../../history')
    assert 'unresolved runtime promotion' in run(failure).stderr
    assert snapshot(failure / 'rootfs') == original and history.read_text() == 'user history remains'
    invalid_lock = seed_state('invalid-lock')
    (invalid_lock / '.setup.lock').symlink_to(history)
    assert 'invalid setup lock' in run(invalid_lock).stderr and history.read_text() == 'user history remains'
    invalid_generations = seed_state('invalid-generations')
    (invalid_generations / '.runtime-generations').symlink_to(history.parent)
    assert 'must not be a symlink' in run(invalid_generations).stderr
    assert list(history.parent.iterdir()) == [history]
    invalid_root = work / 'invalid-rootfs'
    invalid_root.mkdir()
    (invalid_root / 'rootfs').write_text('unrelated file')
    assert 'invalid runtime path' in run(invalid_root, '--force').stderr
    assert (invalid_root / 'rootfs').read_text() == 'unrelated file'
print('ok openvino-setup: staged failure, fingerprint, retained generations/config/history, flock, low space, force checksums, three SIGKILL points, rename rollback, unknown/symlink refusal')
