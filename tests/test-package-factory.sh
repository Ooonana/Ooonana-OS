#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$ROOT/.github/workflows/build-ooonana-packages.yml"
GITLAB_CI="$ROOT/.gitlab-ci.yml"
IMPORTER="$ROOT/scripts/import-apk-package.sh"
BUILDER="$ROOT/scripts/build-package-repo.sh"
KERNEL_PACKAGER="$ROOT/scripts/build-kernel-package.sh"
CORE_PACKAGER="$ROOT/scripts/build-ooonana-core-package.sh"
OPENVINO_PACKAGER="$ROOT/scripts/build-openvino-chat-package.sh"
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
[[ -x "$KERNEL_PACKAGER" ]] || fail "missing executable kernel package builder"
[[ -x "$CORE_PACKAGER" ]] || fail "missing executable core package builder"
[[ -x "$OPENVINO_PACKAGER" ]] || fail "missing executable OpenVINO package builder"
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
assert_contains "$cloud_profile" "bubblewrap"
assert_contains "$cloud_profile" "xz"
assert_contains "$default_profile" "curl"
assert_contains "$default_profile" "python3"
assert_contains "$both_profile" "nano"
assert_contains "$both_profile" "bash"
assert_contains "$both_profile" "perl"
assert_contains "$both_profile" "curl"
assert_contains "$both_profile" "ca-certificates"
assert_contains "$both_profile" "bubblewrap"
assert_contains "$both_profile" "xz"
assert_contains "$both_profile" "i3wm"
assert_contains "$both_profile" "chromium"
assert_contains "$both_profile" "nemo"
grep -qx "linux-firmware" "$BOTH_PROFILE" &&
  fail "combined profile includes broad linux-firmware metapackage"
assert_contains "$both_profile" "networkmanager"
assert_contains "$both_profile" "font-awesome-free"
assert_contains "$both_profile" "font-awesome-brands"
assert_contains "$both_profile" "font-misc-misc"
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
assert_contains "$full_i3_profile" "bash"
assert_contains "$full_i3_profile" "perl"
assert_contains "$full_i3_profile" "i3lock"
assert_contains "$full_i3_profile" "xset"
assert_contains "$full_i3_profile" "grub-efi"
assert_contains "$full_i3_profile" "xsetroot"
assert_contains "$full_i3_profile" "xinput"
assert_contains "$full_i3_profile" "python3"
assert_contains "$full_i3_profile" "polybar"
assert_contains "$full_i3_profile" "rofi"
assert_contains "$full_i3_profile" "yad"
assert_contains "$full_i3_profile" "picom"
assert_contains "$full_i3_profile" "font-awesome-free"
assert_contains "$full_i3_profile" "font-awesome-brands"
assert_contains "$full_i3_profile" "font-misc-misc"
assert_contains "$full_i3_profile" "adwaita-icon-theme"
assert_contains "$full_i3_profile" "dunst"
assert_contains "$full_i3_profile" "chromium"
assert_contains "$full_i3_profile" "nemo"
assert_contains "$full_i3_profile" "geany"
assert_contains "$full_i3_profile" "networkmanager"
assert_contains "$full_i3_profile" "networkmanager-cli"
assert_contains "$full_i3_profile" "py3-cairo"
assert_contains "$full_i3_profile" "networkmanager-tui"
assert_contains "$full_i3_profile" "network-manager-applet"
assert_contains "$full_i3_profile" "blueman"
assert_contains "$full_i3_profile" "bluez"
assert_contains "$full_i3_profile" "iproute2"
assert_contains "$full_i3_profile" "util-linux-misc"
assert_contains "$full_i3_profile" "pulseaudio-utils"
assert_contains "$full_i3_profile" "pipewire-alsa"
assert_contains "$full_i3_profile" "pipewire-spa-bluez"
assert_contains "$full_i3_profile" "wireplumber"
assert_contains "$full_i3_profile" "font-noto-cjk"
assert_contains "$full_i3_profile" "musl-locales"
assert_contains "$full_i3_profile" "iw"
assert_contains "$full_i3_profile" "wireless-tools"
assert_contains "$full_i3_profile" "wpa_supplicant"
assert_contains "$full_i3_profile" "wireless-regdb"
grep -qx "linux-firmware" "$FULL_I3_PROFILE" &&
  fail "full profile includes broad linux-firmware metapackage"
assert_contains "$full_i3_profile" "linux-firmware-i915"
assert_contains "$full_i3_profile" "linux-firmware-intel"
assert_contains "$full_i3_profile" "linux-firmware-amdgpu"
assert_contains "$full_i3_profile" "linux-firmware-brcm"
assert_contains "$full_i3_profile" "linux-firmware-qca"
assert_contains "$full_i3_profile" "linux-firmware-rtl_nic"
assert_contains "$full_i3_profile" "linux-firmware-rtlwifi"
assert_contains "$full_i3_profile" "linux-firmware-rtw88"
assert_contains "$full_i3_profile" "linux-firmware-rtw89"
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
assert_contains "$workflow" "kernel_version:"
assert_contains "$workflow" "kernel_url:"
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
assert_contains "$workflow" "--kernel-url"
assert_contains "$workflow" "--kernel-version"
assert_contains "$workflow" "--kernel-sha256"
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
assert_contains "$gitlab_ci" "workflow:"
assert_contains "$gitlab_ci" "ci-smoke:"
assert_contains "$gitlab_ci" "PACKAGE_SET: \"both\""
assert_contains "$gitlab_ci" "PACKAGE_PROFILE: \"\""
assert_contains "$gitlab_ci" "deploy-package-repo:"
assert_contains "$gitlab_ci" "pages: true"
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
assert_contains "$gitlab_ci" "OOONANA_KERNEL_VERSION"
assert_contains "$gitlab_ci" "OOONANA_CORE_VERSION"
assert_contains "$gitlab_ci" 'OOONANA_CORE_VERSION: "0.8.18"'
assert_contains "$gitlab_ci" "OOONANA_OPENVINO_CHAT_VERSION"
assert_contains "$gitlab_ci" "OOONANA_KERNEL_PACKAGE_URL"
assert_contains "$gitlab_ci" "OOONANA_KERNEL_PACKAGE_SHA256"
assert_contains "$gitlab_ci" 'OOONANA_KERNEL_PACKAGE_URL: ""'
assert_contains "$gitlab_ci" "--kernel-url"
assert_contains "$gitlab_ci" "--kernel-sha256"
assert_contains "$gitlab_ci" "--kernel-version"
assert_contains "$gitlab_ci" "configs/packages/ooonana-cloud.list"
assert_contains "$gitlab_ci" "configs/packages/full-i3.list"
assert_contains "$gitlab_ci" "configs/packages/both.list"

builder_help="$(bash "$BUILDER" --help)"
assert_contains "$builder_help" "Build an Ooonana package repo"
assert_contains "$builder_help" "--cloud-url URL"
assert_contains "$builder_help" "--full-i3"
assert_contains "$builder_help" "--sign-key PATH"
assert_contains "$builder_help" "--public-key PATH"
assert_contains "$builder_help" "--kernel PATH"
assert_contains "$builder_help" "--kernel-url URL"
assert_contains "$builder_help" "--kernel-sha256 SHA256"
assert_contains "$builder_help" "--core-version VER"
assert_contains "$builder_help" "--openvino-version VER"
builder_dry="$(bash "$BUILDER" --dry-run --package-profile "$CLOUD_PROFILE" --repo-url file:///apk --cloud-url https://example.test/ooonana nano vim)"
assert_contains "$builder_dry" "packages: nano bash curl wget ca-certificates ca-certificates-bundle python3 bubblewrap xz vim"
assert_contains "$builder_dry" "cloud: cloud https://example.test/ooonana"
assert_contains "$builder_dry" "scripts/import-apk-package.sh"
assert_contains "$builder_dry" "scripts/build-ooonana-core-package.sh"
assert_contains "$builder_dry" "scripts/build-openvino-chat-package.sh"
builder_kernel_dry="$(bash "$BUILDER" --dry-run --package-profile "$CLOUD_PROFILE" --kernel-url https://example.test/vmlinuz --kernel-sha256 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef --kernel-version 9.9.9 nano)"
assert_contains "$builder_kernel_dry" "kernel-url: https://example.test/vmlinuz"
assert_contains "$builder_kernel_dry" "kernel-sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
assert_contains "$builder_kernel_dry" "scripts/build-kernel-package.sh"
assert_contains "$builder_kernel_dry" "--version 9.9.9"
kernel_builder_help="$(bash "$KERNEL_PACKAGER" --help)"
assert_contains "$kernel_builder_help" "Build an Ooonana kernel package"
assert_contains "$kernel_builder_help" "--kernel PATH_OR_URL"
assert_contains "$kernel_builder_help" "--sha256 SHA256"
if bash "$KERNEL_PACKAGER" --dry-run --kernel https://example.test/vmlinuz >/dev/null 2>&1; then
  fail "remote kernel package accepted without SHA-256"
fi
kernel_builder_dry="$(bash "$KERNEL_PACKAGER" --dry-run --kernel /tmp/vmlinuz --out-dir /tmp/repo --version 9.9.9)"
assert_contains "$kernel_builder_dry" "id: ooonana-kernel"
assert_contains "$kernel_builder_dry" "version: 9.9.9"
core_builder_dry="$(bash "$CORE_PACKAGER" --dry-run --out-dir /tmp/repo --version 0.8.1)"
assert_contains "$core_builder_dry" "id: ooonana-core"
assert_contains "$core_builder_dry" "runtime-id: ooonana-core-runtime"
assert_contains "$core_builder_dry" "version: 0.8.1"
openvino_builder_dry="$(bash "$OPENVINO_PACKAGER" --dry-run --out-dir /tmp/repo --version 0.1.1)"
assert_contains "$openvino_builder_dry" "id: openvino-chat"
assert_contains "$openvino_builder_dry" "version: 0.1.1"
cli_dry="$(OOONANA_SOURCE_ROOT="$ROOT" "$ROOT/packages/ooonana/usr/bin/ooonana" repo build --dry-run --package-profile "$CLOUD_PROFILE" nano)"
assert_contains "$cli_dry" "packages: nano bash curl wget ca-certificates ca-certificates-bundle python3 bubblewrap xz"

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
cat > "$out/dbus-daemon-launch-helper.pkg" <<'PKG'
OOONANA_PKG_ID="dbus-daemon-launch-helper"
OOONANA_PKG_VERSION="1.0"
OOONANA_PKG_KIND="profile"
OOONANA_PKG_SUMMARY="D-Bus activation helper"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE=""
OOONANA_PKG_SHA256=""
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
[[ -f "$tmp/repo/base.pkg" ]] || fail "builder missing scratch base metadata"
[[ -f "$tmp/repo/ooonana-core.pkg" ]] || fail "builder missing core meta package"
[[ -f "$tmp/repo/ooonana-core-runtime.pkg" ]] || fail "builder missing core runtime package"
[[ -f "$tmp/repo/openvino-chat.pkg" ]] || fail "builder missing OpenVINO Chat package"
[[ -f "$tmp/repo/archives/openvino-chat-0.1.1.tar.gz" ]] || fail "builder missing OpenVINO Chat archive"
assert_contains "$(<"$tmp/repo/ooonana-core.pkg")" 'OOONANA_PKG_DEPS="ooonana-core-runtime"'
assert_contains "$(<"$tmp/repo/ooonana-core-runtime.pkg")" 'OOONANA_PKG_DEPS="dbus-daemon-launch-helper"'
assert_contains "$(<"$tmp/repo/ooonana-core.pkg")" 'OOONANA_PKG_ARCHIVE=""'
core_runtime_archive="$(find "$tmp/repo/archives" -maxdepth 1 -name 'ooonana-core-runtime-*.tar.gz' -print -quit)"
[[ -f "$core_runtime_archive" ]] || fail "builder missing core runtime archive"
tar -tzf "$core_runtime_archive" | grep 'var/lib/ooonana/packages/files/ooonana-core.list' >/dev/null || fail "core runtime missing legacy manifest guard"
tar -tzf "$core_runtime_archive" | grep './usr/bin/ooonana-audio-start' >/dev/null || fail "core runtime missing audio session helper"
tar -tzf "$core_runtime_archive" | grep './usr/bin/ooonana-game-launch' >/dev/null || fail "core runtime missing game launcher"
tar -tzf "$core_runtime_archive" | grep './usr/share/ooonana/wallpapers/ooonana-notes.jpg' >/dev/null || fail "core runtime missing Notes wallpaper"
tar -tzf "$core_runtime_archive" | grep './etc/gtk-3.0/settings.ini' >/dev/null || fail "core runtime missing GTK window controls"
[[ "$(tar -tvzf "$core_runtime_archive" ./usr/bin/ooonana-game-launch | awk '{print $1}')" == "-rwxr-xr-x" ]] ||
  fail "core runtime game launcher is not executable"
[[ "$(tar -tvzf "$core_runtime_archive" ./usr/lib/ooonana/oonana_game.py | awk '{print $1}')" == "-rwxr-xr-x" ]] ||
  fail "core runtime Python game is not executable"
tar -tzf "$core_runtime_archive" | grep './usr/bin/which' >/dev/null || fail "core runtime missing which helper"
tar -tzf "$core_runtime_archive" | grep './usr/bin/strings' >/dev/null || fail "core runtime missing strings helper"
tar -tzf "$core_runtime_archive" | grep './usr/bin/hsetroot' >/dev/null || fail "core runtime missing wallpaper renderer"
tar -tzf "$core_runtime_archive" | grep './usr/bin/ooonana-wallpaper' >/dev/null || fail "core runtime missing wallpaper settings"
tar -tzf "$core_runtime_archive" | grep './usr/bin/ooonana-theme-env' >/dev/null || fail "core runtime missing desktop theme helper"
tar -tzf "$core_runtime_archive" | grep './etc/i3/config' >/dev/null || fail "core runtime missing updated i3 config"
tar -tzf "$core_runtime_archive" | grep './etc/profile.d/00-ooonana-locale.sh' >/dev/null || fail "core runtime missing UTF-8 locale profile"
[[ -f "$tmp/repo/index.tsv" ]] || fail "builder missing index"
core_upgrade_root="$tmp/core-upgrade-root"
core_upgrade_state="$core_upgrade_root/var/lib/ooonana/packages"
mkdir -p "$core_upgrade_root/usr/bin" "$core_upgrade_state/installed" "$core_upgrade_state/files"
printf 'old core\n' > "$core_upgrade_root/usr/bin/ooonana"
printf 'usr/bin/ooonana\n' > "$core_upgrade_state/files/ooonana-core.list"
cat > "$core_upgrade_state/installed/ooonana-core.pkg" <<'EOF'
OOONANA_PKG_ID="ooonana-core"
OOONANA_PKG_VERSION="0.8.1"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Legacy Ooonana core"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="archives/ooonana-core-0.8.1.tar.gz"
OOONANA_PKG_SHA256="legacy"
EOF
core_upgrade="$(OOONANA_REPO_DIR="$tmp/repo" \
  OOONANA_CACHE_DIR="$tmp/core-upgrade-cache" \
  OOONANA_ROOT="$core_upgrade_root" \
  "$ROOT/packages/ooonana/usr/bin/ooonana" upgrade ooonana-core)"
assert_contains "$core_upgrade" "installed ooonana-core-runtime"
assert_contains "$core_upgrade" "upgraded ooonana-core 0.8.1"
[[ -x "$core_upgrade_root/usr/bin/ooonana" ]] || fail "core migration removed upgraded CLI"
assert_contains "$(OOONANA_ROOT="$core_upgrade_root" "$core_upgrade_root/usr/bin/ooonana" version)" "ooonana 0.8.18"
assert_contains "$(<"$tmp/repo/cloud.repo")" 'OOONANA_REPO_URI="https://example.test/repo"'
assert_contains "$(<"$tmp/repo/README.txt")" "ooonana update"

full_stub="$tmp/import-full-stub.sh"
cat > "$full_stub" <<'EOF'
#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --out-dir) out="$2"; shift 2 ;;
    --repo-url|--packages) shift 2 ;;
    *) shift ;;
  esac
done
mkdir -p "$out"
cat > "$out/full-i3.pkg" <<'PKG'
OOONANA_PKG_ID="full-i3"
OOONANA_PKG_VERSION="1.0"
OOONANA_PKG_KIND="profile"
OOONANA_PKG_SUMMARY="full i3"
OOONANA_PKG_DEPS="base"
OOONANA_PKG_ARCHIVE=""
OOONANA_PKG_SHA256=""
PKG
cat > "$out/dbus-daemon-launch-helper.pkg" <<'PKG'
OOONANA_PKG_ID="dbus-daemon-launch-helper"
OOONANA_PKG_VERSION="1.0"
OOONANA_PKG_KIND="profile"
OOONANA_PKG_SUMMARY="D-Bus activation helper"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE=""
OOONANA_PKG_SHA256=""
PKG
EOF
chmod +x "$full_stub"
OOONANA_TEST_ROOT="$ROOT" OOONANA_IMPORT_I3_SCRIPT="$full_stub" bash "$BUILDER" \
  --out-dir "$tmp/full-repo" \
  --package-profile /dev/null \
  --packages nano \
  --full-i3 \
  --clean >/dev/null
[[ -f "$tmp/full-repo/base.pkg" ]] || fail "full repo missing base dependency"
OOONANA_REPO_DIR="$tmp/full-repo" \
  OOONANA_SOURCES_DIR="$tmp/empty-sources" \
  OOONANA_STATE_DIR="$tmp/full-state" \
  OOONANA_CACHE_DIR="$tmp/full-cache" \
  "$ROOT/packages/ooonana/usr/bin/ooonana" install full-i3 --dry-run >/dev/null ||
  fail "full repo dependency closure is broken"

printf 'kernel-test\n' > "$tmp/vmlinuz"
kernel_sha256="$(sha256sum "$tmp/vmlinuz" | awk '{print $1}')"
bash "$KERNEL_PACKAGER" \
  --out-dir "$tmp/kernel-repo" \
  --kernel "$tmp/vmlinuz" \
  --sha256 "$kernel_sha256" \
  --version 9.9.9 >/dev/null
[[ -f "$tmp/kernel-repo/ooonana-kernel.pkg" ]] || fail "kernel package missing"
[[ -f "$tmp/kernel-repo/archives/ooonana-kernel-9.9.9.tar.gz" ]] || fail "kernel archive missing"
assert_contains "$(<"$tmp/kernel-repo/index.tsv")" $'ooonana-kernel\t9.9.9\tkernel'
tar -tzf "$tmp/kernel-repo/archives/ooonana-kernel-9.9.9.tar.gz" | grep -q 'boot/vmlinuz' || fail "kernel archive missing /boot/vmlinuz"
if bash "$KERNEL_PACKAGER" --out-dir "$tmp/bad-kernel-repo" --kernel "$tmp/vmlinuz" \
  --sha256 0000000000000000000000000000000000000000000000000000000000000000 >/dev/null 2>&1; then
  fail "kernel package accepted mismatched SHA-256"
fi

OOONANA_TEST_ROOT="$ROOT" OOONANA_IMPORT_APK_SCRIPT="$stub" bash "$BUILDER" \
  --out-dir "$tmp/repo-with-kernel" \
  --package-profile /dev/null \
  --packages nano \
  --kernel "$tmp/vmlinuz" \
  --kernel-version 9.9.9 \
  --clean >/dev/null
[[ -f "$tmp/repo-with-kernel/ooonana-kernel.pkg" ]] || fail "builder did not add kernel package"
assert_contains "$(<"$tmp/repo-with-kernel/index.tsv")" $'ooonana-kernel\t9.9.9\tkernel'

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
assert_contains "$i3_importer" "configs/packages/full-i3.list"
assert_contains "$i3_importer" "alpine/edge/community/x86_64"
assert_contains "$full_i3_profile" "xf86-video-vesa"
assert_contains "$full_i3_profile" "libxcb"
assert_contains "$full_i3_profile" "libxau"
assert_contains "$full_i3_profile" "libxdmcp"
assert_contains "$full_i3_profile" "xf86-video-fbdev"
assert_contains "$full_i3_profile" "eudev"
assert_contains "$full_i3_profile" "polybar"
assert_contains "$full_i3_profile" "geany"
assert_contains "$full_i3_profile" "maim"
assert_contains "$full_i3_profile" "ncmpcpp"
assert_contains "$full_i3_profile" "brightnessctl"
assert_contains "$full_i3_profile" "xrandr"

readme="$(<"$README")"
assert_contains "$readme" "Package Factory"
assert_contains "$readme" "scripts/build-package-repo.sh"
assert_contains "$readme" "scripts/import-apk-package.sh"
assert_contains "$readme" "scripts/build-kernel-package.sh"
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
assert_contains "$readme" "ooonana-kernel"

printf 'ok package-factory\n'
