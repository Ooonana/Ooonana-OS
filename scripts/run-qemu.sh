#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
ROOTFS="$WORK_DIR/rootfs"
IMAGE="$WORK_DIR/ooonana-rootfs.ext4"
KERNEL=""
INITRD=""
MEMORY="1024"
CPUS="2"
SMOKE=0
DRY_RUN=0
TIMEOUT_SECONDS="120"
LOG_FILE="${OOONANA_QEMU_LOG:-$WORK_DIR/qemu-smoke.log}"

usage() {
  cat <<'USAGE'
Boot Ooonana rootfs with QEMU.

Usage:
  scripts/run-qemu.sh [options]

Options:
  --rootfs PATH       Rootfs directory with boot files
  --image PATH        Ext4 rootfs image
  --kernel PATH       Kernel path
  --initrd PATH       Initrd path
  --memory MB         Memory size (default: 1024)
  --cpus N            CPU count (default: 2)
  --smoke             Boot smoke service and expect OOONANA_BOOT_OK
  --timeout SECONDS   Smoke timeout (default: 120)
  --log PATH          Smoke log path
  --dry-run           Print QEMU command only
  -h, --help          Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --image) IMAGE="$2"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --initrd) INITRD="$2"; shift 2 ;;
    --memory) MEMORY="$2"; shift 2 ;;
    --cpus) CPUS="$2"; shift 2 ;;
    --smoke) SMOKE=1; shift ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --log) LOG_FILE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

pick_latest() {
  local pattern="$1"
  local latest
  latest="$(find "$ROOTFS/boot" -maxdepth 1 -type f -name "$pattern" | sort -V | tail -n 1)"
  [[ -n "$latest" ]] || ooonana_die "missing boot file: $pattern in $ROOTFS/boot"
  printf '%s\n' "$latest"
}

build_command() {
  local append="root=/dev/vda rw console=ttyS0 panic=1"
  if [[ "$SMOKE" -eq 1 ]]; then
    append="$append systemd.unit=ooonana-smoke.service"
  else
    append="$append systemd.unit=multi-user.target"
  fi

  QEMU_CMD=(
    qemu-system-x86_64
    -m "$MEMORY"
    -smp "$CPUS"
    -nographic
    -no-reboot
    -drive "file=$IMAGE,format=raw,if=virtio"
    -kernel "$KERNEL"
    -initrd "$INITRD"
    -append "$append"
  )
}

main() {
  ooonana_require_linux

  [[ -n "$KERNEL" ]] || KERNEL="$(pick_latest 'vmlinuz-*')"
  [[ -n "$INITRD" ]] || INITRD="$(pick_latest 'initrd.img-*')"
  [[ -f "$IMAGE" ]] || ooonana_die "missing image: $IMAGE"
  [[ -f "$KERNEL" ]] || ooonana_die "missing kernel: $KERNEL"
  [[ -f "$INITRD" ]] || ooonana_die "missing initrd: $INITRD"

  build_command

  if [[ "$DRY_RUN" -eq 1 ]]; then
    ooonana_print_command "${QEMU_CMD[@]}"
    exit 0
  fi

  ooonana_require_commands qemu-system-x86_64 timeout tee grep

  if [[ "$SMOKE" -eq 0 ]]; then
    exec "${QEMU_CMD[@]}"
  fi

  mkdir -p "$(dirname "$LOG_FILE")"
  ooonana_log "smoke boot timeout: ${TIMEOUT_SECONDS}s"
  set +e
  timeout --foreground "$TIMEOUT_SECONDS" "${QEMU_CMD[@]}" 2>&1 | tee "$LOG_FILE"
  qemu_status=${PIPESTATUS[0]}
  set -e

  if grep -q 'OOONANA_BOOT_OK' "$LOG_FILE"; then
    ooonana_log "QEMU smoke boot passed"
    exit 0
  fi

  ooonana_die "QEMU smoke boot failed, status $qemu_status, log: $LOG_FILE"
}

main "$@"
