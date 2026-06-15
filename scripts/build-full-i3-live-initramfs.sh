#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
ROOTFS="$WORK_DIR/full-i3-rootfs"
KERNEL="$WORK_DIR/ooonana-kernel/vmlinuz-ooonana"
INITRAMFS="$WORK_DIR/ooonana-full-i3-live-initramfs.cpio.gz"
ROOTFS_IMAGE="$WORK_DIR/ooonana-full-i3-live-rootfs.ext4"
FORCE=0
LIVE_INIT_TREE=""

cleanup() {
  if [[ -n "${LIVE_INIT_TREE:-}" ]]; then
    rm -rf "$LIVE_INIT_TREE"
  fi
}
trap cleanup EXIT

usage() {
  cat <<'USAGE'
Build Ooonana full-i3 live initramfs.

Usage:
  scripts/build-full-i3-live-initramfs.sh [options]

Options:
  --work-dir PATH    Build directory (default: /var/tmp/ooonana-os/build)
  --rootfs PATH      Full-i3 rootfs path (default: WORK_DIR/full-i3-rootfs)
  --rootfs-image PATH
                     Output ext4 live rootfs image
  --kernel PATH      Kernel path to stage as /boot/vmlinuz
  --initramfs PATH   Output live initramfs
  --force            Replace existing initramfs
  -h, --help         Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; ROOTFS="$2/full-i3-rootfs"; KERNEL="$2/ooonana-kernel/vmlinuz-ooonana"; INITRAMFS="$2/ooonana-full-i3-live-initramfs.cpio.gz"; ROOTFS_IMAGE="$2/ooonana-full-i3-live-rootfs.ext4"; shift 2 ;;
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --rootfs-image) ROOTFS_IMAGE="$2"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --initramfs) INITRAMFS="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

main() {
  ooonana_require_linux
  ooonana_require_commands cpio du find gzip install ln mkdir mke2fs rm truncate
  [[ -d "$ROOTFS" ]] || ooonana_die "missing full-i3 rootfs: $ROOTFS"
  [[ -f "$ROOTFS/etc/ooonana/edition" ]] || ooonana_die "missing full-i3 edition marker: $ROOTFS"
  grep -qx 'full-i3' "$ROOTFS/etc/ooonana/edition" || ooonana_die "rootfs is not full-i3: $ROOTFS"
  [[ -x "$ROOTFS/usr/bin/start-ooonana-i3" ]] || ooonana_die "missing start-ooonana-i3: $ROOTFS"
  [[ -x "$ROOTFS/bin/busybox" ]] || ooonana_die "missing busybox for live initramfs: $ROOTFS/bin/busybox"
  [[ -f "$KERNEL" ]] || ooonana_die "missing kernel: $KERNEL"

  if [[ -e "$INITRAMFS" && "$FORCE" -ne 1 ]]; then
    ooonana_die "initramfs exists: $INITRAMFS (use --force)"
  fi
  if [[ -e "$ROOTFS_IMAGE" && "$FORCE" -ne 1 ]]; then
    ooonana_die "live rootfs image exists: $ROOTFS_IMAGE (use --force)"
  fi

  mkdir -p "$(dirname "$INITRAMFS")" "$(dirname "$ROOTFS_IMAGE")" "$ROOTFS/boot" "$ROOTFS/dev" "$ROOTFS/proc" "$ROOTFS/sys" "$ROOTFS/run" "$ROOTFS/tmp"
  install -m 0644 "$KERNEL" "$ROOTFS/boot/vmlinuz"
  rm -rf "$ROOTFS/dev/"* "$ROOTFS/proc/"* "$ROOTFS/sys/"* "$ROOTFS/run/"* "$ROOTFS/tmp/"* 2>/dev/null || true
  rm -f "$INITRAMFS" "$ROOTFS_IMAGE"

  local used_kb image_kb
  read -r used_kb _ < <(du -sk "$ROOTFS")
  image_kb=$((used_kb + used_kb / 3 + 262144))
  truncate -s "${image_kb}K" "$ROOTFS_IMAGE"
  mke2fs -q -t ext4 -L OOONANA_LIVE -d "$ROOTFS" "$ROOTFS_IMAGE"

  LIVE_INIT_TREE="$(mktemp -d)"
  mkdir -p "$LIVE_INIT_TREE/bin" "$LIVE_INIT_TREE/sbin" "$LIVE_INIT_TREE/lib" "$LIVE_INIT_TREE/dev" "$LIVE_INIT_TREE/proc" "$LIVE_INIT_TREE/sys" "$LIVE_INIT_TREE/mnt/iso" "$LIVE_INIT_TREE/mnt/root-ro" "$LIVE_INIT_TREE/cow" "$LIVE_INIT_TREE/newroot"
  install -m 0755 "$ROOTFS/bin/busybox" "$LIVE_INIT_TREE/bin/busybox"
  if [[ -f "$ROOTFS/lib/ld-musl-x86_64.so.1" ]]; then
    install -m 0755 "$ROOTFS/lib/ld-musl-x86_64.so.1" "$LIVE_INIT_TREE/lib/ld-musl-x86_64.so.1"
  fi
  if [[ -e "$ROOTFS/lib/libc.musl-x86_64.so.1" ]]; then
    install -m 0755 "$ROOTFS/lib/libc.musl-x86_64.so.1" "$LIVE_INIT_TREE/lib/libc.musl-x86_64.so.1"
  fi
  for applet in sh mount mkdir mknod sleep cat echo switch_root ls grep umount losetup mdev modprobe; do
    ln -sf busybox "$LIVE_INIT_TREE/bin/$applet"
  done
  ln -sf ../bin/busybox "$LIVE_INIT_TREE/sbin/mdev"
  ln -sf ../bin/busybox "$LIVE_INIT_TREE/sbin/modprobe"
  ln -sf ../bin/busybox "$LIVE_INIT_TREE/sbin/switch_root"
  cat > "$LIVE_INIT_TREE/init" <<'EOF'
#!/bin/sh
set -eu

PATH=/bin:/sbin
LIVE_IMAGE="/images/ooonana-full-i3-live-rootfs.ext4"

for arg in $(cat /proc/cmdline 2>/dev/null || true); do
  case "$arg" in
    ooonana.live.rootfs=*) LIVE_IMAGE="${arg#ooonana.live.rootfs=}" ;;
  esac
done

fail() {
  echo "Ooonana live init failed: $*" >/dev/console
  exec sh
}

mount -t proc proc /proc 2>/dev/null || true
mount -t sysfs sysfs /sys 2>/dev/null || true
mount -t devtmpfs devtmpfs /dev 2>/dev/null || {
  mkdir -p /dev
  [ -c /dev/console ] || mknod /dev/console c 5 1
  [ -c /dev/null ] || mknod /dev/null c 1 3
}
mkdir -p /dev/pts /mnt/iso /mnt/root-ro /cow/upper /cow/work /newroot
mount -t devpts devpts /dev/pts 2>/dev/null || true
echo /sbin/mdev >/proc/sys/kernel/hotplug 2>/dev/null || true
mdev -s 2>/dev/null || true
modprobe loop 2>/dev/null || true
modprobe iso9660 2>/dev/null || true
modprobe overlay 2>/dev/null || true

[ -b /dev/loop0 ] || mknod /dev/loop0 b 7 0 2>/dev/null || true
[ -c /dev/loop-control ] || mknod /dev/loop-control c 10 237 2>/dev/null || true

tries=0
while [ "$tries" -lt 40 ]; do
  mdev -s 2>/dev/null || true
  for dev in /dev/sr0 /dev/sr1 /dev/cdrom /dev/hdc /dev/sd? /dev/sd?? /dev/vd? /dev/vd?? /dev/xvd? /dev/xvd?? /dev/nvme?n? /dev/nvme?n?p?; do
    [ -b "$dev" ] || continue
    if mount -t iso9660 -o ro "$dev" /mnt/iso 2>/dev/null || mount -o ro "$dev" /mnt/iso 2>/dev/null; then
      if [ -f "/mnt/iso$LIVE_IMAGE" ]; then
        break 2
      fi
      umount /mnt/iso 2>/dev/null || true
    fi
  done
  tries=$((tries + 1))
  sleep 1
done

[ -f "/mnt/iso$LIVE_IMAGE" ] || fail "cannot find $LIVE_IMAGE on boot media"
losetup /dev/loop0 "/mnt/iso$LIVE_IMAGE" || fail "cannot attach live rootfs image"
mount -t ext4 -o ro /dev/loop0 /mnt/root-ro || fail "cannot mount live rootfs image"
mount -t tmpfs -o mode=0755 tmpfs /cow || fail "cannot mount writable tmpfs overlay"
mkdir -p /cow/upper /cow/work /newroot
mount -t overlay overlay -o lowerdir=/mnt/root-ro,upperdir=/cow/upper,workdir=/cow/work /newroot || fail "cannot mount overlay root"

mkdir -p /newroot/proc /newroot/sys /newroot/dev /newroot/run/ooonana-live/iso /newroot/run/ooonana-live/root-ro /newroot/run/ooonana-live/cow
mount --bind /mnt/iso /newroot/run/ooonana-live/iso 2>/dev/null || true
mount --bind /mnt/root-ro /newroot/run/ooonana-live/root-ro 2>/dev/null || true
mount --bind /cow /newroot/run/ooonana-live/cow 2>/dev/null || true
mount --move /proc /newroot/proc 2>/dev/null || true
mount --move /sys /newroot/sys 2>/dev/null || true
mount --move /dev /newroot/dev 2>/dev/null || true

exec switch_root /newroot /sbin/init
fail "switch_root failed"
EOF
  chmod 0755 "$LIVE_INIT_TREE/init"

  (
    cd "$LIVE_INIT_TREE"
    find . -print0 | cpio --null -ov --format=newc 2>/dev/null | gzip -n > "$INITRAMFS"
  )
  chmod a+rw "$INITRAMFS"
  chmod a+rw "$ROOTFS_IMAGE"
  ooonana_log "full-i3 live initramfs ready: $INITRAMFS"
  ooonana_log "full-i3 live rootfs image ready: $ROOTFS_IMAGE"
}

main "$@"
