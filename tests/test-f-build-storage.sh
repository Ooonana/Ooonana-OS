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
   "$source_text" == *'trap cleanup EXIT'* &&
   "$source_text" == *'sync -f "$native"'* &&
   "$source_text" == *'workspace already attached'* &&
   "$source_text" == *'export OOONANA_STAGE_DIR="$native/release-stage"'* &&
   "$source_text" == *'export TMPDIR="$native/tmp"'* &&
   "$source_text" == *'export OOONANA_KERNEL_WORK_DIR="$native/kernel-work"'* ]]
source "$ROOT/scripts/lib/f-build-budget.sh"
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
