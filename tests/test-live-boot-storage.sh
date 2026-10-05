#!/bin/sh
set -eu

ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
. "$ROOT/scripts/lib/live-boot-storage.sh"
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
reject() { if "$@"; then fail "accepted unsafe case: $*"; fi; }
mkdir() {
  if [ "${RCS_FIXTURE:-0}" = 1 ]; then return 0; fi
  command mkdir "$@"
}

live_cmdline_has_arg ooonana.persistence=1 'console=ttyS0 ooonana.persistence=1 quiet' || fail 'exact persistence flag'
reject live_cmdline_has_arg ooonana.persistence=1 'ooonana.persistence=10'
reject live_cmdline_has_arg ooonana.persistence=1 'other=ooonana.persistence=1'
[ "$(live_cmdline_value ooonana.live.boot_uuid 'ooonana.live.boot_uuid=ABCD-1234')" = ABCD-1234 ] || fail 'boot UUID argument'
reject live_cmdline_value key 'key=one key=two'
reject live_normalize_uuid '../sda'
[ "$(live_normalize_uuid ABCD-1234)" = abcd-1234 ] || fail 'UUID normalization'

parent_disk_name() {
  case "$1" in /dev/sdb*) echo sdb ;; /dev/sdc*) echo sdc ;; /dev/sda*) echo sda ;; *) return 1 ;; esac
}
boot_media_candidate() { case "$1" in /dev/sdb*|/dev/sdc*) return 0 ;; *) return 1 ;; esac; }
readlink() {
  case "$2" in /dev/*) printf '%s\n' "$2" ;; *) command readlink "$@" ;; esac
}
blkid_value() {
  case "$1:$2" in
    UUID:/dev/sdb|UUID:/dev/sdb1|UUID:/dev/sdc1|UUID:/dev/sda1) echo ABCD-1234 ;;
    LABEL:/dev/sdb2|LABEL:/dev/sdb3|LABEL:/dev/sdc2|LABEL:/dev/sda2) echo OOONANA_PERSIST ;;
    TYPE:/dev/sdb2|TYPE:/dev/sdc2|TYPE:/dev/sda2) echo ext4 ;;
    TYPE:/dev/sdb3) echo "${SECOND_FS:-vfat}" ;;
    *) return 1 ;;
  esac
}
[ "$(live_boot_parent_for_uuid abcd-1234 /dev/sda1 /dev/sdb /dev/sdb1)" = sdb ] || fail 'same-parent aliases/internal-disk exclusion'
reject live_boot_parent_for_uuid abcd-1234 /dev/sdb1 /dev/sdc1
[ -z "$(live_boot_parent_for_uuid unknown /dev/sdb1)" ] || fail 'unknown UUID'
[ "$(live_persistence_device /dev/sdb1 /dev/sda2 /dev/sdc2 /dev/sdb2 /dev/sdb3)" = /dev/sdb2 ] || fail 'wrong USB/internal/wrong filesystem exclusion'
SECOND_FS=ext4
export SECOND_FS
reject live_persistence_device /dev/sdb1 /dev/sdb2 /dev/sdb3
reject live_persistence_device /dev/sda1 /dev/sda2
[ -z "$(live_persistence_device /dev/sdb1 /dev/sda2 /dev/sdc2)" ] || fail 'missing same-USB partition'
[ "$(live_persistence_device /dev/sdb1 /dev/sdb2 /dev/sdb2)" = /dev/sdb2 ] || fail 'device alias deduplication'

tmp="$(command mktemp -d)"
trap 'rm -rf "$tmp"' 0
command mkdir -p "$tmp/persist" "$tmp/unrelated"
printf 'preserve\n' >"$tmp/unrelated/important"
live_overlay_paths_safe "$tmp/persist" overlay || fail 'new saved overlay'
command mkdir -p "$tmp/persist/overlay/upper" "$tmp/persist/overlay/work"
live_saved_base_matches "$tmp/persist" ABCD-1234 || fail 'new base identity'
live_saved_base_matches "$tmp/persist" abcd-1234 || fail 'same base identity'
reject live_saved_base_matches "$tmp/persist" different-base
rm "$tmp/persist/overlay/base-id"
printf 'saved\n' >"$tmp/persist/overlay/upper/user-file"
reject live_saved_base_matches "$tmp/persist" abcd-1234
printf 'abcd-1234\n' >"$tmp/persist/overlay/base-id"
live_saved_base_matches "$tmp/persist" abcd-1234 || fail 'saved data with matching base'
live_overlay_paths_safe "$tmp/persist" overlay || fail 'existing saved overlay'
reject live_overlay_paths_safe "$tmp/persist" ../unrelated
ln -s "$tmp/unrelated" "$tmp/persist/temporary-overlay"
reject live_overlay_paths_safe "$tmp/persist" temporary-overlay
rm "$tmp/persist/temporary-overlay"
command mkdir -p "$tmp/persist/temporary-overlay"
ln -s "$tmp/unrelated" "$tmp/persist/temporary-overlay/upper"
reject live_overlay_paths_safe "$tmp/persist" temporary-overlay
rm "$tmp/persist/temporary-overlay/upper"
printf 'not directory\n' >"$tmp/persist/temporary-overlay/work"
reject live_overlay_paths_safe "$tmp/persist" temporary-overlay

command mkdir -p "$tmp/newroot/mnt/ooonana-live"
live_handoff_paths_safe "$tmp/newroot" || fail 'safe handoff paths'
ln -s "$tmp/unrelated" "$tmp/newroot/mnt/ooonana-live/persist"
reject live_handoff_paths_safe "$tmp/newroot"
rm "$tmp/newroot/mnt/ooonana-live/persist"
ln -s "$tmp/unrelated/important" "$tmp/newroot/mnt/ooonana-live/persistence-mode"
reject live_handoff_paths_safe "$tmp/newroot"

df() { printf 'Filesystem 1024-blocks Used Available Capacity Mounted\nfixture 131072 1024 %s 1%% %s\n' "${FIXTURE_FREE_KB:-65536}" "$tmp/persist"; }
live_persistence_writable "$tmp/persist" || fail 'writable persistence'
[ -z "$(find "$tmp/persist" -name '.ooonana-write-check.*' -print)" ] || fail 'probe cleanup'
FIXTURE_FREE_KB=16383
export FIXTURE_FREE_KB
reject live_persistence_writable "$tmp/persist"
FIXTURE_FREE_KB=invalid
reject live_persistence_writable "$tmp/persist"
FIXTURE_FREE_KB=65536
mktemp() { return 1; }
reject live_persistence_writable "$tmp/persist"
[ "$(cat "$tmp/persist/overlay/upper/user-file")" = saved ] || fail 'saved overlay changed'
[ "$(cat "$tmp/unrelated/important")" = preserve ] || fail 'unrelated data changed'

# Exercise rcS reporting without real mounts or /proc changes.
rcs_function="$(awk '/^start_persistence\(\) \{/ { capture=1 } capture { print } capture && /^}$/ { exit }' "$ROOT/scripts/build-full-i3-rootfs.sh")"
[ -n "$rcs_function" ] || fail 'rcS persistence function missing'
eval "$rcs_function"
cat() {
  case "$1" in
    /proc/cmdline) printf '%s\n' "${FIXTURE_CMDLINE:-ooonana.persistence=1}" ;;
    */persistence-mode) printf '%s\n' "${FIXTURE_MODE:-usb}" ;;
    */persistence-device) echo /dev/sdb2 ;;
    *) command cat "$@" ;;
  esac
}
RCS_FIXTURE=1
mount() { return "${FIXTURE_MOUNT_STATUS:-0}"; }
output="$(start_persistence)" || fail 'rcS successful bind'
[ "$output" = 'OOONANA_PERSISTENCE_OK:/dev/sdb2' ] || fail 'rcS success marker'
FIXTURE_MOUNT_STATUS=1
export FIXTURE_MOUNT_STATUS
if output="$(start_persistence)"; then fail 'rcS mount failure reported success'; fi
[ "$output" = OOONANA_PERSISTENCE_FAILED:bind ] || fail 'rcS failed bind marker'
FIXTURE_CMDLINE=ooonana.persistence=10
export FIXTURE_CMDLINE
[ -z "$(start_persistence)" ] || fail 'rcS substring flag'
FIXTURE_CMDLINE=ooonana.persistence=1
FIXTURE_MODE=ram
export FIXTURE_MODE
if output="$(start_persistence)"; then fail 'rcS missing overlay reported success'; fi
[ "$output" = 'OOONANA_PERSISTENCE_FAILED:missing verified overlay' ] || fail 'rcS missing overlay marker'

printf 'ok live-boot-storage\n'
