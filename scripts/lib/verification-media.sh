#!/bin/sh
# Optional verification mirror only. Never creates/rebuilds the source ISO.
RAM_MEDIA_DIR=''
RAM_MEDIA_ISO=''

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
  linux_kb="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  windows_kb=0
  if grep -qi microsoft /proc/sys/kernel/osrelease; then
    windows_ps=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
    [ -x "$windows_ps" ] || { echo 'FAIL: cannot check Windows RAM headroom' >&2; return 1; }
    windows_kb="$("$windows_ps" -NoProfile -NonInteractive -Command \
      '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory' </dev/null | tr -d '[:space:]')" || return 1
    case "$windows_kb" in ''|0|*[!0-9]*) echo 'FAIL: invalid Windows RAM reading' >&2; return 1 ;; esac
  fi
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
