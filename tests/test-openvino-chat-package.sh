#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILDER="$ROOT/scripts/build-openvino-chat-package.sh"
SOURCE="$ROOT/packages/openvino-chat/source"
PAYLOAD="$ROOT/packages/openvino-chat/rootfs"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$BUILDER" ]] || fail "missing executable OpenVINO package builder"
[[ -f "$SOURCE/pyproject.toml" ]] || fail "missing vendored pyproject"
[[ -f "$SOURCE/src/openvino_chat/cli.py" ]] || fail "missing vendored CLI"
[[ -x "$PAYLOAD/usr/bin/openvino" ]] || fail "missing OpenVINO launcher"
[[ -x "$PAYLOAD/usr/bin/ooonana-openvino-setup" ]] || fail "missing runtime setup"

source_text="$(<"$SOURCE/src/openvino_chat/cli.py")"
assert_contains "$source_text" 'choices=["GPU", "NPU", "CPU"]'

setup_dry="$("$PAYLOAD/usr/bin/ooonana-openvino-setup" --dry-run)"
assert_contains "$setup_dry" "Ubuntu Python venv + openvino-genai"
assert_contains "$setup_dry" "OOONANA_OPENVINO_SETUP_DRY_OK"

setup_text="$(<"$PAYLOAD/usr/bin/ooonana-openvino-setup")"
assert_contains "$setup_text" "/tmp/ooonana-openvino-src"
assert_contains "$setup_text" "pip install --no-cache-dir --upgrade /tmp/ooonana-openvino-src"
assert_contains "$setup_text" "--exclude='./dev/*'"

launcher_help="$("$PAYLOAD/usr/bin/openvino" --help)"
assert_contains "$launcher_help" "openvino chat [--device GPU|NPU|CPU]"
assert_contains "$launcher_help" "Inference works offline"

launcher_text="$(<"$PAYLOAD/usr/bin/openvino")"
assert_contains "$launcher_text" "--unshare-user"
assert_contains "$launcher_text" "--unshare-uts"
[[ "$launcher_text" != *"--unshare-all"* ]] || fail "runtime PID namespace would kill background API"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
built="$(bash "$BUILDER" --out-dir "$tmp/repo" --version 0.1.2)"
assert_contains "$built" "openvino-chat.pkg"
[[ -f "$tmp/repo/openvino-chat.pkg" ]] || fail "missing package metadata"
[[ -f "$tmp/repo/archives/openvino-chat-0.1.2.tar.gz" ]] || fail "missing package archive"

metadata="$(<"$tmp/repo/openvino-chat.pkg")"
assert_contains "$metadata" 'OOONANA_PKG_ID="openvino-chat"'
assert_contains "$metadata" 'OOONANA_PKG_DEPS="bubblewrap xz curl ca-certificates coreutils"'
assert_contains "$metadata" "Offline Ooonana AI"

contents="$(tar -tzf "$tmp/repo/archives/openvino-chat-0.1.2.tar.gz")"
assert_contains "$contents" "./usr/bin/openvino"
assert_contains "$contents" "./usr/bin/ooonana-openvino-setup"
assert_contains "$contents" "./usr/lib/ooonana/openvino-chat/src/openvino_chat/cli.py"
assert_contains "$contents" "./usr/share/applications/ooonana-openvino.desktop"

printf 'ok openvino-chat-package\n'
