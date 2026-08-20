#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR=""
VERSION="1.0.0"
PAYLOAD_DIR="$ROOT/packages/wine-compat/rootfs"
DRY_RUN=0

usage() {
  cat <<'EOF'
Build the Ooonana Wine compatibility package.

Usage:
  scripts/build-wine-compat-package.sh --out-dir PATH [options]

Options:
  --version VER  Package version (default: 1.0.0)
  --dry-run      Print resolved package details
  -h, --help     Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'build-wine-compat-package: unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done

[[ -n "$OUT_DIR" ]] || { printf 'build-wine-compat-package: --out-dir required\n' >&2; exit 1; }
[[ "$VERSION" =~ ^[0-9][0-9A-Za-z._+-]*$ ]] || { printf 'build-wine-compat-package: bad version\n' >&2; exit 1; }
[[ -x "$PAYLOAD_DIR/usr/bin/ooonana-wine" ]] || { printf 'missing Ooonana Wine launcher\n' >&2; exit 1; }
[[ -x "$PAYLOAD_DIR/usr/bin/wine" ]] || { printf 'missing Wine compatibility command\n' >&2; exit 1; }

archive_rel="archives/wine-$VERSION.tar.gz"
archive="$OUT_DIR/$archive_rel"
metadata="$OUT_DIR/wine.pkg"

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'id: wine\nversion: %s\npayload: %s\narchive: %s\n' "$VERSION" "$PAYLOAD_DIR" "$archive"
  exit 0
fi

command -v tar >/dev/null 2>&1 || { printf 'missing command: tar\n' >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { printf 'missing command: sha256sum\n' >&2; exit 1; }
mkdir -p "$OUT_DIR/archives"
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
cp -a "$PAYLOAD_DIR/." "$staging/"
chmod 0755 "$staging/usr/bin/ooonana-wine" "$staging/usr/bin/wine"

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
OOONANA_PKG_ID="wine"
OOONANA_PKG_VERSION="$VERSION"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Windows application compatibility through Flathub Wine"
OOONANA_PKG_DEPS="flatpak"
OOONANA_PKG_ARCHIVE="$archive_rel"
OOONANA_PKG_SHA256="$archive_sha"
OOONANA_PKG_COMPONENTS="windows exe wine flatpak compatibility"
OOONANA_PKG_NOTES="Run ooonana wine setup once to install the Wine runtime for the current user"
EOF

printf 'built %s\nbuilt %s\n' "$archive" "$metadata"
