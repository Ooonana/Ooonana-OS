#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${OOONANA_NATIVE_PDF_WORK:-/var/tmp/ooonana-os/native-pdf}"
SOURCE=""
JOBS="${OOONANA_KERNEL_JOBS:-4}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) SOURCE="$2"; shift 2 ;;
    --work-dir) WORK="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --help|-h) printf 'Build native RISC-V64 Linux 6.18.37 + static BusyBox 1.37.0 for PDF.\nUsage: %s --source VERIFIED_LINUX_SOURCE [--work-dir PATH] [--jobs N]\n' "$0"; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done
[[ -f "$SOURCE/Makefile" ]] || { printf 'Verified Linux source required: --source PATH\n' >&2; exit 2; }
for command in riscv64-linux-gnu-gcc make curl sha256sum tar python3; do command -v "$command" >/dev/null || { printf 'Missing command: %s\n' "$command" >&2; exit 2; }; done
mkdir -p "$WORK/kernel" "$WORK/downloads" "$WORK/busybox-build"
[[ "$(make -s -C "$SOURCE" kernelversion)" = 6.18.37 ]] || { printf 'Tested kernel version required: 6.18.37\n' >&2; exit 2; }
export ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- SOURCE_DATE_EPOCH=0
export KBUILD_BUILD_TIMESTAMP='Thu Jan 1 00:00:00 UTC 1970' KBUILD_BUILD_USER=ooonana KBUILD_BUILD_HOST=builder
make -C "$SOURCE" O="$WORK/kernel" allnoconfig
KCONFIG_ALLCONFIG="$ROOT/configs/kernel/ooonana-pdf-riscv64.fragment" make -C "$SOURCE" O="$WORK/kernel" allnoconfig
make -C "$SOURCE" O="$WORK/kernel" -j"$JOBS" Image
archive="$WORK/downloads/busybox-1.37.0.tar.bz2"
if [[ ! -f "$archive" ]]; then curl -fL --retry 2 https://busybox.net/downloads/busybox-1.37.0.tar.bz2 -o "$archive"; fi
curl -fL --retry 2 https://busybox.net/downloads/busybox-1.37.0.tar.bz2.sha256 -o "$archive.sha256"
expected="$(awk '{print $1; exit}' "$archive.sha256")"
[[ "$expected" =~ ^[0-9a-f]{64}$ ]] || { printf 'Invalid BusyBox upstream checksum\n' >&2; exit 1; }
printf '%s  %s\n' "$expected" "$archive" | sha256sum -c -
[[ -d "$WORK/busybox-1.37.0" ]] || tar -xjf "$archive" -C "$WORK"
make -C "$WORK/busybox-1.37.0" O="$WORK/busybox-build" defconfig
sed -i 's/^# CONFIG_STATIC is not set$/CONFIG_STATIC=y/; s/^CONFIG_TC=y$/# CONFIG_TC is not set/' "$WORK/busybox-build/.config"
sed -i -E 's/^(CONFIG_SHA(1|256)_HWACCEL)=y$/# \1 is not set/' "$WORK/busybox-build/.config"
make -C "$WORK/busybox-1.37.0" O="$WORK/busybox-build" oldconfig </dev/null
make -C "$WORK/busybox-1.37.0" O="$WORK/busybox-build" -j"$JOBS"
runtime="$(mktemp -d "$WORK/runtime.XXXXXX")"
mkdir -p "$runtime/rootfs"
make -C "$WORK/busybox-1.37.0" O="$WORK/busybox-build" CONFIG_PREFIX="$runtime/rootfs" install
bash "$ROOT/scripts/inject-ooonana-pdf-root.sh" "$runtime/rootfs"
cp "$WORK/kernel/arch/riscv/boot/Image" "$runtime/kernel-riscv64.bin"
cp "$WORK/kernel/.config" "$runtime/kernel.config"
python3 - "$runtime" "$expected" <<'MANIFEST'
import hashlib, json, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1])
files = ("kernel-riscv64.bin", "kernel.config", "rootfs/bin/busybox")
manifest = dict(kernel="6.18.37", busybox="1.37.0", busybox_source_sha256=sys.argv[2], architecture="riscv64", compiler=subprocess.check_output(["riscv64-linux-gnu-gcc", "--version"], text=True).splitlines()[0], files={name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}, verification="built; VM boot verification required")
(root / "RUNTIME-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
MANIFEST
printf 'Native PDF runtime built: %s\n' "$runtime"
