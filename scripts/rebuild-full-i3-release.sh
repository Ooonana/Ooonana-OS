#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${OOONANA_BUILD_DIR:-/var/tmp/ooonana-os/build}"
RELEASE_DIR="${OOONANA_RELEASE_DIR:-/var/tmp/ooonana-os/release}"
KERNEL_VERSION="${OOONANA_KERNEL_VERSION:-6.18.37}"
KERNEL_WORK="${OOONANA_KERNEL_WORK:-/var/tmp/ooonana-kernel-work}"
JOBS="${OOONANA_BUILD_JOBS:-$(nproc)}"
FORCE_KERNEL=0
SKIP_QEMU=0

usage() {
  cat <<'USAGE'
Build and verify Ooonana full-i3 release ISO.

Usage:
  scripts/rebuild-full-i3-release.sh [options]

Options:
  --work-dir PATH       Cached build directory
  --release-dir PATH    Release output directory
  --kernel-version VER  Cached Linux source version (default: 6.18.37)
  --kernel-work PATH    Fast local kernel workspace
  --jobs N              Kernel build jobs
  --force-kernel        Rebuild kernel even when output exists
  --skip-qemu           Skip runtime smoke; ISO remains structurally verified
  -h, --help            Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; shift 2 ;;
    --release-dir) RELEASE_DIR="$2"; shift 2 ;;
    --kernel-version) KERNEL_VERSION="$2"; shift 2 ;;
    --kernel-work) KERNEL_WORK="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --force-kernel) FORCE_KERNEL=1; shift ;;
    --skip-qemu) SKIP_QEMU=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'rebuild-full-i3-release: unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

die() {
  printf '[ooonana] ERROR: %s\n' "$*" >&2
  exit 1
}

run_step() {
  printf '\n[%s/7] %s\n' "$1" "$2"
}

build_kernel() {
  local archive="$WORK_DIR/linux-$KERNEL_VERSION.tar.xz"
  local output="$WORK_DIR/ooonana-kernel/vmlinuz-ooonana"

  if [[ -s "$output" && "$FORCE_KERNEL" -ne 1 ]]; then
    printf '[ooonana] reusing kernel: %s\n' "$output"
    return
  fi
  [[ -s "$archive" ]] ||
    die "missing cached kernel source: $archive (run scripts/fetch-kernel-source.sh first)"

  rm -rf "$KERNEL_WORK"
  mkdir -p "$KERNEL_WORK/linux"
  tar -xJf "$archive" --strip-components=1 -C "$KERNEL_WORK/linux"
  bash "$ROOT/scripts/build-kernel.sh" \
    --source "$KERNEL_WORK/linux" \
    --build-dir "$KERNEL_WORK/kernel-build" \
    --out-dir "$WORK_DIR/ooonana-kernel" \
    --jobs "$JOBS" \
    --force
  [[ -s "$output" ]] || die "kernel build produced no $output"
}

verify_rootfs_commands() {
  local command
  for command in \
    python3 ooonana chromium \
    nmcli NetworkManager iw wpa_supplicant rfkill \
    bluetoothctl bluetoothd \
    pulseaudio pactl pavucontrol \
    brightnessctl setxkbmap sensors \
    ooonana-wifi-panel ooonana-bluetooth-panel \
    ooonana-audio-panel ooonana-brightness-panel \
    ooonana-keyboard-panel ooonana-thermal-panel \
    ooonana-hardware-profile \
    sudo su doas; do
    if [[ -x "$WORK_DIR/full-i3-rootfs/usr/bin/$command" ||
          -x "$WORK_DIR/full-i3-rootfs/usr/sbin/$command" ||
          -x "$WORK_DIR/full-i3-rootfs/bin/$command" ||
          -x "$WORK_DIR/full-i3-rootfs/sbin/$command" ]]; then
      printf '[done] runtime command: %s\n' "$command"
    else
      die "rootfs command missing: $command"
    fi
  done
}

main() {
  local new_iso final_iso
  cd "$ROOT"
  mkdir -p "$WORK_DIR" "$RELEASE_DIR"
  [[ -f "$WORK_DIR/full-i3-repo/index.tsv" ]] ||
    die "missing package repo index: $WORK_DIR/full-i3-repo/index.tsv"

  new_iso="$RELEASE_DIR/ooonana-full-i3.iso.new"
  final_iso="$RELEASE_DIR/ooonana-full-i3.iso"
  rm -f "$new_iso"

  run_step 1 "Kernel"
  build_kernel

  run_step 2 "Scratch rootfs and initramfs"
  bash scripts/build-scratch-rootfs.sh --work-dir "$WORK_DIR" --force
  bash scripts/build-scratch-initramfs.sh --work-dir "$WORK_DIR" --force

  run_step 3 "Full-i3 rootfs"
  bash scripts/build-full-i3-rootfs.sh \
    --work-dir "$WORK_DIR" \
    --repo "$WORK_DIR/full-i3-repo" \
    --force
  verify_rootfs_commands

  run_step 4 "Live rootfs and installer disk"
  bash scripts/build-full-i3-live-initramfs.sh --work-dir "$WORK_DIR" --force
  bash scripts/build-full-i3-disk.sh --work-dir "$WORK_DIR" --force

  run_step 5 "Hybrid BIOS/UEFI ISO"
  bash scripts/build-full-i3-iso.sh \
    --work-dir "$WORK_DIR" \
    --iso "$new_iso" \
    --force

  run_step 6 "Verification"
  bash scripts/verify-rufus-iso.sh --iso "$new_iso" --edition full-i3
  if [[ "$SKIP_QEMU" -eq 0 ]]; then
    bash tests/qemu-service-smoke.sh --iso-runtime "$new_iso"
  else
    printf '[warn] QEMU runtime smoke skipped\n'
  fi

  run_step 7 "Promote release"
  mv -f "$new_iso" "$final_iso"
  (
    cd "$RELEASE_DIR"
    sha256sum ooonana-full-i3.iso >ooonana-full-i3.iso.sha256
  )
  sync
  ls -lh "$final_iso"
  cat "$RELEASE_DIR/ooonana-full-i3.iso.sha256"
  printf 'OOONANA_REBUILD_COMPLETE\n'
}

main "$@"
