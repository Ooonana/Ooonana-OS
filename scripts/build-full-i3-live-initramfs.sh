#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
ROOTFS="$WORK_DIR/full-i3-rootfs"
KERNEL="$WORK_DIR/ooonana-kernel/vmlinuz-ooonana"
INITRAMFS="$WORK_DIR/ooonana-full-i3-live-initramfs.cpio.gz"
FORCE=0

usage() {
  cat <<'USAGE'
Build Ooonana full-i3 live initramfs.

Usage:
  scripts/build-full-i3-live-initramfs.sh [options]

Options:
  --work-dir PATH    Build directory (default: /var/tmp/ooonana-os/build)
  --rootfs PATH      Full-i3 rootfs path (default: WORK_DIR/full-i3-rootfs)
  --kernel PATH      Kernel path to stage as /boot/vmlinuz
  --initramfs PATH   Output live initramfs
  --force            Replace existing initramfs
  -h, --help         Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; ROOTFS="$2/full-i3-rootfs"; KERNEL="$2/ooonana-kernel/vmlinuz-ooonana"; INITRAMFS="$2/ooonana-full-i3-live-initramfs.cpio.gz"; shift 2 ;;
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --initramfs) INITRAMFS="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

main() {
  ooonana_require_linux
  ooonana_require_commands cpio find gzip install mkdir rm
  [[ -d "$ROOTFS" ]] || ooonana_die "missing full-i3 rootfs: $ROOTFS"
  [[ -f "$ROOTFS/etc/ooonana/edition" ]] || ooonana_die "missing full-i3 edition marker: $ROOTFS"
  grep -qx 'full-i3' "$ROOTFS/etc/ooonana/edition" || ooonana_die "rootfs is not full-i3: $ROOTFS"
  [[ -x "$ROOTFS/usr/bin/start-ooonana-i3" ]] || ooonana_die "missing start-ooonana-i3: $ROOTFS"
  [[ -f "$KERNEL" ]] || ooonana_die "missing kernel: $KERNEL"

  if [[ -e "$INITRAMFS" && "$FORCE" -ne 1 ]]; then
    ooonana_die "initramfs exists: $INITRAMFS (use --force)"
  fi

  mkdir -p "$(dirname "$INITRAMFS")" "$ROOTFS/boot" "$ROOTFS/dev" "$ROOTFS/proc" "$ROOTFS/sys" "$ROOTFS/run" "$ROOTFS/tmp"
  install -m 0644 "$KERNEL" "$ROOTFS/boot/vmlinuz"
  rm -rf "$ROOTFS/dev/"* "$ROOTFS/proc/"* "$ROOTFS/sys/"* "$ROOTFS/run/"* "$ROOTFS/tmp/"* 2>/dev/null || true
  rm -f "$INITRAMFS"

  (
    cd "$ROOTFS"
    find . -print0 | cpio --null -ov --format=newc 2>/dev/null | gzip -n > "$INITRAMFS"
  )
  chmod a+rw "$INITRAMFS"
  ooonana_log "full-i3 live initramfs ready: $INITRAMFS"
}

main "$@"
