#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILDER="$ROOT/scripts/build-ooonana-pdf-os.sh"
INJECTOR="$ROOT/scripts/inject-ooonana-pdf-root.sh"
PDF="$ROOT/docs/ooonana.pdf"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$BUILDER" ]] || fail "missing executable PDF OS builder"
[[ -x "$INJECTOR" ]] || fail "missing executable PDF root injector"

help="$(bash "$BUILDER" --help)"
assert_contains "$help" "Build bootable Ooonana OS PDF"
assert_contains "$help" "docs/ooonana.pdf"
assert_contains "$help" "linuxpdf is GPLv3"
assert_contains "$help" "--prepare-only"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

dry="$(bash "$BUILDER" --work-dir "$tmp/work" --out "$tmp/ooonana.pdf" --dry-run --force)"
assert_contains "$dry" "would build Ooonana OS PDF"
assert_contains "$dry" "git clone"
assert_contains "$dry" "OOONANA_SOURCE_ROOT="
assert_contains "$dry" "OOONANA_PDF_BITS="
assert_contains "$dry" "install -m 0644"

rootfs="$tmp/rootfs"
mkdir -p "$rootfs"
inject="$(bash "$INJECTOR" "$rootfs")"
assert_contains "$inject" "injected Ooonana PDF rootfs"
[[ -x "$rootfs/usr/bin/ooonana" ]] || fail "missing injected ooonana CLI"
[[ -x "$rootfs/sbin/init" ]] || fail "missing injected init"
[[ -f "$rootfs/usr/share/ooonana/logo.txt" ]] || fail "missing injected logo"
[[ -f "$rootfs/etc/os-release" ]] || fail "missing injected os-release"
assert_contains "$(<"$rootfs/sbin/init")" "Ooonana OS PDF Minimal"
assert_contains "$(<"$rootfs/root/.profile")" "ooonana help packages"
assert_contains "$(<"$rootfs/etc/os-release")" 'PRETTY_NAME="Ooonana OS PDF Minimal"'

if [[ -f "$PDF" ]]; then
  head="$(LC_ALL=C head -c 5 "$PDF")"
  [[ "$head" == "%PDF-" ]] || fail "bad OS PDF header"
  pdf_text="$(LC_ALL=C strings "$PDF")"
  assert_contains "$pdf_text" "OoonanaPDF"
  assert_contains "$pdf_text" "Ooonana OS in PDF"
fi

printf 'ok ooonana-pdf-os\n'
