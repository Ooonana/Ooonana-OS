#!/usr/bin/env python3
"""Actual watchdog lifecycle in isolated paths; never repair host services."""
import argparse
import os
from pathlib import Path
import shlex
import signal
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--busybox-rootfs', type=Path)
args = parser.parse_args()
source = (root / 'scripts/build-full-i3-rootfs.sh').read_text()
marker = 'install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-service-watchdog" <<\'EOF\'\n'
watchdog = source.split(marker, 1)[1].split('\nEOF', 1)[0]
if args.busybox_rootfs:
    base = args.busybox_rootfs.resolve()
    busybox = [str(base / 'lib/ld-musl-x86_64.so.1'), '--library-path',
               f'{base}/lib:{base}/usr/lib', str(base / 'bin/busybox')]
    shell = busybox + ['sh', '-c']
    flock = shlex.join(busybox + ['flock'])
else:
    shell, flock = ['sh', '-c'], 'flock'

children = []
with tempfile.TemporaryDirectory(prefix='ooonana-watchdog-test-') as temporary:
    fixture = Path(temporary)
    (fixture / 'run').mkdir()
    pidfile = fixture / 'run/service-watchdog.pid'
    isolated = watchdog.replace('/run/ooonana', str(fixture / 'run'))
    isolated = isolated.replace('/var/log', str(fixture / 'log'))
    isolated = isolated.replace('/bin/busybox flock', flock)
    # Stub only service probes and interval duration; real kernel flock,
    # metadata, signal traps and wait/cleanup remain unchanged.
    isolated = isolated.replace('ooonana-service-repair force-', 'fixture_repair force-')
    isolated = isolated.replace('while :; do', '''
sleep() {
  if [ "$test_phase" = idle ]; then exec /bin/sleep 5; fi
  exec /bin/sleep 0.01
}
dbus_ready() {
  if [ "$test_phase" = probe ]; then
    printf probe >"$test_marker"
    exec /bin/sleep 5
  fi
  [ "$test_phase" != repair ]
}
network_manager_ready() { return 0; }
bluez_ready() { return 0; }
fixture_repair() { printf repair >"$test_marker"; exec /bin/sleep 5; }
while :; do''', 1)

    def launch(phase='idle'):
        settings = f'test_phase={shlex.quote(phase)}\ntest_marker={shlex.quote(str(fixture / "job-started"))}\n'
        child = subprocess.Popen(shell + [settings + isolated], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        children.append(child)
        return child

    def wait_started(child):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise AssertionError(f'watchdog exited: {child.stderr.read().decode()}')
            if pidfile.exists() and pidfile.read_text().strip() == str(child.pid):
                return
            time.sleep(0.01)
        raise AssertionError('watchdog did not publish own PID')

    def stop(child, sig=signal.SIGTERM):
        child.send_signal(sig)
        assert child.wait(timeout=1) == 0, 'watchdog did not stop cleanly'

    try:
        unrelated = subprocess.Popen(['/bin/sleep', '30'], start_new_session=True)
        children.append(unrelated)
        pidfile.write_text(f'{unrelated.pid}\n')
        child = launch()
        wait_started(child)
        assert unrelated.poll() is None, 'unrelated process touched'
        stop(child)
        assert not pidfile.exists(), 'own PID file left after TERM'
        print('ok watchdog: stale unrelated PID ignored; TERM exits promptly')

        for value in ('not-a-pid', '99999999'):
            pidfile.write_text(value + '\n')
            child = launch()
            wait_started(child)
            stop(child)
        print('ok watchdog: malformed/dead PID metadata does not block startup')

        batch = [launch() for _ in range(6)]
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            alive = [item for item in batch if item.poll() is None]
            if len(alive) == 1 and pidfile.exists():
                break
            time.sleep(0.01)
        assert len(alive) == 1, 'concurrent duplicate watchdogs started'
        wait_started(alive[0])
        for item in batch:
            if item is not alive[0]:
                assert item.wait(timeout=1) == 0
        stop(alive[0], signal.SIGINT)
        assert not pidfile.exists(), 'own PID file left after INT'
        print('ok watchdog: six concurrent starts yield one owner; INT exits')

        child = launch()
        wait_started(child)
        pidfile.write_text('replacement-owner\n')
        stop(child)
        assert pidfile.read_text().strip() == 'replacement-owner', 'replacement metadata deleted'
        print('ok watchdog: stop preserves replacement PID metadata')

        for phase in ('probe', 'repair'):
            marker_file = fixture / 'job-started'
            marker_file.unlink(missing_ok=True)
            child = launch(phase)
            wait_started(child)
            deadline = time.monotonic() + 2
            while not marker_file.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert marker_file.read_text() == phase, 'worker fixture did not start'
            stop(child)
            assert not pidfile.exists(), f'PID metadata left during {phase}'
        print('ok watchdog: TERM interrupts active probe/repair, not just sleep')

        child = launch()
        wait_started(child)
        child.kill()
        child.wait(timeout=1)
        restarted = launch()
        wait_started(restarted)
        stop(restarted)
        print('ok watchdog: crash releases lock even while interval child remains')
    finally:
        for child in children:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait(timeout=2)
            if child.stderr:
                child.stderr.close()
print('ok service-watchdog lifecycle')
