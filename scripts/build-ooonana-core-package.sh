#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR=""
VERSION="0.8.2"
DRY_RUN=0

usage() {
  cat <<'USAGE'
Build the native Ooonana system update package.

Usage:
  scripts/build-ooonana-core-package.sh --out-dir PATH [options]

Options:
  --version VER  Package version (default: 0.8.2)
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

archive_rel="archives/ooonana-core-$VERSION.tar.gz"
archive="$OUT_DIR/$archive_rel"
metadata="$OUT_DIR/ooonana-core.pkg"

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'id: ooonana-core\nversion: %s\noverlay: %s\narchive: %s\n' \
    "$VERSION" "$ROOT/packages/ooonana" "$archive"
  exit 0
fi

command -v tar >/dev/null 2>&1 || { printf 'missing command: tar\n' >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { printf 'missing command: sha256sum\n' >&2; exit 1; }
[[ -x "$ROOT/packages/ooonana/usr/bin/ooonana" ]] || { printf 'missing Ooonana overlay\n' >&2; exit 1; }

mkdir -p "$OUT_DIR/archives"
tar -C "$ROOT/packages/ooonana" -czf "$archive" .
archive_sha="$(sha256sum "$archive" | awk '{print $1}')"
cat > "$metadata" <<EOF
OOONANA_PKG_ID="ooonana-core"
OOONANA_PKG_VERSION="$VERSION"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Ooonana OS CLI, desktop apps, services, game, and defaults"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="$archive_rel"
OOONANA_PKG_SHA256="$archive_sha"
OOONANA_PKG_NOTES="Native Ooonana system overlay; archives download only during install or upgrade"
EOF

printf 'built %s\n' "$metadata"
