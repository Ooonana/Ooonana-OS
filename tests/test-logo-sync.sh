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

readme_logo="$(
  awk '
    /^```$/ {
      fence += 1
      if (fence == 2) {
        exit
      }
      next
    }
    fence == 1 {
      print
    }
  ' "$ROOT/README.md"
)"

[[ -n "$readme_logo" ]] || fail "missing README logo"
assert_contains "$readme_logo" "Ooonana OS"
assert_contains "$readme_logo" "\\______/"

for logo_file in \
  "$ROOT/docs/logo.txt" \
  "$ROOT/packages/ooonana/usr/share/ooonana/logo.txt"; do
  [[ -f "$logo_file" ]] || fail "missing logo file: $logo_file"
  diff -u <(printf '%s\n' "$readme_logo") "$logo_file" || fail "logo mismatch: $logo_file"
done

scratch_builder="$ROOT/scripts/build-scratch-rootfs.sh"
scratch_src="$(<"$scratch_builder")"
assert_contains "$scratch_src" 'cp "$ROOTFS/usr/share/ooonana/logo.txt" "$ROOTFS/etc/motd"'
assert_contains "$scratch_src" 'cp "$ROOTFS/usr/share/ooonana/logo.txt" "$ROOTFS/etc/issue"'

printf 'ok logo-sync\n'
