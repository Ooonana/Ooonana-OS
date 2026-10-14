#!/bin/sh
# Optional verification mirror only. Never creates/rebuilds the source ISO.
RAM_MEDIA_DIR=''
RAM_MEDIA_ISO=''
DISK_MEDIA_ROOT=''
DISK_MEDIA_DIR=''
DISK_MEDIA_ISO=''
DISK_MEDIA_SOURCE=''

verification_available_memory() {
  linux_kb="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  windows_kb=0
  windows_ps=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
  if grep -qi microsoft /proc/sys/kernel/osrelease; then
    [ -x "$windows_ps" ] || { echo 'FAIL: cannot check Windows RAM headroom' >&2; return 1; }
    windows_kb="$("$windows_ps" -NoProfile -NonInteractive -Command \
      '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory' </dev/null | tr -d '[:space:]')" || return 1
    case "$windows_kb" in ''|0|*[!0-9]*) echo 'FAIL: invalid Windows RAM reading' >&2; return 1 ;; esac
  fi
}

verification_guest_log_ok() {
  [ -f "$1" ] || return 1
  if grep -Eq 'I/O error, dev|Buffer I/O error|EXT4-fs error|Remounting filesystem read-only|Kernel panic|Out of memory: Killed process' "$1"; then
    return 1
  else
    # A grep read error is not proof of a healthy guest.
    [ "$?" -eq 1 ]
  fi
}

ram_media_memory_ok() {
  # ISO bytes, guest MiB, Linux available KiB, Windows available KiB (0=not WSL).
  required_kb=''
  [ "$#" -eq 4 ] || return 1
  for memory_value in "$@"; do
    case "$memory_value" in ''|*[!0-9]*|0[0-9]*) return 1 ;; esac
  done
  [ "$1" -gt 0 ] && [ "$2" -ge 1024 ] || return 1
  required_kb=$((($1 + 1023) / 1024 + $2 * 1024 + 2 * 1024 * 1024))
  [ "$3" -ge "$required_kb" ] || return 1
  [ "$4" -eq 0 ] || [ "$4" -ge "$required_kb" ]
}

prepare_ram_media() {
  source_iso="$1"
  guest_mib="$2"
  [ "$(id -u)" -eq 0 ] || { echo 'FAIL: RAM verification requires root' >&2; return 1; }
  [ -f "$source_iso" ] || return 1
  media_bytes="$(stat -c %s "$source_iso")"
  verification_available_memory || return 1
  if ! ram_media_memory_ok "$media_bytes" "$guest_mib" "$linux_kb" "$windows_kb"; then
    echo 'FAIL: RAM verification needs ISO + guest RAM + 2 GiB reserve; close apps or use stable native storage' >&2
    printf 'RAM budget KiB: required=%s Linux=%s Windows=%s\n' "${required_kb:-invalid}" "$linux_kb" "$windows_kb" >&2
    return 1
  fi
  RAM_MEDIA_DIR="$(mktemp -d /var/tmp/ooonana-verify-ram.XXXXXXXX)"
  # noswap prevents this mirror from growing a WSL swap/VHD on C:.
  mount -t tmpfs -o "noswap,mode=0700,size=$((media_bytes + 16 * 1024 * 1024))" \
    ooonana-verify-ram "$RAM_MEDIA_DIR" || return 1
  RAM_MEDIA_ISO="$RAM_MEDIA_DIR/verification.iso"
  cp "$source_iso" "$RAM_MEDIA_ISO" || return 1
  [ "$(stat -c %s "$RAM_MEDIA_ISO")" = "$media_bytes" ] || return 1
  printf '[verify] Read-only media mirror in nonswappable RAM: %s\n' "$RAM_MEDIA_ISO"
}

disk_media_space_ok() {
  # ISO bytes, destination free KiB, Windows C: free KiB (0=not WSL).
  disk_required_kb=''
  [ "$#" -eq 3 ] || return 1
  for space_value in "$@"; do
    case "$space_value" in ''|*[!0-9]*|0[0-9]*) return 1 ;; esac
  done
  [ "$1" -gt 0 ] || return 1
  disk_required_kb=$((($1 + 1023) / 1024 + 2 * 1024 * 1024))
  [ "$2" -ge "$disk_required_kb" ] || return 1
  [ "$3" -eq 0 ] || [ "$3" -ge "$disk_required_kb" ]
}

prepare_disk_media() {
  source_iso="$1"
  guest_mib="$2"
  disk_root="$3"
  [ "$(id -u)" -eq 0 ] && [ -f "$source_iso" ] && [ -d "$disk_root" ] || return 1
  disk_root="$(realpath -e "$disk_root")" || return 1
  media_bytes="$(stat -c %s "$source_iso")"
  verification_available_memory || return 1
  # Disk cache is reclaimable, unlike pinned nonswappable tmpfs media.
  ram_media_memory_ok 1 "$guest_mib" "$linux_kb" "$windows_kb" || {
    printf 'FAIL: disk verification needs guest RAM + 2 GiB reserve (KiB: required=%s Linux=%s Windows=%s)\n' \
      "${required_kb:-invalid}" "$linux_kb" "$windows_kb" >&2; return 1;
  }
  destination_kb="$(df -Pk "$disk_root" | awk 'NR == 2 {print $4}')"
  windows_disk_kb=0
  if grep -qi microsoft /proc/sys/kernel/osrelease; then
    case "$(findmnt -n -o SOURCE --target "$disk_root")" in
      'C:'|C:\\) ;;
      *) echo 'FAIL: WSL disk verification needs C: DrvFS; no distro VHD growth or F: remirroring' >&2; return 1 ;;
    esac
    windows_disk_bytes="$("$windows_ps" -NoProfile -NonInteractive -Command \
      '(Get-PSDrive -Name C).Free' </dev/null | tr -d '[:space:]')" || return 1
    case "$windows_disk_bytes" in ''|0|*[!0-9]*|0[0-9]*) return 1 ;; esac
    windows_disk_kb=$((windows_disk_bytes / 1024))
  fi
  disk_media_space_ok "$media_bytes" "$destination_kb" "$windows_disk_kb" || {
    echo 'FAIL: temporary disk verification needs ISO size + 2 GiB disk reserve' >&2; return 1;
  }
  DISK_MEDIA_ROOT="$disk_root"
  DISK_MEDIA_SOURCE="$(findmnt -n -o SOURCE --target "$disk_root")" || return 1
  DISK_MEDIA_DIR="$(mktemp -d "$disk_root/ooonana-verify-disk.XXXXXXXX")" || return 1
  DISK_MEDIA_ISO="$DISK_MEDIA_DIR/verification.iso"
  printf '[verify] Temporary disk mirror: %s (guest=%s MiB, 2 GiB RAM/disk reserves)\n' "$DISK_MEDIA_ISO" "$guest_mib"
  cp "$source_iso" "$DISK_MEDIA_ISO" || return 1
  printf '[verify] Comparing copied media; reading F: source may take several minutes\n'
  cmp -s "$source_iso" "$DISK_MEDIA_ISO" || { echo 'FAIL: verification media copy differs' >&2; return 1; }
  printf '[verify] Disk mirror copy verified\n'
}

cleanup_disk_media() {
  [ -n "$DISK_MEDIA_DIR" ] || return 0
  case "$DISK_MEDIA_DIR" in "$DISK_MEDIA_ROOT"/ooonana-verify-disk.*) ;; *) return 1 ;; esac
  [ ! -L "$DISK_MEDIA_DIR" ] && [ "$(realpath -e "$DISK_MEDIA_DIR")" = "$DISK_MEDIA_DIR" ] || return 1
  [ -n "$DISK_MEDIA_SOURCE" ] &&
    [ "$(findmnt -n -o SOURCE --target "$DISK_MEDIA_DIR")" = "$DISK_MEDIA_SOURCE" ] || return 1
  if mountpoint -q "$DISK_MEDIA_DIR"; then
    echo 'FAIL: disk mirror became a mount; retained' >&2; return 1
  fi
  [ "$DISK_MEDIA_ISO" = "$DISK_MEDIA_DIR/verification.iso" ] && [ ! -L "$DISK_MEDIA_ISO" ] || return 1
  # Remove only our one copied file. Unknown contents prevent rmdir, never recurse.
  rm -f -- "$DISK_MEDIA_ISO" || return 1
  rmdir -- "$DISK_MEDIA_DIR" || return 1
  DISK_MEDIA_ROOT=''
  DISK_MEDIA_DIR=''
  DISK_MEDIA_ISO=''
  DISK_MEDIA_SOURCE=''
}

cleanup_ram_media() {
  [ -n "$RAM_MEDIA_DIR" ] || return 0
  if mountpoint -q "$RAM_MEDIA_DIR"; then
    [ "$(findmnt -n -o SOURCE --target "$RAM_MEDIA_DIR")" = ooonana-verify-ram ] || {
      echo 'FAIL: RAM mirror mount ownership changed; left untouched' >&2; return 1;
    }
    umount "$RAM_MEDIA_DIR" || {
      printf 'FAIL: RAM mirror still busy; retained: %s\n' "$RAM_MEDIA_DIR" >&2; return 1;
    }
  fi
  rmdir "$RAM_MEDIA_DIR" || return 1
  RAM_MEDIA_DIR=''
  RAM_MEDIA_ISO=''
}
