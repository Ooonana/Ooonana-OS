#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
KERNEL="$WORK_DIR/ooonana-kernel/vmlinuz-ooonana"
INITRAMFS="$WORK_DIR/ooonana-scratch-initramfs.cpio.gz"
LIVE_INITRAMFS="$WORK_DIR/ooonana-full-i3-live-initramfs.cpio.gz"
DISK_IMAGE="$WORK_DIR/ooonana-full-i3-disk.raw"
ISO_TREE="$WORK_DIR/full-i3-iso-tree"
ISO="$WORK_DIR/ooonana-full-i3.iso"
VOLUME="OOONANA_FULL_I3"
INSTALL_TARGET="auto"
SMOKE=0
LIVE_SMOKE=0
FORCE=0
UEFI_MODE="auto"

usage() {
  cat <<'USAGE'
Build Ooonana full-i3 live/installer ISO.

Usage:
  scripts/build-full-i3-iso.sh [options]

Options:
  --work-dir PATH      Build directory (default: /var/tmp/ooonana-os/build)
  --kernel PATH        Kernel path (default: WORK_DIR/ooonana-kernel/vmlinuz-ooonana)
  --initramfs PATH     Scratch installer initramfs path
  --live-initramfs PATH
                       Full-i3 live initramfs path
  --disk-image PATH    Full-i3 bootable raw disk image
  --iso-tree PATH      ISO staging directory (default: WORK_DIR/full-i3-iso-tree)
  --iso PATH           ISO output path (default: WORK_DIR/ooonana-full-i3.iso)
  --volume NAME        ISO volume label (default: OOONANA_FULL_I3)
  --install-target DEV Installer target device, or auto (default: auto)
  --smoke              Add smoke boot kernel argument
  --live-smoke         Smoke-test live i3 path instead of installer path
  --uefi               Require GRUB x86_64 EFI modules for UEFI boot
  --force              Delete existing ISO staging tree and ISO first
  -h, --help           Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; KERNEL="$2/ooonana-kernel/vmlinuz-ooonana"; INITRAMFS="$2/ooonana-scratch-initramfs.cpio.gz"; LIVE_INITRAMFS="$2/ooonana-full-i3-live-initramfs.cpio.gz"; DISK_IMAGE="$2/ooonana-full-i3-disk.raw"; ISO_TREE="$2/full-i3-iso-tree"; ISO="$2/ooonana-full-i3.iso"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --initramfs) INITRAMFS="$2"; shift 2 ;;
    --live-initramfs) LIVE_INITRAMFS="$2"; shift 2 ;;
    --disk-image) DISK_IMAGE="$2"; shift 2 ;;
    --iso-tree) ISO_TREE="$2"; shift 2 ;;
    --iso) ISO="$2"; shift 2 ;;
    --volume) VOLUME="$2"; shift 2 ;;
    --install-target) INSTALL_TARGET="$2"; shift 2 ;;
    --smoke) SMOKE=1; shift ;;
    --live-smoke) LIVE_SMOKE=1; shift ;;
    --uefi) UEFI_MODE="on"; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

write_grub_config() {
  local console_args="console=ttyS0 console=tty0"
  if [[ "$SMOKE" -eq 1 ]]; then
    console_args="console=tty0 console=ttyS0"
  fi
  local live_append="$console_args panic=1 rdinit=/init ooonana.live=1 ooonana.edition=full-i3"
  local persistent_append="$live_append ooonana.persistence=1"
  local install_append="$console_args panic=1 rdinit=/init ooonana.install=1 ooonana.install.target=$INSTALL_TARGET ooonana.install.image=/mnt/install/images/ooonana-full-i3-disk.raw"
  local safe_install_append="$install_append nomodeset"
  local default_entry=0
  if [[ "$SMOKE" -eq 1 && "$LIVE_SMOKE" -eq 1 ]]; then
    live_append="$live_append ooonana.smoke=1 ooonana.gui-smoke=1"
  elif [[ "$SMOKE" -eq 1 ]]; then
    default_entry=2
    install_append="$install_append ooonana.smoke=1"
  fi

  cat > "$ISO_TREE/boot/grub/grub.cfg" <<EOF
insmod all_video
if loadfont /boot/grub/fonts/unicode.pf2; then
  insmod gfxterm
fi
serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial
if [ -f /boot/grub/theme.txt ]; then
  set theme=/boot/grub/theme.txt
fi
if terminal_output gfxterm serial; then
  true
fi
clear
echo 'Ooonana OS'
if [ -f /boot/grub/ooonana-logo.txt ]; then
  cat /boot/grub/ooonana-logo.txt
fi
set timeout=5
set default=$default_entry

menuentry 'Ooonana OS Full i3 Live' {
  linux /boot/vmlinuz $live_append
  initrd /boot/live-initramfs.cpio.gz
}

menuentry 'Ooonana OS Full i3 Live (persistent USB)' {
  linux /boot/vmlinuz $persistent_append
  initrd /boot/live-initramfs.cpio.gz
}

menuentry 'Install Ooonana OS Full i3' {
  linux /boot/vmlinuz $install_append
  initrd /boot/install-initramfs.cpio.gz
}

menuentry 'Install Ooonana OS Full i3 (safe graphics)' {
  linux /boot/vmlinuz $safe_install_append
  initrd /boot/install-initramfs.cpio.gz
}
EOF
}

stage_iso_tree() {
  [[ -f "$KERNEL" ]] || ooonana_die "missing kernel: $KERNEL"
  [[ -f "$INITRAMFS" ]] || ooonana_die "missing initramfs: $INITRAMFS"
  [[ -f "$LIVE_INITRAMFS" ]] || ooonana_die "missing live initramfs: $LIVE_INITRAMFS"
  [[ -f "$DISK_IMAGE" ]] || ooonana_die "missing full-i3 disk image: $DISK_IMAGE"

  rm -rf "$ISO_TREE"
  mkdir -p "$ISO_TREE/boot/grub" "$ISO_TREE/images"

  install -m 0644 "$KERNEL" "$ISO_TREE/boot/vmlinuz"
  install -m 0644 "$INITRAMFS" "$ISO_TREE/boot/install-initramfs.cpio.gz"
  install -m 0644 "$LIVE_INITRAMFS" "$ISO_TREE/boot/live-initramfs.cpio.gz"
  install -m 0644 "$DISK_IMAGE" "$ISO_TREE/images/ooonana-full-i3-disk.raw"
  install -m 0644 "$ROOT/packages/ooonana/usr/share/ooonana/logo.txt" "$ISO_TREE/boot/grub/ooonana-logo.txt"
  cat > "$ISO_TREE/boot/grub/theme.txt" <<'EOF'
title-text: "Ooonana OS"
title-color: "#ffb21a"
desktop-color: "#050505"
terminal-font: "Unifont Regular 16"
message-color: "#ffb21a"
selected-item-color: "#050505"
selected-item-background-color: "#ffb21a"
item-color: "#ffb21a"
item-font: "Unifont Regular 16"
EOF
  write_grub_config
  chmod -R a+rwX "$ISO_TREE" 2>/dev/null || true
}

build_iso() {
  mkdir -p "$(dirname "$ISO")"
  rm -f "$ISO"
  grub-mkrescue -volid "$VOLUME" -o "$ISO" "$ISO_TREE"
}

validate_grub_modules() {
  [[ -d /usr/lib/grub/i386-pc ]] || ooonana_die "missing GRUB BIOS modules: install grub-pc-bin"
  if [[ -d /usr/lib/grub/x86_64-efi ]]; then
    ooonana_log "GRUB EFI modules found: building hybrid BIOS/UEFI ISO"
  elif [[ "$UEFI_MODE" == "on" ]]; then
    ooonana_die "missing GRUB EFI modules: install grub-efi-amd64-bin"
  else
    ooonana_log "GRUB EFI modules missing: building BIOS-only ISO"
  fi
}

main() {
  ooonana_require_linux
  ooonana_require_commands grub-mkrescue install
  validate_grub_modules

  if [[ "$FORCE" -eq 1 ]]; then
    rm -rf "$ISO_TREE" "$ISO"
  fi

  stage_iso_tree
  build_iso
  chmod a+rx "$(dirname "$WORK_DIR")" "$WORK_DIR" 2>/dev/null || true
  chmod a+rw "$ISO"

  ooonana_log "full-i3 live/installer iso ready: $ISO"
}

main "$@"
