#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
EDITION="minimal"
ROOTFS=""
TARBALL=""
ROOTFS_SET=0
TARBALL_SET=0
FORCE=0

edition_rootfs() {
  case "$EDITION" in
    minimal) printf '%s/scratch-rootfs\n' "$WORK_DIR" ;;
    full-i3) printf '%s/full-i3-rootfs\n' "$WORK_DIR" ;;
    *) ooonana_die "unknown WSL edition: $EDITION" ;;
  esac
}

edition_tarball() {
  case "$EDITION" in
    minimal) printf '%s/ooonana-wsl-rootfs.tar.gz\n' "$WORK_DIR" ;;
    full-i3) printf '%s/ooonana-full-i3-wsl-rootfs.tar.gz\n' "$WORK_DIR" ;;
    *) ooonana_die "unknown WSL edition: $EDITION" ;;
  esac
}

refresh_defaults() {
  if [[ "$ROOTFS_SET" -eq 0 ]]; then
    ROOTFS="$(edition_rootfs)"
  fi
  if [[ "$TARBALL_SET" -eq 0 ]]; then
    TARBALL="$(edition_tarball)"
  fi
}

validate_edition() {
  case "$EDITION" in
    minimal|full-i3) ;;
    *) ooonana_die "--edition must be minimal or full-i3" ;;
  esac
}

refresh_defaults

usage() {
  cat <<USAGE
Build Ooonana WSL rootfs tarball.

Usage:
  scripts/build-wsl-rootfs.sh [options]

Options:
  --work-dir PATH  Build directory (default: /var/tmp/ooonana-os/build)
  --edition minimal|full-i3
                   WSL edition to export (default: minimal)
  --rootfs PATH    Rootfs path (default: $ROOTFS)
  --tarball PATH   Output tarball (default: $TARBALL)
  --force          Replace existing tarball
  -h, --help       Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; refresh_defaults; shift 2 ;;
    --edition) EDITION="$2"; validate_edition; refresh_defaults; shift 2 ;;
    --rootfs) ROOTFS="$2"; ROOTFS_SET=1; shift 2 ;;
    --tarball) TARBALL="$2"; TARBALL_SET=1; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

main() {
  ooonana_require_linux
  ooonana_require_commands mkdir tar gzip
  validate_edition
  [[ -d "$ROOTFS" ]] || ooonana_die "missing rootfs: $ROOTFS"
  [[ -x "$ROOTFS/bin/sh" ]] || ooonana_die "invalid rootfs: missing /bin/sh"
  [[ -f "$ROOTFS/etc/wsl.conf" ]] || ooonana_die "invalid rootfs: missing /etc/wsl.conf"
  [[ -f "$ROOTFS/etc/passwd" ]] || ooonana_die "invalid rootfs: missing /etc/passwd"
  if [[ "$EDITION" == "full-i3" ]]; then
    [[ -f "$ROOTFS/etc/ooonana/edition" ]] || ooonana_die "invalid full-i3 rootfs: missing /etc/ooonana/edition"
    grep -qx 'full-i3' "$ROOTFS/etc/ooonana/edition" || ooonana_die "rootfs is not full-i3: $ROOTFS"
    [[ -x "$ROOTFS/usr/bin/start-ooonana-i3" ]] || ooonana_die "invalid full-i3 rootfs: missing /usr/bin/start-ooonana-i3"
    [[ -x "$ROOTFS/usr/bin/ooonana-gui-installer" ]] || ooonana_die "invalid full-i3 rootfs: missing /usr/bin/ooonana-gui-installer"
    [[ -x "$ROOTFS/usr/bin/ooonana-install-wizard" ]] || ooonana_die "invalid full-i3 rootfs: missing /usr/bin/ooonana-install-wizard"
  fi

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
