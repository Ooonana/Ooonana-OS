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
assert_contains "$dry_run" "root=/dev/vda1 rw console=ttyS0 panic=1 init=/sbin/init ooonana.smoke=1"
assert_contains "$dry_run" "OOONANA_DISK_OK"
assert_not_contains "$dry_run" "systemd.unit"

printf 'ok scratch-disk\n'
