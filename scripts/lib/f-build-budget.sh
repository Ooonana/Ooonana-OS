#!/usr/bin/env bash
# A sparse ext4 file has virtual capacity; check its Windows backing drive too.
check_wsl_system_headroom() {
  grep -qi microsoft /proc/sys/kernel/osrelease || return 0
  local windows_ps=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe system_free
  [[ -x "$windows_ps" ]] || { echo 'FAIL: cannot check Windows system-drive headroom' >&2; return 1; }
  system_free="$("$windows_ps" -NoProfile -NonInteractive -Command \
    '(Get-PSDrive -Name C).Free' </dev/null | tr -d '[:space:]')" || return 1
  if [[ ! "$system_free" =~ ^[1-9][0-9]*$ ]] || (( system_free < 1073741824 )); then
    echo 'FAIL: keep at least 1 GiB free on C: for Windows/WSL host operation (bulk staging stays F:)' >&2
    return 1
  fi
}

check_f_build_budget() {
  local image="${OOONANA_STAGE_BACKING_IMAGE:-}" free_kb blocks bytes
  [[ -n "$image" ]] || return 0
  check_wsl_system_headroom || return 1
  [[ "$image" == /mnt/winf/Ooonana/ooonana-os/build-storage/release-stage.ext4 &&
     -f "$image" && ! -L "$image" &&
     "$(findmnt -n -o SOURCE --target "$image")" == F: ]] || {
    printf 'FAIL: invalid F: stage backing image\n' >&2; return 1;
  }
  free_kb="$(df -Pk "$image" | awk 'NR == 2 {print $4}')"
  blocks="$(stat -c %b "$image")"
  bytes="$(stat -c %s "$image")"
  [[ "$free_kb" =~ ^[0-9]+$ && "$blocks" =~ ^[0-9]+$ && "$bytes" =~ ^[0-9]+$ ]] || return 1
  # Already allocated image extents are reusable, not additional free host space.
  if (( free_kb < 8 * 1024 * 1024 ||
        free_kb + blocks / 2 < bytes / 1024 + 8 * 1024 * 1024 )); then
    printf 'FAIL: F: needs room for full workspace capacity plus 8 GiB output reserve\n' >&2
    return 1
  fi
}
