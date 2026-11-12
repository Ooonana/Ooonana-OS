#!/usr/bin/env bash
set -euo pipefail
RUNTIME="${1:?Usage: probe-native-pdf-kernel.sh RUNTIME [LINUXPDF_TREE]}"
PDF_TREE="${2:-/var/tmp/ooonana-os/linuxpdf/linuxpdf}"
[[ -f "$RUNTIME/kernel-riscv64.bin" && -d "$RUNTIME/rootfs" && -x "$PDF_TREE/tinyemu/temu" ]] || { echo 'Native runtime/emulator missing' >&2; exit 2; }
work="$(mktemp -d /var/tmp/ooonana-native-probe.XXXXXX)"
python3 - "$RUNTIME" "$PDF_TREE" "$work/vm.cfg" <<'PY'
import json, sys
from pathlib import Path
runtime, pdf = map(lambda value: Path(value).resolve(), sys.argv[1:3])
config = dict(version=1, machine="riscv64", memory_size=128,
              bios=str(pdf / "build/vm/bbl64.bin"), kernel=str(runtime / "kernel-riscv64.bin"),
              cmdline="loglevel=7 console=hvc0 no4lvl root=root rootfstype=9p rootflags=trans=virtio rw",
              fs0=dict(file=str(runtime / "rootfs")))
Path(sys.argv[3]).write_text(json.dumps(config, indent=2))
PY
echo "Probe config: $work/vm.cfg"
python3 - "$PDF_TREE/tinyemu/temu" "$work/vm.cfg" <<'PROBE'
import os
import selectors
import subprocess
import sys
import time

limit = int(os.environ.get("OOONANA_PDF_PROBE_TIMEOUT", "90"))
if not 1 <= limit <= 600:
    raise SystemExit("Probe timeout must be 1..600 seconds")
process = subprocess.Popen([sys.argv[1], "-ctrlc", sys.argv[2]],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
poll = selectors.DefaultSelector()
poll.register(process.stdout, selectors.EVENT_READ)
tail = b""
deadline = time.monotonic() + limit
try:
    while time.monotonic() < deadline:
        for key, _ in poll.select(0.25):
            chunk = os.read(key.fileobj.fileno(), 4096)
            if not chunk:
                raise SystemExit("Native PDF guest exited before prompt")
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            tail = (tail + chunk)[-65536:]
            if b"Kernel panic" in tail or b"PDF boot failed:" in tail:
                raise SystemExit("Native PDF boot failed")
            if b"OOONANA_PDF_BOOT_OK" in tail and b"ooonana# " in tail:
                print("\nok native-pdf-probe: guest reached interactive prompt", flush=True)
                sys.exit(0)
    raise SystemExit("Native PDF prompt timeout")
finally:
    poll.close()
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
PROBE
