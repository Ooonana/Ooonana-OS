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
assert_contains "$builder" "/usr/bin/ooonana-installer-gui"
assert_contains "$builder" "/usr/bin/ooonana-install-wizard"
assert_contains "$builder" "/usr/share/applications/ooonana-installer.desktop"
assert_contains "$builder" 'yad --center --title "Install Ooonana OS"'
assert_contains "$builder" "custom-existing-partitions"
assert_contains "$builder" "--home-part"
assert_contains "$builder" "--swap-part"
assert_contains "$builder" "--efi-part"
assert_contains "$builder" 'xterm -title "Ooonana Installer"'
assert_contains "$builder" "Step 1/8: Target disk"
assert_contains "$builder" "Step 2/8: User account"
assert_contains "$builder" "Step 4/8: Theme"
assert_contains "$builder" "Step 5/8: Package repo"
assert_contains "$builder" "Repo picker"
assert_contains "$builder" "Fallback shell"
assert_contains "$builder" "Press Enter to reboot"
assert_contains "$builder" "/var/log/ooonana-install-wizard.log"
assert_contains "$builder" "/usr/sbin/ooonana-install"
assert_contains "$builder" "OOONANA_INSTALLER_GUI_OK"
assert_contains "$builder" "toggle)"
assert_contains "$i3_config" 'bindsym $mod+Shift+i exec ooonana-gui-installer'
assert_contains "$i3_config" 'bindsym $mod+Shift+a exec ooonana-ai-launch'
assert_contains "$i3_config" 'bindsym $mod+Shift+t exec ooonana-theme-env toggle'
assert_contains "$i3_config" "client.focused"
assert_contains "$i3_config" "exec_always --no-startup-id sh -c 'command -v polybar"
assert_contains "$full_test" "ooonana-gui-installer"
assert_contains "$full_test" "ooonana-installer-gui"
assert_contains "$full_test" "ooonana-ai.desktop"

printf 'ok gui-installer\n'
