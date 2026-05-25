#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

assert_not_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" != *"$needle"* ]] || fail "unexpected: $needle"
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

cat > "$tmp/packages.list" <<'LIST'
# comment
ca-certificates

linux-image-amd64 # inline comment
 systemd-sysv
LIST

# shellcheck source=/dev/null
source "$ROOT/scripts/lib/common.sh"

mapfile -t packages < <(ooonana_read_package_profile "$tmp/packages.list")
[[ "${packages[*]}" == "ca-certificates linux-image-amd64 systemd-sysv" ]] || fail "package parser output: ${packages[*]}"

default_build_dir="$(HOME="$tmp/home" ooonana_default_build_dir)"
[[ "$default_build_dir" == "/var/tmp/ooonana-os/build" ]] || fail "default build dir: $default_build_dir"

custom_build_dir="$(OOONANA_BUILD_DIR="$tmp/custom" HOME="$tmp/home" ooonana_default_build_dir)"
[[ "$custom_build_dir" == "$tmp/custom" ]] || fail "custom build dir: $custom_build_dir"

build_help="$(bash "$ROOT/scripts/build-rootfs.sh" --help)"
assert_contains "$build_help" "Build Ooonana rootfs"
assert_contains "$build_help" "--suite"
assert_contains "$build_help" "--force"

deps_help="$(bash "$ROOT/scripts/install-wsl-deps.sh" --help)"
assert_contains "$deps_help" "grub-pc"
assert_contains "$deps_help" "parted"

run_help="$(bash "$ROOT/scripts/run-qemu.sh" --help)"
assert_contains "$run_help" "Boot Ooonana rootfs with QEMU"
assert_contains "$run_help" "--initramfs-boot"
assert_contains "$run_help" "--scratch-disk-boot"
assert_contains "$run_help" "--disk-boot"
assert_contains "$run_help" "--smoke"
assert_contains "$run_help" "--dry-run"

if grep -q 'chmod -R' "$ROOT/scripts/build-rootfs.sh"; then
  fail "build script must not recursively chmod rootfs"
fi
if grep -q 'mount --rbind' "$ROOT/scripts/build-rootfs.sh"; then
  fail "build script must not rbind host /dev or /sys in WSL"
fi
if grep -q 'devpts' "$ROOT/scripts/build-rootfs.sh"; then
  fail "build script must not mount devpts in WSL"
fi
grep -q 'chmod a+rwx "$WORK_DIR"' "$ROOT/scripts/build-rootfs.sh" || fail "build dir must be writable for QEMU logs"
grep -q 'chmod a+rw "$IMAGE"' "$ROOT/scripts/build-rootfs.sh" || fail "image must be writable for non-root QEMU"

mkdir -p "$tmp/rootfs/boot" "$tmp/build"
touch "$tmp/rootfs/boot/vmlinuz-6.1.0-ooonana"
touch "$tmp/rootfs/boot/initrd.img-6.1.0-ooonana"
touch "$tmp/build/ooonana-rootfs.ext4"

dry_run="$(bash "$ROOT/scripts/run-qemu.sh" --dry-run --smoke --rootfs "$tmp/rootfs" --image "$tmp/build/ooonana-rootfs.ext4")"
assert_contains "$dry_run" "qemu-system-x86_64"
assert_contains "$dry_run" "systemd.unit=ooonana-smoke.service"
assert_contains "$dry_run" "ooonana.smoke=1"
assert_contains "$dry_run" "root=/dev/vda"

touch "$tmp/build/ooonana-scratch-initramfs.cpio.gz"
initramfs_dry_run="$(bash "$ROOT/scripts/run-qemu.sh" --dry-run --smoke --initramfs-boot --rootfs "$tmp/rootfs" --initrd "$tmp/build/ooonana-scratch-initramfs.cpio.gz")"
assert_contains "$initramfs_dry_run" "qemu-system-x86_64"
assert_contains "$initramfs_dry_run" "rdinit=/init"
assert_contains "$initramfs_dry_run" "ooonana.smoke=1"
assert_contains "$initramfs_dry_run" "-initrd"
if [[ "$initramfs_dry_run" == *"root=/dev/vda"* ]]; then
  fail "scratch initramfs boot must not use Debian root disk"
fi

mkdir -p "$tmp/build/ooonana-kernel"
touch "$tmp/build/ooonana-kernel/vmlinuz-ooonana"
own_kernel_dry_run="$(OOONANA_BUILD_DIR="$tmp/build" bash "$ROOT/scripts/run-qemu.sh" --dry-run --smoke --initramfs-boot --rootfs "$tmp/rootfs" --initrd "$tmp/build/ooonana-scratch-initramfs.cpio.gz")"
assert_contains "$own_kernel_dry_run" "$tmp/build/ooonana-kernel/vmlinuz-ooonana"

scratch_disk_dry_run="$(OOONANA_BUILD_DIR="$tmp/build" bash "$ROOT/scripts/run-qemu.sh" --dry-run --smoke --scratch-disk-boot --image "$tmp/build/ooonana-rootfs.ext4" --rootfs "$tmp/rootfs")"
assert_contains "$scratch_disk_dry_run" "$tmp/build/ooonana-kernel/vmlinuz-ooonana"
assert_contains "$scratch_disk_dry_run" "root=/dev/vda"
assert_contains "$scratch_disk_dry_run" "init=/sbin/init"
assert_not_contains "$scratch_disk_dry_run" "-initrd"
assert_not_contains "$scratch_disk_dry_run" "systemd.unit"

touch "$tmp/build/ooonana-scratch-disk.raw"
self_boot_dry_run="$(OOONANA_BUILD_DIR="$tmp/build" bash "$ROOT/scripts/run-qemu.sh" --dry-run --smoke --disk-boot --image "$tmp/build/ooonana-scratch-disk.raw")"
assert_contains "$self_boot_dry_run" "qemu-system-x86_64"
assert_contains "$self_boot_dry_run" "file=$tmp/build/ooonana-scratch-disk.raw\\,format=raw\\,if=virtio"
assert_contains "$self_boot_dry_run" "-boot c"
assert_not_contains "$self_boot_dry_run" "-kernel"
assert_not_contains "$self_boot_dry_run" "-cdrom"

printf 'ok rootfs-qemu\n'
