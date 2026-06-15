#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOT_MATRIX="$ROOT/scripts/verify-installed-boot-matrix.sh"
SECURE_BOOT="$ROOT/scripts/build-secure-boot-assets.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$BOOT_MATRIX" ]] || fail "boot matrix script not executable"
[[ -x "$SECURE_BOOT" ]] || fail "secure boot script not executable"

boot_plan="$(bash "$BOOT_MATRIX" --disk /tmp/ooonana-installed.raw --iso /tmp/ooonana-full-i3.iso --dry-run)"
assert_contains "$boot_plan" "[qemu-bios]"
assert_contains "$boot_plan" "[qemu-uefi]"
assert_contains "$boot_plan" "[vmware]"
assert_contains "$boot_plan" "[real-pc-rufus]"
assert_contains "$boot_plan" "DD mode"
assert_contains "$boot_plan" "OOONANA_BOOT_MATRIX_PLAN_OK"

secure_plan="$(bash "$SECURE_BOOT" --efi-dir /tmp/efi --kernel /tmp/vmlinuz --key /tmp/MOK.key --cert /tmp/MOK.crt --out-dir /tmp/sb --dry-run)"
assert_contains "$secure_plan" "sbsign"
assert_contains "$secure_plan" "mokutil --import"
assert_contains "$secure_plan" "OOONANA_SECURE_BOOT_PLAN_OK"

printf 'ok boot-matrix-secure-boot\n'
