#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FULL_TEST="$ROOT/tests/test-full-i3-rootfs.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

builder="$(<"$ROOT/scripts/build-full-i3-rootfs.sh")"
i3_config="$(<"$ROOT/branding/i3/config")"
full_test="$(<"$FULL_TEST")"

assert_contains "$builder" "write_gui_installer"
assert_contains "$builder" "/usr/bin/ooonana-gui-installer"
assert_contains "$builder" "/usr/share/applications/ooonana-installer.desktop"
assert_contains "$builder" "xmessage"
assert_contains "$builder" "/usr/sbin/ooonana-install"
assert_contains "$i3_config" 'bindsym $mod+Shift+i exec ooonana-gui-installer'
assert_contains "$full_test" "ooonana-gui-installer"

printf 'ok gui-installer\n'
