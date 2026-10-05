#!/bin/sh
# Shared by live init and fixture tests. Never format, repair, or choose by label alone.

live_cmdline_has_arg() (
  set -f
  for live_arg in $2; do
    [ "$live_arg" != "$1" ] || return 0
  done
  return 1
)

live_cmdline_value() (
  set -f
  live_found=0
  live_value=""
  for live_arg in $2; do
    case "$live_arg" in
      "$1="*)
        [ "$live_found" = 0 ] || return 2
        live_value="${live_arg#*=}"
        live_found=1
        ;;
    esac
  done
  printf '%s\n' "$live_value"
)

live_normalize_uuid() {
  case "$1" in ''|*[!a-zA-Z0-9-]*) return 1 ;; esac
  printf '%s\n' "$1" | tr 'A-Z' 'a-z'
}

live_uuid_matches() (
  live_expected="$(live_normalize_uuid "$1")" || return 1
  live_actual="$(blkid_value UUID "$2")" || return 1
  live_actual="$(live_normalize_uuid "$live_actual")" || return 1
  [ "$live_actual" = "$live_expected" ]
)

# Whole-disk/partition aliases on one parent are okay; cloned media on two are not.
live_boot_parent_for_uuid() (
  live_uuid="$1"
  shift
  live_parent=""
  for live_device in "$@"; do
    boot_media_candidate "$live_device" || continue
    live_uuid_matches "$live_uuid" "$live_device" || continue
    live_next_parent="$(parent_disk_name "$live_device")"
    [ -n "$live_next_parent" ] || return 1
    [ -z "$live_parent" ] || [ "$live_parent" = "$live_next_parent" ] || return 2
    live_parent="$live_next_parent"
  done
  printf '%s\n' "$live_parent"
)

live_persistence_device() (
  live_boot_device="$1"
  shift
  boot_media_candidate "$live_boot_device" || return 1
  live_boot_device="$(readlink -f "$live_boot_device")" || return 1
  live_boot_parent="$(parent_disk_name "$live_boot_device")"
  [ -n "$live_boot_parent" ] || return 1
  live_selected=""
  for live_device in "$@"; do
    live_device="$(readlink -f "$live_device")" || continue
    [ "$live_device" != "$live_boot_device" ] || continue
    [ "$(parent_disk_name "$live_device")" = "$live_boot_parent" ] || continue
    [ "$(blkid_value LABEL "$live_device" 2>/dev/null || true)" = "OOONANA_PERSIST" ] || continue
    [ "$(blkid_value TYPE "$live_device" 2>/dev/null || true)" = "ext4" ] || continue
    [ -z "$live_selected" ] || [ "$live_selected" = "$live_device" ] || return 2
    live_selected="$live_device"
  done
  printf '%s\n' "$live_selected"
)

live_overlay_paths_safe() (
  live_root="$1"
  case "$2" in overlay|temporary-overlay) live_name="$2" ;; *) return 1 ;; esac
  [ -d "$live_root" ] && [ ! -L "$live_root" ] || return 1
  [ "$(readlink -f "$live_root")" = "$live_root" ] || return 1
  for live_path in "$live_root/$live_name" "$live_root/$live_name/upper" "$live_root/$live_name/work"; do
    [ ! -L "$live_path" ] || return 1
    [ ! -e "$live_path" ] || [ -d "$live_path" ] || return 1
  done
)

live_persistence_writable() (
  live_free_kb="$(df -Pk "$1" | awk 'NR == 2 { print $4 }')" || return 1
  case "$live_free_kb" in ''|*[!0-9]*) return 1 ;; esac
  # Refuse disk-full startup instead of booting a desktop unable to save settings.
  [ "$live_free_kb" -ge 16384 ] || return 1
  live_probe="$(mktemp "$1/.ooonana-write-check.XXXXXX")" || return 1
  trap 'rm -f "$live_probe"' 0
  printf 'writable\n' >"$live_probe" || return 1
)

# Root-image filesystem UUID changes on rebuild; stale upper files must not hide
# new boot services. Legacy/nonmatching overlays require explicit offline backup.
live_saved_base_matches() (
  live_root="$1"
  live_base="$(live_normalize_uuid "$2")" || return 1
  live_overlay_paths_safe "$live_root" overlay || return 1
  live_marker="$live_root/overlay/base-id"
  [ ! -L "$live_marker" ] || return 1
  if [ -e "$live_marker" ]; then
    [ -f "$live_marker" ] || return 1
    [ "$(cat "$live_marker")" = "$live_base" ]
    return $?
  fi
  [ -z "$(ls -A "$live_root/overlay/upper")" ] || return 1
  live_pending="$(mktemp "$live_root/overlay/.base-id.XXXXXX")" || return 1
  trap 'rm -f "$live_pending"' 0
  printf '%s\n' "$live_base" >"$live_pending" || return 1
  mv "$live_pending" "$live_marker" || return 1
  sync
)

live_handoff_paths_safe() (
  live_root="$1"
  [ -d "$live_root" ] && [ ! -L "$live_root" ] || return 1
  for live_suffix in proc sys dev mnt mnt/ooonana-live mnt/ooonana-live/iso mnt/ooonana-live/root-ro mnt/ooonana-live/cow mnt/ooonana-live/persist mnt/ooonana-live/temporary; do
    live_path="$live_root/$live_suffix"
    [ ! -L "$live_path" ] || return 1
    [ ! -e "$live_path" ] || [ -d "$live_path" ] || return 1
  done
  for live_suffix in boot-device persistence-mode persistence-device base-id; do
    live_path="$live_root/mnt/ooonana-live/$live_suffix"
    [ ! -L "$live_path" ] || return 1
    [ ! -e "$live_path" ] || [ -f "$live_path" ] || return 1
  done
)
