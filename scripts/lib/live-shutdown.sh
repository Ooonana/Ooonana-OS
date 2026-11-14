#!/bin/sh
# Trusted initramfs copy, invoked only by guarded BusyBox shutdown action.
set -eu
PATH=/mnt/ooonana-shutdown/bin
export PATH
[ "${1:-}" = --from-init ] && [ "${PPID:-0}" = 1 ] || exit 1
# Never let PID1 proceed to poweroff after incomplete cleanup.
shutdown_failed() {
  [ "$1" = 0 ] && return 0
  if command -v ooonana_console_end >/dev/null 2>&1; then
    ooonana_console_end || true
  fi
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
stage() {
  if command -v ooonana_console_stage >/dev/null 2>&1; then
    ooonana_console_stage "$1"
  fi
  echo "OOONANA_SHUTDOWN_STAGE: $1"
}
mode="$(cat /mnt/ooonana-live/persistence-mode)"
storage_file="$(cat /mnt/ooonana-live/persistence-file)"
case "$mode:$storage_file" in
  ram:|usb:|usb-temporary:|usb:/mnt/ooonana-live/iso/ooonana-persistence.ext4|usb-temporary:/mnt/ooonana-live/iso/ooonana-persistence.ext4) ;;
  *) exit 1 ;;
esac
awk '$2 == "/mnt/ooonana-shutdown" && $3 == "tmpfs" { found=1 } END { exit !found }' /proc/mounts || exit 1
echo OOONANA_SHUTDOWN_RAM_START
kill -TERM -1 2>/dev/null || true
if [ -r /mnt/ooonana-shutdown/console-ui.sh ]; then
  . /mnt/ooonana-shutdown/console-ui.sh
  timeout -k 1 2 chvt 1 2>/dev/null || true
  ooonana_console_begin /mnt/ooonana-shutdown/boot-logo.txt
  stage "Closing session"
  ooonana_console_wait 2
else
  sleep 2
fi
kill -KILL -1 2>/dev/null || true
# RAM-only zram can be discarded on poweroff. Swapping it back into RAM here
# can exhaust memory. Explicit disk/file swaps must still be deactivated.
disk_swaps="$(awk 'NR > 1 && $1 !~ /^\/dev\/zram[0-9]+$/ { print $1 }' /proc/swaps)"
for swap in $disk_swaps; do
  swapoff "$(printf '%b' "$swap")"
done
stage "Closing USB files"
mount --make-rprivate /
cd /mnt/ooonana-shutdown
pivot_root . oldroot
cd /
PATH=/bin
export PATH
for directory in dev proc sys; do
  mount --move "/oldroot/$directory" "/$directory"
done
for directory in iso root-ro; do
  mount --move "/oldroot/mnt/ooonana-live/$directory" "/$directory"
done
if [ "$mode" != ram ]; then
  mount --move /oldroot/mnt/ooonana-live/persist /persist
fi
# Release deepest child mounts first, without lazy/forced unmounts. Saved
# temporary-overlay bind and normal desktop mounts must not pin old root.
awk '$2 ~ /^\/oldroot\// { print length($2), $2 }' /proc/mounts |
  sort -rn | while read -r _length escaped_target; do
    target="$(printf '%b' "$escaped_target")"
    umount "$target" || exit 1
  done
umount /oldroot
if [ "$mode" != ram ]; then
  stage "Saving persistent changes"
  sync -f /persist
  mount -o remount,ro /persist
  echo OOONANA_PERSISTENCE_READ_ONLY
  umount /persist
fi
if [ -n "$storage_file" ]; then
  losetup -d /dev/loop1
  if losetup /dev/loop1 >/dev/null 2>&1; then
    echo OOONANA_SHUTDOWN_LOOP_FAILED >&2
    exit 1
  fi
fi
umount /root-ro
losetup -d /dev/loop0
if [ -n "$storage_file" ]; then
  stage "Flushing USB storage"
  sync -f /iso
  mount -o remount,ro /iso
else
  awk '$2 == "/iso" && $4 ~ /^ro(,|$)/ { found=1 } END { exit !found }' /proc/mounts
fi
echo OOONANA_BOOT_STORAGE_READ_ONLY
stage "Ejecting boot storage"
umount /iso
if command -v ooonana_console_end >/dev/null 2>&1; then
  ooonana_console_end
fi
echo OOONANA_SHUTDOWN_CLEANUP_DONE
