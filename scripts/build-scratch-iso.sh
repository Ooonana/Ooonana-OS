#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
KERNEL_ROOTFS="$WORK_DIR/rootfs"
INITRAMFS="$WORK_DIR/ooonana-scratch-initramfs.cpio.gz"
ISO_TREE="$WORK_DIR/scratch-iso-tree"
ISO="$WORK_DIR/ooonana-scratch.iso"
OOONANA_KERNEL="$WORK_DIR/ooonana-kernel/vmlinuz-ooonana"
KERNEL=""
VOLUME="OOONANA_SCRATCH"
SMOKE=0
FORCE=0

usage() {
  cat <<'USAGE'
Build Ooonana scratch boot ISO.

Usage:
  scripts/build-scratch-iso.sh [options]

Options:
  --work-dir PATH       Build directory (default: /var/tmp/ooonana-os/build)
  --kernel-rootfs PATH  Rootfs with /boot/vmlinuz-* helper kernel (default: WORK_DIR/rootfs)
  --kernel PATH         Kernel path (default: WORK_DIR/ooonana-kernel/vmlinuz-ooonana, fallback helper rootfs)
  --initramfs PATH      Scratch initramfs path (default: WORK_DIR/ooonana-scratch-initramfs.cpio.gz)
  --iso-tree PATH       ISO staging directory (default: WORK_DIR/scratch-iso-tree)
  --iso PATH            ISO output path (default: WORK_DIR/ooonana-scratch.iso)
  --volume NAME         ISO volume label (default: OOONANA_SCRATCH)
  --smoke               Boot straight to Ooonana smoke marker
  --force               Delete existing ISO staging tree and ISO first
  -h, --help            Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; KERNEL_ROOTFS="$2/rootfs"; INITRAMFS="$2/ooonana-scratch-initramfs.cpio.gz"; ISO_TREE="$2/scratch-iso-tree"; ISO="$2/ooonana-scratch.iso"; OOONANA_KERNEL="$2/ooonana-kernel/vmlinuz-ooonana"; shift 2 ;;
    --kernel-rootfs) KERNEL_ROOTFS="$2"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --initramfs) INITRAMFS="$2"; shift 2 ;;
    --iso-tree) ISO_TREE="$2"; shift 2 ;;
    --iso) ISO="$2"; shift 2 ;;
    --volume) VOLUME="$2"; shift 2 ;;
    --smoke) SMOKE=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

pick_latest_kernel() {
  local latest
  latest="$(find "$KERNEL_ROOTFS/boot" -maxdepth 1 -type f -name 'vmlinuz-*' | sort -V | tail -n 1)"
  [[ -n "$latest" ]] || ooonana_die "missing helper kernel in $KERNEL_ROOTFS/boot"
  printf '%s\n' "$latest"
}

pick_default_kernel() {
  if [[ -f "$OOONANA_KERNEL" ]]; then
    printf '%s\n' "$OOONANA_KERNEL"
    return 0
  fi

  pick_latest_kernel
}

first_existing() {
  local path
  for path in "$@"; do
    if [[ -n "$path" && -f "$path" ]]; then
      printf '%s\n' "$path"
      return 0
    fi
  done
  return 1
}

write_isolinux_config() {
  local append="console=ttyS0 panic=1 rdinit=/init"
  if [[ "$SMOKE" -eq 1 ]]; then
    append="$append ooonana.smoke=1"
  fi

  cat > "$ISO_TREE/isolinux/isolinux.cfg" <<EOF
SERIAL 0 115200
CONSOLE 0
DEFAULT ooonana
PROMPT 0
TIMEOUT 10

LABEL ooonana
  KERNEL /boot/vmlinuz
  INITRD /boot/initramfs.cpio.gz
  APPEND $append
EOF
}

stage_iso_tree() {
  local isolinux_bin ldlinux_c32

  [[ -n "$KERNEL" ]] || KERNEL="$(pick_default_kernel)"
  [[ -f "$KERNEL" ]] || ooonana_die "missing kernel: $KERNEL"
  [[ -f "$INITRAMFS" ]] || ooonana_die "missing initramfs: $INITRAMFS"

  isolinux_bin="$(first_existing "${OOONANA_ISOLINUX_BIN:-}" /usr/lib/ISOLINUX/isolinux.bin /usr/lib/syslinux/isolinux.bin)" ||
    ooonana_die "missing isolinux.bin"
  ldlinux_c32="$(first_existing "${OOONANA_LDLINUX_C32:-}" /usr/lib/syslinux/modules/bios/ldlinux.c32 /usr/lib/syslinux/ldlinux.c32)" ||
    ooonana_die "missing ldlinux.c32"

  rm -rf "$ISO_TREE"
  mkdir -p "$ISO_TREE/boot" "$ISO_TREE/isolinux"

  install -m 0644 "$KERNEL" "$ISO_TREE/boot/vmlinuz"
  install -m 0644 "$INITRAMFS" "$ISO_TREE/boot/initramfs.cpio.gz"
  install -m 0644 "$isolinux_bin" "$ISO_TREE/isolinux/isolinux.bin"
  install -m 0644 "$ldlinux_c32" "$ISO_TREE/isolinux/ldlinux.c32"

  write_isolinux_config
  chmod -R a+rwX "$ISO_TREE" 2>/dev/null || true
}

build_iso() {
  mkdir -p "$(dirname "$ISO")"
  rm -f "$ISO"
  xorriso -as mkisofs \
    -r -J -l \
    -V "$VOLUME" \
    -o "$ISO" \
    -b isolinux/isolinux.bin \
    -c isolinux/boot.cat \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    "$ISO_TREE"
}

main() {
  ooonana_require_linux
  ooonana_require_commands find sort tail install xorriso

  if [[ "$FORCE" -eq 1 ]]; then
    rm -rf "$ISO_TREE" "$ISO"
  fi

  stage_iso_tree
  build_iso
  chmod a+rx "$(dirname "$WORK_DIR")" "$WORK_DIR" 2>/dev/null || true
  chmod a+rw "$ISO"

  ooonana_log "scratch iso ready: $ISO"
}

main "$@"
