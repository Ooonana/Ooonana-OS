#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/tests/qemu-live-kernel-smoke.sh"
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

# Run the actual success gate, not a separately implemented approximation.
predicate="$(awk '/^assert_kernel_smoke_result\(\) \{/ { capture=1 }
  capture { print } capture && /^\}/ { exit }' "$SCRIPT")"
[[ -n "$predicate" ]] || fail 'kernel smoke result gate missing'
fixture="$(mktemp -d)"
trap 'rm -rf -- "$fixture"' EXIT
printf '%s\n' OOONANA_BOOT_OK '[40.0] reboot: Restarting system' >"$fixture/good.log"
awk '{ printf "%s\r\n", $0 }' "$fixture/good.log" >"$fixture/crlf.log"
sed 's/Restarting system/Power down/' "$fixture/good.log" >"$fixture/powerdown.log"
for fault in panic failure oops bug; do
  cp "$fixture/good.log" "$fixture/$fault.log"
done
printf '%s\n' 'Kernel panic - not syncing: fixture' >>"$fixture/panic.log"
printf '%s\n' OOONANA_STORAGE_FAIL >>"$fixture/failure.log"
printf '%s\n' 'Oops: fixture' >>"$fixture/oops.log"
printf '%s\n' '[41.0] BUG: fixture' >>"$fixture/bug.log"
grep -v '^OOONANA_BOOT_OK$' "$fixture/good.log" >"$fixture/no-success.log"
grep -v 'reboot:' "$fixture/good.log" >"$fixture/no-reboot.log"
sed 's/^OOONANA_BOOT_OK$/PREFIX_OOONANA_BOOT_OK/' "$fixture/good.log" >"$fixture/prefixed.log"
sed 's/^OOONANA_BOOT_OK$/OOONANA_BOOT_OK_MORE/' "$fixture/good.log" >"$fixture/suffixed.log"
sed 's/reboot:/PREFIX reboot:/' "$fixture/good.log" >"$fixture/fake-reboot.log"
printf '%s\n' '[40.0] reboot: Restarting system' OOONANA_BOOT_OK >"$fixture/wrong-order.log"
: >"$fixture/empty.log"

check_result() {
  bash -c 'eval "$1"; assert_kernel_smoke_result "$2" "$3"' probe \
    "$predicate" "$fixture/$1.log" "$2" >"$fixture/result.log" 2>&1
}
for accepted in good crlf powerdown; do
  check_result "$accepted" 0 || fail "valid completion rejected: $accepted"
done
for rejected in 'good 124' 'good 137' 'good 1' 'panic 0' 'failure 0' 'oops 0' \
  'bug 0' 'no-success 0' 'no-reboot 0' 'prefixed 0' 'suffixed 0' \
  'fake-reboot 0' 'wrong-order 0' 'empty 0' 'missing 0'; do
  read -r name status <<<"$rejected"
  if check_result "$name" "$status"; then
    fail "invalid kernel smoke accepted: $rejected"
  fi
done
# A failed first scan must not be mistaken for "no panic" even when later
# marker reads work. No actual file/device read faults needed.
if bash -c 'eval "$1"; scans=0
  grep() { if (( scans == 0 )); then scans=1; return 2; fi; command grep "$@"; }
  assert_kernel_smoke_result "$2" 0' probe "$predicate" "$fixture/good.log" \
  >"$fixture/result.log" 2>&1; then
  fail 'serial log read error accepted'
fi
source_text="$(<"$SCRIPT")"
# shellcheck disable=SC2016 # Match literal runtime variable references.
[[ "$source_text" == *'timeout "$QEMU_TIMEOUT" qemu-system-x86_64'* &&
   "$source_text" == *'-accel "$QEMU_ACCEL"'* &&
   "$source_text" == *'if assert_kernel_smoke_result "$smoke_dir/serial.log" "$qemu_exit"; then'* &&
   "$source_text" == *'-audiodev none,id=ooonana-audio'* ]] ||
  fail 'kernel smoke lacks wired result gate/bounded configurable QEMU/silent audio'
printf 'ok qemu-live-kernel-smoke (3 valid / 16 rejected)\n'
