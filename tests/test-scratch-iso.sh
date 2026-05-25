#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-scratch-iso.sh"

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

[[ -x "$SCRIPT" ]] || fail "missing executable scratch ISO builder"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana scratch boot ISO"
assert_contains "$help" "--kernel-rootfs"
assert_contains "$help" "--initramfs"
assert_contains "$help" "--iso"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin" "$tmp/kernel-rootfs/boot" "$tmp/build/ooonana-kernel"
touch "$tmp/kernel-rootfs/boot/vmlinuz-6.1.0-ooonana"
printf 'own kernel\n' > "$tmp/build/ooonana-kernel/vmlinuz-ooonana"
touch "$tmp/initramfs.cpio.gz" "$tmp/isolinux.bin" "$tmp/ldlinux.c32"

cat > "$tmp/bin/xorriso" <<'EOF'
#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    out="$1"
  fi
  shift || true
done
[ -n "$out" ] || exit 2
printf 'fake iso\n' > "$out"
EOF
chmod +x "$tmp/bin/xorriso"

PATH="$tmp/bin:$PATH" \
OOONANA_ISOLINUX_BIN="$tmp/isolinux.bin" \
OOONANA_LDLINUX_C32="$tmp/ldlinux.c32" \
bash "$SCRIPT" \
  --work-dir "$tmp/build" \
  --kernel-rootfs "$tmp/kernel-rootfs" \
  --initramfs "$tmp/initramfs.cpio.gz" \
  --iso "$tmp/ooonana-scratch.iso" \
  --smoke \
  --force >/dev/null

[[ -s "$tmp/ooonana-scratch.iso" ]] || fail "missing scratch ISO"
[[ -f "$tmp/build/scratch-iso-tree/boot/vmlinuz" ]] || fail "missing staged kernel"
[[ -f "$tmp/build/scratch-iso-tree/boot/initramfs.cpio.gz" ]] || fail "missing staged initramfs"
[[ -f "$tmp/build/scratch-iso-tree/isolinux/isolinux.cfg" ]] || fail "missing isolinux config"
[[ "$(<"$tmp/build/scratch-iso-tree/boot/vmlinuz")" == "own kernel" ]] || fail "scratch ISO must prefer Ooonana kernel"

cfg="$(<"$tmp/build/scratch-iso-tree/isolinux/isolinux.cfg")"
assert_contains "$cfg" "INITRD /boot/initramfs.cpio.gz"
assert_contains "$cfg" "rdinit=/init"
assert_contains "$cfg" "ooonana.smoke=1"
assert_not_contains "$cfg" "root=/dev/sr0"
assert_not_contains "$cfg" "systemd.unit"

printf 'ok scratch-iso\n'
