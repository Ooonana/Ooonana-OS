#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="$ROOT/packages/ooonana/usr/lib/ooonana/ui"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

for app in common setup_app settings_app wifi_app bluetooth_app packages_app ai_app controls_app launcher_app; do
  [[ -f "$UI_DIR/$app.py" ]] || fail "missing GTK app: $app"
done

PYTHONPYCACHEPREFIX="$tmp/pycache" python3 -m py_compile "$UI_DIR"/*.py

common="$(<"$UI_DIR/common.py")"
settings="$(<"$UI_DIR/settings_app.py")"
wifi="$(<"$UI_DIR/wifi_app.py")"
bluetooth="$(<"$UI_DIR/bluetooth_app.py")"
packages="$(<"$UI_DIR/packages_app.py")"
ai="$(<"$UI_DIR/ai_app.py")"
controls="$(<"$UI_DIR/controls_app.py")"
setup="$(<"$UI_DIR/setup_app.py")"
launcher="$(<"$UI_DIR/launcher_app.py")"

assert_contains "$common" 'gi.require_version("Gtk", "3.0")'
assert_contains "$common" 'gi.require_version("Gdk", "3.0")'
assert_contains "$common" "#ffb21a"
assert_contains "$common" "decoration_layout"
assert_contains "$settings" "Desktop runs without root privileges"
assert_contains "$settings" "ooonana-wifi-panel"
assert_contains "$settings" "ooonana-bluetooth-panel"
assert_contains "$wifi" '["nmcli"'
assert_contains "$wifi" "connect_selected"
assert_contains "$wifi" "NetworkManager repair failed"
assert_contains "$bluetooth" '["bluetoothctl"'
assert_contains "$bluetooth" "pair"
assert_contains "$bluetooth" "trust"
assert_contains "$bluetooth" "connect"
assert_contains "$bluetooth" "Bluetooth repair failed"
assert_contains "$packages" '["ooonana", "update"]'
assert_contains "$packages" '["ooonana", "upgrade"]'
assert_contains "$ai" "Chat"
assert_contains "$ai" '["ooonana-ai", "ask", prompt]'
assert_contains "$ai" "Offline Intel"
assert_contains "$ai" '["openvino", "doctor"]'
assert_contains "$ai" '["openvino", "--model-dir", model, "api", "start", "--device", device]'
assert_contains "$ai" '["ooonana-ai", "provider", "set", "openvino"]'
assert_contains "$controls" "BrightnessWindow"
assert_contains "$controls" "AudioWindow"
assert_contains "$controls" "PowerWindow"
assert_contains "$controls" 'run_async(command, done, timeout=20)'
assert_contains "$setup" "SetupWindow"
assert_contains "$setup" "Apply setup"
assert_contains "$setup" "admin_command"
assert_contains "$launcher" "Gio.AppInfo.get_all"
assert_contains "$launcher" "Search applications"

boot_logo="$(<"$ROOT/packages/ooonana/usr/share/ooonana/boot-logo.txt")"
assert_contains "$boot_logo" "O O O N A N A   O S"
assert_contains "$boot_logo" "__________________________________"

bunana="$(<"$ROOT/packages/ooonana/usr/bin/bunana")"
assert_contains "$bunana" 'echo "bunana: shutdown failed"'
assert_contains "$bunana" 'echo "bunana: restart failed"'
[[ "$bunana" != *'|| exit 0'* ]] || fail "bunana must report failed power actions"

printf 'ok native-ui\n'
