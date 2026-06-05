#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

OUT_DIR="$ROOT/packages/ooonana/usr/lib/ooonana/repo"
REPO_ARGS=()
I3_PACKAGES="xorg-server xinit xf86-video-vesa xf86-video-fbdev xf86-input-libinput xf86-input-evdev eudev i3wm i3status dmenu feh xterm xsetroot xinput coreutils parted grub-bios e2fsprogs rsync util-linux"
BRANDING_VERSION="0.1.0"

usage() {
  cat <<'USAGE'
Import the Ooonana full-i3 Alpine package set.

Usage:
  scripts/import-i3-package-set.sh [options]

Options:
  --repo-url URL      Alpine APK repository URL or path. Can be repeated.
  --out-dir PATH      Ooonana repo output directory
  --packages "LIST"   Space-separated APK packages for the i3 bundle
  -h, --help          Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url) REPO_ARGS+=("--repo-url" "$2"); shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --packages) I3_PACKAGES="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

shell_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

write_pkg() {
  local path="$1"
  local id="$2"
  local version="$3"
  local kind="$4"
  local summary="$5"
  local deps="$6"
  local archive="${7:-}"
  local sha="${8:-}"
  local components="${9:-}"
  local notes="${10:-}"
  cat > "$path" <<EOF
OOONANA_PKG_ID="$(shell_escape "$id")"
OOONANA_PKG_VERSION="$(shell_escape "$version")"
OOONANA_PKG_KIND="$(shell_escape "$kind")"
OOONANA_PKG_SUMMARY="$(shell_escape "$summary")"
OOONANA_PKG_DEPS="$(shell_escape "$deps")"
EOF
  if [[ -n "$archive" ]]; then
    printf 'OOONANA_PKG_ARCHIVE="%s"\n' "$(shell_escape "$archive")" >> "$path"
  fi
  if [[ -n "$sha" ]]; then
    printf 'OOONANA_PKG_SHA256="%s"\n' "$(shell_escape "$sha")" >> "$path"
  fi
  if [[ -n "$components" ]]; then
    printf 'OOONANA_PKG_COMPONENTS="%s"\n' "$(shell_escape "$components")" >> "$path"
  fi
  if [[ -n "$notes" ]]; then
    printf 'OOONANA_PKG_NOTES="%s"\n' "$(shell_escape "$notes")" >> "$path"
  fi
}

build_branding_archive() {
  local work="$1"
  local archive_rel="archives/ooonana-branding-$BRANDING_VERSION.tar.gz"
  local archive_path="$OUT_DIR/$archive_rel"
  local payload="$work/branding-payload"
  mkdir -p \
    "$payload/usr/share/ooonana/wallpapers" \
    "$payload/etc/i3" \
    "$OUT_DIR/archives"
  install -m 0644 "$ROOT/branding/logo.svg" "$payload/usr/share/ooonana/logo.svg"
  install -m 0644 "$ROOT/branding/logo.png" "$payload/usr/share/ooonana/logo.png"
  install -m 0644 "$ROOT/branding/wallpaper.svg" "$payload/usr/share/ooonana/wallpapers/ooonana-wallpaper.svg"
  install -m 0644 "$ROOT/branding/wallpaper.png" "$payload/usr/share/ooonana/wallpapers/ooonana-wallpaper.png"
  install -m 0644 "$ROOT/branding/i3/config" "$payload/etc/i3/config"
  tar \
    --sort=name \
    --mtime='UTC 1970-01-01' \
    --numeric-owner \
    --owner=0 \
    --group=0 \
    --pax-option=delete=atime,delete=ctime \
    -C "$payload" \
    -cf - \
    . | gzip -n > "$archive_path"
  chmod a+rw "$archive_path"
  printf '%s\n' "$archive_rel"
}

main() {
  ooonana_require_linux
  ooonana_require_commands chmod gzip install mkdir sed sha256sum tar
  [[ -f "$ROOT/branding/logo.svg" ]] || ooonana_die "missing branding/logo.svg"
  [[ -f "$ROOT/branding/logo.png" ]] || ooonana_die "missing branding/logo.png"
  [[ -f "$ROOT/branding/wallpaper.svg" ]] || ooonana_die "missing branding/wallpaper.svg"
  [[ -f "$ROOT/branding/wallpaper.png" ]] || ooonana_die "missing branding/wallpaper.png"
  [[ -f "$ROOT/branding/i3/config" ]] || ooonana_die "missing branding/i3/config"
  mkdir -p "$OUT_DIR"

  # shellcheck disable=SC2086
  bash "$ROOT/scripts/import-apk-package.sh" "${REPO_ARGS[@]}" --out-dir "$OUT_DIR" $I3_PACKAGES

  work="$(mktemp -d)"
  trap 'rm -rf "$work"' EXIT
  branding_archive="$(build_branding_archive "$work")"
  branding_sha="$(sha256sum "$OUT_DIR/$branding_archive" | awk '{print $1}')"

  write_pkg \
    "$OUT_DIR/branding.pkg" \
    "branding" \
    "$BRANDING_VERSION" \
    "assets" \
    "Ooonana logo, wallpaper, and i3 config" \
    "" \
    "$branding_archive" \
    "$branding_sha" \
    "logo wallpaper i3-config" \
    "First-party Ooonana full-i3 branding files"

  write_pkg \
    "$OUT_DIR/i3.pkg" \
    "i3" \
    "$BRANDING_VERSION" \
    "bundle" \
    "Ooonana i3 desktop wrapper" \
    "$I3_PACKAGES" \
    "" \
    "" \
    "xorg i3 dmenu feh xterm" \
    "Wrapper package for imported Alpine i3 desktop payloads"

  write_pkg \
    "$OUT_DIR/full-i3.pkg" \
    "full-i3" \
    "$BRANDING_VERSION" \
    "profile" \
    "Ooonana full i3 desktop profile" \
    "base branding i3" \
    "" \
    "" \
    "edition full-i3" \
    "Full edition marker package; minimal edition remains separate"

  "$ROOT/packages/ooonana/usr/bin/ooonana" repo index "$OUT_DIR" >/dev/null
  ooonana_log "full-i3 package set ready: $OUT_DIR"
}

main "$@"
