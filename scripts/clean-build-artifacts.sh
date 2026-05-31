#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
YES=0
DRY_RUN=0
KEEP_SOURCE=0
ORIGINAL_ARGS=("$@")

usage() {
  cat <<'USAGE'
Clean Ooonana build artifacts.

Usage:
  scripts/clean-build-artifacts.sh [options]

Options:
  --work-dir PATH  Build directory (default: /var/tmp/ooonana-os/build)
  --keep-source    Keep Linux source/archive and kernel build cache
  --dry-run        Print removals only
  --yes            Required before deleting anything
  -h, --help       Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; shift 2 ;;
    --keep-source) KEEP_SOURCE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --yes) YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

resolve_path() {
  local path="$1"
  local parent base
  parent="$(dirname "$path")"
  base="$(basename "$path")"
  mkdir -p "$parent"
  printf '%s/%s\n' "$(cd "$parent" && pwd -P)" "$base"
}

assert_safe_work_dir() {
  local real="$1"
  case "$real" in
    */ooonana-os/build|*/Ooonana/ooonana-os/build|*/OoonanaOS/build) ;;
    *) ooonana_die "refusing unsafe build dir: $real" ;;
  esac
}

remove_path() {
  local path="$1"
  [[ -e "$path" ]] || return 0
  if [[ "$DRY_RUN" -eq 1 ]]; then
    ooonana_print_command rm -rf "$path"
  else
    rm -rf "$path"
    ooonana_log "removed: $path"
  fi
}

main() {
  ooonana_require_linux
  local real_work_dir item
  real_work_dir="$(resolve_path "$WORK_DIR")"
  assert_safe_work_dir "$real_work_dir"

  if [[ "$YES" -ne 1 ]]; then
    ooonana_die "use --yes to clean: $real_work_dir"
  fi
  if [[ "$DRY_RUN" -ne 1 ]]; then
    ooonana_reexec_as_root "${ORIGINAL_ARGS[@]}"
  fi

  local generated_items=(
    rootfs
    ooonana-rootfs.ext4
    ooonana.iso
    iso-tree
    install.ext4
    scratch-rootfs
    ooonana-scratch.ext4
    ooonana-scratch-initramfs.cpio.gz
    scratch-iso-tree
    ooonana-scratch.iso
    scratch-grub-iso-tree
    ooonana-scratch-grub.iso
    ooonana-scratch-disk.raw
    install-scratch.raw
    install-scratch-boot.raw
    scratch-disk-mnt
    ooonana-wsl-rootfs.tar.gz
    qemu-smoke.log
    qemu-*.log
    ooonana-kernel
  )

  if [[ "$KEEP_SOURCE" -ne 1 ]]; then
    generated_items+=(kernel-build linux linux-*.tar.xz)
  fi

  for item in "${generated_items[@]}"; do
    for path in "$real_work_dir"/$item; do
      remove_path "$path"
    done
  done
}

main "$@"
