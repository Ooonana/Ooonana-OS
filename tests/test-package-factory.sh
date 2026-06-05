#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$ROOT/.github/workflows/build-ooonana-packages.yml"
IMPORTER="$ROOT/scripts/import-apk-package.sh"
BUILDER="$ROOT/scripts/build-package-repo.sh"
README="$ROOT/README.md"
DEFAULT_PROFILE="$ROOT/configs/packages/ooonana-repo.list"
CLOUD_PROFILE="$ROOT/configs/packages/ooonana-cloud.list"
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
[[ -x "$BUILDER" ]] || fail "missing executable package repo builder"
[[ -f "$WORKFLOW" ]] || fail "missing package workflow"
[[ -f "$DEFAULT_PROFILE" ]] || fail "missing default package profile"
[[ -f "$CLOUD_PROFILE" ]] || fail "missing cloud package profile"
[[ -f "$FULL_I3_PROFILE" ]] || fail "missing full-i3 package profile"

default_profile="$(<"$DEFAULT_PROFILE")"
cloud_profile="$(<"$CLOUD_PROFILE")"
full_i3_profile="$(<"$FULL_I3_PROFILE")"
assert_contains "$default_profile" "nano"
assert_contains "$cloud_profile" "nano"
assert_contains "$cloud_profile" "ca-certificates"
assert_contains "$default_profile" "curl"
assert_contains "$full_i3_profile" "i3wm"
assert_contains "$full_i3_profile" "xorg-server"
assert_contains "$full_i3_profile" "xf86-video-vesa"
assert_contains "$full_i3_profile" "xf86-video-fbdev"
assert_contains "$full_i3_profile" "xf86-input-libinput"
assert_contains "$full_i3_profile" "xf86-input-evdev"
assert_contains "$full_i3_profile" "eudev"
assert_contains "$full_i3_profile" "xsetroot"
assert_contains "$full_i3_profile" "xinput"

workflow="$(<"$WORKFLOW")"
assert_contains "$workflow" "workflow_dispatch:"
assert_contains "$workflow" "packages:"
assert_contains "$workflow" "package_profile:"
assert_contains "$workflow" "alpine_repo:"
assert_contains "$workflow" "full_i3_profile:"
assert_contains "$workflow" "publish_pages:"
assert_contains "$workflow" "scripts/build-package-repo.sh"
assert_contains "$workflow" "actions/upload-artifact"
assert_contains "$workflow" "actions/upload-pages-artifact"
assert_contains "$workflow" "actions/deploy-pages"
assert_contains "$workflow" "gh release upload"
assert_contains "$workflow" 'pages_url="https://${OWNER}.github.io/${REPO_NAME}"'
assert_contains "$workflow" 'release_url="https://github.com/${OWNER}/${REPO_NAME}/releases/download/${RELEASE_TAG}/ooonana-package-repo.tar.gz"'
assert_contains "$workflow" 'cloud_url="$release_url"'
[[ "$workflow" != *'default: "nano"'* ]] || fail "workflow default must not be nano-only"
assert_contains "$workflow" "configs/packages/ooonana-cloud.list"
assert_contains "$workflow" "configs/packages/full-i3.list"

builder_help="$(bash "$BUILDER" --help)"
assert_contains "$builder_help" "Build an Ooonana package repo"
assert_contains "$builder_help" "--cloud-url URL"
assert_contains "$builder_help" "--full-i3"
builder_dry="$(bash "$BUILDER" --dry-run --package-profile "$CLOUD_PROFILE" --repo-url file:///apk --cloud-url https://example.test/ooonana nano vim)"
assert_contains "$builder_dry" "packages: nano bash curl wget ca-certificates vim"
assert_contains "$builder_dry" "cloud: cloud https://example.test/ooonana"
assert_contains "$builder_dry" "scripts/import-apk-package.sh"
cli_dry="$(OOONANA_SOURCE_ROOT="$ROOT" "$ROOT/packages/ooonana/usr/bin/ooonana" repo build --dry-run --package-profile "$CLOUD_PROFILE" nano)"
assert_contains "$cli_dry" "packages: nano bash curl wget ca-certificates"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
stub="$tmp/import-stub.sh"
cat > "$stub" <<'EOF'
#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --out-dir) out="$2"; shift 2 ;;
    --repo-url) shift 2 ;;
    --packages) shift 2 ;;
    *) shift ;;
  esac
done
mkdir -p "$out"
cat > "$out/nano.pkg" <<'PKG'
OOONANA_PKG_ID="nano"
OOONANA_PKG_VERSION="1.0"
OOONANA_PKG_SUMMARY="nano"
PKG
"$OOONANA_TEST_ROOT/packages/ooonana/usr/bin/ooonana" repo index "$out" >/dev/null
EOF
chmod +x "$stub"
OOONANA_TEST_ROOT="$ROOT" OOONANA_IMPORT_APK_SCRIPT="$stub" bash "$BUILDER" \
  --out-dir "$tmp/repo" \
  --package-profile /dev/null \
  --packages nano \
  --cloud-url https://example.test/repo \
  --clean >/dev/null
[[ -f "$tmp/repo/nano.pkg" ]] || fail "builder did not run importer"
[[ -f "$tmp/repo/index.tsv" ]] || fail "builder missing index"
assert_contains "$(<"$tmp/repo/cloud.repo")" 'OOONANA_REPO_URI="https://example.test/repo"'
assert_contains "$(<"$tmp/repo/README.txt")" "ooonana update"

i3_importer="$(<"$ROOT/scripts/import-i3-package-set.sh")"
assert_contains "$i3_importer" "xf86-video-vesa"
assert_contains "$i3_importer" "xf86-video-fbdev"
assert_contains "$i3_importer" "eudev"

readme="$(<"$README")"
assert_contains "$readme" "Package Factory"
assert_contains "$readme" "scripts/build-package-repo.sh"
assert_contains "$readme" "scripts/import-apk-package.sh"
assert_contains "$readme" "configs/packages/ooonana-cloud.list"
assert_contains "$readme" "configs/packages/ooonana-repo.list"
assert_contains "$readme" "ooonana get nano"
assert_contains "$readme" "GitHub Pages"
assert_contains "$readme" "ooonana-package-repo.tar.gz"

printf 'ok package-factory\n'
