#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
ROOTFS="$WORK_DIR/rootfs"
IMAGE="$WORK_DIR/ooonana-rootfs.ext4"
ISO="$WORK_DIR/ooonana.iso"
OOONANA_KERNEL="$WORK_DIR/ooonana-kernel/vmlinuz-ooonana"
ISO_MODE=0
INITRAMFS_BOOT=0
DISK=""
INSTALL=0
KERNEL=""
INITRD=""
MEMORY="1024"
CPUS="2"
SMOKE=0
DRY_RUN=0
TIMEOUT_SECONDS="120"
LOG_FILE="${OOONANA_QEMU_LOG:-$WORK_DIR/qemu-smoke.log}"
SMOKE_MARKER="OOONANA_BOOT_OK"

usage() {
  cat <<'USAGE'
Boot Ooonana rootfs with QEMU.

Usage:
  scripts/run-qemu.sh [options]

Options:
  --rootfs PATH       Rootfs directory with boot files
  --image PATH        Ext4 rootfs image
  --iso PATH          Boot ISO path instead of rootfs image
  --initramfs-boot    Boot scratch initramfs without a root disk
  --disk PATH         Attach writable raw disk or ext4 image
  --install           Require ISO install mode and writable disk
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
    --iso) ISO="$2"; ISO_MODE=1; shift 2 ;;
    --initramfs-boot) INITRAMFS_BOOT=1; shift ;;
    --disk) DISK="$2"; shift 2 ;;
    --install) INSTALL=1; ISO_MODE=1; shift ;;
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

pick_scratch_kernel() {
  if [[ -f "$OOONANA_KERNEL" ]]; then
    printf '%s\n' "$OOONANA_KERNEL"
    return 0
  fi

  pick_latest 'vmlinuz-*'
}

build_command() {
  local append="root=/dev/vda rw console=ttyS0 panic=1"
  if [[ "$SMOKE" -eq 1 ]]; then
    append="$append systemd.unit=ooonana-smoke.service ooonana.smoke=1"
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

build_initramfs_command() {
  local append="console=ttyS0 panic=1 rdinit=/init"
  if [[ "$SMOKE" -eq 1 ]]; then
    append="$append ooonana.smoke=1"
  fi

  QEMU_CMD=(
    qemu-system-x86_64
    -m "$MEMORY"
    -smp "$CPUS"
    -nographic
    -no-reboot
    -kernel "$KERNEL"
    -initrd "$INITRD"
    -append "$append"
  )
}

build_iso_command() {
  QEMU_CMD=(
    qemu-system-x86_64
    -m "$MEMORY"
    -smp "$CPUS"
    -nographic
    -no-reboot
    -cdrom "$ISO"
    -boot d
  )
  if [[ -n "$DISK" ]]; then
    QEMU_CMD+=(-drive "file=$DISK,format=raw,if=virtio")
  fi
}

main() {
  ooonana_require_linux

  if [[ "$ISO_MODE" -eq 1 ]]; then
    [[ -f "$ISO" ]] || ooonana_die "missing ISO: $ISO"
    if [[ "$INSTALL" -eq 1 ]]; then
      [[ -n "$DISK" ]] || ooonana_die "--install requires --disk"
      [[ -f "$DISK" ]] || ooonana_die "missing disk: $DISK"
      SMOKE_MARKER="OOONANA_INSTALL_OK"
    fi
    build_iso_command
    if [[ "$DRY_RUN" -eq 1 ]]; then
      ooonana_print_command "${QEMU_CMD[@]}"
      exit 0
    fi
    ooonana_require_commands qemu-system-x86_64 timeout tee grep
    if [[ "$SMOKE" -eq 0 ]]; then
      exec "${QEMU_CMD[@]}"
    fi
    mkdir -p "$(dirname "$LOG_FILE")"
    ooonana_log "ISO smoke boot timeout: ${TIMEOUT_SECONDS}s"
    set +e
    timeout --foreground "$TIMEOUT_SECONDS" "${QEMU_CMD[@]}" 2>&1 | tee "$LOG_FILE"
    qemu_status=${PIPESTATUS[0]}
    set -e
    if grep -q "$SMOKE_MARKER" "$LOG_FILE"; then
      ooonana_log "QEMU ISO smoke boot passed"
      exit 0
    fi
    ooonana_die "QEMU ISO smoke boot failed, status $qemu_status, log: $LOG_FILE"
  fi

  if [[ "$INITRAMFS_BOOT" -eq 1 ]]; then
    [[ -n "$KERNEL" ]] || KERNEL="$(pick_scratch_kernel)"
    [[ -n "$INITRD" ]] || INITRD="$WORK_DIR/ooonana-scratch-initramfs.cpio.gz"
    [[ -f "$KERNEL" ]] || ooonana_die "missing kernel: $KERNEL"
    [[ -f "$INITRD" ]] || ooonana_die "missing initramfs: $INITRD"

    build_initramfs_command

    if [[ "$DRY_RUN" -eq 1 ]]; then
      ooonana_print_command "${QEMU_CMD[@]}"
      exit 0
    fi

    ooonana_require_commands qemu-system-x86_64 timeout tee grep

    if [[ "$SMOKE" -eq 0 ]]; then
      exec "${QEMU_CMD[@]}"
    fi

    mkdir -p "$(dirname "$LOG_FILE")"
    ooonana_log "scratch initramfs smoke boot timeout: ${TIMEOUT_SECONDS}s"
    set +e
    timeout --foreground "$TIMEOUT_SECONDS" "${QEMU_CMD[@]}" 2>&1 | tee "$LOG_FILE"
    qemu_status=${PIPESTATUS[0]}
    set -e

    if grep -q "$SMOKE_MARKER" "$LOG_FILE"; then
      ooonana_log "QEMU scratch initramfs smoke boot passed"
      exit 0
    fi

    ooonana_die "QEMU scratch initramfs smoke boot failed, status $qemu_status, log: $LOG_FILE"
  fi

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
