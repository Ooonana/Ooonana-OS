#!/bin/sh
set -eu
ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
. "$ROOT/scripts/lib/live-persistence-file.sh"
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
reject() { if "$@"; then fail "accepted unsafe case: $*"; fi; }

[ "$(live_persistence_file_limit 10485760 vfat)" = 4095 ] || fail 'FAT maximum'
[ "$(live_persistence_file_limit 10485760 ext4)" = 9984 ] || fail 'ext4 maximum'
[ "$(live_persistence_file_limit 524288 ext4)" = 256 ] || fail 'outer reserve'
reject live_persistence_file_limit 524287 ext4
reject live_persistence_file_limit invalid ext4
reject live_persistence_file_limit 10485760 iso9660
live_persistence_size_valid 256 4095 || fail 'minimum size'
live_persistence_size_valid 4095 4095 || fail 'FAT limit accepted'
for value in '' 0 0123 255 4096 -1 '1;echo' 99999999999999999999; do
  reject live_persistence_size_valid "$value" 4095
done

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' 0
image="$tmp/ooonana-persistence.ext4"
live_persistence_file_safe "$image" || fail 'absent image'
mkdir "$image"
reject live_persistence_file_safe "$image"
rmdir "$image"
printf 'existing content\n' >"$tmp/saved"
ln -s "$tmp/saved" "$image"
reject live_persistence_file_safe "$image"
rm "$image"
truncate -s 256M "$image"
live_persistence_file_safe "$image" || fail 'regular image'
ln "$image" "$tmp/hardlink"
reject live_persistence_file_safe "$image"
rm "$tmp/hardlink"
truncate -s 255M "$image"
reject live_persistence_file_safe "$image"
[ "$(cat "$tmp/saved")" = 'existing content' ] || fail 'unrelated content changed'

# Test default/explicit sizes, exact confirmation and cancellation without disks.
boot_media_device=/dev/fixtureUSB
exec 3>"$tmp/prompt"
live_persistence_read() {
  if [ "${read_count:-0}" = 0 ]; then
    LIVE_SETUP_REPLY="${size_reply:-}"
  else
    LIVE_SETUP_REPLY="${confirm_reply:-CREATE}"
  fi
  read_count=$((${read_count:-0} + 1))
}
read_count=0
live_persistence_file_prompt 900 || fail 'default prompt'
[ "$live_size_mib" = 900 ] || fail 'default uses available space'
read_count=0
size_reply=512
live_persistence_file_prompt 4095 || fail 'explicit prompt'
[ "$live_size_mib" = 512 ] || fail 'explicit size'
for size_reply in cancel 4096 0123; do
  read_count=0
  reject live_persistence_file_prompt 4095
done
size_reply=512
for confirm_reply in '' yes create CANCEL; do
  read_count=0
  # Empty reply must stay empty, not get test default.
  live_persistence_read() {
    if [ "$read_count" = 0 ]; then LIVE_SETUP_REPLY="$size_reply"; else LIVE_SETUP_REPLY="$confirm_reply"; fi
    read_count=$((read_count + 1))
  }
  reject live_persistence_file_prompt 4095
done
live_persistence_read() { return 1; }
reject live_persistence_file_prompt 4095
exec 3>&-
grep -q 'No existing files erased' "$tmp/prompt" || fail 'safety text'
grep -q 'Type CREATE' "$tmp/prompt" || fail 'confirmation text'

# Failure rollback touches only known initramfs mount paths/owned loop1.
abort_log="$tmp/abort.log"
sync() { printf 'sync\n' >>"$abort_log"; }
live_file_mounted() { case "$1" in /newroot|/persist) return 0 ;; *) return 1 ;; esac; }
readlink() { [ "$1" = -f ] && printf '%s\n' "$2"; }
umount() { printf 'unmount:%s\n' "$1" >>"$abort_log"; }
mount() { printf 'mount:%s\n' "$*" >>"$abort_log"; }
losetup() {
  if [ "$1" = -d ]; then
    printf 'detach:%s\n' "$2" >>"$abort_log"
    return 0
  fi
  return "${loop_still_attached:-1}"
}
live_persistence_file_abort || fail 'empty rollback'
[ ! -e "$abort_log" ] || fail 'rollback without owned writable storage'
live_file_outer_writable=1
live_file_loop_attached=1
live_persistence_file_abort >"$tmp/abort.out" || fail 'failure rollback'
[ "$live_file_outer_writable" = 0 ] && [ "$live_file_loop_attached" = 0 ] || fail 'rollback state'
expected='sync
unmount:/newroot
unmount:/persist
detach:/dev/loop1
mount:-o remount,ro /mnt/iso
sync'
[ "$(cat "$abort_log")" = "$expected" ] || fail 'rollback ordering/target'
grep -q '^OOONANA_BOOT_STORAGE_READ_ONLY$' "$tmp/abort.out" || fail 'outer read-only marker'
live_file_outer_writable=1
live_file_loop_attached=1
loop_still_attached=0
reject live_persistence_file_abort >"$tmp/abort-reject.out"
loop_still_attached=1
live_file_outer_writable=1
live_file_loop_attached=1
live_file_mounted() { case "$1" in /newroot/proc|/newroot/sys|/newroot/dev|/newroot/mnt/ooonana-live/iso|/newroot|/persist) return 0 ;; *) return 1 ;; esac; }
: >"$abort_log"
live_persistence_file_abort >"$tmp/moved-abort.out" || fail 'moved mount rollback'
grep -qx 'mount:--move /newroot/proc /proc' "$abort_log" || fail 'restore proc mount'
grep -qx 'mount:--move /newroot/sys /sys' "$abort_log" || fail 'restore sys mount'
grep -qx 'mount:--move /newroot/dev /dev' "$abort_log" || fail 'restore dev mount'
grep -qx 'mount:--move /newroot/mnt/ooonana-live/iso /mnt/iso' "$abort_log" || fail 'restore boot mount'

# Shutdown must explicitly remount the outer filesystem before unmount aliases.
grep -q 'mount -o remount,ro /iso' "$ROOT/scripts/lib/live-shutdown.sh" || fail 'outer shutdown cleanup'

# Guard immutable boot/helper integration and no raw-device formatting/partitioning.
grep -q 'mv -nT' "$ROOT/scripts/lib/live-persistence-file.sh" || fail 'no-clobber publication'
grep -q 'live_storage_identity_safe' "$ROOT/scripts/lib/live-persistence-file.sh" || fail 'identity recheck'
grep -q 'live_persistence_file_attach' "$ROOT/scripts/build-full-i3-live-initramfs.sh" || fail 'boot integration'
if grep -Eq 'mklabel|mkpart|sfdisk|parted|mke2fs.*\$boot_media_device' "$ROOT/scripts/lib/live-persistence-file.sh"; then
  fail 'automatic device formatting/partitioning'
fi
printf 'ok live-persistence-file\n'
