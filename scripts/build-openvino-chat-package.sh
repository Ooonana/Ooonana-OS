#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR=""
VERSION="0.1.0"
SOURCE_DIR="${OOONANA_OPENVINO_CHAT_SOURCE:-$ROOT/packages/openvino-chat/source}"
PAYLOAD_DIR="$ROOT/packages/openvino-chat/rootfs"
DRY_RUN=0

usage() {
  cat <<'EOF'
Build Ooonana OpenVINO Chat package.

Usage:
  scripts/build-openvino-chat-package.sh --out-dir PATH [options]

Options:
  --version VER      Package version (default: 0.1.0)
  --source-dir PATH  OpenVINO Chat source snapshot
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
    *) printf 'build-openvino-chat-package: unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done

[[ -n "$OUT_DIR" ]] || { printf 'build-openvino-chat-package: --out-dir required\n' >&2; exit 1; }
[[ "$VERSION" =~ ^[0-9][0-9A-Za-z._+-]*$ ]] || { printf 'build-openvino-chat-package: bad version\n' >&2; exit 1; }
[[ -f "$SOURCE_DIR/pyproject.toml" ]] || { printf 'missing OpenVINO Chat pyproject.toml\n' >&2; exit 1; }
[[ -d "$SOURCE_DIR/src/openvino_chat" ]] || { printf 'missing OpenVINO Chat source package\n' >&2; exit 1; }
[[ -x "$PAYLOAD_DIR/usr/bin/openvino" ]] || { printf 'missing OpenVINO launcher payload\n' >&2; exit 1; }

archive_rel="archives/openvino-chat-$VERSION.tar.gz"
archive="$OUT_DIR/$archive_rel"
metadata="$OUT_DIR/openvino-chat.pkg"

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'id: openvino-chat\nversion: %s\nsource: %s\narchive: %s\n' "$VERSION" "$SOURCE_DIR" "$archive"
  exit 0
fi

command -v tar >/dev/null 2>&1 || { printf 'missing command: tar\n' >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { printf 'missing command: sha256sum\n' >&2; exit 1; }

mkdir -p "$OUT_DIR/archives"
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
cp -a "$PAYLOAD_DIR/." "$staging/"
install -d "$staging/usr/lib/ooonana/openvino-chat"
cp -a "$SOURCE_DIR/pyproject.toml" "$staging/usr/lib/ooonana/openvino-chat/"
cp -a "$SOURCE_DIR/README.md" "$staging/usr/lib/ooonana/openvino-chat/"
cp -a "$SOURCE_DIR/src" "$staging/usr/lib/ooonana/openvino-chat/"
chmod 0755 \
  "$staging/usr/bin/openvino" \
  "$staging/usr/bin/ooonana-openvino" \
  "$staging/usr/bin/ooonana-openvino-setup"

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
OOONANA_PKG_ID="openvino-chat"
OOONANA_PKG_VERSION="$VERSION"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Offline Ooonana AI for Intel GPU and NPU using OpenVINO GenAI"
OOONANA_PKG_DEPS="bubblewrap xz curl ca-certificates coreutils"
OOONANA_PKG_ARCHIVE="$archive_rel"
OOONANA_PKG_SHA256="$archive_sha"
OOONANA_PKG_COMPONENTS="offline-ai openvino intel gpu npu local-api chat"
OOONANA_PKG_NOTES="Run openvino setup, download a model once, then inference works offline"
EOF

printf 'built %s\nbuilt %s\n' "$archive" "$metadata"
