#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/run-iso-build-wsl.sh"
[[ -f "$SCRIPT" ]] || { echo 'missing WSL ISO launcher' >&2; exit 1; }
bash -n "$SCRIPT"
source="$(<"$SCRIPT")"
[[ "$source" == *'mount -t drvfs F: "$MOUNT_DIR"'* ]]
[[ "$source" == *'findmnt -n -o SOURCE --target "$MOUNT_DIR"'* ]]
[[ "$source" == *'exec bash "$SCRIPT_DIR/rebuild-full-i3-release.sh" "$@"'* ]]
printf 'ok iso-launcher\n'
