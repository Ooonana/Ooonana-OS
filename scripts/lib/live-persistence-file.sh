#!/bin/sh
# Static, file-backed persistence on the verified boot filesystem only.
# Caller owns UUID/USB validation. Never partition, resize or format a device.

live_file_mounted() {
  live_mount_table=/proc/mounts
  [ -r "$live_mount_table" ] || live_mount_table=/newroot/proc/mounts
  awk -v target="$1" '$2 == target { found=1 } END { exit !found }' "$live_mount_table" 2>/dev/null
}

live_file_unmount() {
  live_file_mounted "$1" || return 0
  # Failed handoff may contain saved symlinks. Do not follow them outside here.
  [ "$(readlink -f "$1")" = "$1" ] || return 1
  umount "$1"
}

live_persistence_file_abort() {
  [ "${live_file_outer_writable:-0}" = 1 ] || return 0
  live_abort_ok=1
  sync || live_abort_ok=0
  for live_abort_system in proc sys dev; do
    if live_file_mounted "/newroot/$live_abort_system"; then
      [ "$(readlink -f "/newroot/$live_abort_system")" = "/newroot/$live_abort_system" ] &&
        mount --move "/newroot/$live_abort_system" "/$live_abort_system" || live_abort_ok=0
    fi
  done
  # Handoff now moves the original mounts, avoiding unreachable writable mounts.
  # Recover outer mount before releasing children so final RO remount stays real.
  if live_file_mounted /newroot/mnt/ooonana-live/iso; then
    [ "$(readlink -f /newroot/mnt/ooonana-live/iso)" = /newroot/mnt/ooonana-live/iso ] &&
      mount --move /newroot/mnt/ooonana-live/iso /mnt/iso || live_abort_ok=0
  fi
  if [ "${live_file_loop_attached:-0}" = 1 ]; then
    # Only mounts made by this boot; no forced/lazy unmount or saved-file removal.
    for live_abort_path in /newroot/mnt/ooonana-live/temporary /newroot/mnt/ooonana-live/persist \
      /newroot/mnt/ooonana-live/iso /newroot/mnt/ooonana-live/root-ro \
      /newroot/mnt/ooonana-live/cow /newroot/mnt/ooonana-shutdown /newroot /persist; do
      live_file_unmount "$live_abort_path" || live_abort_ok=0
    done
    losetup -d /dev/loop1 || live_abort_ok=0
    if losetup /dev/loop1 >/dev/null 2>&1; then
      live_abort_ok=0  # Still referenced: never claim successful detach.
    else
      live_file_loop_attached=0
    fi
  fi
  if mount -o remount,ro /mnt/iso; then
    live_file_outer_writable=0
    echo OOONANA_BOOT_STORAGE_READ_ONLY
  else
    live_abort_ok=0
  fi
  sync || live_abort_ok=0
  [ "$live_abort_ok" = 1 ]
}

live_persistence_file_safe() (
  live_file="$1"
  [ ! -L "$live_file" ] || return 1
  [ ! -e "$live_file" ] && return 0
  [ -f "$live_file" ] || return 1
  [ "$(readlink -f "$live_file")" = "$live_file" ] || return 1
  [ "$(stat -c %h "$live_file")" = 1 ] || return 1
  live_size="$(stat -c %s "$live_file")" || return 1
  case "$live_size" in ''|*[!0-9]*) return 1 ;; esac
  [ "$live_size" -ge 268435456 ] || return 1
)

live_persistence_outer_clean() (
  # Read-only check before FAT gains writable mounts. Linux fat_set_state uses
  # the extended BPB state byte (FAT12/16:37, FAT32:65), dirty mask 0x01.
  # A clean flag is not a full filesystem validation or durability guarantee.
  case "$2" in ext4) return 0 ;; vfat) ;; *) return 1 ;; esac
  live_fat_signature="$(od -An -tx1 -j 510 -N 2 "$1" 2>/dev/null | tr -d '[:space:]')"
  [ "$live_fat_signature" = 55aa ] || return 1
  live_fat_length="$(od -An -tx1 -j 22 -N 2 "$1" 2>/dev/null | tr -d '[:space:]')"
  case "$live_fat_length" in
    0000) live_fat_state_offset=65 ;;
    ???? ) live_fat_state_offset=37 ;;
    *) return 1 ;;
  esac
  live_fat_state="$(od -An -tu1 -j "$live_fat_state_offset" -N 1 "$1" 2>/dev/null | tr -d '[:space:]')"
  case "$live_fat_state" in ''|*[!0-9]*) return 1 ;; esac
  [ "$((live_fat_state & 1))" = 0 ]
)

live_persistence_file_limit() (
  # Keep 256 MiB on the outer filesystem for metadata/other USB files.
  live_free_kb="$1"
  case "$live_free_kb" in ''|*[!0-9]*) return 1 ;; esac
  live_limit=$((live_free_kb / 1024 - 256))
  case "$2" in
    vfat) [ "$live_limit" -le 4095 ] || live_limit=4095 ;;
    ext4) ;;
    *) return 1 ;;
  esac
  [ "$live_limit" -ge 256 ] || return 1
  printf '%s\n' "$live_limit"
)

live_persistence_size_valid() (
  case "$1" in ''|0*|*[!0-9]*) return 1 ;; esac
  # Bound arithmetic even on corrupt/untrusted input.
  [ "${#1}" -le 9 ] || return 1
  [ "$1" -ge 256 ] && [ "$1" -le "$2" ]
)

live_persistence_read() {
  # BusyBox ash supports read -t. Unattended boots fail rather than fake saving.
  LIVE_SETUP_REPLY=""
  read -r -t 120 LIVE_SETUP_REPLY <&3
}

live_persistence_file_prompt() {
  live_max="$1"
  live_default=4095
  [ "$live_default" -le "$live_max" ] || live_default="$live_max"
  printf '\nOoonana persistent USB setup\n' >&3
  printf 'Boot USB: %s\n' "$boot_media_device" >&3
  printf 'Creates ext4 storage FILE, not partition. No existing files erased.\n' >&3
  printf 'Writes save directly to USB. Internal disks are not used.\n' >&3
  printf 'Storage size MiB: 256..%s [%s]; cancel to stop: ' "$live_max" "$live_default" >&3
  live_persistence_read || return 1
  live_size_mib="${LIVE_SETUP_REPLY:-$live_default}"
  live_persistence_size_valid "$live_size_mib" "$live_max" || return 1
  printf 'Create %s MiB on %s? Type CREATE: ' "$live_size_mib" "$boot_media_device" >&3
  live_persistence_read || return 1
  [ "$LIVE_SETUP_REPLY" = CREATE ] || return 1
}

live_persistence_file_create() (
  live_size_mib="$1"
  live_image=/mnt/iso/ooonana-persistence.ext4
  # Check again immediately before writing; never overwrite saved storage.
  [ ! -e "$live_image" ] && [ ! -L "$live_image" ] || return 1
  live_pending="$(mktemp /mnt/iso/.ooonana-persistence.XXXXXX)" || return 1
  live_bound_mnt=0
  live_bound_dev=0
  live_file_cleanup() {
    [ "$live_bound_dev" = 0 ] || umount /mnt/root-ro/dev
    [ "$live_bound_mnt" = 0 ] || umount /mnt/root-ro/mnt
    # Only this newly owned temporary file, never an existing persistence image.
    rm -f "$live_pending"
  }
  trap live_file_cleanup 0
  printf 'Allocating storage; slow USBs may take several minutes...\n' >&3
  # Fully allocate, not sparse: guest ext4 must not later exhaust outer storage.
  dd if=/dev/zero of="$live_pending" bs=1048576 count="$live_size_mib" >&3 2>&3 || return 1
  mount --bind /mnt/iso /mnt/root-ro/mnt || return 1
  live_bound_mnt=1
  mount --bind /dev /mnt/root-ro/dev || return 1
  live_bound_dev=1
  # Use bundled musl e2fsprogs/config/libs, not a host binary or user-supplied tool.
  chroot /mnt/root-ro /sbin/mke2fs -q -t ext4 -m 0 \
    -E lazy_itable_init=0,lazy_journal_init=0 -L OOONANA_PERSIST \
    "/mnt/${live_pending##*/}" >&3 2>&3 || return 1
  umount /mnt/root-ro/dev || return 1
  live_bound_dev=0
  umount /mnt/root-ro/mnt || return 1
  live_bound_mnt=0
  [ "$(blkid_value TYPE "$live_pending")" = ext4 ] || return 1
  [ "$(blkid_value LABEL "$live_pending")" = OOONANA_PERSIST ] || return 1
  live_persistence_file_safe "$live_pending" || return 1
  sync || return 1
  # FAT has no hardlinks. BusyBox's no-clobber rename refuses existing targets;
  # verify source disappeared because -n can return success without moving it.
  mv -nT "$live_pending" "$live_image" || return 1
  [ ! -e "$live_pending" ] || return 1
  sync || return 1
)

live_persistence_file_attach() {
  live_image=/mnt/iso/ooonana-persistence.ext4
  live_boot_fs="$(blkid_value TYPE "$boot_media_device")" || return 1
  case "$live_boot_fs" in vfat|ext4) ;; *) return 1 ;; esac
  live_persistence_outer_clean "$boot_media_device" "$live_boot_fs" || {
    echo 'OOONANA_BOOT_STORAGE_NEEDS_OFFLINE_CHECK: dirty/unreadable FAT; back up USB, check filesystem offline; no writable mount' >&2
    return 1
  }
  live_persistence_file_safe "$live_image" || return 1
  if [ ! -e "$live_image" ]; then
    [ "$persistence_requested" = 1 ] || return 1
    [ -x /mnt/root-ro/sbin/mke2fs ] || return 1
    live_max="$(live_persistence_file_limit "$(df -Pk /mnt/iso | awk 'NR == 2 { print $4 }')" "$live_boot_fs")" || return 1
    # Physical desktop boots show/read tty1; serial-only fixtures use console.
    live_console=/dev/console
    live_cmdline_has_arg console=tty0 "$cmdline" && live_console=/dev/tty1
    exec 3<>"$live_console" || return 1
    live_persistence_file_prompt "$live_max" || { exec 3>&-; return 1; }
    # Revalidate drive identity and free space after the user's confirmation.
    live_storage_identity_safe || { exec 3>&-; return 1; }
    live_max="$(live_persistence_file_limit "$(df -Pk /mnt/iso | awk 'NR == 2 { print $4 }')" "$live_boot_fs")" || { exec 3>&-; return 1; }
    live_persistence_size_valid "$live_size_mib" "$live_max" || { exec 3>&-; return 1; }
    live_persistence_outer_clean "$boot_media_device" "$live_boot_fs" || { exec 3>&-; return 1; }
    mount -o remount,rw,nosuid,nodev,noexec /mnt/iso || { exec 3>&-; return 1; }
    live_file_outer_writable=1
    live_persistence_file_create "$live_size_mib" || {
      exec 3>&-
      live_persistence_file_abort || echo OOONANA_BOOT_STORAGE_CLEANUP_FAILED >&2
      return 1
    }
    printf 'Storage ready. Future persistent boots reuse it.\n' >&3
    exec 3>&-
  fi
  # Validate content before changing outer mount to writable. Bad files stay intact.
  [ "$(blkid_value TYPE "$live_image")" = ext4 ] || return 1
  [ "$(blkid_value LABEL "$live_image")" = OOONANA_PERSIST ] || return 1
  live_storage_identity_safe || return 1
  if [ "${live_file_outer_writable:-0}" != 1 ]; then
    live_persistence_outer_clean "$boot_media_device" "$live_boot_fs" || return 1
  fi
  mount -o remount,rw,nosuid,nodev,noexec /mnt/iso || return 1
  live_file_outer_writable=1
  [ -b /dev/loop1 ] || mknod /dev/loop1 b 7 1 || return 1
  losetup /dev/loop1 "$live_image" || return 1
  live_file_loop_attached=1
  persistence_device=/dev/loop1
  persistence_file=/mnt/ooonana-live/iso/ooonana-persistence.ext4
}
