#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    *) printf 'build-firefox-package: unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done
[[ -n "$OUT_DIR" ]] || { printf 'Required: --out-dir PATH\n' >&2; exit 2; }
mkdir -p "$OUT_DIR/archives"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
cp -a "$ROOT/packages/firefox/rootfs/." "$stage/"
chmod 0755 "$stage/usr/bin/ooonana-firefox" "$stage/usr/bin/firefox"
archive="archives/firefox-1.0.0.tar.gz"
tar --sort=name --mtime='UTC 1970-01-01' --numeric-owner --owner=0 --group=0 \
  --pax-option=delete=atime,delete=ctime -C "$stage" -cf - . | gzip -n > "$OUT_DIR/$archive"
checksum="$(sha256sum "$OUT_DIR/$archive" | awk '{print $1}')"
cat > "$OUT_DIR/firefox.pkg" <<EOF
OOONANA_PKG_ID="firefox"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Firefox launcher with isolated current-user Flatpak runtime"
OOONANA_PKG_DEPS="flatpak"
OOONANA_PKG_ARCHIVE="$archive"
OOONANA_PKG_SHA256="$checksum"
OOONANA_PKG_COMPONENTS="browser firefox flatpak"
OOONANA_PKG_NOTES="Launcher only; run ooonana-firefox setup as desktop user to download browser/runtime"
EOF
printf 'built %s/firefox.pkg\n' "$OUT_DIR"
