#!/usr/bin/env bash
set -euo pipefail

ISO="${1:?usage: qemu-live-kernel-smoke.sh ISO KERNEL}"
KERNEL="${2:?usage: qemu-live-kernel-smoke.sh ISO KERNEL}"
[[ -f "$ISO" && -f "$KERNEL" ]] || { echo 'ISO or kernel missing' >&2; exit 1; }
for command in xorriso qemu-system-x86_64 timeout mktemp realpath; do
  command -v "$command" >/dev/null || { echo "missing: $command" >&2; exit 1; }
done

smoke_dir="$(mktemp -d /var/tmp/ooonana-boot-smoke.XXXXXXXX)"
cleanup() {
  if [[ "$(realpath "$smoke_dir")" == /var/tmp/ooonana-boot-smoke.* ]]; then
    rm -rf -- "$smoke_dir"
  fi
}
trap cleanup EXIT

xorriso -osirrox on -indev "$ISO" \
  -extract /boot/live-initramfs.cpio.gz "$smoke_dir/live-initramfs.cpio.gz" >/dev/null 2>&1
set +e
timeout 130 qemu-system-x86_64 \
  -m 2048 -smp 2 -display none -serial "file:$smoke_dir/serial.log" \
  -monitor none -no-reboot \
  -drive "file=$ISO,format=raw,if=ide,media=cdrom,readonly=on" \
  -kernel "$KERNEL" -initrd "$smoke_dir/live-initramfs.cpio.gz" \
  -append 'console=tty0 console=ttyS0 panic=1 rdinit=/init ooonana.live=1 ooonana.edition=full-i3 ooonana.smoke=1'
qemu_exit=$?
set -e
grep -E 'OOONANA_BOOT_OK|OOONANA_.*FAIL|Kernel panic|VFS:|zram' "$smoke_dir/serial.log" | tail -30 || true
if grep -q OOONANA_BOOT_OK "$smoke_dir/serial.log"; then
  echo OOONANA_NEW_KERNEL_BOOT_OK
else
  echo "OOONANA_NEW_KERNEL_BOOT_FAIL code=$qemu_exit" >&2
  tail -60 "$smoke_dir/serial.log" >&2
  exit 1
fi
