#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILDER="$ROOT/scripts/build-ooonana-pdf-os.sh"
INJECTOR="$ROOT/scripts/inject-ooonana-pdf-root.sh"
PDF="$ROOT/docs/ooonana.pdf"
VM_TEST="$ROOT/scripts/test-ooonana-pdf-vm.js"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$BUILDER" ]] || fail "missing executable PDF OS builder"
[[ -x "$INJECTOR" ]] || fail "missing executable PDF root injector"
[[ -f "$VM_TEST" ]] || fail "missing PDF VM boot test"

help="$(bash "$BUILDER" --help)"
assert_contains "$help" "Build bootable Ooonana OS PDF"
assert_contains "$help" "docs/ooonana.pdf"
assert_contains "$help" "linuxpdf is GPLv3"
assert_contains "$help" "--prepare-only"
assert_contains "$help" "--lite"
assert_contains "$(<"$INJECTOR")" 'exec sudo bash "$0" "$TARGET_ROOT"'
assert_contains "$(<"$BUILDER")" "OOONANA_FRAMEBUFFER_CACHE"
assert_contains "$(<"$BUILDER")" "OOONANA_AMBER_PALETTE"
assert_contains "$(<"$BUILDER")" "OOONANA_MONO_FRAMEBUFFER"
assert_contains "$(<"$BUILDER")" "OOONANA_INDIRECT_WIDGETS"
assert_contains "$(<"$BUILDER")" "OOONANA_SERIAL_TERMINAL_LAYOUT"
assert_contains "$(<"$BUILDER")" "OOONANA_SERIAL_TERMINAL"
assert_contains "$(<"$BUILDER")" "OOONANA_SERIAL_CONSOLE_WRITE"
assert_contains "$(<"$BUILDER")" "OOONANA_BOOT_MESSAGE"
assert_contains "$(<"$BUILDER")" "OOONANA_VM_BATCH"
assert_contains "$(<"$BUILDER")" "OOONANA_TERMINAL_RENDER_BATCH"
assert_contains "$(<"$BUILDER")" "OOONANA_INTERACTIVE_ECHO"
assert_contains "$(<"$BUILDER")" "serial_output && vm_boot_complete"
assert_contains "$(<"$BUILDER")" "OOONANA_BOOT_HEARTBEAT"
assert_contains "$(<"$BUILDER")" "vm_boot_complete ? 2 : 8"
assert_contains "$(<"$BUILDER")" "Starting JavaScript..."
assert_contains "$(<"$BUILDER")" "terminal_write(str, true)"
assert_contains "$(<"$BUILDER")" "loglevel=7 ignore_loglevel"
assert_contains "$(<"$BUILDER")" "OOONANA_PDF_LITE_GENERATOR"
assert_contains "$(<"$BUILDER")" "gen_pdf_lite.py"
assert_contains "$(<"$BUILDER")" "Type command, press Enter"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

dry="$(bash "$BUILDER" --work-dir "$tmp/work" --out "$tmp/ooonana.pdf" --dry-run --force)"
assert_contains "$dry" "would build Ooonana OS PDF"
assert_contains "$dry" "git clone"
assert_contains "$dry" "OOONANA_SOURCE_ROOT="
assert_contains "$dry" "OOONANA_PDF_BITS="
assert_contains "$dry" "cp -f"

lite_dry="$(bash "$BUILDER" --work-dir "$tmp/lite-work" --dry-run --lite --force)"
assert_contains "$lite_dry" "ooonana-lite.pdf"
assert_contains "$lite_dry" "lite: 1"
assert_contains "$lite_dry" "OOONANA_PDF_LITE=1"

rootfs="$tmp/rootfs"
mkdir -p "$rootfs/bin" "$rootfs/usr/bin"
printf 'riscv-busybox\n' > "$rootfs/bin/busybox"
chmod 0755 "$rootfs/bin/busybox"
ln -s ../../bin/busybox "$rootfs/usr/bin/clear"
inject="$(bash "$INJECTOR" "$rootfs")"
assert_contains "$inject" "injected Ooonana PDF rootfs"
[[ "$(<"$rootfs/bin/busybox")" == "riscv-busybox" ]] || fail "package overlay replaced target busybox"
[[ ! -L "$rootfs/usr/bin/clear" ]] || fail "clear shim remained a busybox symlink"
[[ -x "$rootfs/usr/bin/ooonana" ]] || fail "missing injected ooonana CLI"
[[ -x "$rootfs/sbin/init" ]] || fail "missing injected init"
[[ -f "$rootfs/usr/share/ooonana/logo.txt" ]] || fail "missing injected logo"
[[ -f "$rootfs/etc/os-release" ]] || fail "missing injected os-release"
assert_contains "$(<"$rootfs/sbin/init")" "OOONANA_PDF_BOOT_OK"
assert_contains "$(<"$rootfs/sbin/init")" "stty cols 80 rows 30"
assert_contains "$(<"$rootfs/sbin/init")" "PDF Minimal 0.5 | pkg 0.8.21"
assert_contains "$(<"$rootfs/sbin/init")" "exec </dev/hvc0 >/dev/hvc0 2>&1"
assert_contains "$(<"$rootfs/sbin/init")" "--- Ooonana userspace ready ---"
assert_contains "$(<"$rootfs/root/.profile")" "ooonana help packages"
assert_contains "$(<"$rootfs/root/.profile")" "ooonana ai status"
assert_contains "$(<"$rootfs/etc/os-release")" 'PRETTY_NAME="Ooonana OS PDF Minimal"'
assert_contains "$(<"$rootfs/etc/os-release")" 'VERSION_ID="0.5-pdf"'
[[ -f "$rootfs/etc/ooonana/pdf-release" ]] || fail "missing PDF release metadata"
assert_contains "$(<"$rootfs/etc/ooonana/pdf-release")" 'OOONANA_PDF_PACKAGE_MANAGER="0.8.21"'

if [[ -f "$PDF" ]]; then
  head="$(LC_ALL=C head -c 5 "$PDF")"
  [[ "$head" == "%PDF-" ]] || fail "bad OS PDF header"
  pdf_text="$(LC_ALL=C strings "$PDF")"
  assert_contains "$pdf_text" "OoonanaPDF"
  assert_contains "$pdf_text" "Ooonana OS in PDF"
fi

printf 'ok ooonana-pdf-os\n'
