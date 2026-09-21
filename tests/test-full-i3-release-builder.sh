#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/rebuild-full-i3-release.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

contains() {
  [[ "$1" == *"$2"* ]] || fail "missing: $2"
}

[[ -f "$SCRIPT" ]] || fail "missing release builder"
bash -n "$SCRIPT"
help="$(bash "$SCRIPT" --help)"
body="$(<"$SCRIPT")"
contains "$help" "Build and verify Ooonana full-i3 release ISO"
contains "$help" "--skip-qemu"
contains "$body" 'linux-$KERNEL_VERSION.tar.xz'
contains "$body" "build-full-i3-rootfs.sh"
contains "$body" "build-full-i3-live-initramfs.sh"
contains "$body" "build-full-i3-disk.sh"
contains "$body" 'build-full-i3-iso.sh'
contains "$body" '--iso "$new_iso"'
contains "$body" "verify-rufus-iso.sh"
contains "$body" "qemu-service-smoke.sh"
contains "$body" "NetworkManager"
contains "$body" "wpa_supplicant"
contains "$body" "ooonana-keyboard-panel"
contains "$body" "ooonana-thermal-panel"
contains "$body" "ooonana-hardware-profile"
contains "$body" 'mv -f "$new_iso" "$final_iso"'

printf 'ok full-i3-release-builder\n'
