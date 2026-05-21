#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
ROOTFS="$WORK_DIR/rootfs"
ISO_TREE="$WORK_DIR/iso-tree"
ISO="$WORK_DIR/ooonana.iso"
VOLUME="OOONANA_OS"
SMOKE=0
FORCE=0

usage() {
  cat <<'USAGE'
Build Ooonana boot ISO.

Usage:
  scripts/build-iso.sh [options]

Options:
  --work-dir PATH     Build directory (default: /var/tmp/ooonana-os/build)
  --rootfs PATH       Rootfs directory (default: WORK_DIR/rootfs)
  --iso-tree PATH     ISO staging directory (default: WORK_DIR/iso-tree)
  --iso PATH          ISO output path (default: WORK_DIR/ooonana.iso)
  --volume NAME       ISO volume label (default: OOONANA_OS)
  --smoke             Boot straight to smoke marker service
  --force             Delete existing ISO staging tree and ISO first
  -h, --help          Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; ROOTFS="$2/rootfs"; ISO_TREE="$2/iso-tree"; ISO="$2/ooonana.iso"; shift 2 ;;
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --iso-tree) ISO_TREE="$2"; shift 2 ;;
    --iso) ISO="$2"; shift 2 ;;
    --volume) VOLUME="$2"; shift 2 ;;
    --smoke) SMOKE=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

pick_latest() {
  local pattern="$1"
  local latest
  latest="$(find "$ROOTFS/boot" -maxdepth 1 -type f -name "$pattern" | sort -V | tail -n 1)"
  [[ -n "$latest" ]] || ooonana_die "missing boot file: $pattern in $ROOTFS/boot"
  printf '%s\n' "$latest"
}

first_existing() {
  local path
  for path in "$@"; do
    if [[ -f "$path" ]]; then
      printf '%s\n' "$path"
      return 0
    fi
  done
  return 1
}

write_isolinux_config() {
  local append="root=/dev/sr0 rootfstype=iso9660 ro console=ttyS0 panic=1"
  if [[ "$SMOKE" -eq 1 ]]; then
    append="$append systemd.unit=ooonana-smoke.service"
  else
    append="$append systemd.unit=multi-user.target"
  fi

  cat > "$ISO_TREE/isolinux/isolinux.cfg" <<EOF
SERIAL 0 115200
CONSOLE 0
DEFAULT ooonana
PROMPT 0
TIMEOUT 10

LABEL ooonana
  KERNEL /boot/vmlinuz
  INITRD /boot/initrd.img
  APPEND $append
EOF
}

stage_iso_tree() {
  local kernel initrd isolinux_bin ldlinux_c32

  kernel="$(pick_latest 'vmlinuz-*')"
  initrd="$(pick_latest 'initrd.img-*')"
  isolinux_bin="$(first_existing /usr/lib/ISOLINUX/isolinux.bin /usr/lib/syslinux/isolinux.bin)" ||
    ooonana_die "missing isolinux.bin"
  ldlinux_c32="$(first_existing /usr/lib/syslinux/modules/bios/ldlinux.c32 /usr/lib/syslinux/ldlinux.c32)" ||
    ooonana_die "missing ldlinux.c32"

  rm -rf "$ISO_TREE"
  mkdir -p "$ISO_TREE" "$ISO_TREE/isolinux" "$ISO_TREE/boot"

  rsync -aH --numeric-ids \
    --exclude '/boot/initrd.img*' \
    --exclude '/boot/vmlinuz*' \
    --exclude '/tmp/*' \
    --exclude '/var/cache/apt/archives/*' \
    --exclude '/var/lib/apt/lists/*' \
    "$ROOTFS"/ "$ISO_TREE"/

  install -m 0644 "$kernel" "$ISO_TREE/boot/vmlinuz"
  install -m 0644 "$initrd" "$ISO_TREE/boot/initrd.img"
  install -m 0644 "$isolinux_bin" "$ISO_TREE/isolinux/isolinux.bin"
  install -m 0644 "$ldlinux_c32" "$ISO_TREE/isolinux/ldlinux.c32"

  write_isolinux_config
}

build_iso() {
  mkdir -p "$(dirname "$ISO")"
  rm -f "$ISO"
  xorriso -as mkisofs \
    -r -J -l \
    -V "$VOLUME" \
    -o "$ISO" \
    -b isolinux/isolinux.bin \
    -c isolinux/boot.cat \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    "$ISO_TREE"
}

main() {
  ooonana_require_linux
  ooonana_reexec_as_root "$@"
  ooonana_require_commands find sort tail rsync install xorriso

  [[ -d "$ROOTFS" ]] || ooonana_die "missing rootfs: $ROOTFS"
  [[ -x "$ROOTFS/bin/sh" ]] || ooonana_die "invalid rootfs: $ROOTFS"

  if [[ "$FORCE" -eq 1 ]]; then
    rm -rf "$ISO_TREE" "$ISO"
  fi

  stage_iso_tree
  build_iso
  chmod a+rx "$(dirname "$WORK_DIR")" "$WORK_DIR"
  chmod a+rw "$ISO"

  ooonana_log "iso ready: $ISO"
}

main "$@"
