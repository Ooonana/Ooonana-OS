#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$ROOT/.github/workflows/build-ooonana-packages.yml"
IMPORTER="$ROOT/scripts/import-apk-package.sh"
README="$ROOT/README.md"
DEFAULT_PROFILE="$ROOT/configs/packages/ooonana-repo.list"
FULL_I3_PROFILE="$ROOT/configs/packages/full-i3.list"

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
[[ -f "$DEFAULT_PROFILE" ]] || fail "missing default package profile"
[[ -f "$FULL_I3_PROFILE" ]] || fail "missing full-i3 package profile"

default_profile="$(<"$DEFAULT_PROFILE")"
full_i3_profile="$(<"$FULL_I3_PROFILE")"
assert_contains "$default_profile" "nano"
assert_contains "$default_profile" "curl"
assert_contains "$full_i3_profile" "i3wm"
assert_contains "$full_i3_profile" "xorg-server"
assert_contains "$full_i3_profile" "xf86-video-vesa"
assert_contains "$full_i3_profile" "xf86-video-fbdev"

workflow="$(<"$WORKFLOW")"
assert_contains "$workflow" "workflow_dispatch:"
assert_contains "$workflow" "packages:"
assert_contains "$workflow" "package_profile:"
assert_contains "$workflow" "alpine_repo:"
assert_contains "$workflow" "full_i3_profile:"
assert_contains "$workflow" "publish_pages:"
assert_contains "$workflow" "scripts/import-apk-package.sh"
assert_contains "$workflow" "scripts/import-i3-package-set.sh"
assert_contains "$workflow" "actions/upload-artifact"
assert_contains "$workflow" "actions/upload-pages-artifact"
assert_contains "$workflow" "actions/deploy-pages"
assert_contains "$workflow" "gh release upload"
assert_contains "$workflow" "Write cloud repo hints"
assert_contains "$workflow" '$out/cloud.repo'
assert_contains "$workflow" 'pages_url="https://${OWNER}.github.io/${REPO_NAME}"'
assert_contains "$workflow" 'OOONANA_REPO_URI="$pages_url"'
[[ "$workflow" != *'default: "nano"'* ]] || fail "workflow default must not be nano-only"
assert_contains "$workflow" "configs/packages/ooonana-repo.list"
assert_contains "$workflow" "configs/packages/full-i3.list"

i3_importer="$(<"$ROOT/scripts/import-i3-package-set.sh")"
assert_contains "$i3_importer" "xf86-video-vesa"
assert_contains "$i3_importer" "xf86-video-fbdev"

readme="$(<"$README")"
assert_contains "$readme" "Package Factory"
assert_contains "$readme" "scripts/import-apk-package.sh"
assert_contains "$readme" "configs/packages/ooonana-repo.list"
assert_contains "$readme" "ooonana get nano"
assert_contains "$readme" "GitHub Pages"

printf 'ok package-factory\n'
