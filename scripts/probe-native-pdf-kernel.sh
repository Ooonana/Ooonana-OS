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
timeout 30 "$PDF_TREE/tinyemu/temu" -ctrlc "$work/vm.cfg"
