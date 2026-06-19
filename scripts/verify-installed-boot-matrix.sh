#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DISK=""
ISO=""
MEMORY="2048"
DRY_RUN=0

usage() {
  cat <<'USAGE'
Verify installed Ooonana OS boot matrix.

Usage:
  scripts/verify-installed-boot-matrix.sh --disk PATH [--iso PATH] [--memory MB] [--dry-run]

Checks:
  qemu-bios       installed disk legacy BIOS boot
  qemu-uefi       installed disk UEFI boot when OVMF exists
  vmware          manual VM checklist
  real-pc-rufus   manual Rufus USB checklist
USAGE
}

die() {
  printf 'verify-boot-matrix: %s\n' "$*" >&2
  exit 1
}

print_cmd() {
  local arg
  for arg in "$@"; do
    printf '%q ' "$arg"
  done
  printf '\n'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --disk) DISK="$2"; shift 2 ;;
    --iso) ISO="$2"; shift 2 ;;
    --memory) MEMORY="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[[ -n "$DISK" ]] || die "--disk required"
[[ "$DRY_RUN" -eq 1 || -f "$DISK" ]] || die "disk missing: $DISK"

qemu_bios=(qemu-system-x86_64 -m "$MEMORY" -drive "file=$DISK,format=raw,if=virtio" -serial stdio -display none -no-reboot)
qemu_uefi=(qemu-system-x86_64 -m "$MEMORY" -drive "file=$DISK,format=raw,if=virtio" -bios /usr/share/OVMF/OVMF_CODE.fd -serial stdio -display none -no-reboot)

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '[qemu-bios] '
  print_cmd "${qemu_bios[@]}"
  printf '[qemu-uefi] '
  print_cmd "${qemu_uefi[@]}"
  printf '[vmware] create VM, firmware BIOS then UEFI, attach disk %s, expect GRUB then Ooonana login/i3\n' "$DISK"
  if [[ -n "$ISO" ]]; then
    printf '[real-pc-rufus] flash %s in ISO mode, disable Secure Boot unless signed, test live persistent install\n' "$ISO"
  else
    printf '[real-pc-rufus] flash release ISO in ISO mode, disable Secure Boot unless signed, test live persistent install\n'
  fi
  printf 'OOONANA_BOOT_MATRIX_PLAN_OK\n'
  exit 0
fi

command -v qemu-system-x86_64 >/dev/null 2>&1 || die "missing qemu-system-x86_64"

printf '[qemu-bios] start\n'
"${qemu_bios[@]}"
printf '[qemu-bios] done\n'

if [[ -f /usr/share/OVMF/OVMF_CODE.fd ]]; then
  printf '[qemu-uefi] start\n'
  "${qemu_uefi[@]}"
  printf '[qemu-uefi] done\n'
else
  printf '[qemu-uefi] skipped: missing /usr/share/OVMF/OVMF_CODE.fd\n'
fi

printf 'OOONANA_BOOT_MATRIX_OK\n'
