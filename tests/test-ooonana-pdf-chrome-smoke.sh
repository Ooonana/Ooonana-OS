#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/test-ooonana-pdf-chrome.ps1"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -f "$SCRIPT" ]] || fail "missing Chrome PDF tester"

body="$(<"$SCRIPT")"
assert_contains "$body" "Test Ooonana OS PDF in Chrome"
assert_contains "$body" "--headless=new"
assert_contains "$body" "--screenshot="
assert_contains "$body" "ooonana.pdf"

if command -v powershell.exe >/dev/null 2>&1; then
  win_script="$(wslpath -w "$SCRIPT" 2>/dev/null || printf '%s' "$SCRIPT")"
  help="$(powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$win_script" -Help)"
  assert_contains "$help" "Test Ooonana OS PDF in Chrome"
  assert_contains "$help" "Chromium PDF viewer"
fi

printf 'ok ooonana-pdf-chrome-smoke\n'
