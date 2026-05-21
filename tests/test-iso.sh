#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

iso_help="$(bash "$ROOT/scripts/build-iso.sh" --help)"
assert_contains "$iso_help" "Build Ooonana boot ISO"
assert_contains "$iso_help" "--rootfs"
assert_contains "$iso_help" "--iso"
assert_contains "$iso_help" "--volume"

deps_help="$(bash "$ROOT/scripts/install-wsl-deps.sh" --help)"
assert_contains "$deps_help" "xorriso"
assert_contains "$deps_help" "isolinux"
assert_contains "$deps_help" "syslinux-common"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/rootfs/boot"
touch "$tmp/rootfs/boot/vmlinuz-6.1.0-ooonana"
touch "$tmp/rootfs/boot/initrd.img-6.1.0-ooonana"
touch "$tmp/ooonana.iso"

dry_run="$(bash "$ROOT/scripts/run-qemu.sh" --dry-run --smoke --iso "$tmp/ooonana.iso" --rootfs "$tmp/rootfs")"
assert_contains "$dry_run" "qemu-system-x86_64"
assert_contains "$dry_run" "-cdrom"
assert_contains "$dry_run" "$tmp/ooonana.iso"
assert_contains "$dry_run" "-boot d"
assert_not_contains "$dry_run" "-kernel"
assert_not_contains "$dry_run" "root=/dev/vda"

mkdir -p "$tmp/build"
touch "$tmp/build/ooonana.iso" "$tmp/build/ooonana-rootfs.ext4"
default_iso_dry_run="$(OOONANA_BUILD_DIR="$tmp/build" bash "$ROOT/scripts/run-qemu.sh" --dry-run --smoke --iso "$tmp/build/ooonana.iso" --rootfs "$tmp/rootfs")"
assert_contains "$default_iso_dry_run" "-cdrom"
assert_contains "$default_iso_dry_run" "$tmp/build/ooonana.iso"
assert_not_contains "$default_iso_dry_run" "-drive"
assert_not_contains "$default_iso_dry_run" "root=/dev/vda"

printf 'ok iso\n'
