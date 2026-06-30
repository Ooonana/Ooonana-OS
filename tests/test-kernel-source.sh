#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/fetch-kernel-source.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable kernel source fetcher"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Fetch Ooonana Linux kernel source"
assert_contains "$help" "--version"
assert_contains "$help" "default: 6.18.37"
assert_contains "$help" "--tarball"
assert_contains "$help" "--dry-run"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

dry_run="$(bash "$SCRIPT" \
  --version 6.6.32 \
  --source-dir "$tmp/linux" \
  --archive "$tmp/linux-6.6.32.tar.xz" \
  --dry-run)"
assert_contains "$dry_run" "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.6.32.tar.xz"
assert_contains "$dry_run" "curl"
assert_contains "$dry_run" "tar"
assert_contains "$dry_run" "$tmp/linux"

default_dry_run="$(bash "$SCRIPT" \
  --work-dir "$tmp/default-build" \
  --dry-run)"
assert_contains "$default_dry_run" "linux-6.18.37.tar.xz"
assert_contains "$default_dry_run" "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.18.37.tar.xz"

mkdir -p "$tmp/tar-src/linux-9.9.9/arch/x86"
touch "$tmp/tar-src/linux-9.9.9/Makefile"
printf 'source marker\n' > "$tmp/tar-src/linux-9.9.9/README"
tar -C "$tmp/tar-src" -cJf "$tmp/linux-9.9.9.tar.xz" "linux-9.9.9"
hash="$(sha256sum "$tmp/linux-9.9.9.tar.xz" | awk '{ print $1 }')"

bash "$SCRIPT" \
  --version 9.9.9 \
  --source-dir "$tmp/linux" \
  --tarball "$tmp/linux-9.9.9.tar.xz" \
  --sha256 "$hash" \
  --force >/dev/null

[[ -f "$tmp/linux/Makefile" ]] || fail "missing extracted Makefile"
[[ -d "$tmp/linux/arch/x86" ]] || fail "missing extracted x86 arch"
[[ "$(<"$tmp/linux/README")" == "source marker" ]] || fail "wrong source payload"
[[ -f "$tmp/linux/.ooonana-kernel-source" ]] || fail "missing source metadata"

metadata="$(<"$tmp/linux/.ooonana-kernel-source")"
assert_contains "$metadata" "OOONANA_KERNEL_VERSION=9.9.9"
assert_contains "$metadata" "OOONANA_KERNEL_SOURCE=$tmp/linux"

printf 'ok kernel-source\n'
