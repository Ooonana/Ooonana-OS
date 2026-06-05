#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
ROOTFS="$WORK_DIR/full-i3-rootfs"
KERNEL="$WORK_DIR/ooonana-kernel/vmlinuz-ooonana"
DISK_IMAGE="$WORK_DIR/ooonana-full-i3-disk.raw"
SIZE="768M"
MOUNT_POINT="$WORK_DIR/full-i3-disk-mnt"
SMOKE=0
GUI_SMOKE=0
FORCE=0
DRY_RUN=0
LOOP_DEV=""
ORIGINAL_ARGS=("$@")

usage() {
  cat <<'USAGE'
Build Ooonana full-i3 boot disk.

Usage:
  scripts/build-full-i3-disk.sh [options]

Options:
  --work-dir PATH     Build directory (default: /var/tmp/ooonana-os/build)
  --rootfs PATH       Full-i3 rootfs path (default: WORK_DIR/full-i3-rootfs)
  --kernel PATH       Kernel path (default: WORK_DIR/ooonana-kernel/vmlinuz-ooonana)
  --disk-image PATH   Raw boot disk output (default: WORK_DIR/ooonana-full-i3-disk.raw)
  --size SIZE         Raw disk size (default: 768M)
  --mount-point PATH  Temporary mount point (default: WORK_DIR/full-i3-disk-mnt)
  --smoke             Add smoke boot kernel argument
  --gui-smoke         Add GUI smoke kernel argument
  --force             Replace existing disk image
  --dry-run           Print commands only
  -h, --help          Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; ROOTFS="$2/full-i3-rootfs"; KERNEL="$2/ooonana-kernel/vmlinuz-ooonana"; DISK_IMAGE="$2/ooonana-full-i3-disk.raw"; MOUNT_POINT="$2/full-i3-disk-mnt"; shift 2 ;;
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --disk-image) DISK_IMAGE="$2"; shift 2 ;;
    --size) SIZE="$2"; shift 2 ;;
    --mount-point) MOUNT_POINT="$2"; shift 2 ;;
    --smoke) SMOKE=1; shift ;;
    --gui-smoke) GUI_SMOKE=1; shift ;;
    --force) FORCE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    ooonana_print_command "$@"
  else
    "$@"
  fi
}

partition_path() {
  printf '%sp1\n' "$1"
}

wait_for_block() {
  local path="$1"
  local i
  for i in $(seq 1 50); do
    [[ -b "$path" ]] && return 0
    sleep 0.1
  done
  return 1
}

kernel_append() {
  local root_spec="${1:-PARTUUID=TARGET_PARTUUID}"
  local append="root=$root_spec rw console=tty0 console=ttyS0 panic=1 init=/sbin/init ooonana.edition=full-i3"
  if [[ "$SMOKE" -eq 1 ]]; then
    append="$append ooonana.smoke=1"
  fi
  if [[ "$GUI_SMOKE" -eq 1 ]]; then
    append="$append ooonana.gui-smoke=1"
  fi
  printf '%s\n' "$append"
}

write_grub_config() {
  local target="$1"
  local root_spec="$2"
  local append
  append="$(kernel_append "$root_spec")"
  mkdir -p "$target/boot/grub"
  cat > "$target/boot/grub/grub.cfg" <<EOF
serial --unit=0 --speed=115200
terminal_input serial
terminal_output serial
set timeout=1
set default=0

menuentry 'Ooonana OS Full i3' {
  linux /boot/vmlinuz $append
}
EOF
}

write_disk_metadata() {
  mkdir -p "$MOUNT_POINT/var/lib/ooonana" "$MOUNT_POINT/etc/ooonana"
  printf 'full-i3-disk\n' > "$MOUNT_POINT/var/lib/ooonana/disk-ok"
  printf 'full-i3\n' > "$MOUNT_POINT/etc/ooonana/edition"
  cat > "$MOUNT_POINT/etc/fstab" <<'EOF'
LABEL=OOONANA_ROOT / ext4 defaults 0 1
proc /proc proc defaults 0 0
EOF
}

cleanup() {
  if [[ "$DRY_RUN" -eq 0 ]]; then
    if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
      umount "$MOUNT_POINT"
    fi
    if [[ -n "$LOOP_DEV" ]]; then
      losetup -d "$LOOP_DEV" 2>/dev/null || true
    fi
  fi
}
trap cleanup EXIT

main() {
  ooonana_require_linux
  [[ -d "$ROOTFS" ]] || ooonana_die "missing full-i3 rootfs: $ROOTFS"
  [[ -f "$ROOTFS/etc/ooonana/edition" ]] || ooonana_die "missing full-i3 edition marker: $ROOTFS"
  grep -qx 'full-i3' "$ROOTFS/etc/ooonana/edition" || ooonana_die "rootfs is not full-i3: $ROOTFS"
  [[ -f "$KERNEL" ]] || ooonana_die "missing kernel: $KERNEL"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    run_cmd truncate -s "$SIZE" "$DISK_IMAGE"
    run_cmd parted -s "$DISK_IMAGE" mklabel msdos mkpart primary ext4 1MiB 100% set 1 boot on
    run_cmd losetup --find --show --partscan "$DISK_IMAGE"
    run_cmd mkfs.ext4 -F -L OOONANA_ROOT LOOP_PARTITION
    run_cmd mount LOOP_PARTITION "$MOUNT_POINT"
    run_cmd cp -a "$ROOTFS/." "$MOUNT_POINT/"
    run_cmd install -m 0644 "$KERNEL" "$MOUNT_POINT/boot/vmlinuz"
    printf 'grub.cfg: linux /boot/vmlinuz %s\n' "$(kernel_append "PARTUUID=TARGET_PARTUUID")"
    run_cmd grub-install --target=i386-pc --boot-directory="$MOUNT_POINT/boot" --modules="part_msdos ext2" --no-floppy LOOP_DEVICE
    printf 'OOONANA_FULL_I3_DISK_OK\n'
    return 0
  fi

  ooonana_reexec_as_root "${ORIGINAL_ARGS[@]}"
  ooonana_require_commands truncate parted losetup mkfs.ext4 mount umount grub-install cp grep install sync blkid

  if [[ -e "$DISK_IMAGE" && "$FORCE" -ne 1 ]]; then
    ooonana_die "disk image exists: $DISK_IMAGE (use --force)"
  fi
  case "$MOUNT_POINT" in
    ""|"/") ooonana_die "unsafe mount point: $MOUNT_POINT" ;;
  esac

  rm -rf "$MOUNT_POINT"
  mkdir -p "$(dirname "$DISK_IMAGE")" "$MOUNT_POINT"
  rm -f "$DISK_IMAGE"

  truncate -s "$SIZE" "$DISK_IMAGE"
  parted -s "$DISK_IMAGE" mklabel msdos mkpart primary ext4 1MiB 100% set 1 boot on

  LOOP_DEV="$(losetup --find --show --partscan "$DISK_IMAGE")"
  partprobe "$LOOP_DEV" 2>/dev/null || true
  part="$(partition_path "$LOOP_DEV")"
  wait_for_block "$part" || ooonana_die "missing loop partition: $part"

  mkfs.ext4 -F -L OOONANA_ROOT "$part"
  partuuid="$(blkid -s PARTUUID -o value "$part" 2>/dev/null || true)"
  [[ -n "$partuuid" ]] || ooonana_die "missing PARTUUID for $part"
  mount "$part" "$MOUNT_POINT"
  cp -a "$ROOTFS/." "$MOUNT_POINT/"
  mkdir -p "$MOUNT_POINT/boot"
  install -m 0644 "$KERNEL" "$MOUNT_POINT/boot/vmlinuz"
  write_disk_metadata
  write_grub_config "$MOUNT_POINT" "PARTUUID=$partuuid"
  grub-install --target=i386-pc --boot-directory="$MOUNT_POINT/boot" --modules="part_msdos ext2" --no-floppy "$LOOP_DEV"
  sync
  umount "$MOUNT_POINT"
  losetup -d "$LOOP_DEV"
  LOOP_DEV=""
  chmod a+rw "$DISK_IMAGE"

  ooonana_log "full-i3 boot disk ready: $DISK_IMAGE"
  printf 'OOONANA_FULL_I3_DISK_OK\n'
}

main "$@"
