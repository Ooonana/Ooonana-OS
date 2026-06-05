#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GENERATOR="$ROOT/scripts/generate-ooonana-pdf.py"
PDF="$ROOT/docs/ooonana-guide.pdf"

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
python3 "$GENERATOR" >/dev/null
[[ -s "$PDF" ]] || fail "missing PDF"
head="$(LC_ALL=C head -c 8 "$PDF")"
[[ "$head" == "%PDF-1.4" ]] || fail "bad PDF header"
pdf_text="$(LC_ALL=C strings "$PDF")"
assert_contains "$pdf_text" "Ooonana OS v1 field guide"
assert_contains "$pdf_text" "ooonana-package-repo.tar.gz"
assert_contains "$pdf_text" "start-ooonana-i3"

printf 'ok ooonana-pdf\n'
