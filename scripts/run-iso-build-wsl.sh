#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOUNT_DIR=/mnt/winf

if [[ "$(id -u)" != 0 ]]; then
  printf 'run-iso-build-wsl: root required for F: mount\n' >&2
  exit 1
fi
mkdir -p "$MOUNT_DIR"
if ! mountpoint -q "$MOUNT_DIR"; then
  mount -t drvfs F: "$MOUNT_DIR"
fi
if [[ "$(findmnt -n -o SOURCE --target "$MOUNT_DIR")" != "F:" ]]; then
  printf 'run-iso-build-wsl: %s is not F:\n' "$MOUNT_DIR" >&2
  exit 1
fi
if [[ ! -d "$MOUNT_DIR/Ooonana/ooonana-os/build/full-i3-repo" ]]; then
  printf 'run-iso-build-wsl: F: package repository missing\n' >&2
  exit 1
fi

public_cursor=0
release_args=()
for argument in "$@"; do
  case "$argument" in
    --public-cursor) public_cursor=1 ;;
    *) release_args+=("$argument") ;;
  esac
done
personal_cursor="$MOUNT_DIR/Ooonana/ooonana-os/build/personal-cursor/WindowsCursorConceptPersonal"
if [[ "$public_cursor" -eq 1 ]]; then
  unset OOONANA_PERSONAL_CURSOR_DIR OOONANA_PERSONAL_CURSOR_SIZE
elif [[ -z "${OOONANA_PERSONAL_CURSOR_DIR:-}" && -d "$personal_cursor" ]]; then
  [[ -s "$personal_cursor/index.theme" && -s "$personal_cursor/cursors/left_ptr" ]] || {
    printf 'run-iso-build-wsl: incomplete personal cursor theme\n' >&2
    exit 1
  }
  export OOONANA_PERSONAL_CURSOR_DIR="$personal_cursor"
  if [[ -z "${OOONANA_PERSONAL_CURSOR_SIZE:-}" && -f "$personal_cursor/cursor-size" ]]; then
    IFS= read -r OOONANA_PERSONAL_CURSOR_SIZE <"$personal_cursor/cursor-size" || true
  fi
  export OOONANA_PERSONAL_CURSOR_SIZE="${OOONANA_PERSONAL_CURSOR_SIZE:-32}"
  printf '[cursor] personal cursor included; resulting ISO is for personal use only\n'
fi

exec bash "$SCRIPT_DIR/rebuild-full-i3-release.sh" "${release_args[@]}"
