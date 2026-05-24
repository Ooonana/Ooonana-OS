#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
ROOTFS="$WORK_DIR/scratch-rootfs"
INITRAMFS="$WORK_DIR/ooonana-scratch-initramfs.cpio.gz"
FORCE=0
TMP_INITRAMFS=""

usage() {
  cat <<'USAGE'
Build Ooonana scratch initramfs.

Usage:
  scripts/build-scratch-initramfs.sh [options]

Options:
  --work-dir PATH     Build directory (default: /var/tmp/ooonana-os/build)
  --rootfs PATH       Scratch rootfs path (default: WORK_DIR/scratch-rootfs)
  --initramfs PATH    Initramfs output path (default: WORK_DIR/ooonana-scratch-initramfs.cpio.gz)
  --force             Replace existing initramfs
  -h, --help          Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; ROOTFS="$2/scratch-rootfs"; INITRAMFS="$2/ooonana-scratch-initramfs.cpio.gz"; shift 2 ;;
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --initramfs) INITRAMFS="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

main() {
  ooonana_require_linux
  ooonana_require_commands cpio find gzip sort

  [[ -d "$ROOTFS" ]] || ooonana_die "missing scratch rootfs: $ROOTFS"
  [[ -x "$ROOTFS/init" ]] || ooonana_die "invalid scratch rootfs: missing executable /init"
  [[ -x "$ROOTFS/bin/busybox" ]] || ooonana_die "invalid scratch rootfs: missing executable /bin/busybox"

  if [[ -e "$INITRAMFS" && "$FORCE" -ne 1 ]]; then
    ooonana_die "initramfs exists: $INITRAMFS (use --force)"
  fi

  mkdir -p "$(dirname "$INITRAMFS")"
  TMP_INITRAMFS="${INITRAMFS}.tmp.$$"
  trap '[[ -z "${TMP_INITRAMFS:-}" ]] || rm -f "$TMP_INITRAMFS"' EXIT

  (
    cd "$ROOTFS"
    find . -xdev -print0 |
      LC_ALL=C sort -z |
      cpio --null -o -H newc 2>/dev/null |
      gzip -9
  ) > "$TMP_INITRAMFS"

  mv "$TMP_INITRAMFS" "$INITRAMFS"
  TMP_INITRAMFS=""
  chmod a+r "$INITRAMFS"

  ooonana_log "scratch initramfs ready: $INITRAMFS"
}

main "$@"
