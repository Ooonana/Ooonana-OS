#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
ROOTFS="$WORK_DIR/scratch-rootfs"
TARBALL="$WORK_DIR/ooonana-wsl-rootfs.tar.gz"
FORCE=0

usage() {
  cat <<'USAGE'
Build Ooonana WSL rootfs tarball.

Usage:
  scripts/build-wsl-rootfs.sh [options]

Options:
  --work-dir PATH  Build directory (default: /var/tmp/ooonana-os/build)
  --rootfs PATH    Scratch rootfs path (default: WORK_DIR/scratch-rootfs)
  --tarball PATH   Output tarball (default: WORK_DIR/ooonana-wsl-rootfs.tar.gz)
  --force          Replace existing tarball
  -h, --help       Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; ROOTFS="$2/scratch-rootfs"; TARBALL="$2/ooonana-wsl-rootfs.tar.gz"; shift 2 ;;
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --tarball) TARBALL="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

main() {
  ooonana_require_linux
  ooonana_require_commands mkdir tar gzip
  [[ -d "$ROOTFS" ]] || ooonana_die "missing rootfs: $ROOTFS"
  [[ -x "$ROOTFS/bin/sh" ]] || ooonana_die "invalid rootfs: missing /bin/sh"
  [[ -f "$ROOTFS/etc/wsl.conf" ]] || ooonana_die "invalid rootfs: missing /etc/wsl.conf"
  [[ -f "$ROOTFS/etc/passwd" ]] || ooonana_die "invalid rootfs: missing /etc/passwd"

  if [[ -e "$TARBALL" && "$FORCE" -ne 1 ]]; then
    ooonana_die "tarball exists: $TARBALL (use --force)"
  fi

  mkdir -p "$(dirname "$TARBALL")"
  rm -f "$TARBALL"
  tar \
    --sort=name \
    --numeric-owner \
    --owner=0 \
    --group=0 \
    --exclude='./dev/*' \
    -C "$ROOTFS" \
    -czf "$TARBALL" \
    .
  chmod a+rw "$TARBALL"
  ooonana_log "WSL rootfs tarball ready: $TARBALL"
}

main "$@"
