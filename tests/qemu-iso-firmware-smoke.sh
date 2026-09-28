#!/usr/bin/env bash
set -euo pipefail

ISO="${1:?usage: qemu-iso-firmware-smoke.sh ISO}"
[[ -f "$ISO" ]] || { echo "ISO missing: $ISO" >&2; exit 1; }
command -v qemu-system-x86_64 >/dev/null || exit 1
[[ -f /usr/share/ovmf/OVMF.fd ]] || { echo 'OVMF firmware missing' >&2; exit 1; }

smoke_dir="$(mktemp -d /var/tmp/ooonana-firmware-smoke.XXXXXXXX)"
qemu_pid=""
cleanup() {
  if [[ -n "$qemu_pid" ]]; then
    kill "$qemu_pid" 2>/dev/null || true
    wait "$qemu_pid" 2>/dev/null || true
  fi
  if [[ "$(realpath "$smoke_dir")" == /var/tmp/ooonana-firmware-smoke.* ]]; then
    rm -rf -- "$smoke_dir"
  fi
}
trap cleanup EXIT

cp "$ISO" "$smoke_dir/ooonana-full-i3.iso"
ISO="$smoke_dir/ooonana-full-i3.iso"
boot_wait="${OOONANA_FIRMWARE_SMOKE_TIMEOUT:-300}"
for mode in bios uefi; do
  serial_log="$smoke_dir/$mode.log"
  firmware=()
  if [[ "$mode" == uefi ]]; then
    firmware=(-bios /usr/share/ovmf/OVMF.fd)
  fi
  qemu-system-x86_64 \
    -accel tcg,thread=multi -machine q35 -m 2048 -smp 2 \
    -display none -serial "file:$serial_log" -monitor none -no-reboot \
    -boot d -cdrom "$ISO" \
    "${firmware[@]}" &
  qemu_pid=$!
  ready=0
  for _attempt in $(seq 1 "$boot_wait"); do
    if grep -q 'Ooonana full i3 rootfs' "$serial_log" 2>/dev/null; then
      ready=1
      break
    fi
    if grep -q 'Kernel panic\|OOONANA_.*FAIL' "$serial_log" 2>/dev/null; then
      break
    fi
    kill -0 "$qemu_pid" 2>/dev/null || break
    sleep 1
  done
  if [[ "$ready" -ne 1 ]]; then
    echo "OOONANA_${mode^^}_ISO_BOOT_FAIL" >&2
    tail -50 "$serial_log" >&2 || true
    exit 1
  fi
  echo "OOONANA_${mode^^}_ISO_BOOT_OK"
  kill "$qemu_pid" 2>/dev/null || true
  wait "$qemu_pid" 2>/dev/null || true
  qemu_pid=""
done
