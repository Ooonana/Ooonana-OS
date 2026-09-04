#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR=""
VERSION="0.8.24"
DRY_RUN=0

usage() {
  cat <<'USAGE'
Build the native Ooonana system update package.

Usage:
  scripts/build-ooonana-core-package.sh --out-dir PATH [options]

Options:
  --version VER  Package version (default: 0.8.24)
  --dry-run      Print resolved package details
  -h, --help     Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'build-ooonana-core-package: unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done

[[ -n "$OUT_DIR" ]] || { printf 'build-ooonana-core-package: --out-dir required\n' >&2; exit 1; }
[[ "$VERSION" =~ ^[0-9][0-9A-Za-z._+-]*$ ]] || { printf 'build-ooonana-core-package: bad version\n' >&2; exit 1; }

runtime_id="ooonana-core-runtime"
archive_rel="archives/$runtime_id-$VERSION.tar.gz"
archive="$OUT_DIR/$archive_rel"
metadata="$OUT_DIR/ooonana-core.pkg"
runtime_metadata="$OUT_DIR/$runtime_id.pkg"

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'id: ooonana-core\nruntime-id: %s\nversion: %s\noverlay: %s\narchive: %s\n' \
    "$runtime_id" "$VERSION" "$ROOT/packages/ooonana" "$archive"
  exit 0
fi

command -v tar >/dev/null 2>&1 || { printf 'missing command: tar\n' >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { printf 'missing command: sha256sum\n' >&2; exit 1; }
[[ -x "$ROOT/packages/ooonana/usr/bin/ooonana" ]] || { printf 'missing Ooonana overlay\n' >&2; exit 1; }

extract_helper() {
  local marker="$1"
  local output="$2"
  awk -v marker="$marker" '
    index($0, marker) { capture=1; next }
    capture && $0 == "EOF" { exit }
    capture { print }
  ' "$ROOT/scripts/build-full-i3-rootfs.sh" >"$output"
  [[ -s "$output" ]] || { printf 'missing generated helper: %s\n' "$marker" >&2; exit 1; }
  chmod 0755 "$output"
}

extract_config() {
  local marker="$1"
  local output="$2"
  awk -v marker="$marker" '
    index($0, marker) { capture=1; next }
    capture && $0 == "EOF" { exit }
    capture { print }
  ' "$ROOT/scripts/build-full-i3-rootfs.sh" >"$output"
  [[ -s "$output" ]] || { printf 'missing generated config: %s\n' "$marker" >&2; exit 1; }
  chmod 0644 "$output"
}

mkdir -p "$OUT_DIR/archives"
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
cp -a "$ROOT/packages/ooonana/." "$staging/"
find "$staging" -type d -exec chmod 0755 {} +
find "$staging" -type f -exec chmod 0644 {} +
find "$staging/usr/bin" "$staging/usr/sbin" -type f -exec chmod 0755 {} +
chmod 0755 "$staging/usr/lib/ooonana/oonana_game.py"
mkdir -p "$staging/etc/i3"
install -m 0644 "$ROOT/branding/i3/config" "$staging/etc/i3/config"
install -m 0644 "$ROOT/branding/i3/config" "$staging/etc/i3/config.keycodes"
for helper in \
  ooonana-theme-env ooonana-open ooonana-apps ooonana-run-admin \
  ooonana-browser ooonana-files ooonana-hardware-reprobe \
  ooonana-wireless-diagnose ooonana-service-repair ooonana-service-watchdog \
  ooonana-wifi ooonana-bluetooth ooonana-touchpad ooonana-rofi-wifi \
  ooonana-rofi-bluetooth ooonana-wifi-panel ooonana-wifi-status \
  ooonana-bluetooth-panel ooonana-bluetooth-status ooonana-rofi-brightness \
  ooonana-brightness-panel ooonana-audio-panel ooonana-audio-status \
  ooonana-battery-status ooonana-volume ooonana-rofi-power \
  ooonana-power-menu ooonana-screenshot ooonana-editor ooonana-processes \
  ooonana-process-kill \
  ooonana-ranger ooonana-brightness ooonana-brightness-status \
  ooonana-packages-app ooonana-packages ooonana-settings \
  ooonana-settings-launch ooonana-installer-gui ooonana-gui-installer \
  ooonana-install-wizard ooonana-i3-smoke-session ooonana-i3-session \
  ooonana-i3-installer-session; do
  extract_helper "ROOTFS/usr/bin/$helper" "$staging/usr/bin/$helper"
done

for config in \
  etc/NetworkManager/NetworkManager.conf \
  etc/bluetooth/main.conf \
  etc/ooonana/xsettingsd.conf \
  etc/ooonana/polybar.ini \
  etc/ooonana/rofi.rasi \
  etc/ooonana/picom.conf \
  etc/ooonana/dunstrc; do
  mkdir -p "$staging/$(dirname "$config")"
  extract_config "ROOTFS/$config" "$staging/$config"
done
mkdir -p "$staging/var/lib/ooonana/packages/files"
: > "$staging/var/lib/ooonana/packages/files/ooonana-core.list"
tar -C "$staging" -czf "$archive" .
archive_sha="$(sha256sum "$archive" | awk '{print $1}')"
cat > "$runtime_metadata" <<EOF
OOONANA_PKG_ID="$runtime_id"
OOONANA_PKG_VERSION="$VERSION"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Ooonana OS native CLI, desktop apps, services, game, and defaults"
OOONANA_PKG_DEPS="dbus-daemon-launch-helper"
OOONANA_PKG_ARCHIVE="$archive_rel"
OOONANA_PKG_SHA256="$archive_sha"
OOONANA_PKG_NOTES="Native Ooonana system payload; archives download only during install or upgrade"
EOF
cat > "$metadata" <<EOF
OOONANA_PKG_ID="ooonana-core"
OOONANA_PKG_VERSION="$VERSION"
OOONANA_PKG_KIND="bundle"
OOONANA_PKG_SUMMARY="Ooonana OS native system update"
OOONANA_PKG_DEPS="$runtime_id"
OOONANA_PKG_ARCHIVE=""
OOONANA_PKG_SHA256=""
OOONANA_PKG_NOTES="Stable meta package for migration-safe native Ooonana updates"
EOF

printf 'built %s\nbuilt %s\n' "$runtime_metadata" "$metadata"
