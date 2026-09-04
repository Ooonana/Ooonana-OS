#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR=""
VERSION="0.1.1"
SOURCE_DIR="${OOONANA_BUNANACHAT_LINUX_SOURCE:-$ROOT/packages/bunanachat-linux/source/dist}"
PAYLOAD_DIR="$ROOT/packages/bunanachat-linux/rootfs"
DRY_RUN=0

usage() {
  cat <<'EOF'
Build the native BunanaChat Linux package for Ooonana.

Usage:
  scripts/build-bunanachat-linux-package.sh --out-dir PATH [options]

Options:
  --version VER      Package version (default: 0.1.1)
  --source-dir PATH  linux-musl-x64 publish directory
  --dry-run          Print resolved package details
  -h, --help         Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --source-dir) SOURCE_DIR="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'build-bunanachat-linux-package: unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done

[[ -n "$OUT_DIR" ]] || { printf 'build-bunanachat-linux-package: --out-dir required\n' >&2; exit 1; }
[[ "$VERSION" =~ ^[0-9][0-9A-Za-z._+-]*$ ]] || { printf 'build-bunanachat-linux-package: bad version\n' >&2; exit 1; }
for file in BunanaChat.Linux libSkiaSharp.so libHarfBuzzSharp.so; do
  [[ -f "$SOURCE_DIR/$file" ]] || { printf 'missing BunanaChat Linux publish file: %s\n' "$SOURCE_DIR/$file" >&2; exit 1; }
done
[[ -x "$PAYLOAD_DIR/usr/bin/bunanachat" ]] || { printf 'missing BunanaChat launcher payload\n' >&2; exit 1; }

archive_rel="archives/bunanachat-$VERSION.tar.gz"
archive="$OUT_DIR/$archive_rel"
metadata="$OUT_DIR/bunanachat.pkg"

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'id: bunanachat\nversion: %s\nsource: %s\narchive: %s\n' "$VERSION" "$SOURCE_DIR" "$archive"
  exit 0
fi

command -v tar >/dev/null 2>&1 || { printf 'missing command: tar\n' >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { printf 'missing command: sha256sum\n' >&2; exit 1; }

mkdir -p "$OUT_DIR/archives"
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
cp -a "$PAYLOAD_DIR/." "$staging/"
install -d "$staging/opt/bunanachat"
install -m 0755 "$SOURCE_DIR/BunanaChat.Linux" "$staging/opt/bunanachat/BunanaChat.Linux"
install -m 0755 "$SOURCE_DIR/libSkiaSharp.so" "$staging/opt/bunanachat/libSkiaSharp.so"
install -m 0755 "$SOURCE_DIR/libHarfBuzzSharp.so" "$staging/opt/bunanachat/libHarfBuzzSharp.so"
chmod 0755 "$staging/usr/bin/bunanachat"

tar \
  --sort=name \
  --mtime='UTC 1970-01-01' \
  --numeric-owner \
  --owner=0 \
  --group=0 \
  --pax-option=delete=atime,delete=ctime \
  -C "$staging" \
  -cf - \
  . | gzip -n > "$archive"

archive_sha="$(sha256sum "$archive" | awk '{print $1}')"
cat > "$metadata" <<EOF
OOONANA_PKG_ID="bunanachat"
OOONANA_PKG_VERSION="$VERSION"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Native nearby encrypted chat over Bluetooth LE"
OOONANA_PKG_DEPS="bluez dbus fontconfig freetype libx11 libice libsm mesa-gl icu-libs zlib libgcc libstdc++"
OOONANA_PKG_ARCHIVE="$archive_rel"
OOONANA_PKG_SHA256="$archive_sha"
OOONANA_PKG_COMPONENTS="chat bluetooth ble encrypted nearby avalonia"
OOONANA_PKG_NOTES="Native Linux client; Android has Wi-Fi Aware, Linux uses BLE until driver and NAN datapath support exist"
EOF

printf 'built %s\nbuilt %s\n' "$archive" "$metadata"
