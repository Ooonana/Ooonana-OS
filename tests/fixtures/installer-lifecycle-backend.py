#!/usr/bin/python3
"""Inert installer replacement. Only run in guarded, device-free QA namespace."""
import json
import os
from pathlib import Path
import sys
import time

assert os.getuid() == 0
assert Path('/run/ooonana-installer-lifecycle-fixture').is_file()
assert not any(Path('/dev').glob('sd*')) and not any(Path('/dev').glob('nvme*'))
args = sys.argv[1:]
assert args[args.index('--target')+1] == '/dev/ooonana-qa-target'
assert '--password-stdin' in args and '--yes' in args
secret = sys.stdin.readline().rstrip('\n')
assert secret == ' private|target password '
output = Path('/qa/installer-lifecycle')
scenario = (output/'scenario').read_text().strip()
assert scenario in ('cancel', 'success', 'failure', 'blocked')
dry = '--dry-run' in args
with (output/(scenario+'.jsonl')).open('a') as stream:
    stream.write(json.dumps(dict(preview=dry, uid=os.getuid(), password_received=True,
                                args=args))+'\n')
print('QA target only: /dev/ooonana-qa-target; no block device opened.', flush=True)
if dry:
    print('Preview blocked.' if scenario == 'blocked' else 'Root format: yes. Other disks: excluded.', flush=True)
    raise SystemExit(7 if scenario == 'blocked' else 0)
(output/(scenario+'.started')).touch()
until = time.monotonic()+25
while not (output/(scenario+'.release')).exists():
    assert time.monotonic() < until, 'QA release timed out'
    time.sleep(.05)
print('QA completed.' if scenario == 'success' else 'QA controlled failure.', flush=True)
raise SystemExit(0 if scenario == 'success' else 7)
