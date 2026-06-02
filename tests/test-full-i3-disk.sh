#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-full-i3-disk.sh"

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

[[ -x "$SCRIPT" ]] || fail "missing executable full-i3 disk builder"

script_src="$(<"$SCRIPT")"
assert_contains "$script_src" "Ooonana OS Full i3"
assert_contains "$script_src" "ooonana.edition=full-i3"
assert_contains "$script_src" "ooonana.gui-smoke=1"
assert_contains "$script_src" "OOONANA_FULL_I3_DISK_OK"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana full-i3 boot disk"
assert_contains "$help" "--rootfs"
assert_contains "$help" "--disk-image"
assert_contains "$help" "--gui-smoke"
assert_contains "$help" "--dry-run"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/rootfs/etc/ooonana" "$tmp/rootfs/usr/bin"
printf 'full-i3\n' > "$tmp/rootfs/etc/ooonana/edition"
printf 'kernel\n' > "$tmp/vmlinuz"

dry_run="$(bash "$SCRIPT" \
  --rootfs "$tmp/rootfs" \
  --kernel "$tmp/vmlinuz" \
  --disk-image "$tmp/ooonana-full-i3-disk.raw" \
  --size 768M \
  --smoke \
  --gui-smoke \
  --force \
  --dry-run)"

assert_contains "$dry_run" "truncate -s 768M $tmp/ooonana-full-i3-disk.raw"
assert_contains "$dry_run" "parted -s $tmp/ooonana-full-i3-disk.raw mklabel msdos"
assert_contains "$dry_run" "mkfs.ext4 -F -L OOONANA_ROOT"
assert_contains "$dry_run" "grub-install --target=i386-pc"
assert_contains "$dry_run" "root=/dev/vda1 rw console=ttyS0 panic=1 init=/sbin/init ooonana.edition=full-i3 ooonana.smoke=1 ooonana.gui-smoke=1"
assert_contains "$dry_run" "OOONANA_FULL_I3_DISK_OK"
assert_not_contains "$dry_run" "systemd.unit"

printf 'ok full-i3-disk\n'
