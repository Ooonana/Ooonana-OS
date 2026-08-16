#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/tests/qemu-service-smoke.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

source_text="$(<"$SCRIPT")"
[[ "$source_text" == *'for bluetoothd_path in'* ]] ||
  fail "service smoke does not accept packaged bluetoothd path"
[[ "$source_text" == *'/usr/lib/bluetooth/bluetoothd'* ]] ||
  fail "service smoke missing Alpine bluetoothd path"
[[ "$source_text" == *'OOONANA_QEMU_SERVICE_TIMEOUT:-900'* ]] ||
  fail "service smoke timeout is not configurable"
[[ "$source_text" == *'timeout "$QEMU_TIMEOUT" qemu-system-x86_64'* ]] ||
  fail "service smoke does not apply configured timeout"
[[ "$source_text" == *'OOONANA_QEMU_ACCEL'* ]] ||
  fail "service smoke accelerator is not configurable"
[[ "$source_text" == *'QEMU_ACCEL=kvm'* ]] ||
  fail "service smoke does not use available KVM"
[[ "$source_text" == *'QEMU_ACCEL=tcg,thread=multi'* ]] ||
  fail "service smoke lacks multi-threaded TCG fallback"
[[ "$source_text" == *'-accel "$QEMU_ACCEL"'* ]] ||
  fail "service smoke does not apply selected accelerator"
[[ "$source_text" == *'OOONANA_SERVICE_SMOKE_STEP'* ]] ||
  fail "service smoke lacks progress markers"
[[ "$source_text" == *'ooonana-audio-start --restart'* ]] ||
  fail "service smoke does not exercise Ooonana audio startup"
[[ "$source_text" == *'file:///tmp/ooonana-chromium-input.html'* ]] ||
  fail "service smoke does not use deterministic Chromium input"
[[ "$source_text" != *'--disable-software-rasterizer'* ]] ||
  fail "service smoke disables Chromium software rendering"
[[ "$source_text" == *'audio default sink did not appear'* ]] ||
  fail "service smoke does not wait for audio device discovery"
[[ "$source_text" == *'placeholder machine ID'* ]] ||
  fail "service smoke does not reject placeholder machine ID"
[[ "$source_text" == *'D-Bus machine ID mismatch'* ]] ||
  fail "service smoke does not verify D-Bus machine ID"
[[ "$source_text" == *'service watchdog did not recover D-Bus, NetworkManager, and BlueZ'* ]] ||
  fail "service smoke does not verify daemon supervision"

printf 'ok qemu-service-smoke-source\n'
