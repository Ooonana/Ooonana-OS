#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/packages/ooonana/usr/bin/ooonana"
ORDER="$ROOT/packages/ooonana/usr/lib/ooonana/version-order.awk"
# Keep uppercase V in filenames: the fallback mock must reject version-sort
# options, not an incidental character in a randomly generated input path.
work="$(mktemp -d "${TMPDIR:-/tmp}/ooonana-version-V.XXXXXXXXXX")"
trap 'rm -rf "$work"' EXIT
compare() {
  LC_ALL=C awk -v mode=compare -v left="$1" -v right="$2" -f "$ORDER"
}
compare_files() {
  if command -v cmp >/dev/null 2>&1; then cmp "$@"; else busybox cmp "$@"; fi
}
[[ "$(compare 1.9 1.10)" == '<' ]]
[[ "$(compare 2.0-r9 2.0-r10)" == '<' ]]
[[ "$(compare '1.0~rc1' 1.0)" == '<' ]]
[[ "$(compare 1.0 1.0a)" == '<' ]]
[[ "$(compare 1.01 1.1)" == '=' ]]
[[ "$(compare 100000000000000000001 100000000000000000000)" == '>' ]]
eval "$(sed -n '/^version_order_script() {$/,/^}$/p' "$CLI")"
eval "$(sed -n '/^version_compare() {$/,/^}$/p' "$CLI")"
eval "$(sed -n '/^select_best_index_entries() {$/,/^}$/p' "$CLI")"
SCRIPT_DIR="$ROOT/packages/ooonana/usr/bin"
have() { return 1; } # Exercise no-APK comparison without host dependencies.
[[ "$(version_compare 1.9 1.10)" == '<' ]]
printf 'first\tdemo\t1.9\tarchive\tOld\nsecond\tdemo\t1.10\tarchive\tNew\nfirst\ttie\t2\tbundle\tFirst\nsecond\ttie\t2\tbundle\tSecond\n' >"$work/input"
select_best_index_entries "$work/input" "$work/gnu"
mkdir "$work/bin"
real_sort="$(command -v sort)"
printf '#!/bin/sh\nfor option in "$@"; do case "$option" in -*V*) exit 2;; esac; done\nexec "%s" "$@"\n' "$real_sort" >"$work/bin/sort"
chmod +x "$work/bin/sort"
PATH="$work/bin:$PATH" select_best_index_entries "$work/input" "$work/portable"
compare_files "$work/gnu" "$work/portable"
grep -q $'^second\tdemo\t1.10\t' "$work/portable"
grep -q $'^first\ttie\t2\t' "$work/portable"
if command -v busybox >/dev/null; then
  printf '#!/bin/sh\nexec "%s" sort "$@"\n' "$(command -v busybox)" >"$work/bin/sort"
  PATH="$work/bin:$PATH" select_best_index_entries "$work/input" "$work/busybox"
  compare_files "$work/gnu" "$work/busybox"
fi
printf 'ok version-order: natural versions, revisions, stable ties, long integers, BusyBox fallback\n'
