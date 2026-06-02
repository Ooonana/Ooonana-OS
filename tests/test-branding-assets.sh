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
assert_contains "$logo" "#ffb21a"
assert_contains "$logo" 'd="M172 154h-38L84 208"'
assert_contains "$logo" 'd="M468 154h38l50 54"'
[[ "$logo" != *'M172 154h-38c'* ]] || fail "left arm must be straight"
[[ "$logo" != *'M468 154h38c'* ]] || fail "right arm must be straight"
assert_contains "$wallpaper" 'viewBox="0 0 1920 1080"'
assert_contains "$wallpaper" "Ooonana OS"
assert_contains "$wallpaper" "ooonana-wallpaper"
assert_contains "$wallpaper" "#ffb21a"
assert_contains "$wallpaper" 'd="M172 154h-38L84 208"'
assert_contains "$wallpaper" 'd="M468 154h38l50 54"'
assert_contains "$config" '# i3 config file (v4)'
assert_contains "$config" 'set $mod Mod4'
assert_contains "$config" 'bindsym $mod+Return exec ooonana-theme-env xterm'
assert_contains "$config" 'exec_always --no-startup-id ooonana-theme-env apply'

printf 'ok branding-assets\n'
