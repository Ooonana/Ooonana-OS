#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
ROOTFS="$WORK_DIR/scratch-rootfs"
TARBALL="$WORK_DIR/ooonana-rootfs.tar.gz"
FORCE=0

usage() {
  cat <<'USAGE'
Build Ooonana generic rootfs tarball.

Usage:
  scripts/build-rootfs-tarball.sh [options]

Options:
  --work-dir PATH  Build directory (default: /var/tmp/ooonana-os/build)
  --rootfs PATH    Scratch rootfs path (default: WORK_DIR/scratch-rootfs)
  --tarball PATH   Output tarball (default: WORK_DIR/ooonana-rootfs.tar.gz)
  --force          Replace existing tarball
  -h, --help       Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; ROOTFS="$2/scratch-rootfs"; TARBALL="$2/ooonana-rootfs.tar.gz"; shift 2 ;;
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --tarball) TARBALL="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

require_rootfs_file() {
  local path="$1"
  [[ -e "$ROOTFS/$path" ]] || ooonana_die "invalid rootfs: missing /$path"
}

main() {
  ooonana_require_linux
  ooonana_require_commands chmod dirname gzip mkdir rm tar
  [[ -d "$ROOTFS" ]] || ooonana_die "missing rootfs: $ROOTFS"
  [[ -x "$ROOTFS/bin/sh" ]] || ooonana_die "invalid rootfs: missing executable /bin/sh"
  [[ -x "$ROOTFS/usr/bin/ooonana" ]] || ooonana_die "invalid rootfs: missing executable /usr/bin/ooonana"
  require_rootfs_file "etc/os-release"
  require_rootfs_file "etc/passwd"
  require_rootfs_file "etc/group"
  require_rootfs_file "etc/motd"
  require_rootfs_file "etc/issue"
  require_rootfs_file "usr/share/ooonana/logo.txt"
  require_rootfs_file "usr/lib/ooonana/repo/base.pkg"
  require_rootfs_file "var/lib/ooonana/packages/installed/base.pkg"

  if [[ -e "$TARBALL" && "$FORCE" -ne 1 ]]; then
    ooonana_die "tarball exists: $TARBALL (use --force)"
  fi

  mkdir -p "$(dirname "$TARBALL")"
  rm -f "$TARBALL"
  tar \
    --sort=name \
    --mtime='UTC 1970-01-01' \
    --numeric-owner \
    --owner=0 \
    --group=0 \
    --pax-option=delete=atime,delete=ctime \
    --exclude='./dev/*' \
    --exclude='./proc/*' \
    --exclude='./sys/*' \
    --exclude='./run/*' \
    --exclude='./tmp/*' \
    --exclude='./mnt/*' \
    --exclude='./media/*' \
    --exclude='./lost+found' \
    -C "$ROOTFS" \
    -cf - \
    . | gzip -n > "$TARBALL"
  chmod a+rw "$TARBALL"
  ooonana_log "generic rootfs tarball ready: $TARBALL"
}

main "$@"
