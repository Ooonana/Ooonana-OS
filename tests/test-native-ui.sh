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
assert_contains "$common" 'encoding="utf-8"'
assert_contains "$common" 'command_env["LC_ALL"] = "C"'
assert_contains "$common" 'command_env["LANG"] = "C"'
assert_contains "$common" "Minimize to scratchpad"
assert_contains "$common" "Toggle fullscreen"
assert_contains "$common" 'window-close-symbolic'
assert_contains "$common" 'OoonanaApp'
assert_contains "$common" "#ffb21a"
assert_contains "$common" "decoration_layout"
assert_contains "$common" "def flow_row"
assert_contains "$common" "button:disabled"
assert_contains "$common" "textview text"
assert_contains "$common" "progressbar progress"
assert_contains "$settings" "Desktop runs without root privileges"
assert_contains "$settings" "ooonana-wifi-panel"
assert_contains "$settings" "ooonana-bluetooth-panel"
assert_contains "$wifi" '["nmcli"'
assert_contains "$wifi" "connect_selected"
assert_contains "$wifi" "NetworkManager repair failed"
assert_contains "$wifi" '"force-wifi"'
assert_contains "$wifi" '"deep-wifi"'
assert_contains "$wifi" "current_wifi_devices"
assert_contains "$wifi" "direct_scan_done"
assert_contains "$wifi" "trying activation anyway"
assert_contains "$wifi" "flow_row"
assert_contains "$wifi" '"NAME,DEVICE,TYPE"'
assert_contains "$wifi" 'fields[2] in ("802-11-wireless", "wifi")'
assert_contains "$wifi" "self.ready_wifi_devices"
assert_contains "$wifi" "def collect_refresh_data"
assert_contains "$wifi" "self.refresh_running"
assert_contains "$wifi" "run_async_task(task, done)"
assert_contains "$wifi" "Services: D-Bus + NetworkManager + supplicant"
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
assert_contains "$wifi" 'for key in ("security", "security_kind", "security_label")'
assert_not_contains "$wifi" '"device", "set", device, "managed"'
assert_contains "$wifi" "802-1x.domain-suffix-match"
assert_contains "$wifi" "GENERAL.NM-MANAGED"
assert_contains "$wifi" "WIFI_DEVICE_READY_TIMEOUT = 20"
assert_contains "$wifi" "WIFI_ACTIVATION_TIMEOUT = 45"
assert_contains "$wifi" "WIFI_SCAN_SETTLE_TIMEOUT = 30"
assert_contains "$wifi" "Do not validate certificate (unsafe)"
assert_contains "$wifi" "Network options"
assert_contains "$wifi" "Automatic (DHCP)"
assert_contains "$wifi" "Stable address per network"
assert_contains "$wifi" '"connection.metered"'
assert_contains "$common" "system_dbus_ready"
assert_contains "$common" "org.freedesktop.DBus.ListNames"
assert_not_contains "$common" "org.freedesktop.DBus.Peer.Ping"
assert_contains "$wifi" '"proxy.pac-url"'
assert_contains "$wifi" 'ca_policy == "custom"'
assert_contains "$wifi" "group_wifi_access_points"
assert_contains "$wifi" 'button("CSI 3D"'
assert_contains "$wifi" "ruvnet/RuView"
assert_contains "$wifi" "MaliosDark/wifi-3d-fusion"
assert_contains "$wifi" '"sensing-server", "--source", "wifi" if use_linux_rssi else "simulate"'
assert_contains "$wifi" '"--tick-ms", "500"'
assert_contains "$wifi" 'http://127.0.0.1:3000/ui/observatory.html'
assert_not_contains "$wifi" 'ruview-pointcloud'
assert_contains "$wifi" '"connection", "delete", "uuid", fields[1]'
assert_contains "$wifi" 'NAME,UUID,TYPE'
assert_contains "$wifi" "verify_profile_connected"
assert_contains "$wifi" "IP4.ADDRESS,IP6.ADDRESS"
assert_contains "$wifi" "802-11-wireless-security.psk-flags"
assert_contains "$wifi" "802-1x.password-flags"
assert_contains "$wifi" '"802-11-wireless-security.key-mgmt", "owe"'
assert_contains "$wifi" '"802-11-wireless-security.wep-key-type"'
assert_contains "$bluetooth" '["bluetoothctl"'
assert_contains "$bluetooth" "pair"
assert_contains "$bluetooth" "trust"
assert_contains "$bluetooth" "connect"
assert_contains "$bluetooth" "Bluetooth repair failed"
assert_contains "$bluetooth" '"force-bluetooth"'
assert_contains "$bluetooth" '"deep-bluetooth"'
assert_contains "$bluetooth" "flow_row"
assert_contains "$bluetooth" '"--agent", "KeyboardDisplay"'
assert_contains "$bluetooth" "connect_with_retry"
assert_contains "$bluetooth" "def collect_refresh_data"
assert_contains "$bluetooth" "self.refresh_running"
assert_contains "$bluetooth" 'state["connected"]'
assert_contains "$bluetooth" "parse_bluetooth_info"
assert_contains "$bluetooth" "SignalMapWindow"
assert_contains "$bluetooth" '"category": "device"'
assert_contains "$bluetooth" '"signal_known": values["rssi"] is not None'
assert_contains "$bluetooth" "Services: D-Bus + BlueZ"
assert_contains "$wireless" "split_nmcli_terse"
assert_contains "$wireless" "group_wifi_access_points"
assert_contains "$wireless" '"enterprise"'
assert_contains "$signal_map" "Wi-Fi routers (orange)"
assert_contains "$signal_map" "Nearby LAN devices (green)"
assert_contains "$signal_map" "filtered_items"
assert_contains "$signal_map" "PangoCairo.show_layout"
assert_contains "$wireless" "parse_ip_neighbors"
assert_contains "$packages" '["ooonana", "update"]'
assert_contains "$packages" '["ooonana", "upgrade"]'
assert_contains "$ai" "Chat"
assert_contains "$ai" '["ooonana-ai", "ask", prompt]'
assert_contains "$ai" "Offline Intel"
assert_contains "$ai" 'Path.home() / ".openvino/models/'
assert_not_contains "$ai" 'model = "/root/.openvino/models/'
assert_contains "$ai" "Checking OpenVINO runtime..."
assert_contains "$ai" '["openvino", "doctor"]'
assert_contains "$ai" '["openvino", "--model-dir", model, "api", "start", "--device", device]'
assert_contains "$ai" '["ooonana-ai", "provider", "set", "openvino"]'
assert_contains "$controls" "BrightnessWindow"
assert_contains "$controls" "AudioWindow"
assert_contains "$controls" "audio_command"
assert_contains "$controls" "ooonana-audio-start"
assert_contains "$controls" "list_audio_devices"
assert_contains "$controls" "def collect_audio_state"
assert_contains "$controls" "def refresh_audio"
audio_start_line="$(grep -n 'service_rc, service_output = self.audio_command("info")' "$UI_DIR/controls_app.py" | cut -d: -f1)"
audio_refresh_line="$(grep -n 'outputs = self.list_audio_devices("sinks")' "$UI_DIR/controls_app.py" | cut -d: -f1)"
[[ -n "$audio_start_line" && -n "$audio_refresh_line" && "$audio_start_line" -lt "$audio_refresh_line" ]] ||
  fail "audio UI must start its server before enumerating devices"
assert_contains "$controls" "set-default-sink"
assert_contains "$settings" "run_async_task(task, done)"
assert_contains "$ai" "run_async_task(task, done)"
assert_contains "$controls" 'self.add(root)'
assert_contains "$controls" "PowerWindow"
power_window="$(sed -n '/^class PowerWindow/,/^def main/p' "$UI_DIR/controls_app.py")"
assert_contains "$power_window" 'self.add(root)'
assert_contains "$controls" 'run_async(command, done, timeout=20)'
assert_contains "$setup" "SetupWindow"
assert_contains "$setup" "Apply setup"
assert_contains "$setup" "admin_command"
assert_contains "$launcher" "Gio.AppInfo.get_all"
assert_contains "$launcher" "Ooonana Spotlight"
assert_contains "$launcher" "Search apps, settings, and commands"
assert_contains "$launcher" "OoonanaSpotlight"
assert_contains "$launcher" "Gdk.KEY_Down"

PYTHONDONTWRITEBYTECODE=1 "$PYTHON" "$ROOT/tests/test-wireless-utils.py"
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" "$ROOT/tests/test-wireless-actions.py"
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" "$ROOT/tests/test-signal-map.py"

boot_logo="$(<"$ROOT/packages/ooonana/usr/share/ooonana/boot-logo.txt")"
assert_contains "$boot_logo" "Ooonana OS"
assert_contains "$boot_logo" '      __________________'
assert_contains "$boot_logo" '  /  |     \______/     | \'

bunana="$(<"$ROOT/packages/ooonana/usr/bin/bunana")"
assert_contains "$bunana" 'echo "bunana: shutdown failed"'
assert_contains "$bunana" 'echo "bunana: restart failed"'
assert_contains "$bunana" '/sbin/poweroff -f'
[[ "$bunana" != *'|| exit 0'* ]] || fail "bunana must report failed power actions"

printf 'ok native-ui\n'
