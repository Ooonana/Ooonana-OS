#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/run-qemu.sh"

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

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "--vnc"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
printf 'disk\n' > "$tmp/full.raw"

dry_run="$(bash "$SCRIPT" --disk-boot --image "$tmp/full.raw" --smoke --vnc :7 --dry-run)"
assert_contains "$dry_run" "-display none"
assert_contains "$dry_run" "-vnc :7"
assert_contains "$dry_run" "-serial stdio"
assert_contains "$dry_run" "-monitor none"
assert_not_contains "$dry_run" "-nographic"

printf 'ok qemu-gui\n'
