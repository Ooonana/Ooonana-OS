#!/bin/sh
# Trusted initramfs copy, invoked only by guarded BusyBox shutdown action.
set -eu
PATH=/mnt/ooonana-shutdown/bin
export PATH
[ "${1:-}" = --from-init ] && [ "${PPID:-0}" = 1 ] || exit 1
# Never let PID1 proceed to poweroff after incomplete cleanup.
shutdown_failed() {
  [ "$1" = 0 ] && return 0
  echo OOONANA_SHUTDOWN_CLEANUP_FAILED >&2 || true
  # PID1 waits for this action, not its rescue child. Never exec/return here:
  # closing a rescue shell must not release init into low-level poweroff.
  while :; do
    echo "Shutdown held: storage cleanup failed. Exiting shell keeps shutdown held." >&2 || true
    if [ -x /mnt/ooonana-shutdown/lib/ld-musl-x86_64.so.1 ]; then
      /mnt/ooonana-shutdown/lib/ld-musl-x86_64.so.1 /mnt/ooonana-shutdown/bin/busybox sh || true
    elif [ -x /mnt/ooonana-shutdown/bin/busybox ]; then
      /mnt/ooonana-shutdown/bin/busybox sh || true
    else
      /bin/sh || true
    fi
    echo OOONANA_SHUTDOWN_HELD >&2 || true
    sleep 1 || true
  done
}
trap 'shutdown_failed "$?"' 0
[ "$(cat /mnt/ooonana-live/persistence-file)" = /mnt/ooonana-live/iso/ooonana-persistence.ext4 ] || exit 1
awk '$2 == "/mnt/ooonana-shutdown" && $3 == "tmpfs" { found=1 } END { exit !found }' /proc/mounts || exit 1
echo OOONANA_SHUTDOWN_RAM_START
kill -TERM -1 2>/dev/null || true
sleep 2
kill -KILL -1 2>/dev/null || true
sync
if [ -x /mnt/ooonana-shutdown/lib/ld-musl-x86_64.so.1 ]; then
  /mnt/ooonana-shutdown/lib/ld-musl-x86_64.so.1 /mnt/ooonana-shutdown/bin/busybox swapoff -a 2>/dev/null || true
else
  /mnt/ooonana-shutdown/bin/busybox swapoff -a 2>/dev/null || true
fi
mount --make-rprivate /
cd /mnt/ooonana-shutdown
pivot_root . oldroot
cd /
PATH=/bin
export PATH
for directory in dev proc sys; do
  mount --move "/oldroot/$directory" "/$directory"
done
for directory in iso persist root-ro; do
  mount --move "/oldroot/mnt/ooonana-live/$directory" "/$directory"
done
# Release deepest child mounts first, without lazy/forced unmounts. Saved
# temporary-overlay bind and normal desktop mounts must not pin old root.
awk '$2 ~ /^\/oldroot\// { print length($2), $2 }' /proc/mounts |
  sort -rn | while read -r _length escaped_target; do
    target="$(printf '%b' "$escaped_target")"
    umount "$target" || exit 1
  done
umount /oldroot
mount -o remount,ro /persist
echo OOONANA_PERSISTENCE_READ_ONLY
umount /persist
losetup -d /dev/loop1
if losetup /dev/loop1 >/dev/null 2>&1; then
  echo OOONANA_SHUTDOWN_LOOP_FAILED >&2
  exit 1
fi
umount /root-ro
losetup -d /dev/loop0
mount -o remount,ro /iso
echo OOONANA_BOOT_STORAGE_READ_ONLY
umount /iso
sync
echo OOONANA_SHUTDOWN_CLEANUP_DONE
