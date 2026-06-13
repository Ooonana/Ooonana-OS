#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-scratch-disk.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

assert_not_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" != *"$needle"* ]] || fail "unexpected: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable scratch disk builder"

script_src="$(<"$SCRIPT")"
assert_contains "$script_src" "grub-install"
assert_contains "$script_src" "part_msdos ext2"
assert_contains "$script_src" "ooonana_reexec_as_root"
assert_contains "$script_src" "unsafe mount point"
assert_contains "$script_src" "Ooonana OS Minimal"
assert_contains "$script_src" "ooonana-logo.txt"
assert_not_contains "$script_src" "set theme=/boot/grub/theme.txt"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana scratch boot disk"
assert_contains "$help" "--disk-image"
assert_contains "$help" "--size"
assert_contains "$help" "--smoke"
assert_contains "$help" "--dry-run"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/rootfs/etc" "$tmp/rootfs/usr/bin"
printf 'NAME="Ooonana OS"\n' > "$tmp/rootfs/etc/os-release"
printf 'kernel\n' > "$tmp/vmlinuz"

dry_run="$(bash "$SCRIPT" \
  --rootfs "$tmp/rootfs" \
  --kernel "$tmp/vmlinuz" \
  --disk-image "$tmp/ooonana-scratch-disk.raw" \
  --size 128M \
  --smoke \
  --force \
  --dry-run)"

assert_contains "$dry_run" "truncate -s 128M $tmp/ooonana-scratch-disk.raw"
assert_contains "$dry_run" "parted -s $tmp/ooonana-scratch-disk.raw mklabel msdos"
assert_contains "$dry_run" "mkfs.ext4 -F -L OOONANA_ROOT"
assert_contains "$dry_run" "grub-install --target=i386-pc"
assert_contains "$dry_run" "root=/dev/vda1 rw console=tty0 console=ttyS0 panic=1 init=/sbin/init ooonana.smoke=1"
assert_contains "$dry_run" "OOONANA_DISK_OK"
assert_not_contains "$dry_run" "systemd.unit"
assert_contains "$script_src" "terminal_input console serial"
assert_contains "$script_src" "terminal_output console serial"
assert_contains "$script_src" "terminal_output gfxterm serial"
assert_contains "$script_src" "set color_normal=yellow/black"
assert_contains "$script_src" "set color_highlight=black/yellow"
assert_contains "$script_src" 'title-color: "#ffb21a"'
assert_contains "$script_src" 'message-color: "#ffb21a"'
assert_not_contains "$script_src" "selected-item-color"
assert_not_contains "$script_src" "selected-item-background-color"
assert_not_contains "$script_src" "item-color"
assert_not_contains "$script_src" "item-font"

printf 'ok scratch-disk\n'
