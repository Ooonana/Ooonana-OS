#!/usr/bin/env bash
# Native Linux scratch on F:; never relocates or modifies a WSL distro disk.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/f-build-budget.sh
source "$SCRIPT_DIR/lib/f-build-budget.sh"

die() { printf 'F build storage: %s\n' "$*" >&2; exit 1; }
[[ "$(id -u)" == 0 ]] || die 'root required'
[[ $# -gt 0 ]] || die 'command required'
for tool in awk blkid df findmnt flock losetup ls mkfs.ext4 mount mountpoint mv realpath rm stat sync truncate umount wslpath; do
  command -v "$tool" >/dev/null || die "missing command: $tool"
done
[[ "$(findmnt -n -o SOURCE --target /mnt/winf)" == F: &&
   "$(findmnt -n -o FSTYPE --target /mnt/winf)" == 9p ]] || die '/mnt/winf must be F: drvfs'

storage=/mnt/winf/Ooonana/ooonana-os/build-storage
image="$storage/release-stage.ext4"
identity="$storage/release-stage.identity"
partial="$image.creating"
native=/var/tmp/ooonana-f-build-storage
size_gib="${OOONANA_F_STAGE_SIZE_GIB:-21}"
if [[ ! "$size_gib" =~ ^[1-9][0-9]?$ ]] || (( size_gib < 21 )); then
  die 'workspace size must be 21-99 GiB'
fi
size_bytes=$((size_gib * 1024 * 1024 * 1024))
reserve_kb=$((8 * 1024 * 1024))
[[ "$(realpath -m "$storage")" == "$storage" ]] || die 'storage path contains a symlink'
[[ "$(realpath -m "$native")" == "$native" ]] || die 'mount path contains a symlink'
mkdir -p /var/lock
exec 8>/var/lock/ooonana-f-build-storage.lock
flock -n 8 || die 'another F-backed build is running'
mkdir -p "$storage" "$native"
mountpoint -q "$native" && die 'workspace already mounted; do not detach an unknown mount'
[[ -z "$(ls -A "$native")" ]] || die 'mount directory not empty'

loop=''
creating=0
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -n "$loop" ]]; then
    if mountpoint -q "$native"; then
      if ! sync -f "$native" || ! umount "$native"; then
        printf 'F build storage: flush/unmount failed; workspace retained, loop %s\n' "$loop" >&2
        exit 1
      fi
    fi
    losetup -d "$loop" || exit 1
  fi
  # Only an incomplete image exclusively created by this invocation is removed.
  if (( creating )); then rm -f -- "$partial"; fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

available_kb="$(df -Pk /mnt/winf | awk 'NR == 2 {print $4}')"
[[ "$available_kb" =~ ^[0-9]+$ ]] || die 'cannot read physical F: free space'
if [[ ! -e "$image" ]]; then
  [[ ! -L "$image" && ! -e "$identity" && ! -L "$identity" && ! -e "$partial" && ! -L "$partial" ]] ||
    die 'incomplete/unknown workspace exists; refusing to overwrite'
  (( available_kb >= size_bytes / 1024 + reserve_kb )) ||
    die "need $((size_gib + 8)) GiB free on F: for initial workspace plus output reserve"
  [[ -x /mnt/c/Windows/System32/fsutil.exe ]] || die 'Windows fsutil required for sparse NTFS scratch'
  printf '[storage] Creating %s GiB sparse ext4 workspace on F: (one-time)\n' "$size_gib"
  (set -o noclobber; : >"$partial")
  creating=1
  # Without this flag NTFS zero-fills the entire gap before end-of-file writes.
  /mnt/c/Windows/System32/fsutil.exe sparse setflag "$(wslpath -w "$partial")"
  truncate -s "$size_bytes" "$partial"
  mkfs.ext4 -q -F -m 0 -i 65536 -L OOONANA_BUILD -E nodiscard,lazy_journal_init=1 "$partial"
  uuid="$(blkid -p -s UUID -o value "$partial")"
  [[ "$uuid" =~ ^[0-9a-f-]{36}$ ]] || die 'new filesystem identity missing'
  printf '%s %s\n' "$uuid" "$size_bytes" >"$identity"
  sync -f "$storage"
  mv -T "$partial" "$image"
  creating=0
  sync -f "$storage"
fi
validate_workspace() {
  local expected_uuid expected_size extra
  [[ -f "$image" && ! -L "$image" && -f "$identity" && ! -L "$identity" ]] || die 'invalid workspace files'
  read -r expected_uuid expected_size extra <"$identity" || die 'invalid workspace identity'
  [[ "$expected_uuid" =~ ^[0-9a-f-]{36}$ && "$expected_size" == "$size_bytes" && -z "${extra:-}" ]] ||
    die 'workspace identity/size mismatch; no automatic resize or reformat'
  [[ "$(stat -c %s "$image")" == "$expected_size" &&
     "$(blkid -p -s TYPE -o value "$image")" == ext4 &&
     "$(blkid -p -s LABEL -o value "$image")" == OOONANA_BUILD &&
     "$(blkid -p -s UUID -o value "$image")" == "$expected_uuid" ]] || die 'foreign/damaged workspace; refusing to format'
}
validate_workspace
[[ -z "$(losetup -j "$image")" ]] || die 'workspace already attached; refusing to steal a loop device'
available_kb="$(df -Pk /mnt/winf | awk 'NR == 2 {print $4}')"
(( available_kb >= reserve_kb )) || die 'keep at least 8 GiB free on F: for release output'
loop="$(losetup --find --show "$image")"
mount -t ext4 -o rw,noatime "$loop" "$native" || die 'mount failed; no automatic fsck/reformat'
[[ "$(findmnt -n -o SOURCE --target "$native")" == "$loop" &&
   "$(findmnt -n -o FSTYPE --target "$native")" == ext4 ]] || die 'unexpected workspace mount'
mkdir -p "$native/tmp" "$native/kernel-work"
chmod 0700 "$native/tmp"
export TMPDIR="$native/tmp"
export PYTHONDONTWRITEBYTECODE=1
export OOONANA_STAGE_DIR="$native/release-stage"
export OOONANA_KERNEL_WORK_DIR="$native/kernel-work"
export OOONANA_STAGE_BACKING_IMAGE="$image"
check_f_build_budget || die 'insufficient physical F: backing capacity'
printf '[storage] F: ext4 staging: %s; WSL distro disk unchanged\n' "$OOONANA_STAGE_DIR"
"$@"
