#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

assert_png() {
  local path="$1"
  [[ -f "$path" ]] || fail "missing PNG: $path"
  magic="$(xxd -p -l 8 "$path")"
  [[ "$magic" == "89504e470d0a1a0a" ]] || fail "bad PNG magic: $path"
}

logo_svg="$ROOT/branding/logo.svg"
wallpaper_svg="$ROOT/branding/wallpaper.svg"
i3_config="$ROOT/branding/i3/config"

[[ -f "$logo_svg" ]] || fail "missing logo.svg"
[[ -f "$wallpaper_svg" ]] || fail "missing wallpaper.svg"
[[ -f "$i3_config" ]] || fail "missing i3 config"
assert_png "$ROOT/branding/logo.png"
assert_png "$ROOT/branding/wallpaper.png"

logo="$(<"$logo_svg")"
wallpaper="$(<"$wallpaper_svg")"
config="$(<"$i3_config")"

assert_contains "$logo" "<svg"
assert_contains "$logo" "Ooonana OS"
assert_contains "$logo" "ooonana-face"
assert_contains "$logo" "ooonana-ascii"
assert_contains "$logo" "#ffb21a"
assert_contains "$logo" '      __________________'
assert_contains "$logo" '  /  |     \______/     | \'
[[ "$logo" != *'<path'* ]] || fail "logo must be ASCII rendered, not vector face"
assert_contains "$wallpaper" 'viewBox="0 0 1920 1080"'
assert_contains "$wallpaper" "Ooonana OS"
assert_contains "$wallpaper" "ooonana-wallpaper"
assert_contains "$wallpaper" 'id="ooonana-horizon"'
assert_contains "$wallpaper" "ooonana-ascii"
assert_contains "$wallpaper" "default dark mode"
assert_contains "$wallpaper" "#ffb21a"
assert_contains "$wallpaper" '      __________________'
assert_contains "$wallpaper" '  /  |     \______/     | \'
assert_contains "$config" '# i3 config file (v4)'
assert_contains "$config" 'set $mod Mod4'
assert_contains "$config" 'bindsym $mod+Return exec ooonana-theme-env xterm'
assert_contains "$config" 'bindsym $mod+Shift+a exec ooonana-ai-app'
assert_contains "$config" 'bindsym $mod+Shift+t exec ooonana-theme-env toggle'
assert_contains "$config" 'exec_always --no-startup-id ooonana-theme-env apply'

printf 'ok branding-assets\n'
