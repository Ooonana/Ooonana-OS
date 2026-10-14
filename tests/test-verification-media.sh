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
RAM_MEDIA_DIR=/fixture
mountpoint() { return 0; }
findmnt() { printf '%s\n' foreign; }
umount() { echo 'foreign mount must not be detached' >&2; exit 99; }
if cleanup_ram_media 2>/dev/null; then exit 1; fi
echo 'ok verification-media: host/guest RAM guard, noswap, mount ownership'
