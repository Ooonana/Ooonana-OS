#!/bin/sh
set -eu
ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
. "$ROOT/scripts/lib/verification-media.sh"
ram_media_memory_ok 1073741824 2048 5242880 5242880
if ram_media_memory_ok 1073741824 2048 5242879 5242880; then exit 1; fi
if ram_media_memory_ok 1073741824 2048 5242880 5242879; then exit 1; fi
if ram_media_memory_ok invalid 2048 9999999 9999999; then exit 1; fi
if ram_media_memory_ok 1073741824 02048 9999999 9999999; then exit 1; fi
if ram_media_memory_ok 1073741824 512 9999999 9999999; then exit 1; fi
ram_media_memory_ok 1073741824 2048 5242880 0
disk_media_space_ok 1073741824 3145728 3145728
if disk_media_space_ok 1073741824 3145727 3145728; then exit 1; fi
if disk_media_space_ok 1073741824 3145728 3145727; then exit 1; fi
if disk_media_space_ok invalid 9999999 9999999; then exit 1; fi
disk_media_space_ok 1073741824 3145728 0
ram_media_memory_ok 1 1536 3670017 3670017
if ram_media_memory_ok 1 1536 3670016 3670017; then exit 1; fi
fixture="$(mktemp -d)"
trap 'rm -rf -- "$fixture"' EXIT
printf '%s\n' 'Ooonana full i3 rootfs' >"$fixture/boot.log"
verification_guest_log_ok "$fixture/boot.log"
for fault in 'I/O error, dev sr0' 'Buffer I/O error' 'EXT4-fs error' \
  'Remounting filesystem read-only' 'Kernel panic' 'Out of memory: Killed process'; do
  printf '%s\n' 'Ooonana full i3 rootfs' "$fault" >"$fixture/boot.log"
  if verification_guest_log_ok "$fixture/boot.log"; then exit 1; fi
done
if verification_guest_log_ok "$fixture/missing.log"; then exit 1; fi
grep() { return 2; }
if verification_guest_log_ok "$fixture/boot.log"; then exit 1; fi
unset -f grep
source_text="$(cat "$ROOT/scripts/lib/verification-media.sh")"
case "$source_text" in *noswap,mode=0700* ) ;; *) exit 1 ;; esac
# Exercise copied-file cleanup, with unknown files/symlinks/mounts retained.
DISK_MEDIA_ROOT="$fixture"
DISK_MEDIA_SOURCE="$(findmnt -n -o SOURCE --target "$fixture")"
DISK_MEDIA_DIR="$(mktemp -d "$fixture/ooonana-verify-disk.XXXXXXXX")"
DISK_MEDIA_ISO="$DISK_MEDIA_DIR/verification.iso"
printf 'copied ISO\n' >"$DISK_MEDIA_ISO"
cleanup_disk_media
[ -z "$DISK_MEDIA_DIR" ]
DISK_MEDIA_DIR="$(mktemp -d "$fixture/ooonana-verify-disk.XXXXXXXX")"
DISK_MEDIA_ROOT="$fixture"
DISK_MEDIA_SOURCE="$(findmnt -n -o SOURCE --target "$fixture")"
DISK_MEDIA_ISO="$DISK_MEDIA_DIR/verification.iso"
printf 'copied ISO\n' >"$DISK_MEDIA_ISO"
printf 'retain\n' >"$DISK_MEDIA_DIR/unknown"
if cleanup_disk_media 2>/dev/null; then exit 1; fi
[ -f "$DISK_MEDIA_DIR/unknown" ]
ln -s "$fixture/boot.log" "$DISK_MEDIA_ISO"
if cleanup_disk_media 2>/dev/null; then exit 1; fi
[ -f "$fixture/boot.log" ]
findmnt() { printf '%s\n' foreign; }
if cleanup_disk_media 2>/dev/null; then exit 1; fi
unset -f findmnt
mountpoint() { return 0; }
if cleanup_disk_media 2>/dev/null; then exit 1; fi
unset -f mountpoint
RAM_MEDIA_DIR=/fixture
mountpoint() { return 0; }
findmnt() { printf '%s\n' foreign; }
umount() { echo 'foreign mount must not be detached' >&2; exit 99; }
if cleanup_ram_media 2>/dev/null; then exit 1; fi
echo 'ok verification-media: host/guest RAM guard, noswap, mount ownership'
