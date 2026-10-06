#!/usr/bin/env bash
set -euo pipefail

ISO="${1:?usage: qemu-live-kernel-smoke.sh ISO KERNEL}"
KERNEL="${2:?usage: qemu-live-kernel-smoke.sh ISO KERNEL}"
QEMU_TIMEOUT="${OOONANA_QEMU_KERNEL_TIMEOUT:-130}"
QEMU_ACCEL="${OOONANA_QEMU_ACCEL:-}"

assert_kernel_smoke_result() {
  local fault_status=0
  [[ -s "$1" ]] || { echo 'kernel smoke: serial log missing/empty' >&2; return 1; }
  [[ "$2" -eq 0 ]] || { echo "kernel smoke: QEMU did not exit cleanly (rc=$2)" >&2; return 1; }
  LC_ALL=C grep -Eq 'OOONANA_[A-Z0-9_]*FAIL|Kernel panic|Oops:|(^|[[:space:]])BUG:' "$1" || fault_status=$?
  case "$fault_status" in
    0) echo 'kernel smoke: guest failure/panic recorded' >&2; return 1 ;;
    1) ;;
    *) echo 'kernel smoke: serial log could not be checked' >&2; return 1 ;;
  esac
  LC_ALL=C grep -q '^OOONANA_BOOT_OK[[:space:]]*$' "$1" || {
    echo 'kernel smoke: complete boot success marker missing' >&2
    return 1
  }
  # rcS smoke requests a reboot. Require actual kernel termination after boot,
  # not a stale/prefixed success string or QEMU exiting before guest completion.
  LC_ALL=C awk '
    /^OOONANA_BOOT_OK[[:space:]]*$/ { booted=1; next }
    booted && /^(\[[[:space:]]*[0-9.]+\][[:space:]]*)?reboot: (Restarting system|Power down)[[:space:]]*$/ { finished=1 }
    END { exit !finished }
  ' "$1" || {
    echo 'kernel smoke: kernel reboot/power-down after boot missing' >&2
    return 1
  }
}

[[ -f "$ISO" && -f "$KERNEL" ]] || { echo 'ISO or kernel missing' >&2; exit 1; }
for command in xorriso qemu-system-x86_64 timeout mktemp realpath; do
  command -v "$command" >/dev/null || { echo "missing: $command" >&2; exit 1; }
done
if [[ ! "$QEMU_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || (( QEMU_TIMEOUT < 60 )); then
  echo 'kernel smoke timeout must be an integer >= 60 seconds' >&2
  exit 1
fi
if [[ -z "$QEMU_ACCEL" ]]; then
  if [[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then
    QEMU_ACCEL=kvm
  else
    QEMU_ACCEL=tcg,thread=multi
  fi
fi

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
timeout "$QEMU_TIMEOUT" qemu-system-x86_64 \
  -accel "$QEMU_ACCEL" -audiodev none,id=ooonana-audio \
  -m 2048 -smp 2 -display none -serial "file:$smoke_dir/serial.log" \
  -monitor none -no-reboot \
  -drive "file=$ISO,format=raw,if=ide,media=cdrom,readonly=on" \
  -kernel "$KERNEL" -initrd "$smoke_dir/live-initramfs.cpio.gz" \
  -append 'console=tty0 console=ttyS0 panic=1 rdinit=/init ooonana.live=1 ooonana.edition=full-i3 ooonana.smoke=1'
qemu_exit=$?
set -e
grep -E 'OOONANA_BOOT_OK|OOONANA_.*FAIL|Kernel panic|VFS:|zram|reboot:' "$smoke_dir/serial.log" | tail -30 || true
if assert_kernel_smoke_result "$smoke_dir/serial.log" "$qemu_exit"; then
  echo OOONANA_NEW_KERNEL_BOOT_OK
else
  echo "OOONANA_NEW_KERNEL_BOOT_FAIL code=$qemu_exit" >&2
  if [[ -f "$smoke_dir/serial.log" ]]; then
    tail -60 "$smoke_dir/serial.log" >&2
  fi
  exit 1
fi
