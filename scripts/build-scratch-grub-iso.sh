#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
KERNEL="$WORK_DIR/ooonana-kernel/vmlinuz-ooonana"
INITRAMFS="$WORK_DIR/ooonana-scratch-initramfs.cpio.gz"
ROOTFS_IMAGE="$WORK_DIR/ooonana-scratch.ext4"
DISK_IMAGE=""
ISO_TREE="$WORK_DIR/scratch-grub-iso-tree"
ISO="$WORK_DIR/ooonana-scratch-grub.iso"
VOLUME="OOONANAMIN"
INSTALL=0
INSTALL_TARGET="/dev/vda"
SMOKE=0
FORCE=0
UEFI_MODE="auto"

usage() {
  cat <<'USAGE'
Build Ooonana scratch GRUB ISO.

Usage:
  scripts/build-scratch-grub-iso.sh [options]

Options:
  --work-dir PATH      Build directory (default: /var/tmp/ooonana-os/build)
  --kernel PATH        Kernel path (default: WORK_DIR/ooonana-kernel/vmlinuz-ooonana)
  --initramfs PATH     Scratch initramfs path (default: WORK_DIR/ooonana-scratch-initramfs.cpio.gz)
  --rootfs-image PATH  Scratch ext4 image for installer ISO (default: WORK_DIR/ooonana-scratch.ext4)
  --disk-image PATH    Bootable raw disk image for installer ISO
  --iso-tree PATH      ISO staging directory (default: WORK_DIR/scratch-grub-iso-tree)
  --iso PATH           ISO output path (default: WORK_DIR/ooonana-scratch-grub.iso)
  --volume NAME        ISO volume label (default: OOONANAMIN, 11 chars or less for USB tools)
  --install            Build installer ISO that writes rootfs image to target
  --install-target DEV Installer target device inside QEMU (default: /dev/vda)
  --smoke              Boot straight to Ooonana smoke marker
  --uefi               Require GRUB x86_64 EFI modules for UEFI boot
  --force              Delete existing ISO staging tree and ISO first
  -h, --help           Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; KERNEL="$2/ooonana-kernel/vmlinuz-ooonana"; INITRAMFS="$2/ooonana-scratch-initramfs.cpio.gz"; ROOTFS_IMAGE="$2/ooonana-scratch.ext4"; ISO_TREE="$2/scratch-grub-iso-tree"; ISO="$2/ooonana-scratch-grub.iso"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --initramfs) INITRAMFS="$2"; shift 2 ;;
    --rootfs-image) ROOTFS_IMAGE="$2"; shift 2 ;;
    --disk-image) DISK_IMAGE="$2"; shift 2 ;;
    --iso-tree) ISO_TREE="$2"; shift 2 ;;
    --iso) ISO="$2"; shift 2 ;;
    --volume) VOLUME="$2"; shift 2 ;;
    --install) INSTALL=1; shift ;;
    --install-target) INSTALL_TARGET="$2"; shift 2 ;;
    --smoke) SMOKE=1; shift ;;
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
  local live_append="$console_args panic=1 rdinit=/init"
  local install_append="$console_args panic=1 rdinit=/init ooonana.install=1 ooonana.install.target=$INSTALL_TARGET"
  local default_entry=0
  if [[ "$INSTALL" -eq 1 ]]; then
    default_entry=1
  fi
  if [[ "$SMOKE" -eq 1 ]]; then
    if [[ "$INSTALL" -eq 1 ]]; then
      install_append="$install_append ooonana.smoke=1"
    else
      live_append="$live_append ooonana.smoke=1"
    fi
  fi

  cat > "$ISO_TREE/boot/grub/grub.cfg" <<EOF
insmod all_video
if loadfont /boot/grub/fonts/unicode.pf2; then
  insmod gfxterm
fi
serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial
set color_normal=yellow/black
set color_highlight=black/yellow
if terminal_output gfxterm serial; then
  true
fi
clear
echo 'Ooonana OS Minimal'
if [ -f /boot/grub/ooonana-logo.txt ]; then
  cat /boot/grub/ooonana-logo.txt
fi
if [ -f /boot/grub/theme.txt ]; then
  set theme=/boot/grub/theme.txt
  export theme
fi
set timeout=5
set default=$default_entry

menuentry 'Ooonana OS Minimal' {
  linux /boot/vmlinuz $live_append
  initrd /boot/initramfs.cpio.gz
}
EOF
  if [[ "$INSTALL" -eq 1 ]]; then
    cat >> "$ISO_TREE/boot/grub/grub.cfg" <<EOF

menuentry 'Install Ooonana OS Minimal' {
  linux /boot/vmlinuz $install_append
  initrd /boot/initramfs.cpio.gz
}
EOF
  fi
}

write_rufus_note() {
  cat > "$ISO_TREE/RUFUS.md" <<'EOF'
# Ooonana OS Minimal Rufus USB

Recommended Rufus mode:

1. Select `ooonana-scratch.iso`.
2. Click Start.
3. If Rufus says `ISOHybrid image detected`, choose `Write in DD Image mode`.
4. Disable Secure Boot. Ooonana uses unsigned GRUB/kernel builds right now.

Boot support:

- UEFI: needs the ISO built with GRUB EFI modules.
- Legacy BIOS/CSM: GRUB BIOS path is included.
- Minimal shell: use `Ooonana OS Minimal`.
- Installer: use `Install Ooonana OS Minimal` when present.
EOF
}

stage_iso_tree() {
  [[ -f "$KERNEL" ]] || ooonana_die "missing kernel: $KERNEL"
  [[ -f "$INITRAMFS" ]] || ooonana_die "missing initramfs: $INITRAMFS"
  if [[ "$INSTALL" -eq 1 && -n "$DISK_IMAGE" ]]; then
    [[ -f "$DISK_IMAGE" ]] || ooonana_die "missing disk image: $DISK_IMAGE"
  elif [[ "$INSTALL" -eq 1 ]]; then
    [[ -f "$ROOTFS_IMAGE" ]] || ooonana_die "missing rootfs image: $ROOTFS_IMAGE"
  fi

  rm -rf "$ISO_TREE"
  mkdir -p "$ISO_TREE/boot/grub" "$ISO_TREE/images"

  install -m 0644 "$KERNEL" "$ISO_TREE/boot/vmlinuz"
  install -m 0644 "$INITRAMFS" "$ISO_TREE/boot/initramfs.cpio.gz"
  install -m 0644 "$ROOT/packages/ooonana/usr/share/ooonana/logo.txt" "$ISO_TREE/boot/grub/ooonana-logo.txt"
  write_rufus_note
  cat > "$ISO_TREE/boot/grub/theme.txt" <<'EOF'
title-text: "Ooonana OS Minimal"
title-color: "#ffb21a"
desktop-color: "#050505"
terminal-font: "Unifont Regular 16"
message-color: "#ffb21a"
message-bg-color: "#050505"

+ boot_menu {
  left = 16%
  top = 32%
  width = 68%
  height = 38%
}

+ label {
  text = "boot time"
  left = 16%
  top = 82%
  width = 68%
  height = 18
  color = "#ffb21a"
  align = "center"
}

+ progress_bar {
  id = "__timeout__"
  left = 16%
  top = 86%
  width = 68%
  height = 18
  fg_color = "#ffb21a"
  bg_color = "#050505"
  border_color = "#ffb21a"
}
EOF
  if [[ "$INSTALL" -eq 1 && -n "$DISK_IMAGE" ]]; then
    install -m 0644 "$DISK_IMAGE" "$ISO_TREE/images/ooonana-scratch-disk.raw"
  elif [[ "$INSTALL" -eq 1 ]]; then
    install -m 0644 "$ROOTFS_IMAGE" "$ISO_TREE/images/ooonana-scratch.ext4"
  fi
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

  ooonana_log "scratch GRUB iso ready: $ISO"
}

main "$@"
