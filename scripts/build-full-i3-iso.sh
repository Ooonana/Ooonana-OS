#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
KERNEL="$WORK_DIR/ooonana-kernel/vmlinuz-ooonana"
INITRAMFS="$WORK_DIR/ooonana-scratch-initramfs.cpio.gz"
DISK_IMAGE="$WORK_DIR/ooonana-full-i3-disk.raw"
ISO_TREE="$WORK_DIR/full-i3-iso-tree"
ISO="$WORK_DIR/ooonana-full-i3.iso"
VOLUME="OOONANA_FULL_I3"
INSTALL_TARGET="/dev/vda"
SMOKE=0
FORCE=0

usage() {
  cat <<'USAGE'
Build Ooonana full-i3 installer ISO.

Usage:
  scripts/build-full-i3-iso.sh [options]

Options:
  --work-dir PATH      Build directory (default: /var/tmp/ooonana-os/build)
  --kernel PATH        Kernel path (default: WORK_DIR/ooonana-kernel/vmlinuz-ooonana)
  --initramfs PATH     Scratch installer initramfs path
  --disk-image PATH    Full-i3 bootable raw disk image
  --iso-tree PATH      ISO staging directory (default: WORK_DIR/full-i3-iso-tree)
  --iso PATH           ISO output path (default: WORK_DIR/ooonana-full-i3.iso)
  --volume NAME        ISO volume label (default: OOONANA_FULL_I3)
  --install-target DEV Installer target device inside QEMU (default: /dev/vda)
  --smoke              Add smoke boot kernel argument
  --force              Delete existing ISO staging tree and ISO first
  -h, --help           Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; KERNEL="$2/ooonana-kernel/vmlinuz-ooonana"; INITRAMFS="$2/ooonana-scratch-initramfs.cpio.gz"; DISK_IMAGE="$2/ooonana-full-i3-disk.raw"; ISO_TREE="$2/full-i3-iso-tree"; ISO="$2/ooonana-full-i3.iso"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --initramfs) INITRAMFS="$2"; shift 2 ;;
    --disk-image) DISK_IMAGE="$2"; shift 2 ;;
    --iso-tree) ISO_TREE="$2"; shift 2 ;;
    --iso) ISO="$2"; shift 2 ;;
    --volume) VOLUME="$2"; shift 2 ;;
    --install-target) INSTALL_TARGET="$2"; shift 2 ;;
    --smoke) SMOKE=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

write_grub_config() {
  local append="console=ttyS0 panic=1 rdinit=/init ooonana.install=1 ooonana.install.target=$INSTALL_TARGET ooonana.install.image=/mnt/install/images/ooonana-full-i3-disk.raw"
  if [[ "$SMOKE" -eq 1 ]]; then
    append="$append ooonana.smoke=1"
  fi

  cat > "$ISO_TREE/boot/grub/grub.cfg" <<EOF
serial --unit=0 --speed=115200
terminal_input serial
terminal_output serial
set timeout=1
set default=0

menuentry 'Ooonana OS Full i3 Installer' {
  linux /boot/vmlinuz $append
  initrd /boot/initramfs.cpio.gz
}
EOF
}

stage_iso_tree() {
  [[ -f "$KERNEL" ]] || ooonana_die "missing kernel: $KERNEL"
  [[ -f "$INITRAMFS" ]] || ooonana_die "missing initramfs: $INITRAMFS"
  [[ -f "$DISK_IMAGE" ]] || ooonana_die "missing full-i3 disk image: $DISK_IMAGE"

  rm -rf "$ISO_TREE"
  mkdir -p "$ISO_TREE/boot/grub" "$ISO_TREE/images"

  install -m 0644 "$KERNEL" "$ISO_TREE/boot/vmlinuz"
  install -m 0644 "$INITRAMFS" "$ISO_TREE/boot/initramfs.cpio.gz"
  install -m 0644 "$DISK_IMAGE" "$ISO_TREE/images/ooonana-full-i3-disk.raw"
  write_grub_config
  chmod -R a+rwX "$ISO_TREE" 2>/dev/null || true
}

build_iso() {
  mkdir -p "$(dirname "$ISO")"
  rm -f "$ISO"
  grub-mkrescue -volid "$VOLUME" -o "$ISO" "$ISO_TREE"
}

main() {
  ooonana_require_linux
  ooonana_require_commands grub-mkrescue install
  [[ -d /usr/lib/grub/i386-pc ]] || ooonana_die "missing GRUB BIOS modules: install grub-pc-bin"

  if [[ "$FORCE" -eq 1 ]]; then
    rm -rf "$ISO_TREE" "$ISO"
  fi

  stage_iso_tree
  build_iso
  chmod a+rx "$(dirname "$WORK_DIR")" "$WORK_DIR" 2>/dev/null || true
  chmod a+rw "$ISO"

  ooonana_log "full-i3 installer iso ready: $ISO"
}

main "$@"
