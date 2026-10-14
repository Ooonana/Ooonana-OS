#!/usr/bin/env bash
# Extracted function consumes size_bytes; source assertions intentionally stay literal.
# shellcheck disable=SC2034,SC2016
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/with-f-build-storage.sh"
bash -n "$SCRIPT"
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
die() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
eval "$(sed -n '/^validate_workspace() {$/,/^}$/p' "$SCRIPT")"
image="$work/image"
identity="$work/identity"
size_bytes=4
uuid=00000000-0000-0000-0000-000000000001
printf 'data' >"$image"
printf '%s 4\n' "$uuid" >"$identity"
blkid() {
  case "$3" in
    TYPE) printf '%s\n' "${fixture_type:-ext4}" ;;
    LABEL) printf '%s\n' "${fixture_label:-OOONANA_BUILD}" ;;
    UUID) printf '%s\n' "${fixture_uuid:-$uuid}" ;;
    *) return 1 ;;
  esac
}
validate_workspace
if (fixture_type=xfs; validate_workspace) >/dev/null 2>&1; then die 'foreign type accepted'; fi
if (fixture_label=OTHER; validate_workspace) >/dev/null 2>&1; then die 'foreign label accepted'; fi
if (fixture_uuid=00000000-0000-0000-0000-000000000002; validate_workspace) >/dev/null 2>&1; then die 'foreign UUID accepted'; fi
if (size_bytes=5; validate_workspace) >/dev/null 2>&1; then die 'resize silently accepted'; fi
printf '%s 4 unexpected\n' "$uuid" >"$identity"
if (validate_workspace) >/dev/null 2>&1; then die 'malformed identity accepted'; fi
printf '%s 4\n' "$uuid" >"$identity"
mv "$image" "$work/original"
ln -s original "$image"
if (validate_workspace) >/dev/null 2>&1; then die 'symlink accepted'; fi
[[ "$(<"$work/original")" == data ]] || die 'existing image was modified'
source_text="$(<"$SCRIPT")"
[[ "$source_text" == *'fsutil.exe sparse setflag'* &&
   "$source_text" == *'"$(wslpath -w "$partial")" </dev/null'* &&
   "$source_text" == *'trap cleanup EXIT'* &&
   "$source_text" == *'sync -f "$native"'* &&
   "$source_text" == *'workspace already attached'* &&
   "$source_text" == *'export OOONANA_STAGE_DIR="$native/release-stage"'* &&
   "$source_text" == *'export TMPDIR="$native/tmp"'* &&
   "$source_text" == *'export OOONANA_KERNEL_WORK_DIR="$native/kernel-work"'* ]]

# Exercise real EXIT cleanup with fixture commands only; never mount/detach host disks.
cleanup_function="$(sed -n '/^cleanup() {$/,/^}$/p' "$SCRIPT")"
cleanup_probe() {
  bash -c '
    native=/fixture; loop=/dev/loop-fixture; creating=0; count=0
    mountpoint() { return 0; }
    findmnt() { printf "%s\n" "${fixture_owner:-$loop}"; }
    sync() { return 0; }
    sleep() { return 0; }
    umount() { count=$((count + 1)); printf "%s\n" "$count" >>"$fixture_log"; (( count >= fixture_success )); }
    losetup() { printf "detached\n" >>"$fixture_log"; }
    fuser() { return 0; }
    fixture_success="$1"; fixture_log="$2"; fixture_owner="$3"
    eval "$4"
    (exit "$5")
    cleanup
  ' probe "$1" "$work/$2.log" "$3" "$cleanup_function" "$4" >"$work/cleanup-output.log" 2>&1
}
cleanup_probe 3 retry /dev/loop-fixture 0 || die 'transient busy cleanup failed'
[[ "$(tail -1 "$work/retry.log")" == detached && "$(wc -l <"$work/retry.log")" == 4 ]] || die 'wrong detach/retry count'
if cleanup_probe 99 busy /dev/loop-fixture 0; then die 'persistent busy mount accepted'; fi
[[ "$(wc -l <"$work/busy.log")" == 5 ]] || die 'unmount retry not bounded'
if cleanup_probe 1 foreign /dev/foreign 0; then die 'foreign mount detached'; fi
[[ ! -e "$work/foreign.log" ]] || die 'foreign mount modified'
if cleanup_probe 1 prior-error /dev/loop-fixture 7; then die 'original failure lost'; fi

source "$ROOT/scripts/lib/f-build-budget.sh"
check_wsl_system_headroom() { return 0; }
OOONANA_STAGE_BACKING_IMAGE=/mnt/winf/Ooonana/ooonana-os/build-storage/release-stage.ext4
budget_function="$(declare -f check_f_build_budget)"
# Filesystem fixtures provide backing-file presence without touching real F:.
eval "${budget_function/-f \"\$image\"/-f \"\$work\/original\"}"
findmnt() { printf '%s\n' "${fixture_drive:-F:}"; }
df() { printf 'Filesystem Blocks Used Available Capacity Mounted\nF: 40000000 0 %s 0%% /fixture\n' "${fixture_free:-30408704}"; }
stat() { if [[ "$2" == %b ]]; then printf '%s\n' "${fixture_blocks:-0}"; else printf '%s\n' 22548578304; fi; }
check_f_build_budget
if (fixture_free=30408703; check_f_build_budget) >/dev/null 2>&1; then die 'sparse oversubscription accepted'; fi
fixture_free=8388608 fixture_blocks=44040192 check_f_build_budget
if (fixture_free=8388607; fixture_blocks=44040192; check_f_build_budget) >/dev/null 2>&1; then die 'output reserve bypassed'; fi
if (fixture_drive=C:; check_f_build_budget) >/dev/null 2>&1; then die 'C: workspace accepted'; fi
printf 'ok f-build-storage: identity, symlink, capacity and lifecycle guards\n'
