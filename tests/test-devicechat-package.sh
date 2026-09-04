#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILDER="$ROOT/scripts/build-devicechat-package.sh"
SOURCE="$ROOT/packages/devicechat/source/devicechat-0.1.1.tgz"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  [[ "$1" == *"$2"* ]] || fail "missing: $2"
}

[[ -x "$BUILDER" ]] || fail "missing DeviceChat builder"
[[ -f "$SOURCE" ]] || fail "missing DeviceChat source tarball"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fake_npm="$tmp/npm"
cat > "$fake_npm" <<'EOF'
#!/bin/sh
prefix=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix) prefix="$2"; shift 2 ;;
    *) shift ;;
  esac
done
[ -n "$prefix" ] || exit 2
mkdir -p "$prefix/node_modules/test-runtime"
printf '{"name":"test-runtime"}\n' > "$prefix/node_modules/test-runtime/package.json"
EOF
chmod +x "$fake_npm"

bash "$BUILDER" --out-dir "$tmp/repo" --npm "$fake_npm" >/dev/null
[[ -f "$tmp/repo/devicechat.pkg" ]] || fail "missing DeviceChat metadata"
[[ -f "$tmp/repo/archives/devicechat-0.1.1.tar.gz" ]] || fail "missing DeviceChat archive"
metadata="$(<"$tmp/repo/devicechat.pkg")"
assert_contains "$metadata" 'OOONANA_PKG_DEPS="nodejs"'
contents="$(tar -tzf "$tmp/repo/archives/devicechat-0.1.1.tar.gz")"
assert_contains "$contents" './usr/bin/devicechat'
assert_contains "$contents" './usr/bin/devicechat-relay'
assert_contains "$contents" './opt/devicechat/dist/index.js'
assert_contains "$contents" './opt/devicechat/node_modules/test-runtime/package.json'

printf 'ok devicechat-package\n'
