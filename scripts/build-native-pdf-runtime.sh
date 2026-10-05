#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${OOONANA_NATIVE_PDF_WORK:-/var/tmp/ooonana-os/native-pdf}"
SOURCE=""
JOBS="${OOONANA_KERNEL_JOBS:-4}"
REUSE_KERNEL=0
REUSE_RUNTIME=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) SOURCE="$2"; shift 2 ;;
    --work-dir) WORK="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --reuse-kernel) REUSE_KERNEL=1; shift ;;
    --reuse-runtime) REUSE_RUNTIME="$2"; shift 2 ;;
    --help|-h) printf 'Build native RISC-V64 Linux 6.18.37 + static BusyBox 1.37.0 for PDF.\nUsage: %s --source VERIFIED_LINUX_SOURCE [--work-dir PATH] [--jobs N] [--reuse-kernel]\nReuse verified native binaries, refresh minimal payload: --reuse-runtime RUNTIME_DIR\n' "$0"; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done
if [[ -n "$REUSE_RUNTIME" ]]; then
  mkdir -p "$WORK"
  runtime="$(mktemp -d "$WORK/runtime.XXXXXX")"
  python3 - "$REUSE_RUNTIME" "$runtime" <<'REUSE'
import hashlib, json, os, shutil, sys
from pathlib import Path
source, target = map(lambda name: Path(name).resolve(), sys.argv[1:])
manifest = json.loads((source / "RUNTIME-MANIFEST.json").read_text())
assert manifest["architecture"] == "riscv64" and manifest["kernel"] == "6.18.37"
assert manifest["busybox"] == "1.37.0"
for name in ("kernel-riscv64.bin", "kernel.config", "busybox.config", "rootfs/bin/busybox"):
    path = source / name
    assert path.resolve().is_relative_to(source), f"Unsafe runtime input: {name}"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["files"][name], f"Runtime checksum mismatch: {name}"
config = (source / "busybox.config").read_text().splitlines()
assert all(option in config for option in ("CONFIG_STATIC=y", "CONFIG_FEATURE_SH_STANDALONE=y", "CONFIG_FEATURE_SH_NOFORK=y"))
busybox = (source / "rootfs/bin/busybox").resolve()
for name in ("kernel-riscv64.bin", "kernel.config", "busybox.config", "rootfs/bin/busybox"):
    output = target / name
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / name, output)
# Only BusyBox applet links enter fresh root. No previous desktop/custom data.
for path in (source / "rootfs").rglob("*"):
    if path.is_symlink() and path.resolve() == busybox:
        output = target / "rootfs" / path.relative_to(source / "rootfs")
        output.parent.mkdir(parents=True, exist_ok=True)
        link = os.readlink(path)
        assert not os.path.isabs(link), "Absolute BusyBox link unsupported"
        output.symlink_to(link)
manifest["reused_runtime_manifest_sha256"] = hashlib.sha256((source / "RUNTIME-MANIFEST.json").read_bytes()).hexdigest()
manifest["verification"] = "native binaries verified; refreshed payload needs VM verification"
(target / "RUNTIME-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
REUSE
  bash "$ROOT/scripts/inject-ooonana-pdf-root.sh" "$runtime/rootfs"
  printf 'Native PDF runtime built: %s\n' "$runtime"
  exit 0
fi
[[ -f "$SOURCE/Makefile" ]] || { printf 'Verified Linux source required: --source PATH\n' >&2; exit 2; }
for command in riscv64-linux-gnu-gcc make curl sha256sum tar python3; do command -v "$command" >/dev/null || { printf 'Missing command: %s\n' "$command" >&2; exit 2; }; done
mkdir -p "$WORK/kernel" "$WORK/downloads" "$WORK/busybox-build"
[[ "$(make -s -C "$SOURCE" kernelversion)" = 6.18.37 ]] || { printf 'Tested kernel version required: 6.18.37\n' >&2; exit 2; }
export ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- SOURCE_DATE_EPOCH=0
export KBUILD_BUILD_TIMESTAMP='Thu Jan 1 00:00:00 UTC 1970' KBUILD_BUILD_USER=ooonana KBUILD_BUILD_HOST=builder
if [[ "$REUSE_KERNEL" -eq 1 ]]; then
  [[ -s "$WORK/kernel/arch/riscv/boot/Image" && -s "$WORK/kernel/.config" ]] || { printf 'Cached native kernel missing\n' >&2; exit 1; }
  while IFS= read -r option; do
    if [[ "$option" == *=n ]]; then
      # Kconfig writes disabled values as comments or omits unavailable ones.
      ! grep -Eq "^${option%=n}=[ym]$" "$WORK/kernel/.config" || { printf 'Native kernel config mismatch: %s\n' "$option" >&2; exit 1; }
    else
      grep -Fqx "$option" "$WORK/kernel/.config" || { printf 'Native kernel config mismatch: %s\n' "$option" >&2; exit 1; }
    fi
  done < <(grep -E '^(CONFIG_[A-Z0-9_]+=.*|# CONFIG_[A-Z0-9_]+ is not set)$' "$ROOT/configs/kernel/ooonana-pdf-riscv64.fragment")
else
  make -C "$SOURCE" O="$WORK/kernel" allnoconfig
  KCONFIG_ALLCONFIG="$ROOT/configs/kernel/ooonana-pdf-riscv64.fragment" make -C "$SOURCE" O="$WORK/kernel" allnoconfig
  make -C "$SOURCE" O="$WORK/kernel" -j"$JOBS" Image
fi
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
# PDF 9p/ELF loading is expensive. Execute supported applets inside ash,
# retaining their real behavior and all package checksum/signature checks.
sed -i -E 's/^# (CONFIG_FEATURE_SH_STANDALONE|CONFIG_FEATURE_SH_NOFORK) is not set$/\1=y/' "$WORK/busybox-build/.config"
make -C "$WORK/busybox-1.37.0" O="$WORK/busybox-build" oldconfig </dev/null
make -C "$WORK/busybox-1.37.0" O="$WORK/busybox-build" -j"$JOBS"
runtime="$(mktemp -d "$WORK/runtime.XXXXXX")"
mkdir -p "$runtime/rootfs"
make -C "$WORK/busybox-1.37.0" O="$WORK/busybox-build" CONFIG_PREFIX="$runtime/rootfs" install
bash "$ROOT/scripts/inject-ooonana-pdf-root.sh" "$runtime/rootfs"
cp "$WORK/kernel/arch/riscv/boot/Image" "$runtime/kernel-riscv64.bin"
cp "$WORK/kernel/.config" "$runtime/kernel.config"
cp "$WORK/busybox-build/.config" "$runtime/busybox.config"
python3 - "$runtime" "$expected" <<'MANIFEST'
import hashlib, json, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1])
files = ("kernel-riscv64.bin", "kernel.config", "busybox.config", "rootfs/bin/busybox")
manifest = dict(kernel="6.18.37", busybox="1.37.0", busybox_source_sha256=sys.argv[2], architecture="riscv64", shell_applets="standalone/nofork", compiler=subprocess.check_output(["riscv64-linux-gnu-gcc", "--version"], text=True).splitlines()[0], files={name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}, verification="built; VM boot verification required")
(root / "RUNTIME-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
MANIFEST
printf 'Native PDF runtime built: %s\n' "$runtime"
