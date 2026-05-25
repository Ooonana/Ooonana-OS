#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
KERNEL_SOURCE="$WORK_DIR/linux"
KERNEL_BUILD="$WORK_DIR/kernel-build"
KERNEL_OUT="$WORK_DIR/ooonana-kernel"
KERNEL="$KERNEL_OUT/vmlinuz-ooonana"
DEFCONFIG="x86_64_defconfig"
CONFIG=""
JOBS="${OOONANA_KERNEL_JOBS:-$(command -v nproc >/dev/null 2>&1 && nproc || printf '2')}"
DRY_RUN=0
FORCE=0

usage() {
  cat <<'USAGE'
Build Ooonana Linux kernel.

Usage:
  scripts/build-kernel.sh [options]

Options:
  --work-dir PATH   Build directory (default: /var/tmp/ooonana-os/build)
  --source PATH     Linux source tree (default: WORK_DIR/linux)
  --build-dir PATH  Kernel object directory (default: WORK_DIR/kernel-build)
  --out-dir PATH    Kernel output directory (default: WORK_DIR/ooonana-kernel)
  --kernel PATH     Kernel output path (default: OUT_DIR/vmlinuz-ooonana)
  --defconfig NAME  Kernel defconfig target (default: x86_64_defconfig)
  --config PATH     Existing .config to copy before olddefconfig
  --jobs N          Parallel make jobs (default: nproc)
  --dry-run         Print build commands only
  --force           Delete kernel build/output before building
  -h, --help        Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; KERNEL_SOURCE="$2/linux"; KERNEL_BUILD="$2/kernel-build"; KERNEL_OUT="$2/ooonana-kernel"; KERNEL="$2/ooonana-kernel/vmlinuz-ooonana"; shift 2 ;;
    --source) KERNEL_SOURCE="$2"; shift 2 ;;
    --build-dir) KERNEL_BUILD="$2"; shift 2 ;;
    --out-dir) KERNEL_OUT="$2"; KERNEL="$2/vmlinuz-ooonana"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --defconfig) DEFCONFIG="$2"; shift 2 ;;
    --config) CONFIG="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    ooonana_print_command "$@"
  else
    "$@"
  fi
}

validate_source() {
  [[ -f "$KERNEL_SOURCE/Makefile" ]] || ooonana_die "missing Linux Makefile: $KERNEL_SOURCE"
  [[ -d "$KERNEL_SOURCE/arch/x86" ]] || ooonana_die "missing x86 kernel arch tree: $KERNEL_SOURCE/arch/x86"
  if [[ -n "$CONFIG" ]]; then
    [[ -f "$CONFIG" ]] || ooonana_die "missing kernel config: $CONFIG"
  fi
}

write_kernel_env() {
  cat > "$KERNEL_OUT/kernel.env" <<EOF
OOONANA_KERNEL=$KERNEL
OOONANA_KERNEL_SOURCE=$KERNEL_SOURCE
OOONANA_KERNEL_BUILD=$KERNEL_BUILD
OOONANA_KERNEL_DEFCONFIG=$DEFCONFIG
EOF
}

main() {
  ooonana_require_linux
  ooonana_require_commands make install cp mkdir dirname chmod
  validate_source

  if [[ "$FORCE" -eq 1 ]]; then
    rm -rf "$KERNEL_BUILD"
    rm -f "$KERNEL" "$KERNEL_OUT/kernel.env"
  fi

  mkdir -p "$KERNEL_BUILD" "$KERNEL_OUT" "$(dirname "$KERNEL")"

  if [[ -n "$CONFIG" ]]; then
    run_cmd cp "$CONFIG" "$KERNEL_BUILD/.config"
  else
    run_cmd make -C "$KERNEL_SOURCE" O="$KERNEL_BUILD" "$DEFCONFIG"
  fi

  run_cmd make -C "$KERNEL_SOURCE" O="$KERNEL_BUILD" olddefconfig
  run_cmd make -C "$KERNEL_SOURCE" O="$KERNEL_BUILD" -j "$JOBS" bzImage

  if [[ "$DRY_RUN" -eq 1 ]]; then
    ooonana_print_command install -m 0644 "$KERNEL_BUILD/arch/x86/boot/bzImage" "$KERNEL"
    printf 'OOONANA_KERNEL=%s\n' "$KERNEL"
    exit 0
  fi

  [[ -f "$KERNEL_BUILD/arch/x86/boot/bzImage" ]] || ooonana_die "kernel build did not produce bzImage"
  install -m 0644 "$KERNEL_BUILD/arch/x86/boot/bzImage" "$KERNEL"
  write_kernel_env
  chmod a+r "$KERNEL" "$KERNEL_OUT/kernel.env"

  ooonana_log "kernel ready: $KERNEL"
}

main "$@"
