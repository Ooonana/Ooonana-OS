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

exec bash "$SCRIPT_DIR/rebuild-full-i3-release.sh" "$@"
