#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RELEASE_DIR="${OOONANA_RELEASE_DIR:-/var/tmp/ooonana-os/release}"

usage() {
  cat <<'USAGE'
Verify Ooonana VMware, UEFI, and input readiness.

Usage:
  scripts/verify-vmware-uefi-input.sh [options]

Options:
  --release-dir PATH  Release artifact directory (default: /var/tmp/ooonana-os/release)
  -h, --help          Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release-dir) RELEASE_DIR="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'verify-vmware-uefi-input: unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

need_file() {
  [[ -f "$1" ]] || fail "missing file: $1"
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

need_contains() {
  local path="$1"
  local needle="$2"
  need_file "$path"
  grep -qF "$needle" "$path" || fail "missing in $path: $needle"
}

done_item() {
  printf '[done] %s\n' "$*"
}

ISO="$RELEASE_DIR/ooonana-full-i3.iso"
UEFI_LOG="$RELEASE_DIR/qemu-full-i3-uefi-installer.log"
LIVE_LOG="$RELEASE_DIR/qemu-full-i3-live-iso.log"

need_command xorriso
need_file "$ISO"
need_file "$UEFI_LOG"
need_file "$LIVE_LOG"

report="$(xorriso -indev "$ISO" -report_el_torito as_mkisofs 2>/dev/null)"
[[ "$report" == *"--grub2-mbr"* ]] || fail "ISO missing BIOS GRUB El Torito boot"
[[ "$report" == *"-e '/efi.img'"* ]] || fail "ISO missing EFI image"
[[ "$report" == *"-eltorito-alt-boot"* ]] || fail "ISO missing hybrid alternate boot catalog"
done_item "UEFI + BIOS hybrid ISO"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
xorriso -osirrox on -indev "$ISO" -extract /boot/grub/grub.cfg "$tmp/grub.cfg" >/dev/null 2>&1 ||
  fail "could not extract GRUB config from ISO"
need_contains "$tmp/grub.cfg" "terminal_input console serial"
need_contains "$tmp/grub.cfg" "terminal_output console serial"
need_contains "$tmp/grub.cfg" "console=ttyS0 console=tty0"
done_item "VMware-visible GRUB and VGA-first release console"

need_contains "$ROOT/scripts/build-scratch-rootfs.sh" 'console_device="/dev/tty1"'
need_contains "$ROOT/scripts/build-scratch-rootfs.sh" 'console_device="/dev/ttyS0"'
need_contains "$ROOT/scripts/build-scratch-rootfs.sh" "mount -t proc proc /proc"
done_item "init chooses tty1 for humans and ttyS0 for smoke"

need_contains "$ROOT/configs/packages/full-i3.list" "eudev"
need_contains "$ROOT/configs/packages/full-i3.list" "xf86-input-libinput"
need_contains "$ROOT/scripts/build-full-i3-rootfs.sh" "udevd --daemon"
need_contains "$ROOT/scripts/build-full-i3-rootfs.sh" 'Driver "libinput"'
need_contains "$ROOT/scripts/build-full-i3-rootfs.sh" 'MatchIsKeyboard "on"'
need_contains "$ROOT/scripts/build-full-i3-rootfs.sh" 'MatchIsPointer "on"'
done_item "full-i3 input stack"

need_contains "$ROOT/README.md" "full-i3 VM RAM         2048 MB tested"
need_contains "$ROOT/README.md" "ooonana-full-i3-live-rootfs.ext4"
need_contains "$ROOT/README.md" "EFI/simple framebuffer"
done_item "VMware full-i3 2GB live-rootfs fix"

need_contains "$UEFI_LOG" "OOONANA_INSTALL_OK"
need_contains "$LIVE_LOG" "OOONANA_FULL_I3_OK"
need_contains "$LIVE_LOG" 'Using config directory: "/etc/X11/xorg.conf.d"'
done_item "QEMU UEFI installer and live i3 proof logs"

printf 'OOONANA_VMWARE_UEFI_INPUT_OK\n'
