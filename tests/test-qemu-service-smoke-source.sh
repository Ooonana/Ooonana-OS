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
[[ "$source_text" == *'OOONANA_QEMU_SERVICE_TIMEOUT:-1800'* ]] ||
  fail "service smoke timeout is not configurable"
[[ "$source_text" == *'timeout "$QEMU_TIMEOUT" qemu-system-x86_64'* ]] ||
  fail "service smoke does not apply configured timeout"
[[ "$source_text" == *'OOONANA_QEMU_ACCEL'* ]] ||
  fail "service smoke accelerator is not configurable"
[[ "$source_text" == *'OOONANA_QEMU_MEMORY:-1536'* ]] ||
  fail "service smoke memory is not configurable"
[[ "$source_text" == *'-m "$QEMU_MEMORY"'* ]] ||
  fail "service smoke does not apply configured memory"
[[ "$source_text" == *'QEMU_ACCEL=kvm'* ]] ||
  fail "service smoke does not use available KVM"
[[ "$source_text" == *'QEMU_ACCEL=tcg,thread=multi'* ]] ||
  fail "service smoke lacks multi-threaded TCG fallback"
[[ "$source_text" == *'-accel "$QEMU_ACCEL"'* ]] ||
  fail "service smoke does not apply selected accelerator"
[[ "$source_text" == *'OOONANA_SERVICE_SMOKE_STEP'* ]] ||
  fail "service smoke lacks progress markers"
[[ "$source_text" == *'[qemu-service] %s'* ]] ||
  fail "service smoke does not stream progress markers"
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
[[ "$source_text" == *'stale unrelated PID suppressed watchdog startup'* &&
   "$source_text" == *'duplicate watchdog replaced owner metadata'* &&
   "$source_text" == *'watchdog did not exit after TERM'* ]] ||
  fail "service smoke missing watchdog lifecycle regressions"
[[ "$source_text" == *'health snapshot missed frozen BlueZ'* &&
   "$source_text" == *'watchdog did not recover frozen BlueZ endpoint'* ]] ||
  fail "service smoke missing frozen BlueZ regression"
[[ "$source_text" == *'OOONANA_SERVICE_SMOKE_FAIL: live init failure'* ]] ||
  fail "service smoke leaves failed live init waiting for timeout"
[[ "$source_text" == *'! grep -q '\''OOONANA_SERVICE_SMOKE_FAIL'\'''* ]] ||
  fail "service smoke does not report init failure before missing success"
[[ "$source_text" != *'exec switch_root /newroot /usr/bin/ooonana-service-smoke'* ]] ||
  fail "service smoke replaces real PID1 with a shell"
[[ "$source_text" == *'exec switch_root /newroot /sbin/init'* &&
   "$source_text" == *'::once:/usr/bin/ooonana-service-smoke'* &&
   "$source_text" == *'packaged init shutdown hook missing'* ]] ||
  fail "service smoke does not retain verified init shutdown handling"
[[ "$source_text" != *'bunana shutdown returned'* &&
   "$source_text" == *'bunana shutdown timed out'* ]] ||
  fail "service smoke rejects asynchronous shutdown or waits without a bound"

# Exercise actual host predicate without QEMU, power actions or host services.
fixture="$(mktemp -d)"
trap 'rm -rf -- "$fixture"' EXIT
predicate="$(awk '/^assert_service_smoke_result\(\) \{/ { capture=1 }
  capture { print } capture && /^\}/ { exit }' "$SCRIPT")"
[[ -n "$predicate" ]] || fail "missing service smoke result predicate"
printf '%s\n' OOONANA_SERVICE_SMOKE_OK OOONANA_BUNANA_SHUTDOWN_BEGIN \
  OOONANA_SHUTDOWN_CLEANUP_DONE '[60.0] reboot: Power down' >"$fixture/good.log"
printf '%s\n' OOONANA_SERVICE_SMOKE_OK OOONANA_BUNANA_SHUTDOWN_BEGIN \
  '[60.0] reboot: Power down' >"$fixture/no-cleanup.log"
printf '%s\n' OOONANA_SERVICE_SMOKE_OK OOONANA_BUNANA_SHUTDOWN_BEGIN \
  OOONANA_SHUTDOWN_CLEANUP_DONE >"$fixture/no-powerdown.log"
cp "$fixture/good.log" "$fixture/failure.log"
printf '%s\n' 'OOONANA_SERVICE_SMOKE_FAIL: forced poweroff' >>"$fixture/failure.log"
awk '{ printf "%s\r\n", $0 }' "$fixture/good.log" >"$fixture/crlf.log"
grep -v '^OOONANA_SERVICE_SMOKE_OK$' "$fixture/good.log" >"$fixture/no-success.log"
grep -v '^OOONANA_BUNANA_SHUTDOWN_BEGIN$' "$fixture/good.log" >"$fixture/no-request.log"
sed 's/^OOONANA_SERVICE_SMOKE_OK$/PREFIX_OOONANA_SERVICE_SMOKE_OK/' \
  "$fixture/good.log" >"$fixture/prefixed.log"
check_result() {
  sh -c 'fail() { echo "FAIL: $*" >&2; exit 1; }
    eval "$1"
    assert_service_smoke_result "$2" "$3"' probe "$predicate" "$fixture/$1.log" "$2" \
    >"$fixture/result.log" 2>&1
}
check_result good 0 || fail "valid orderly shutdown rejected"
check_result crlf 0 || fail "serial CRLF orderly shutdown rejected"
for rejected in 'good 124' 'good 1' 'no-cleanup 0' 'no-powerdown 0' 'failure 0' \
  'no-success 0' 'no-request 0' 'prefixed 0'; do
  read -r name status <<<"$rejected"
  if check_result "$name" "$status"; then
    fail "invalid shutdown accepted: $rejected"
  fi
done

printf 'ok qemu-service-smoke-source\n'
