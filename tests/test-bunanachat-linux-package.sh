#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILDER="$ROOT/scripts/build-bunanachat-linux-package.sh"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_contains() { [[ "$1" == *"$2"* ]] || fail "missing: $2"; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/publish"
for file in BunanaChat.Linux libSkiaSharp.so libHarfBuzzSharp.so; do
  printf 'ELF test\n' > "$tmp/publish/$file"
done

bash "$BUILDER" --out-dir "$tmp/repo" --source-dir "$tmp/publish" >/dev/null
[[ -f "$tmp/repo/bunanachat.pkg" ]] || fail "missing package metadata"
[[ -f "$tmp/repo/archives/bunanachat-0.1.1.tar.gz" ]] || fail "missing package archive"
metadata="$(<"$tmp/repo/bunanachat.pkg")"
assert_contains "$metadata" 'OOONANA_PKG_DEPS="bluez dbus fontconfig'
contents="$(tar -tzf "$tmp/repo/archives/bunanachat-0.1.1.tar.gz")"
assert_contains "$contents" './opt/bunanachat/BunanaChat.Linux'
assert_contains "$contents" './opt/bunanachat/libSkiaSharp.so'
assert_contains "$contents" './opt/bunanachat/libHarfBuzzSharp.so'
assert_contains "$contents" './usr/bin/bunanachat'
assert_contains "$contents" './usr/share/applications/bunanachat.desktop'
assert_contains "$(<"$ROOT/packages/bunanachat-linux/rootfs/usr/share/applications/bunanachat.desktop")" 'Icon=/usr/share/ooonana/logo.png'

printf 'ok bunanachat-linux-package\n'
