#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GENERATOR="$ROOT/scripts/generate-ooonana-pdf.py"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
PDF="$tmp/ooonana-guide.pdf"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$GENERATOR" ]] || fail "missing executable PDF generator"
python3 -B - "$GENERATOR" <<'PY'
import importlib.util
import sys
spec = importlib.util.spec_from_file_location("guide", sys.argv[1])
guide = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guide)
pages = guide.paginate(["Bootable PDF", *(["body"] * 47), "", "Persistence maintenance", "details"])
assert len(pages) == 2 and pages[1][0] == "Persistence maintenance"
assert not any(len(page) > 48 for page in guide.paginate(guide.build_lines()))
PY
python3 "$GENERATOR" --output "$PDF" >/dev/null
[[ -s "$PDF" ]] || fail "missing PDF"
head="$(LC_ALL=C head -c 8 "$PDF")"
[[ "$head" == "%PDF-1.4" ]] || fail "bad PDF header"
pdf_text="$(LC_ALL=C strings "$PDF")"
assert_contains "$pdf_text" "Ooonana OS 0.10.0 field guide"
assert_contains "$pdf_text" "ooonana.gitlab.io/ooonana-repo"
assert_contains "$pdf_text" "start-ooonana-i3"
assert_contains "$pdf_text" "Evidence refreshed 2026-10-09"
assert_contains "$pdf_text" "insufficient_memory"
assert_contains "$pdf_text" "Real Flatpak launch/portal checks remain pending"
[[ "$pdf_text" != *"held on Chromium sandbox"* ]] || fail "stale Chromium blocker"

printf 'ok ooonana-pdf\n'
