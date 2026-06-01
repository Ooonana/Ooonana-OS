#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$ROOT/.github/workflows/build-ooonana-packages.yml"
IMPORTER="$ROOT/scripts/import-apk-package.sh"
README="$ROOT/README.md"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$IMPORTER" ]] || fail "missing executable importer"
[[ -f "$WORKFLOW" ]] || fail "missing package workflow"

workflow="$(<"$WORKFLOW")"
assert_contains "$workflow" "workflow_dispatch:"
assert_contains "$workflow" "packages:"
assert_contains "$workflow" "alpine_repo:"
assert_contains "$workflow" "full_i3_profile:"
assert_contains "$workflow" "publish_pages:"
assert_contains "$workflow" "scripts/import-apk-package.sh"
assert_contains "$workflow" "scripts/import-i3-package-set.sh"
assert_contains "$workflow" "actions/upload-artifact"
assert_contains "$workflow" "actions/upload-pages-artifact"
assert_contains "$workflow" "actions/deploy-pages"
assert_contains "$workflow" "gh release upload"

readme="$(<"$README")"
assert_contains "$readme" "Package Factory"
assert_contains "$readme" "scripts/import-apk-package.sh"
assert_contains "$readme" "ooonana get nano"
assert_contains "$readme" "GitHub Pages"

printf 'ok package-factory\n'
