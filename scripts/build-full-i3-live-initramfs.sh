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
  ooonana_require_commands cp cpio dirname du find gzip install ln mkdir mke2fs rm truncate
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
  rm -rf "${ROOTFS:?}/dev/"* "${ROOTFS:?}/proc/"* "${ROOTFS:?}/sys/"* "${ROOTFS:?}/run/"* "${ROOTFS:?}/tmp/"* 2>/dev/null || true
  rm -f "$INITRAMFS" "$ROOTFS_IMAGE"

  local used_kb image_kb
  read -r used_kb _ < <(du -sk "$ROOTFS")
  # Live writes go to overlayfs, so root image needs metadata headroom only.
  image_kb=$((used_kb + used_kb / 8 + 131072))
  truncate -s "${image_kb}K" "$ROOTFS_IMAGE"
  mke2fs -q -t ext4 -m 0 -O '^has_journal' -L OOONANA_LIVE -d "$ROOTFS" "$ROOTFS_IMAGE"

  LIVE_INIT_TREE="$(mktemp -d)"
  mkdir -p "$LIVE_INIT_TREE/bin" "$LIVE_INIT_TREE/sbin" "$LIVE_INIT_TREE/lib" "$LIVE_INIT_TREE/dev" "$LIVE_INIT_TREE/proc" "$LIVE_INIT_TREE/sys" "$LIVE_INIT_TREE/mnt/iso" "$LIVE_INIT_TREE/mnt/root-ro" "$LIVE_INIT_TREE/cow" "$LIVE_INIT_TREE/newroot" "$LIVE_INIT_TREE/usr/share/ooonana"
  install -m 0755 "$ROOTFS/bin/busybox" "$LIVE_INIT_TREE/bin/busybox"
  install -m 0644 "$ROOT/scripts/lib/live-boot-storage.sh" "$LIVE_INIT_TREE/lib/ooonana-live-storage.sh"
  if [[ -f "$ROOTFS/usr/share/ooonana/logo.txt" ]]; then
    install -m 0644 "$ROOTFS/usr/share/ooonana/logo.txt" "$LIVE_INIT_TREE/usr/share/ooonana/logo.txt"
  fi
  if [[ -f "$ROOTFS/usr/share/ooonana/boot-logo.txt" ]]; then
    install -m 0644 "$ROOTFS/usr/share/ooonana/boot-logo.txt" "$LIVE_INIT_TREE/usr/share/ooonana/boot-logo.txt"
  fi
  if [[ -f "$ROOTFS/lib/ld-musl-x86_64.so.1" ]]; then
    install -m 0755 "$ROOTFS/lib/ld-musl-x86_64.so.1" "$LIVE_INIT_TREE/lib/ld-musl-x86_64.so.1"
  fi
  if [[ -e "$ROOTFS/lib/libc.musl-x86_64.so.1" ]]; then
    install -m 0755 "$ROOTFS/lib/libc.musl-x86_64.so.1" "$LIVE_INIT_TREE/lib/libc.musl-x86_64.so.1"
  fi
  if [[ -f "$ROOTFS/lib/firmware/regulatory.db" ]]; then
    install -D -m 0644 "$ROOTFS/lib/firmware/regulatory.db" "$LIVE_INIT_TREE/lib/firmware/regulatory.db"
  fi
  if [[ -f "$ROOTFS/lib/firmware/regulatory.db.p7s" ]]; then
    install -D -m 0644 "$ROOTFS/lib/firmware/regulatory.db.p7s" "$LIVE_INIT_TREE/lib/firmware/regulatory.db.p7s"
  fi
  copy_early_firmware() {
    local fw rel
    [[ -d "$ROOTFS/lib/firmware" ]] || return 0
    while IFS= read -r -d '' fw; do
      rel="${fw#"$ROOTFS"/lib/firmware/}"
      if [[ -L "$fw" ]]; then
        mkdir -p "$(dirname "$LIVE_INIT_TREE/lib/firmware/$rel")"
        cp -a "$fw" "$LIVE_INIT_TREE/lib/firmware/$rel"
      else
        install -D -m 0644 "$fw" "$LIVE_INIT_TREE/lib/firmware/$rel"
      fi
    done < <(
      find "$ROOTFS/lib/firmware" \
        \( -name 'iwlwifi-*' \
        -o -path "$ROOTFS/lib/firmware/i915/*" \
        -o -path "$ROOTFS/lib/firmware/amdgpu/*" \
        -o -path "$ROOTFS/lib/firmware/radeon/*" \
        -o -path "$ROOTFS/lib/firmware/intel/ibt-*" \
        -o -path "$ROOTFS/lib/firmware/intel/sof*" \
        -o -path "$ROOTFS/lib/firmware/intel/avs/*" \
        -o -path "$ROOTFS/lib/firmware/rtl_bt/*" \
        -o -path "$ROOTFS/lib/firmware/rtl_nic/*" \
        -o -path "$ROOTFS/lib/firmware/rtlwifi/*" \
        -o -path "$ROOTFS/lib/firmware/rtw88/*" \
        -o -path "$ROOTFS/lib/firmware/rtw89/*" \
        -o -path "$ROOTFS/lib/firmware/qca/*" \
        -o -path "$ROOTFS/lib/firmware/ath10k/*" \
        -o -path "$ROOTFS/lib/firmware/ath11k/*" \
        -o -path "$ROOTFS/lib/firmware/ath12k/*" \
        -o -path "$ROOTFS/lib/firmware/mediatek/*" \
        -o -path "$ROOTFS/lib/firmware/brcm/*" \
        -o -name 'regulatory.db*' \) \
        \( -type f -o -type l \) -print0
    )
  }
  copy_early_firmware
  for applet in sh mount mkdir mknod sleep cat echo switch_root ls grep umount losetup mdev modprobe stty wc readlink dirname basename blkid rm tr df awk mktemp mv sync dd od; do
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
. /lib/ooonana-live-storage.sh

mount -t proc proc /proc 2>/dev/null || true
cmdline="$(cat /proc/cmdline 2>/dev/null || true)"

fail() {
  splash "boot failed" 10
  echo "Ooonana live init failed: $*" >/dev/console
  exec sh
}

mount -t sysfs sysfs /sys 2>/dev/null || true
mount -t devtmpfs devtmpfs /dev 2>/dev/null || {
  mkdir -p /dev
  [ -c /dev/console ] || mknod /dev/console c 5 1
  [ -c /dev/null ] || mknod /dev/null c 1 3
}
[ -c /dev/tty1 ] || mknod /dev/tty1 c 4 1 2>/dev/null || true

splash_console="/dev/tty1"
[ -e "$splash_console" ] || splash_console="/dev/console"
center_line() {
  text="$1"
  len=${#text}
  pad=$(((cols - len) / 2))
  [ "$pad" -lt 0 ] && pad=0
  i=0
  while [ "$i" -lt "$pad" ]; do
    printf ' '
    i=$((i + 1))
  done
  printf '%s\n' "$text"
}
draw_logo() {
  if [ -f /usr/share/ooonana/boot-logo.txt ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      center_line "$line"
    done < /usr/share/ooonana/boot-logo.txt
  elif [ -f /usr/share/ooonana/logo.txt ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      center_line "$line"
    done < /usr/share/ooonana/logo.txt
  else
    center_line 'Ooonana OS'
    center_line '      __________________'
    center_line '     |    __      __    |'
    center_line '     |   /  \    /  \   |'
    center_line '   / |                  |\'
    center_line '  /  |     \______/     | \'
    center_line '     |__________________|'
    center_line '          |        |'
  fi
}
splash() {
  label="$1"
  step="${2:-0}"
  rows=25
  cols=80
  dimensions="$(stty size <"$splash_console" 2>/dev/null || true)"
  if [ -n "$dimensions" ]; then
    rows="${dimensions%% *}"
    cols="${dimensions##* }"
  fi
  case "$rows" in ''|*[!0-9]*) rows=25 ;; esac
  case "$cols" in ''|*[!0-9]*) cols=80 ;; esac
  logo_file="/usr/share/ooonana/logo.txt"
  [ -f /usr/share/ooonana/boot-logo.txt ] && logo_file="/usr/share/ooonana/boot-logo.txt"
  logo_lines="$(wc -l <"$logo_file" 2>/dev/null || echo 10)"
  start_row=$(( (rows - logo_lines - 3) / 2 ))
  [ "$start_row" -lt 2 ] && start_row=2
  filled=""
  empty=""
  i=0
  while [ "$i" -lt "$step" ]; do
    filled="${filled}="
    i=$((i + 1))
  done
  while [ "$i" -lt 10 ]; do
    empty="${empty}."
    i=$((i + 1))
  done
  {
    printf '\033]P3ffb21a\033[2J\033[%s;1H\033[1;33m' "$start_row"
    draw_logo
    printf '\n'
    center_line "[$filled>$empty]  $label"
    printf '\033[0m'
  } >"$splash_console" 2>/dev/null || true
}

persistence_requested=0
live_cmdline_has_arg ooonana.persistence=1 "$cmdline" && persistence_requested=1
BOOT_UUID="$(live_cmdline_value ooonana.live.boot_uuid "$cmdline")" || fail "duplicate boot UUID arguments"
if [ -n "$BOOT_UUID" ]; then
  BOOT_UUID="$(live_normalize_uuid "$BOOT_UUID")" || fail "invalid boot UUID"
fi
if [ "$persistence_requested" = 1 ] && [ -z "$BOOT_UUID" ]; then
  fail "persistent boot needs GRUB boot UUID; no disk written; rebuild ISO or choose normal live"
fi
live_image_arg="$(live_cmdline_value ooonana.live.rootfs "$cmdline")" || fail "duplicate live rootfs arguments"
[ -z "$live_image_arg" ] || LIVE_IMAGE="$live_image_arg"
case "$LIVE_IMAGE" in /*) ;; *) fail "live rootfs path must be absolute" ;; esac

splash "starting live boot" 1
mkdir -p /dev/pts /mnt/iso /mnt/root-ro /cow /persist /newroot
mount -t devpts devpts /dev/pts 2>/dev/null || true
[ -e /proc/sys/kernel/hotplug ] && echo /sbin/mdev >/proc/sys/kernel/hotplug 2>/dev/null || true
mdev -s 2>/dev/null || true
modprobe loop 2>/dev/null || true
modprobe iso9660 2>/dev/null || true
modprobe overlay 2>/dev/null || true

[ -b /dev/loop0 ] || mknod /dev/loop0 b 7 0 2>/dev/null || true
[ -c /dev/loop-control ] || mknod /dev/loop-control c 10 237 2>/dev/null || true

splash "finding boot media" 2
tries=0
boot_media_device=""

parent_disk_name() {
  device="$(readlink -f "$1" 2>/dev/null || printf '%s\n' "$1")"
  base="${device##*/}"
  sys_path="$(readlink -f "/sys/class/block/$base" 2>/dev/null || true)"
  parent="$(basename "$(dirname "$sys_path")")"
  if [ -n "$parent" ] && [ -e "/sys/class/block/$parent" ]; then
    printf '%s\n' "$parent"
  else
    printf '%s\n' "$base"
  fi
}

boot_media_candidate() {
  candidate="$1"
  base="${candidate##*/}"
  case "$base" in
    loop*|ram*|zram*|dm-*|md*) return 1 ;;
  esac

  sys_path="$(readlink -f "/sys/class/block/$base" 2>/dev/null || true)"
  parent="$(parent_disk_name "$candidate")"
  removable="$(cat "/sys/class/block/$parent/removable" 2>/dev/null || echo 0)"
  [ "$removable" = 1 ] && return 0
  case "$sys_path" in
    */usb*/*) return 0 ;;
  esac
  return 1
}

blkid_value() {
  blkid_key="$1"
  blkid_device="$2"
  blkid_metadata="$(blkid "$blkid_device" 2>/dev/null || true)"
  blkid_marker="$blkid_key=\""
  case "$blkid_metadata" in
    *"$blkid_marker"*)
      blkid_value_result="${blkid_metadata#*"$blkid_marker"}"
      printf '%s\n' "${blkid_value_result%%\"*}"
      ;;
    *) return 1 ;;
  esac
}

mount_boot_media() {
  candidate="$1"
  fs_type="$(blkid_value TYPE "$candidate" 2>/dev/null || true)"
  fs_label="$(blkid_value LABEL "$candidate" 2>/dev/null || true)"
  case "$fs_type" in
    iso9660)
      mount -t iso9660 -o ro "$candidate" /mnt/iso 2>/dev/null
      ;;
    vfat)
      [ "$fs_label" = "OOONANAUSB" ] || return 1
      mount -t vfat -o ro "$candidate" /mnt/iso 2>/dev/null
      ;;
    ext4)
      [ "$fs_label" = "OOONANAUSB" ] || return 1
      mount -t ext4 -o ro,noload "$candidate" /mnt/iso 2>/dev/null
      ;;
    *) return 1 ;;
  esac
}

while [ "$tries" -lt 40 ]; do
  mdev -s 2>/dev/null || true
  candidates="/dev/sr0 /dev/sr1 /dev/cdrom /dev/hdc"
  for devpath in /sys/class/block/*; do
    [ -e "$devpath" ] || continue
    candidate="/dev/${devpath##*/}"
    [ -b "$candidate" ] || continue
    boot_media_candidate "$candidate" || continue
    candidates="$candidates $candidate"
  done
  for dev in $candidates; do
    [ -b "$dev" ] || continue
    if [ -n "$BOOT_UUID" ]; then
      live_uuid_matches "$BOOT_UUID" "$dev" || continue
    fi
    if mount_boot_media "$dev"; then
      if [ -f "/mnt/iso$LIVE_IMAGE" ]; then
        boot_media_device="$dev"
        break 2
      fi
      umount /mnt/iso 2>/dev/null || true
    fi
  done
  tries=$((tries + 1))
  sleep 1
done

[ -f "/mnt/iso$LIVE_IMAGE" ] || fail "cannot find $LIVE_IMAGE on boot media"
# Do not trust first-match discovery for writable storage, including cloned ISOs.
if [ -n "$BOOT_UUID" ]; then
  boot_uuid_parent="$(live_boot_parent_for_uuid "$BOOT_UUID" $candidates)" || fail "boot UUID ambiguous across drives; disconnect duplicate USBs; no disk written"
  [ -n "$boot_uuid_parent" ] && [ "$boot_uuid_parent" = "$(parent_disk_name "$boot_media_device")" ] || fail "cannot verify boot USB identity"
fi
live_image_path="$(readlink -f "/mnt/iso$LIVE_IMAGE")" || fail "cannot resolve live rootfs path"
case "$live_image_path" in /mnt/iso/*) ;; *) fail "live rootfs escapes boot media" ;; esac
splash "attaching live rootfs" 4
losetup -r /dev/loop0 "$live_image_path" || fail "cannot attach live rootfs image"
mount -t ext4 -o ro,noload /dev/loop0 /mnt/root-ro || fail "cannot mount live rootfs image"
live_base_id="$(blkid_value UUID /dev/loop0)" || fail "root image identity missing"
live_base_id="$(live_normalize_uuid "$live_base_id")" || fail "invalid root image identity"
splash "creating writable overlay" 6
overlay_upper="/cow/upper"
overlay_work="/cow/work"
persistence_mode="ram"
persistence_device=""

# Legacy direct-kernel boots without GRUB identity are read-only + RAM only.
if [ -n "$BOOT_UUID" ]; then
  persistence_tries=0
  while :; do
    mdev -s 2>/dev/null || true
    storage_candidates=""
    for devpath in /sys/class/block/*; do
      [ -e "$devpath" ] || continue
      candidate="/dev/${devpath##*/}"
      [ -b "$candidate" ] || continue
      storage_candidates="$storage_candidates $candidate"
    done
    boot_uuid_parent="$(live_boot_parent_for_uuid "$BOOT_UUID" $storage_candidates)" || fail "boot UUID ambiguous across drives; no disk written"
    [ "$boot_uuid_parent" = "$(parent_disk_name "$boot_media_device")" ] || fail "boot USB identity changed"
    persistence_device="$(live_persistence_device "$boot_media_device" $storage_candidates)" || fail "multiple or invalid persistence partitions; no disk written"
    [ -z "$persistence_device" ] || break
    [ "$persistence_requested" = 1 ] && [ "$persistence_tries" -lt 10 ] || break
    persistence_tries=$((persistence_tries + 1))
    sleep 1
  done
  if [ -n "$persistence_device" ]; then
    mount -t ext4 -o rw "$persistence_device" /persist 2>/dev/null || fail "cannot mount persistence; no RAM fallback; no automatic repair"
    if [ "$persistence_requested" = 1 ]; then
      live_overlay_paths_safe /persist overlay || fail "unsafe saved overlay paths; saved data untouched"
      live_persistence_writable /persist || fail "persistence unwritable or below 16 MiB free; no RAM fallback"
      mkdir -p /persist/overlay/upper /persist/overlay/work || fail "cannot prepare saved overlay"
      live_saved_base_matches /persist "$live_base_id" || fail "saved overlay belongs to another/legacy ISO; boot normal live, then offline backup/migrate; saved data untouched"
      overlay_upper="/persist/overlay/upper"
      overlay_work="/persist/overlay/work"
      persistence_mode="usb"
    else
      live_overlay_paths_safe /persist temporary-overlay || fail "unsafe temporary overlay paths; saved data untouched"
      rm -rf /persist/temporary-overlay || fail "cannot clear temporary overlay"
      live_persistence_writable /persist || fail "temporary overlay unwritable or below 16 MiB free"
      mkdir -p /persist/temporary-overlay/upper /persist/temporary-overlay/work || fail "cannot prepare temporary overlay"
      overlay_upper="/persist/temporary-overlay/upper"
      overlay_work="/persist/temporary-overlay/work"
      persistence_mode="usb-temporary"
    fi
  fi
fi
[ "$persistence_requested" != 1 ] || [ "$persistence_mode" = "usb" ] || fail "OOONANA_PERSIST missing on boot USB; no RAM fallback; no disk written"

if [ "$persistence_mode" = "ram" ]; then
  mount -t tmpfs -o mode=0755 tmpfs /cow || fail "cannot mount writable tmpfs overlay"
  mkdir -p /cow/upper /cow/work
fi
mkdir -p /newroot
mount -t overlay overlay -o suid,dev,exec,lowerdir=/mnt/root-ro,upperdir="$overlay_upper",workdir="$overlay_work" /newroot || fail "cannot mount overlay root"

splash "starting desktop" 9
live_handoff_paths_safe /newroot || fail "unsafe live handoff paths; saved data not reset"
mkdir -p /newroot/proc /newroot/sys /newroot/dev /newroot/mnt/ooonana-live/iso /newroot/mnt/ooonana-live/root-ro /newroot/mnt/ooonana-live/cow
printf '%s\n' "$boot_media_device" >/newroot/mnt/ooonana-live/boot-device
printf '%s\n' "$persistence_mode" >/newroot/mnt/ooonana-live/persistence-mode
printf '%s\n' "$persistence_device" >/newroot/mnt/ooonana-live/persistence-device
printf '%s\n' "$live_base_id" >/newroot/mnt/ooonana-live/base-id
mount --bind /mnt/iso /newroot/mnt/ooonana-live/iso 2>/dev/null || fail "cannot retain boot media mount"
mount --bind /mnt/root-ro /newroot/mnt/ooonana-live/root-ro 2>/dev/null || fail "cannot retain live rootfs mount"
mount --bind /cow /newroot/mnt/ooonana-live/cow 2>/dev/null || fail "cannot retain RAM overlay mount"
if [ "$persistence_mode" = "usb" ]; then
  mkdir -p /newroot/mnt/ooonana-live/persist
  mount --bind /persist /newroot/mnt/ooonana-live/persist 2>/dev/null || fail "cannot retain persistence mount"
elif [ "$persistence_mode" = "usb-temporary" ]; then
  mkdir -p /newroot/mnt/ooonana-live/temporary
  mount --bind /persist/temporary-overlay /newroot/mnt/ooonana-live/temporary 2>/dev/null || fail "cannot retain temporary overlay mount"
fi
mount --move /proc /newroot/proc 2>/dev/null || fail "cannot move proc mount"
mount --move /sys /newroot/sys 2>/dev/null || fail "cannot move sys mount"
mount --move /dev /newroot/dev 2>/dev/null || fail "cannot move dev mount"

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
