#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WINE_BUILDER="$ROOT/scripts/build-wine-compat-package.sh"
CHAT_BUILDER="$ROOT/scripts/build-ooonana-chat-windows-package.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  [[ "$1" == *"$2"* ]] || fail "missing: $2"
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
printf 'MZtest\n' > "$tmp/OoonanaChat.exe"

bash "$WINE_BUILDER" --out-dir "$tmp/repo" >/dev/null
bash "$CHAT_BUILDER" --out-dir "$tmp/repo" --source "$tmp/OoonanaChat.exe" >/dev/null

[[ -f "$tmp/repo/wine.pkg" ]] || fail "missing Wine metadata"
[[ -f "$tmp/repo/ooonana-chat-windows.pkg" ]] || fail "missing Windows chat metadata"
assert_contains "$(<"$tmp/repo/wine.pkg")" 'OOONANA_PKG_DEPS="flatpak"'
assert_contains "$(<"$tmp/repo/ooonana-chat-windows.pkg")" 'OOONANA_PKG_DEPS="wine"'
wine_contents="$(tar -tzf "$tmp/repo/archives/wine-1.0.0.tar.gz")"
chat_contents="$(tar -tzf "$tmp/repo/archives/ooonana-chat-windows-1.0.0.tar.gz")"
assert_contains "$wine_contents" './usr/bin/ooonana-wine'
assert_contains "$wine_contents" './usr/bin/wine'
assert_contains "$chat_contents" './opt/ooonana-wine/OoonanaChat Setup 1.0.0.exe'
assert_contains "$chat_contents" './usr/share/applications/ooonana-chat-windows.desktop'

help="$("$ROOT/packages/wine-compat/rootfs/usr/bin/ooonana-wine" --help)"
assert_contains "$help" 'ooonana wine setup'
assert_contains "$help" 'ooonana wine run FILE.exe'

printf 'ok wine-compat-package\n'
