#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR=""
VERSION="1.0.0"
SOURCE_EXE="${OOONANA_OONANA_CHAT_WINDOWS_SOURCE:-$ROOT/packages/ooonana-chat-windows/source/OoonanaChat Setup 1.0.0.exe}"
PAYLOAD_DIR="$ROOT/packages/ooonana-chat-windows/rootfs"
DRY_RUN=0

usage() {
  cat <<'EOF'
Build the optional OoonanaChat Windows installer package.

Usage:
  scripts/build-ooonana-chat-windows-package.sh --out-dir PATH [options]

Options:
  --version VER  Package version (default: 1.0.0)
  --source PATH  OoonanaChat Windows .exe installer
  --dry-run      Print resolved package details
  -h, --help     Show help

The Windows installer is intentionally not committed to source control. Set
OOONANA_OONANA_CHAT_WINDOWS_SOURCE in CI when publishing this optional package.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --source) SOURCE_EXE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'build-ooonana-chat-windows-package: unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done

[[ -n "$OUT_DIR" ]] || { printf 'build-ooonana-chat-windows-package: --out-dir required\n' >&2; exit 1; }
[[ "$VERSION" =~ ^[0-9][0-9A-Za-z._+-]*$ ]] || { printf 'build-ooonana-chat-windows-package: bad version\n' >&2; exit 1; }
[[ -f "$SOURCE_EXE" ]] || { printf 'missing OoonanaChat Windows installer: %s\n' "$SOURCE_EXE" >&2; exit 1; }
[[ -x "$PAYLOAD_DIR/usr/bin/ooonana-chat-windows" ]] || { printf 'missing OoonanaChat Wine launcher\n' >&2; exit 1; }

archive_rel="archives/ooonana-chat-windows-$VERSION.tar.gz"
archive="$OUT_DIR/$archive_rel"
metadata="$OUT_DIR/ooonana-chat-windows.pkg"

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'id: ooonana-chat-windows\nversion: %s\nsource: %s\narchive: %s\n' "$VERSION" "$SOURCE_EXE" "$archive"
  exit 0
fi

command -v tar >/dev/null 2>&1 || { printf 'missing command: tar\n' >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { printf 'missing command: sha256sum\n' >&2; exit 1; }
[[ "$(dd if="$SOURCE_EXE" bs=2 count=1 2>/dev/null || true)" == "MZ" ]] || {
  printf 'OoonanaChat installer is not a Windows PE executable\n' >&2
  exit 1
}

mkdir -p "$OUT_DIR/archives"
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
cp -a "$PAYLOAD_DIR/." "$staging/"
install -D -m 0644 "$SOURCE_EXE" "$staging/opt/ooonana-wine/OoonanaChat Setup 1.0.0.exe"
chmod 0755 "$staging/usr/bin/ooonana-chat-windows"

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
OOONANA_PKG_ID="ooonana-chat-windows"
OOONANA_PKG_VERSION="$VERSION"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="OoonanaChat Windows installer through Wine compatibility"
OOONANA_PKG_DEPS="wine"
OOONANA_PKG_ARCHIVE="$archive_rel"
OOONANA_PKG_SHA256="$archive_sha"
OOONANA_PKG_COMPONENTS="chat windows exe wine"
OOONANA_PKG_NOTES="Windows compatibility package; not a native Linux port"
EOF

printf 'built %s\nbuilt %s\n' "$archive" "$metadata"
