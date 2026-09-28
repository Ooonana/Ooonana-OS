#!/usr/bin/env bash
set -euo pipefail

ISO="${1:?usage: qemu-desktop-capture.sh ISO OUTPUT.png}"
OUTPUT="${2:?usage: qemu-desktop-capture.sh ISO OUTPUT.png}"
[[ -f "$ISO" && ! -e "$OUTPUT" ]] || { echo 'ISO missing or output exists' >&2; exit 1; }
for command in qemu-system-x86_64 nc convert; do command -v "$command" >/dev/null || exit 1; done

work="$(mktemp -d /var/tmp/ooonana-desktop-capture.XXXXXXXX)"
qemu_pid=""
cleanup() {
  if [[ -n "$qemu_pid" ]]; then
    kill "$qemu_pid" 2>/dev/null || true
    wait "$qemu_pid" 2>/dev/null || true
  fi
  if [[ "$(realpath "$work")" == /var/tmp/ooonana-desktop-capture.* ]]; then
    rm -rf -- "$work"
  fi
}
trap cleanup EXIT

cp "$ISO" "$work/ooonana-full-i3.iso"
ISO="$work/ooonana-full-i3.iso"
qemu-system-x86_64 -accel tcg,thread=multi -machine q35 -m 2048 -smp 2 -display none \
  -serial "file:$work/serial.log" -monitor "unix:$work/monitor,server,nowait" \
  -boot d -cdrom "$ISO" &
qemu_pid=$!
ready=0
for _attempt in $(seq 1 300); do
  if grep -q 'Ooonana full i3 rootfs' "$work/serial.log" 2>/dev/null; then ready=1; break; fi
  kill -0 "$qemu_pid" 2>/dev/null || break
  sleep 1
done
[[ "$ready" -eq 1 ]] || { tail -40 "$work/serial.log" >&2; exit 1; }
sleep "${OOONANA_DESKTOP_CAPTURE_DELAY:-75}"
if [[ "${OOONANA_DESKTOP_DISMISS_SETUP:-0}" == 1 ]]; then
  printf 'sendkey meta_l-shift-q\n' | nc -U -w 5 "$work/monitor" >/dev/null
  sleep 5
fi
printf 'screendump %s\n' "$work/screen.ppm" | nc -U -w 5 "$work/monitor" >/dev/null
[[ -s "$work/screen.ppm" ]] || { echo 'QEMU screendump missing' >&2; exit 1; }
convert "$work/screen.ppm" "$OUTPUT"
file "$OUTPUT"
