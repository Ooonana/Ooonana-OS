#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISO="${OOONANA_ISO:-/var/tmp/ooonana-os/release/ooonana-full-i3.iso}"
EDITION="full-i3"

usage() {
  cat <<'USAGE'
Verify Ooonana ISO Rufus USB readiness.

Usage:
  scripts/verify-rufus-iso.sh [options]

Options:
  --iso PATH             ISO to inspect (default: /var/tmp/ooonana-os/release/ooonana-full-i3.iso)
  --edition full-i3|minimal
                         Expected ISO edition (default: full-i3)
  -h, --help             Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iso) ISO="$2"; shift 2 ;;
    --edition) EDITION="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'verify-rufus-iso: unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done

case "$EDITION" in
  full-i3|minimal) ;;
  *) printf 'verify-rufus-iso: bad edition: %s\n' "$EDITION" >&2; exit 1 ;;
esac

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

need_contains() {
  local path="$1"
  local needle="$2"
  [[ -f "$path" ]] || fail "missing file: $path"
  grep -qF "$needle" "$path" || fail "missing in $path: $needle"
}

done_item() {
  printf '[done] %s\n' "$*"
}

need_command xorriso
[[ -f "$ISO" ]] || fail "missing ISO: $ISO"

report="$(xorriso -indev "$ISO" -report_el_torito as_mkisofs 2>/dev/null)"
if [[ "$report" != *"--grub2-mbr"* && "$report" != *"-isohybrid-mbr"* ]]; then
  fail "ISO missing hybrid BIOS MBR path for Rufus DD mode"
fi
[[ "$report" == *"-eltorito-alt-boot"* ]] || fail "ISO missing alternate El Torito boot catalog"
[[ "$report" == *"-e '/efi.img'"* || "$report" == *'-e "/efi.img"'* ]] || fail "ISO missing UEFI EFI image"
done_item "ISOHybrid BIOS and UEFI boot paths"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
xorriso -osirrox on -indev "$ISO" -extract /boot/grub/grub.cfg "$tmp/grub.cfg" >/dev/null 2>&1 ||
  fail "could not extract GRUB config from ISO"
xorriso -osirrox on -indev "$ISO" -extract /boot/grub/theme.txt "$tmp/theme.txt" >/dev/null 2>&1 || true
xorriso -osirrox on -indev "$ISO" -extract /RUFUS.md "$tmp/RUFUS.md" >/dev/null 2>&1 ||
  fail "could not extract Rufus note from ISO"

need_contains "$tmp/grub.cfg" "terminal_input console serial"
case "$EDITION" in
  full-i3)
    need_contains "$tmp/grub.cfg" "insmod font"
    need_contains "$tmp/grub.cfg" "set gfxmode=1024x768,800x600,auto"
    need_contains "$tmp/grub.cfg" "set gfxpayload=keep"
    need_contains "$tmp/grub.cfg" "terminal_output gfxterm serial"
    need_contains "$tmp/grub.cfg" "insmod gfxmenu"
    need_contains "$tmp/grub.cfg" "insmod gfxterm_menu"
    ;;
  minimal)
    need_contains "$tmp/grub.cfg" "terminal_output console serial"
    ;;
esac
need_contains "$tmp/grub.cfg" "set color_normal=yellow/black"
need_contains "$tmp/grub.cfg" "set color_highlight=black/yellow"
if grep -qF 'set theme=/boot/grub/theme.txt' "$tmp/grub.cfg"; then
  [[ -f "$tmp/theme.txt" ]] || fail "GRUB config loads missing theme file"
  need_contains "$tmp/theme.txt" "+ progress_bar"
  need_contains "$tmp/theme.txt" 'id = "__timeout__"'
  need_contains "$tmp/theme.txt" 'fg_color = "#ffb21a"'
  need_contains "$tmp/theme.txt" 'bg_color = "#1b1202"'
  done_item "GRUB timeout progress bar"
fi
need_contains "$tmp/grub.cfg" "set timeout=5"
need_contains "$tmp/grub.cfg" "cat /boot/grub/ooonana-logo.txt"
if [[ -f "$tmp/theme.txt" ]] && grep -q 'selected-item-color\|selected-item-background-color\|item-color\|item-font' "$tmp/theme.txt"; then
  fail "GRUB theme contains invalid menu color property"
fi
need_contains "$tmp/RUFUS.md" "Write in DD Image mode"
need_contains "$tmp/RUFUS.md" "Disable Secure Boot"
done_item "Rufus DD-mode note and orange GRUB"

case "$EDITION" in
  full-i3)
    need_contains "$tmp/grub.cfg" "Ooonana OS Full i3 Live"
    need_contains "$tmp/grub.cfg" "Ooonana OS Full i3 Live (persistent USB)"
    need_contains "$tmp/grub.cfg" "Install Ooonana OS Full i3"
    need_contains "$tmp/grub.cfg" "Install Ooonana OS Full i3 (safe graphics)"
    need_contains "$tmp/grub.cfg" "ooonana.persistence=1"
    need_contains "$tmp/grub.cfg" "ooonana.install=1 ooonana.edition=full-i3"
    need_contains "$tmp/grub.cfg" "initrd /boot/live-initramfs.cpio.gz"
    need_contains "$tmp/RUFUS.md" "OOONANA_PERSIST"
    ;;
  minimal)
    need_contains "$tmp/grub.cfg" "Ooonana OS Minimal"
    need_contains "$tmp/RUFUS.md" "Ooonana OS Minimal"
    ;;
esac
done_item "edition menus"

if grep -q 'ooonana.smoke=1\|ooonana.gui-smoke=1' "$tmp/grub.cfg"; then
  fail "release ISO GRUB config contains smoke-only boot args"
fi
done_item "release GRUB has no smoke auto-reboot args"

need_contains "$ROOT/scripts/build-full-i3-iso.sh" 'VOLUME="OOONANAUSB"'
need_contains "$ROOT/scripts/build-scratch-grub-iso.sh" 'VOLUME="OOONANAMIN"'
done_item "USB-friendly volume labels"

printf 'OOONANA_RUFUS_ISO_OK\n'
