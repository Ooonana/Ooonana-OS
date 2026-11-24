#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/run-iso-build-wsl.sh"
[[ -f "$SCRIPT" ]] || { echo 'missing WSL ISO launcher' >&2; exit 1; }
bash -n "$SCRIPT"
source="$(<"$SCRIPT")"
[[ "$source" == *'mount -t drvfs F: "$MOUNT_DIR"'* ]]
[[ "$source" == *'findmnt -n -o SOURCE --target "$MOUNT_DIR"'* ]]
[[ "$source" == *'exec bash "$SCRIPT_DIR/rebuild-full-i3-release.sh" "${release_args[@]}"'* ]]
[[ "$source" == *'exec bash "$SCRIPT_DIR/with-f-build-storage.sh"'* ]]

work="$(mktemp -d "${TMPDIR:-/tmp}/ooonana-iso-cursor-test.XXXXXX")"
trap 'rm -rf -- "$work"' EXIT
export ISO_TEST_MOUNT="$work/f"
sed 's|^MOUNT_DIR=/mnt/winf$|MOUNT_DIR="$ISO_TEST_MOUNT"|' "$SCRIPT" >"$work/launcher.sh"
cat >"$work/with-f-build-storage.sh" <<'STORAGE'
printf 'cursor=%s size=%s\n' "${OOONANA_PERSONAL_CURSOR_DIR:-unset}" "${OOONANA_PERSONAL_CURSOR_SIZE:-unset}"
printf 'arg=%s\n' "$@"
STORAGE
personal="$ISO_TEST_MOUNT/Ooonana/ooonana-os/build/personal-cursor/WindowsCursorConceptPersonal"
mkdir -p "$personal/cursors"
printf '[Icon Theme]\n' >"$personal/index.theme"
printf 'Xcur' >"$personal/cursors/left_ptr"
printf '21\n' >"$personal/cursor-size"

run_launcher() (
  id() { printf '0\n'; }
  mountpoint() { [[ "$*" == "-q $ISO_TEST_MOUNT" ]]; }
  findmnt() { printf 'F:\n'; }
  mount() { return 1; }
  export -f id mountpoint findmnt mount
  bash "$work/launcher.sh" "$@"
)

unset OOONANA_PERSONAL_CURSOR_DIR OOONANA_PERSONAL_CURSOR_SIZE
default="$(run_launcher --repo /candidate --preflight-only)"
[[ "$default" == *'[cursor] official OoonanaTailless cursor'* ]]
[[ "$default" == *'cursor=unset size=unset'* && "$default" != *'personal use only'* ]]
[[ "$default" == *'arg=/candidate'* && "$default" == *'arg=--preflight-only'* ]]
optional="$(run_launcher --personal-cursor)"
[[ "$optional" == *"cursor=$personal size=21"* && "$optional" != *'arg=--personal-cursor'* ]]
explicit="$(OOONANA_PERSONAL_CURSOR_DIR="$personal" OOONANA_PERSONAL_CURSOR_SIZE=22 run_launcher --preflight-only)"
[[ "$explicit" == *"cursor=$personal size=22"* ]]
public="$(OOONANA_PERSONAL_CURSOR_DIR="$personal" OOONANA_PERSONAL_CURSOR_SIZE=22 run_launcher --public-cursor)"
[[ "$public" == *'cursor=unset size=unset'* && "$public" != *'arg=--public-cursor'* ]]

bash -n "$ROOT/scripts/with-f-build-storage.sh"
bash "$ROOT/tests/test-f-build-storage.sh"
sh "$ROOT/tests/test-verification-media.sh"
printf 'ok iso-launcher\n'
