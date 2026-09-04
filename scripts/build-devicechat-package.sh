#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR=""
VERSION="0.1.1"
SOURCE_ARCHIVE="${OOONANA_DEVICECHAT_SOURCE:-$ROOT/packages/devicechat/source/devicechat-0.1.1.tgz}"
NPM_BIN="${OOONANA_DEVICECHAT_NPM:-npm}"
DRY_RUN=0

usage() {
  cat <<'EOF'
Build the native DeviceChat Node.js package for Ooonana.

Usage:
  scripts/build-devicechat-package.sh --out-dir PATH [options]

Options:
  --version VER      Package version (default: 0.1.1)
  --source PATH      DeviceChat npm tarball
  --npm PATH         npm command used to install production dependencies
  --dry-run          Print resolved package details
  -h, --help         Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --source) SOURCE_ARCHIVE="$2"; shift 2 ;;
    --npm) NPM_BIN="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'build-devicechat-package: unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done

[[ -n "$OUT_DIR" ]] || { printf 'build-devicechat-package: --out-dir required\n' >&2; exit 1; }
[[ "$VERSION" =~ ^[0-9][0-9A-Za-z._+-]*$ ]] || { printf 'build-devicechat-package: bad version\n' >&2; exit 1; }
[[ -f "$SOURCE_ARCHIVE" ]] || { printf 'missing DeviceChat source archive: %s\n' "$SOURCE_ARCHIVE" >&2; exit 1; }

archive_rel="archives/devicechat-$VERSION.tar.gz"
archive="$OUT_DIR/$archive_rel"
metadata="$OUT_DIR/devicechat.pkg"

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'id: devicechat\nversion: %s\nsource: %s\nnpm: %s\narchive: %s\n' \
    "$VERSION" "$SOURCE_ARCHIVE" "$NPM_BIN" "$archive"
  exit 0
fi

command -v tar >/dev/null 2>&1 || { printf 'missing command: tar\n' >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { printf 'missing command: sha256sum\n' >&2; exit 1; }
command -v "$NPM_BIN" >/dev/null 2>&1 || { printf 'missing command: %s\n' "$NPM_BIN" >&2; exit 1; }
source_listing="$(tar -tzf "$SOURCE_ARCHIVE")"
grep -qx 'package/package.json' <<<"$source_listing" || {
  printf 'DeviceChat archive missing package/package.json\n' >&2
  exit 1
}
grep -qx 'package/dist/index.js' <<<"$source_listing" || {
  printf 'DeviceChat archive missing package/dist/index.js\n' >&2
  exit 1
}
grep -qx 'package/dist/relay.js' <<<"$source_listing" || {
  printf 'DeviceChat archive missing package/dist/relay.js\n' >&2
  exit 1
}

mkdir -p "$OUT_DIR/archives"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
tar -xzf "$SOURCE_ARCHIVE" -C "$work"
source_dir="$work/package"
staging="$work/staging"
mkdir -p "$staging/opt/devicechat" "$staging/usr/bin"
cp -a "$source_dir/package.json" "$staging/opt/devicechat/"
cp -a "$source_dir/dist" "$staging/opt/devicechat/"

"$NPM_BIN" --prefix "$staging/opt/devicechat" install \
  --omit=dev --ignore-scripts --no-audit --no-fund --package-lock=false
rm -f "$staging/opt/devicechat/package-lock.json"

cat > "$staging/usr/bin/devicechat" <<'EOF'
#!/bin/sh
exec /usr/bin/node /opt/devicechat/dist/index.js "$@"
EOF
cat > "$staging/usr/bin/devicechat-relay" <<'EOF'
#!/bin/sh
exec /usr/bin/node /opt/devicechat/dist/relay.js "$@"
EOF
chmod 0755 "$staging/usr/bin/devicechat" "$staging/usr/bin/devicechat-relay"

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
OOONANA_PKG_ID="devicechat"
OOONANA_PKG_VERSION="$VERSION"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Encrypted terminal chat with local or remote relay"
OOONANA_PKG_DEPS="nodejs"
OOONANA_PKG_ARCHIVE="$archive_rel"
OOONANA_PKG_SHA256="$archive_sha"
OOONANA_PKG_COMPONENTS="chat nodejs relay encrypted"
OOONANA_PKG_NOTES="Native Node.js package; no Wine required"
EOF

printf 'built %s\nbuilt %s\n' "$archive" "$metadata"
