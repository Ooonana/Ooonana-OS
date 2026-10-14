#!/usr/bin/env bash
# A sparse ext4 file has virtual capacity; check its Windows backing drive too.
check_f_build_budget() {
  local image="${OOONANA_STAGE_BACKING_IMAGE:-}" free_kb blocks bytes
  [[ -n "$image" ]] || return 0
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
