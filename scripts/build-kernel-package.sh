#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

OUT_DIR="$ROOT/packages/ooonana/usr/lib/ooonana/repo"
KERNEL=""
VERSION="${OOONANA_KERNEL_VERSION:-6.18.37}"
PKG_ID="ooonana-kernel"
SUMMARY="Ooonana Linux kernel"
DRY_RUN=0

usage() {
  cat <<'USAGE'
Build an Ooonana kernel package.

Usage:
  scripts/build-kernel-package.sh --kernel PATH_OR_URL [options]

Options:
  --kernel PATH_OR_URL  Kernel image path or URL
  --out-dir PATH        Repo output directory
  --version VERSION     Package version
  --id NAME             Package id (default: ooonana-kernel)
  --summary TEXT        Package summary
  --dry-run             Print resolved package settings only
  -h, --help            Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --kernel) KERNEL="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --id) PKG_ID="$2"; shift 2 ;;
    --summary) SUMMARY="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

safe_pkg_id() {
  case "$1" in
    *[!A-Za-z0-9_.+-]*|"") return 1 ;;
    *) return 0 ;;
  esac
}

fetch_kernel() {
  local source="$1"
  local out="$2"
  case "$source" in
    http://*|https://*)
      if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 5 --retry-delay 3 --connect-timeout 30 "$source" -o "$out" && return 0
      fi
      if command -v wget >/dev/null 2>&1; then
        wget -q --tries=5 --timeout=60 -O "$out" "$source" && return 0
      fi
      if command -v python3 >/dev/null 2>&1; then
        python3 - "$source" "$out" <<'PY' && return 0
import sys
import urllib.request

url, out = sys.argv[1], sys.argv[2]
request = urllib.request.Request(url, headers={"User-Agent": "ooonana"})
with urllib.request.urlopen(request, timeout=120) as response:
    with open(out, "wb") as handle:
        handle.write(response.read())
PY
      fi
      ooonana_die "download failed: $source"
      ;;
    file://*) cp "${source#file://}" "$out" ;;
    *) cp "$source" "$out" ;;
  esac
}

shell_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

main() {
  ooonana_require_linux
  ooonana_require_commands chmod cp gzip mkdir rm sed sha256sum tar
  [[ -n "$KERNEL" ]] || ooonana_die "missing --kernel"
  safe_pkg_id "$PKG_ID" || ooonana_die "bad package id: $PKG_ID"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'out: %s\n' "$OUT_DIR"
    printf 'id: %s\n' "$PKG_ID"
    printf 'version: %s\n' "$VERSION"
    printf 'kernel: %s\n' "$KERNEL"
    return 0
  fi

  work="$(mktemp -d)"
  cleanup() {
    chmod -R u+rwX "$work" 2>/dev/null || true
    rm -rf "$work"
  }
  trap cleanup EXIT

  mkdir -p "$OUT_DIR/archives" "$work/root/boot"
  fetch_kernel "$KERNEL" "$work/root/boot/vmlinuz"
  cp "$work/root/boot/vmlinuz" "$work/root/boot/vmlinuz-ooonana"
  cat > "$work/root/boot/ooonana-kernel.env" <<EOF
OOONANA_KERNEL_PACKAGE="$PKG_ID"
OOONANA_KERNEL_VERSION="$VERSION"
OOONANA_KERNEL_PATH="/boot/vmlinuz"
EOF
  chmod 0644 "$work/root/boot/vmlinuz" "$work/root/boot/vmlinuz-ooonana" "$work/root/boot/ooonana-kernel.env"

  archive_rel="archives/$PKG_ID-$VERSION.tar.gz"
  archive_path="$OUT_DIR/$archive_rel"
  tar \
    --sort=name \
    --mtime='UTC 1970-01-01' \
    --numeric-owner \
    --owner=0 \
    --group=0 \
    --pax-option=delete=atime,delete=ctime \
    -C "$work/root" \
    -cf - \
    . | gzip -n > "$archive_path"
  chmod a+rw "$archive_path"
  archive_sha="$(sha256sum "$archive_path" | awk '{print $1}')"

  cat > "$OUT_DIR/$PKG_ID.pkg" <<EOF
OOONANA_PKG_ID="$(shell_escape "$PKG_ID")"
OOONANA_PKG_VERSION="$(shell_escape "$VERSION")"
OOONANA_PKG_KIND="kernel"
OOONANA_PKG_SUMMARY="$(shell_escape "$SUMMARY")"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="$(shell_escape "$archive_rel")"
OOONANA_PKG_SHA256="$(shell_escape "$archive_sha")"
OOONANA_PKG_COMPONENTS="kernel x86_64 boot"
OOONANA_PKG_NOTES="Installs /boot/vmlinuz for installed Ooonana systems"
EOF

  "$ROOT/packages/ooonana/usr/bin/ooonana" repo index "$OUT_DIR" >/dev/null
  ooonana_log "kernel package ready: $OUT_DIR/$PKG_ID.pkg"
}

main "$@"
