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
assert_contains "$help" "OOONANA_AUTO_REBUILD_KERNEL=0"
assert_contains "$help" "OOONANA_KERNEL_WORK_DIR=PATH"
assert_contains "$help" "OOONANA_RELEASE_KERNEL_JOBS=N"

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
assert_contains "$source_text" 'STAGED_ISO="$STAGE_DIR/ooonana-full-i3.iso.new"'
assert_contains "$source_text" '--iso "$STAGED_ISO"'
assert_contains "$source_text" 'Building in WSL-native storage'
assert_contains "$source_text" 'VERIFY_ISO="$WORK/ooonana-full-i3.iso"'
assert_contains "$source_text" 'Copying ISO to WSL-native storage for QEMU'
assert_contains "$source_text" '--iso "$VERIFY_ISO"'
assert_contains "$source_text" '-cdrom "$VERIFY_ISO"'
assert_contains "$source_text" 'iso_sha256="$(sha256sum "$VERIFY_ISO"'
assert_contains "$source_text" 'Copying verified ISO to release storage'
assert_contains "$source_text" 'release ISO copy is incomplete'
assert_contains "$source_text" "printf '%s  ooonana-full-i3.iso"
assert_contains "$source_text" 'rm -rf "$STAGE_DIR"'
assert_contains "$source_text" 'findmnt mount mountpoint'
assert_contains "$source_text" 'install mv python3 qemu-system-x86_64 realpath'
assert_contains "$source_text" 'stale i3.pkg dependency bundle'
assert_contains "$source_text" 'check-release-repo.py'
assert_contains "$source_text" '--core-version "$source_core_version"'
assert_contains "$source_text" 'KERNEL_WORK_DIR="${OOONANA_KERNEL_WORK_DIR:-/var/tmp/ooonana-kernel-work}"'
assert_contains "$source_text" 'KERNEL_SOURCE_VERSION="${OOONANA_KERNEL_SOURCE_VERSION:-6.18.37}"'
assert_contains "$source_text" 'KERNEL_JOBS="${OOONANA_RELEASE_KERNEL_JOBS:-${OOONANA_KERNEL_JOBS:-2}}"'
assert_contains "$source_text" 'AUTO_REBUILD_KERNEL="${OOONANA_AUTO_REBUILD_KERNEL:-1}"'
assert_contains "$source_text" 'kernel_cache_matches_fragment()'
assert_contains "$source_text" 'refresh_cached_kernel()'
assert_contains "$source_text" 'cached kernel has no resolved config'
assert_contains "$source_text" "KERNEL_FRAGMENT=\"\$ROOT/configs/kernel/ooonana-minimal-x86_64.fragment\""
assert_contains "$source_text" "# CONFIG_[A-Z0-9_]+ is not set"
assert_contains "$source_text" 'cached kernel differs from requested option'
assert_contains "$source_text" 'bash "$ROOT/scripts/fetch-kernel-source.sh"'
assert_contains "$source_text" 'fetch_args+=(--tarball "$BUILD_DIR/linux-$KERNEL_SOURCE_VERSION.tar.xz")'
assert_contains "$source_text" 'bash "$ROOT/scripts/build-kernel.sh"'
assert_contains "$source_text" '--config-fragment "$KERNEL_FRAGMENT"'
assert_contains "$source_text" '--jobs "$KERNEL_JOBS"'
assert_contains "$source_text" 'normal release run rebuilds automatically'
assert_contains "$source_text" 'automatic kernel rebuild is disabled'
assert_contains "$source_text" 'kernel rebuild needs command'
assert_contains "$source_text" 'need at least 20 GiB free for kernel work'
assert_contains "$source_text" 'release_input_fingerprint()'
assert_contains "$source_text" '.release-inputs.sha256'
assert_contains "$source_text" '.ooonana-rootfs-complete'
assert_contains "$source_text" 'if [[ -s "$STAGE_DIR/ooonana-full-i3-rootfs.tar.gz" ]]'
assert_contains "$source_text" 'resume stage is incomplete'
assert_contains "$source_text" 'Recovering completed rootfs after interrupted optional export'
assert_contains "$source_text" 'resume stage inputs changed'
assert_contains "$source_text" 'OOONANA_EXPORT_ROOTFS_TARBALL:-auto'
assert_contains "$source_text" 'Skipping optional rootfs tarball export'
assert_contains "$source_text" 'rootfs_cache_part'
assert_contains "$source_text" 'optional rootfs tarball export failed; continuing ISO build'
assert_contains "$source_text" 'need at least 8 GiB free in $BUILD_DIR'
assert_contains "$source_text" 'need at least 20 GiB free for stage'
assert_contains "$source_text" "ooonana-full-i3-release.lock"
assert_contains "$source_text" "another Ooonana full-i3 release build is already running"
assert_contains "$source_text" "ooonana-service-watchdog"
assert_contains "$source_text" "ooonana-service-repair force-wifi"
assert_contains "$source_text" "ooonana-service-repair force-bluetooth"
assert_contains "$source_text" 'die "Wi-Fi UI uses invalid GENERAL.MANAGED field"'
assert_contains "$source_text" 'die "supplicant daemon still uses conflicting D-Bus mode"'
assert_contains "$source_text" 'die "live initramfs writes state into ephemeral /run"'
assert_contains "$source_text" "/newroot/mnt/ooonana-live/boot-device"
assert_contains "$source_text" "persistence_mode=\"usb\""
assert_contains "$source_text" "class MediaWindow"
assert_contains "$source_text" "ooonana-media-control"
assert_contains "$source_text" 'bash "$ROOT/tests/test-full-i3-live-initramfs.sh"'
assert_contains "$source_text" 'QEMU_ACCEL="${OOONANA_QEMU_ACCEL:-}"'
assert_contains "$source_text" 'QEMU_ACCEL=kvm'
assert_contains "$source_text" 'QEMU_ACCEL=tcg,thread=multi'
assert_contains "$source_text" '-accel "$QEMU_ACCEL"'
assert_contains "$(<"$ROOT/scripts/build-full-i3-iso.sh")" 'OOONANA_MAX_ISO_BYTES:-4500000000'

fingerprint_work="$(mktemp -d)"
trap 'rm -rf "$fingerprint_work"' EXIT
ROOT="$fingerprint_work/source"
REPO="$fingerprint_work/repo"
KERNEL="$fingerprint_work/kernel"
KERNEL_CONFIG="$fingerprint_work/kernel-config"
mkdir -p "$ROOT/branding" "$ROOT/packages/ooonana" "$REPO"
for input in configs/packages/full-i3.list scripts/build-scratch-rootfs.sh scripts/build-scratch-initramfs.sh scripts/build-full-i3-rootfs.sh scripts/build-full-i3-live-initramfs.sh scripts/lib/live-boot-storage.sh scripts/lib/live-persistence-file.sh scripts/lib/live-shutdown.sh scripts/build-full-i3-disk.sh scripts/build-full-i3-iso.sh scripts/install-intel-wireless-firmware.sh; do
  install -D -m 0644 /dev/null "$ROOT/$input"
done
touch "$KERNEL" "$KERNEL_CONFIG" "$REPO/SHA256SUMS" "$REPO/i3.pkg"
unset OOONANA_PERSONAL_CURSOR_DIR OOONANA_PERSONAL_CURSOR_SIZE
eval "$(sed -n '/^release_input_fingerprint() {$/,/^}$/p' "$SCRIPT")"
fingerprint_before="$(release_input_fingerprint)"
mkdir -p "$ROOT/packages/ooonana/usr/lib/ooonana/ui/__pycache__"
printf 'generated cache\n' >"$ROOT/packages/ooonana/usr/lib/ooonana/ui/__pycache__/module.pyc"
[[ "$(release_input_fingerprint)" == "$fingerprint_before" ]] || fail "Python cache changes release inputs"
printf 'storage policy change\n' >"$ROOT/scripts/lib/live-boot-storage.sh"
[[ "$(release_input_fingerprint)" != "$fingerprint_before" ]] || fail "Live storage helper missing from release inputs"
fingerprint_before="$(release_input_fingerprint)"
printf 'file setup policy change\n' >"$ROOT/scripts/lib/live-persistence-file.sh"
[[ "$(release_input_fingerprint)" != "$fingerprint_before" ]] || fail "Persistence file helper missing from release inputs"
fingerprint_before="$(release_input_fingerprint)"
printf 'RAM shutdown policy change\n' >"$ROOT/scripts/lib/live-shutdown.sh"
[[ "$(release_input_fingerprint)" != "$fingerprint_before" ]] || fail "RAM shutdown helper missing from release inputs"
fingerprint_before="$(release_input_fingerprint)"
printf 'real source\n' >"$ROOT/packages/ooonana/usr/lib/ooonana/ui/module.py"
[[ "$(release_input_fingerprint)" != "$fingerprint_before" ]] || fail "Native source missing from release inputs"
OOONANA_PERSONAL_CURSOR_DIR="$fingerprint_work/personal-cursor"
mkdir -p "$OOONANA_PERSONAL_CURSOR_DIR"
printf '19\n' >"$OOONANA_PERSONAL_CURSOR_DIR/cursor-size"
fingerprint_before="$(release_input_fingerprint)"
OOONANA_PERSONAL_CURSOR_SIZE=20
[[ "$(release_input_fingerprint)" != "$fingerprint_before" ]] || fail "Personal cursor size missing from release inputs"
printf 'ok rebuild-full-i3-release\n'
PYTHONDONTWRITEBYTECODE=1 python3 "$(dirname "$SCRIPT")/../tests/test-release-repo.py"
