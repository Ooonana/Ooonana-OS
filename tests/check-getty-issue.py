#!/usr/bin/env python3
"""Render the shipped issue through real BusyBox getty in disposable VM PTYs."""
import fcntl
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import sys
import termios
import time

assert os.geteuid() == 0
assert Path('/sys/class/dmi/id/product_name').read_text().strip() == 'OOONANA_DISPOSABLE_VM'
issue, logo = map(Path, sys.argv[1:])
expected = logo.read_bytes().replace(b'\r', b'')
assert expected and b'\\' in expected
for columns in (80, 40):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, columns, 0, 0))
    process = subprocess.Popen(['/bin/busybox', 'getty', '-L', '-f', str(issue),
                                '115200', os.ttyname(slave), 'vt100'],
                               stdin=slave, stdout=slave, stderr=slave,
                               start_new_session=True)
    output = bytearray()
    try:
        deadline = time.monotonic() + 12
        while b' login: ' not in output:
            assert time.monotonic() < deadline and process.poll() is None, bytes(output)
            if select.select([master], [], [], .1)[0]:
                output.extend(os.read(master, 65536))
        rendered = bytes(output).replace(b'\r', b'')
        assert expected in rendered, rendered
        print(f'GETTY_RENDER_COLUMNS={columns}\n' + rendered.decode(), flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        os.close(master)
        os.close(slave)
print('OO_NATIVE_GETTY_LOGO_RENDER_PASS', flush=True)
