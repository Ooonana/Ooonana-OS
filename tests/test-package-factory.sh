#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$ROOT/.github/workflows/build-ooonana-packages.yml"
GITLAB_CI="$ROOT/.gitlab-ci.yml"
IMPORTER="$ROOT/scripts/import-apk-package.sh"
BUILDER="$ROOT/scripts/build-package-repo.sh"
R2_PUBLISHER="$ROOT/scripts/publish-r2-repo.sh"
README="$ROOT/README.md"
DEFAULT_PROFILE="$ROOT/configs/packages/ooonana-repo.list"
CLOUD_PROFILE="$ROOT/configs/packages/ooonana-cloud.list"
FULL_I3_PROFILE="$ROOT/configs/packages/full-i3.list"
BOTH_PROFILE="$ROOT/configs/packages/both.list"

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
[[ -x "$R2_PUBLISHER" ]] || fail "missing executable R2 publisher"
[[ -f "$WORKFLOW" ]] || fail "missing package workflow"
[[ -f "$GITLAB_CI" ]] || fail "missing GitLab CI"
[[ -f "$DEFAULT_PROFILE" ]] || fail "missing default package profile"
[[ -f "$CLOUD_PROFILE" ]] || fail "missing cloud package profile"
[[ -f "$FULL_I3_PROFILE" ]] || fail "missing full-i3 package profile"
[[ -f "$BOTH_PROFILE" ]] || fail "missing both package profile"

default_profile="$(<"$DEFAULT_PROFILE")"
cloud_profile="$(<"$CLOUD_PROFILE")"
full_i3_profile="$(<"$FULL_I3_PROFILE")"
both_profile="$(<"$BOTH_PROFILE")"
assert_contains "$default_profile" "nano"
assert_contains "$cloud_profile" "nano"
assert_contains "$cloud_profile" "ca-certificates"
assert_contains "$cloud_profile" "python3"
assert_contains "$default_profile" "curl"
assert_contains "$default_profile" "python3"
assert_contains "$both_profile" "nano"
assert_contains "$both_profile" "bash"
assert_contains "$both_profile" "curl"
assert_contains "$both_profile" "ca-certificates"
assert_contains "$both_profile" "i3wm"
assert_contains "$both_profile" "chromium"
assert_contains "$both_profile" "nemo"
assert_contains "$both_profile" "linux-firmware"
assert_contains "$both_profile" "networkmanager"
assert_contains "$full_i3_profile" "i3wm"
assert_contains "$full_i3_profile" "xorg-server"
assert_contains "$full_i3_profile" "libxcb"
assert_contains "$full_i3_profile" "libxau"
assert_contains "$full_i3_profile" "libxdmcp"
assert_contains "$full_i3_profile" "xf86-video-vesa"
assert_contains "$full_i3_profile" "xf86-video-fbdev"
assert_contains "$full_i3_profile" "xf86-input-libinput"
assert_contains "$full_i3_profile" "xf86-input-evdev"
assert_contains "$full_i3_profile" "eudev"
assert_contains "$full_i3_profile" "xsetroot"
assert_contains "$full_i3_profile" "xinput"
assert_contains "$full_i3_profile" "python3"
assert_contains "$full_i3_profile" "polybar"
assert_contains "$full_i3_profile" "rofi"
assert_contains "$full_i3_profile" "yad"
assert_contains "$full_i3_profile" "picom"
assert_contains "$full_i3_profile" "dunst"
assert_contains "$full_i3_profile" "chromium"
assert_contains "$full_i3_profile" "nemo"
assert_contains "$full_i3_profile" "geany"
assert_contains "$full_i3_profile" "networkmanager"
assert_contains "$full_i3_profile" "network-manager-applet"
assert_contains "$full_i3_profile" "blueman"
assert_contains "$full_i3_profile" "bluez"
assert_contains "$full_i3_profile" "wpa_supplicant"
assert_contains "$full_i3_profile" "wireless-regdb"
assert_contains "$full_i3_profile" "linux-firmware"
assert_contains "$full_i3_profile" "linux-firmware-i915"
assert_contains "$full_i3_profile" "linux-firmware-amdgpu"
assert_contains "$full_i3_profile" "linux-firmware-brcm"
assert_contains "$full_i3_profile" "linux-firmware-rtlwifi"
assert_contains "$full_i3_profile" "sof-firmware"
assert_contains "$full_i3_profile" "mesa-dri-gallium"
assert_contains "$full_i3_profile" "mesa-va-gallium"
assert_contains "$full_i3_profile" "mesa-vulkan-intel"
assert_contains "$full_i3_profile" "alsa-utils"
assert_contains "$full_i3_profile" "arandr"
assert_contains "$full_i3_profile" "pavucontrol"
assert_contains "$full_i3_profile" "maim"
assert_contains "$full_i3_profile" "mpd"
assert_contains "$full_i3_profile" "mpc"
assert_contains "$full_i3_profile" "ncmpcpp"
assert_contains "$full_i3_profile" "ranger"
assert_contains "$full_i3_profile" "htop"
assert_contains "$full_i3_profile" "vim"
assert_contains "$full_i3_profile" "brightnessctl"
assert_contains "$full_i3_profile" "xrandr"
assert_contains "$full_i3_profile" "dosfstools"

workflow="$(<"$WORKFLOW")"
assert_contains "$workflow" "workflow_dispatch:"
assert_contains "$workflow" "packages:"
assert_contains "$workflow" "package_profile:"
assert_contains "$workflow" "alpine_repo:"
assert_contains "$workflow" "full_i3_profile:"
assert_contains "$workflow" "publish_pages:"
assert_contains "$workflow" "publish_r2:"
assert_contains "$workflow" "r2_bucket:"
assert_contains "$workflow" "r2_prefix:"
assert_contains "$workflow" "r2_public_url:"
assert_contains "$workflow" "scripts/build-package-repo.sh"
assert_contains "$workflow" "scripts/publish-r2-repo.sh"
assert_contains "$workflow" "actions/upload-artifact"
assert_contains "$workflow" "actions/upload-pages-artifact"
assert_contains "$workflow" "actions/deploy-pages"
assert_contains "$workflow" "gh release upload"
assert_contains "$workflow" "awscli"
assert_contains "$workflow" "CLOUDFLARE_ACCOUNT_ID"
assert_contains "$workflow" "R2_ACCESS_KEY_ID"
assert_contains "$workflow" "R2_SECRET_ACCESS_KEY"
assert_contains "$workflow" "OOONANA_REPO_SIGN_KEY_B64"
assert_contains "$workflow" "OOONANA_REPO_PUBLIC_KEY_B64"
assert_contains "$workflow" "--sign-key"
assert_contains "$workflow" "--public-key"
assert_contains "$workflow" 'pages_url="https://${OWNER}.github.io/${REPO_NAME}"'
assert_contains "$workflow" 'release_url="https://github.com/${OWNER}/${REPO_NAME}/releases/download/${RELEASE_TAG}/ooonana-package-repo.tar.gz"'
assert_contains "$workflow" 'cloud_url="$release_url"'
[[ "$workflow" != *'default: "nano"'* ]] || fail "workflow default must not be nano-only"
assert_contains "$workflow" "configs/packages/ooonana-cloud.list"
assert_contains "$workflow" "configs/packages/full-i3.list"
assert_contains "$workflow" "configs/packages/both.list"
assert_contains "$workflow" "default: \"configs/packages/both.list\""
assert_contains "$workflow" "default: true"

gitlab_ci="$(<"$GITLAB_CI")"
assert_contains "$gitlab_ci" "PACKAGE_SET: \"both\""
assert_contains "$gitlab_ci" "PACKAGE_PROFILE: \"\""
assert_contains "$gitlab_ci" "pages:"
assert_contains "$gitlab_ci" "public"
assert_contains "$gitlab_ci" "CI_PAGES_URL"
assert_contains "$gitlab_ci" "OOONANA_PAGES_REPO_URL"
assert_contains "$gitlab_ci" "OOONANA_PAGES_MAX_BYTES"
assert_contains "$gitlab_ci" "scripts/build-package-repo.sh"
assert_contains "$gitlab_ci" '--repo-name "$OOONANA_REPO_NAME"'
assert_contains "$gitlab_ci" "ooonana update"
assert_contains "$gitlab_ci" "ooonana upgrade"
assert_contains "$gitlab_ci" "OOONANA_REPO_SIGN_KEY_B64"
assert_contains "$gitlab_ci" "OOONANA_REPO_PUBLIC_KEY_B64"
assert_contains "$gitlab_ci" "configs/packages/ooonana-cloud.list"
assert_contains "$gitlab_ci" "configs/packages/full-i3.list"
assert_contains "$gitlab_ci" "configs/packages/both.list"

builder_help="$(bash "$BUILDER" --help)"
assert_contains "$builder_help" "Build an Ooonana package repo"
assert_contains "$builder_help" "--cloud-url URL"
assert_contains "$builder_help" "--full-i3"
assert_contains "$builder_help" "--sign-key PATH"
assert_contains "$builder_help" "--public-key PATH"
builder_dry="$(bash "$BUILDER" --dry-run --package-profile "$CLOUD_PROFILE" --repo-url file:///apk --cloud-url https://example.test/ooonana nano vim)"
assert_contains "$builder_dry" "packages: nano bash curl wget ca-certificates python3 vim"
assert_contains "$builder_dry" "cloud: cloud https://example.test/ooonana"
assert_contains "$builder_dry" "scripts/import-apk-package.sh"
cli_dry="$(OOONANA_SOURCE_ROOT="$ROOT" "$ROOT/packages/ooonana/usr/bin/ooonana" repo build --dry-run --package-profile "$CLOUD_PROFILE" nano)"
assert_contains "$cli_dry" "packages: nano bash curl wget ca-certificates python3"

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

r2_help="$(bash "$R2_PUBLISHER" --help)"
assert_contains "$r2_help" "Publish an Ooonana package repo directory to Cloudflare R2"
assert_contains "$r2_help" "--repo-dir DIR"
assert_contains "$r2_help" "--bucket BUCKET"
assert_contains "$r2_help" "--public-url URL"
r2_dry="$(R2_ACCESS_KEY_ID=test-key R2_SECRET_ACCESS_KEY=test-secret CLOUDFLARE_ACCOUNT_ID=abc123 bash "$R2_PUBLISHER" \
  --repo-dir "$tmp/repo" \
  --bucket ooonana-packages \
  --prefix packages-latest \
  --public-url https://packages.example.test/packages-latest \
  --source-file "$tmp/r2.repo" \
  --dry-run)"
assert_contains "$r2_dry" "aws s3 sync"
assert_contains "$r2_dry" "https://abc123.r2.cloudflarestorage.com"
assert_contains "$r2_dry" "s3://ooonana-packages/packages-latest/"
assert_contains "$r2_dry" "https://packages.example.test/packages-latest"
assert_contains "$(<"$tmp/r2.repo")" 'OOONANA_REPO_NAME="r2"'
assert_contains "$(<"$tmp/r2.repo")" 'OOONANA_REPO_URI="https://packages.example.test/packages-latest"'

i3_importer="$(<"$ROOT/scripts/import-i3-package-set.sh")"
assert_contains "$i3_importer" "xf86-video-vesa"
assert_contains "$i3_importer" "libxcb"
assert_contains "$i3_importer" "libxau"
assert_contains "$i3_importer" "libxdmcp"
assert_contains "$i3_importer" "xf86-video-fbdev"
assert_contains "$i3_importer" "eudev"
assert_contains "$i3_importer" "polybar"
assert_contains "$i3_importer" "geany"
assert_contains "$i3_importer" "maim"
assert_contains "$i3_importer" "ncmpcpp"
assert_contains "$i3_importer" "brightnessctl"
assert_contains "$i3_importer" "xrandr"

readme="$(<"$README")"
assert_contains "$readme" "Package Factory"
assert_contains "$readme" "scripts/build-package-repo.sh"
assert_contains "$readme" "scripts/import-apk-package.sh"
assert_contains "$readme" "configs/packages/ooonana-cloud.list"
assert_contains "$readme" "configs/packages/ooonana-repo.list"
assert_contains "$readme" "configs/packages/both.list"
assert_contains "$readme" "ooonana get nano"
assert_contains "$readme" "GitHub Pages"
assert_contains "$readme" "GitLab Pages"
assert_contains "$readme" "Cloudflare R2"
assert_contains "$readme" "scripts/publish-r2-repo.sh"
assert_contains "$readme" "R2_ACCESS_KEY_ID"
assert_contains "$readme" "ooonana-package-repo.tar.gz"

printf 'ok package-factory\n'
