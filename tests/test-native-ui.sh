#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="$ROOT/packages/ooonana/usr/lib/ooonana/ui"
PYTHON="${PYTHON:-python3}"

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

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

for app in common wireless_utils signal_map setup_app settings_app wifi_app bluetooth_app packages_app ai_app controls_app launcher_app; do
  [[ -f "$UI_DIR/$app.py" ]] || fail "missing GTK app: $app"
done

PYTHONPYCACHEPREFIX="$tmp/pycache" "$PYTHON" -m py_compile "$UI_DIR"/*.py

common="$(<"$UI_DIR/common.py")"
settings="$(<"$UI_DIR/settings_app.py")"
wifi="$(<"$UI_DIR/wifi_app.py")"
bluetooth="$(<"$UI_DIR/bluetooth_app.py")"
wireless="$(<"$UI_DIR/wireless_utils.py")"
signal_map="$(<"$UI_DIR/signal_map.py")"
packages="$(<"$UI_DIR/packages_app.py")"
ai="$(<"$UI_DIR/ai_app.py")"
controls="$(<"$UI_DIR/controls_app.py")"
setup="$(<"$UI_DIR/setup_app.py")"
launcher="$(<"$UI_DIR/launcher_app.py")"

assert_contains "$common" 'gi.require_version("Gtk", "3.0")'
assert_contains "$common" 'gi.require_version("Gdk", "3.0")'
assert_contains "$common" "os.killpg"
assert_contains "$common" "except PermissionError"
assert_contains "$common" "process.kill()"
assert_contains "$common" "#ffb21a"
assert_contains "$common" "decoration_layout"
assert_contains "$settings" "Desktop runs without root privileges"
assert_contains "$settings" "ooonana-wifi-panel"
assert_contains "$settings" "ooonana-bluetooth-panel"
assert_contains "$settings" "SERVICE_REPAIR_TIMEOUT = 180"
assert_contains "$wifi" '["nmcli"'
assert_contains "$wifi" "connect_selected"
assert_contains "$wifi" "NetworkManager repair failed"
assert_contains "$wifi" "SERVICE_START_TIMEOUT = 120"
assert_contains "$wifi" "SERVICE_REPAIR_TIMEOUT = 180"
assert_contains "$wifi" "WIFI_DEVICE_READY_TIMEOUT = 60"
assert_contains "$wifi" "WIFI_SCAN_SETTLE_TIMEOUT = 30"
assert_contains "$wifi" '"force-wifi"'
assert_contains "$wifi" "Adapter: {'ready' if self.wifi_devices else 'not detected'}"
assert_contains "$wifi" '"--rescan"'
assert_contains "$wifi" 'parse_iw_scan'
assert_contains "$wifi" '"Scan", "edit-find-symbolic"'
assert_contains "$wifi" '"IN-USE,BSSID,SSID,SIGNAL,SECURITY,DEVICE"'
assert_contains "$wifi" '"802-11-wireless.hidden", "yes" if hidden else "no"'
assert_contains "$wifi" "Let NetworkManager choose the strongest matching BSSID first"
assert_contains "$wifi" '"connection", "up", *identifier'
assert_contains "$wifi" '"uuid", uuid'
assert_not_contains "$wifi" '"device", "wifi", "connect", ssid'
assert_contains "$wifi" "WifiCredentialsDialog"
assert_contains "$wifi" 'row = add_grid_row(grid, row, "Security", self.security)'
assert_contains "$wifi" "wait_for_device_ready"
assert_contains "$wifi" 'GENERAL.NM-MANAGED'
assert_not_contains "$wifi" 'GENERAL.MANAGED'
assert_contains "$wifi" '"WPA2/WPA3 Enterprise"'
assert_contains "$wifi" '"WPA3 Enterprise"'
assert_contains "$wifi" '"connection.metered", "unknown"'
assert_contains "$wifi" '"proxy.method", "none"'
assert_contains "$wifi" '"802-11-wireless.cloned-mac-address", "stable"'
assert_contains "$wifi" 'parse_ip_neighbors'
assert_contains "$wifi" "802-1x.domain-suffix-match"
assert_contains "$wifi" "group_wifi_access_points"
assert_contains "$wifi" 'button("CSI 3D"'
assert_contains "$wifi" "ruvnet/RuView"
assert_contains "$wifi" "MaliosDark/wifi-3d-fusion"
assert_contains "$wifi" '"sensing-server", "--source", "wifi" if use_linux_rssi else "simulate"'
assert_contains "$wifi" '"--tick-ms", "500"'
assert_contains "$wifi" '"Use system certificates"'
assert_contains "$wifi" '"Choose CA certificate"'
assert_contains "$wifi" '"Do not validate certificate (unsafe)"'
assert_contains "$wifi" '"ca_policy"'
assert_contains "$wifi" 'http://127.0.0.1:3000/ui/observatory.html'
assert_not_contains "$wifi" 'ruview-pointcloud'
assert_contains "$wifi" 'connection", "delete", profile'
assert_contains "$wifi" '"802-11-wireless-security.key-mgmt", "owe"'
assert_contains "$wifi" '"802-11-wireless-security.wep-key-type"'
assert_contains "$bluetooth" '["bluetoothctl"'
assert_contains "$bluetooth" "pair"
assert_contains "$bluetooth" "trust"
assert_contains "$bluetooth" "connect"
assert_contains "$bluetooth" "Bluetooth repair failed"
assert_contains "$bluetooth" "SERVICE_START_TIMEOUT = 90"
assert_contains "$bluetooth" "SERVICE_REPAIR_TIMEOUT = 150"
assert_contains "$bluetooth" '"force-bluetooth"'
assert_contains "$bluetooth" '"--agent", "KeyboardDisplay"'
assert_contains "$bluetooth" "connect_with_retry"
assert_contains "$bluetooth" 'state["connected"]'
assert_contains "$bluetooth" "parse_bluetooth_info"
assert_contains "$bluetooth" "SignalMapWindow"
assert_contains "$wireless" "split_nmcli_terse"
assert_contains "$wireless" "group_wifi_access_points"
assert_contains "$wireless" '"enterprise"'
assert_contains "$signal_map" "Computer is center"
assert_contains "$signal_map" "Wi-Fi routers (orange)"
assert_contains "$signal_map" "Nearby LAN devices (green)"
assert_contains "$signal_map" "Nearby Bluetooth devices (blue)"
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
assert_contains "$controls" "KeyboardWindow"
assert_contains "$controls" "ThermalWindow"
assert_contains "$controls" "audio_command"
assert_contains "$controls" "pulseaudio"
assert_contains "$controls" '"set-default-sink"'
assert_contains "$controls" 'platform_profile_choices'
assert_contains "$controls" 'self.add(root)'
assert_contains "$controls" "PowerWindow"
power_window="$(sed -n '/^class PowerWindow/,/^def main/p' "$UI_DIR/controls_app.py")"
assert_contains "$power_window" 'self.add(root)'
assert_contains "$controls" 'run_async(command, done, timeout=20)'
assert_contains "$setup" "SetupWindow"
assert_contains "$setup" "Apply setup"
assert_contains "$setup" "admin_command"
assert_contains "$launcher" "Gio.AppInfo.get_all"
assert_contains "$launcher" "Search applications"

"$PYTHON" "$ROOT/tests/test-wireless-utils.py"
"$PYTHON" "$ROOT/tests/test-wireless-actions.py"

boot_logo="$(<"$ROOT/packages/ooonana/usr/share/ooonana/boot-logo.txt")"
assert_contains "$boot_logo" "O O O N A N A   O S"
assert_contains "$boot_logo" "__________________________________"

bunana="$(<"$ROOT/packages/ooonana/usr/bin/bunana")"
assert_contains "$bunana" 'echo "bunana: shutdown failed"'
assert_contains "$bunana" 'echo "bunana: restart failed"'
assert_contains "$bunana" '/sbin/poweroff -f'
[[ "$bunana" != *'|| exit 0'* ]] || fail "bunana must report failed power actions"

printf 'ok native-ui\n'
