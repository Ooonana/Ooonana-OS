#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/rebuild-full-i3-release.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local text="$1"
  local expected="$2"
  [[ "$text" == *"$expected"* ]] || fail "missing: $expected"
}

[[ -f "$SCRIPT" ]] || fail "release rebuild script is missing"
bash -n "$SCRIPT"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "--preflight-only"
assert_contains "$help" "--resume-after-rootfs"
assert_contains "$help" "--resume-after-iso"

source_text="$(<"$SCRIPT")"
assert_contains "$source_text" 'STAGE_DIR="${OOONANA_STAGE_DIR:-/var/tmp/ooonana-release-stage}"'
assert_contains "$source_text" '[[ "$STAGE_DIR" == /var/tmp/ooonana-* ]]'
assert_contains "$source_text" 'cp -a "$REPO" "$STAGE_DIR/full-i3-repo"'
assert_contains "$source_text" 'install -m 0755 "$KERNEL" "$STAGE_DIR/ooonana-kernel/vmlinuz-ooonana"'
assert_contains "$source_text" 'die "resume stage missing kernel; rerun without --resume-after-rootfs"'
assert_contains "$source_text" 'die "resume stage missing package repo; rerun without --resume-after-rootfs"'
assert_contains "$source_text" 'die "resume stage missing full rootfs; rerun without --resume-after-rootfs"'
assert_contains "$source_text" 'bash "$ROOT/scripts/build-full-i3-rootfs.sh"'
assert_contains "$source_text" '--work-dir "$STAGE_DIR"'
assert_contains "$source_text" 'VERIFY_ISO="$WORK/ooonana-full-i3.iso"'
assert_contains "$source_text" 'Copying ISO to WSL-native storage for QEMU'
assert_contains "$source_text" '--iso "$VERIFY_ISO"'
assert_contains "$source_text" '-cdrom "$VERIFY_ISO"'
assert_contains "$source_text" 'iso_sha256="$(sha256sum "$VERIFY_ISO"'
assert_contains "$source_text" "printf '%s  ooonana-full-i3.iso"
assert_contains "$source_text" 'rm -rf "$STAGE_DIR"'
assert_contains "$source_text" 'findmnt mount mountpoint'
assert_contains "$source_text" 'install mv python3 qemu-system-x86_64 realpath'
assert_contains "$source_text" 'stale i3.pkg dependency bundle'
assert_contains "$source_text" 'cached kernel has no resolved config'
assert_contains "$source_text" "KERNEL_FRAGMENT=\"\$ROOT/configs/kernel/ooonana-minimal-x86_64.fragment\""
assert_contains "$source_text" "grep -E '^CONFIG_[A-Z0-9_]+=' \"\$KERNEL_FRAGMENT\""
assert_contains "$source_text" 'cached kernel differs from requested option'
assert_contains "$source_text" 'release_input_fingerprint()'
assert_contains "$source_text" '.release-inputs.sha256'
assert_contains "$source_text" '.ooonana-rootfs-complete'
assert_contains "$source_text" 'resume stage is incomplete'
assert_contains "$source_text" 'resume stage inputs changed'
assert_contains "$source_text" 'need at least 20 GiB free for stage'
assert_contains "$source_text" "ooonana-full-i3-release.lock"
assert_contains "$source_text" "another Ooonana full-i3 release build is already running"
assert_contains "$source_text" "ooonana-service-watchdog"
assert_contains "$source_text" "ooonana-service-repair force-wifi"
assert_contains "$source_text" "ooonana-service-repair force-bluetooth"
assert_contains "$source_text" "/newroot/mnt/ooonana-live/boot-device"
assert_contains "$source_text" "persistence_mode=\"usb\""
assert_contains "$source_text" "class MediaWindow"
assert_contains "$source_text" "ooonana-media-control"
assert_contains "$source_text" 'QEMU_ACCEL="${OOONANA_QEMU_ACCEL:-}"'
assert_contains "$source_text" 'QEMU_ACCEL=kvm'
assert_contains "$source_text" 'QEMU_ACCEL=tcg,thread=multi'
assert_contains "$source_text" '-accel "$QEMU_ACCEL"'
assert_contains "$(<"$ROOT/scripts/build-full-i3-iso.sh")" 'OOONANA_MAX_ISO_BYTES:-4500000000'

printf 'ok rebuild-full-i3-release\n'
