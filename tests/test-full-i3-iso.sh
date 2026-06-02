#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-full-i3-iso.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable full-i3 ISO builder"

script_src="$(<"$SCRIPT")"
assert_contains "$script_src" "ooonana.install.image=/mnt/install/images/ooonana-full-i3-disk.raw"
assert_contains "$script_src" "OOONANA_FULL_I3"
assert_contains "$script_src" "grub-mkrescue"

installer_src="$(<"$ROOT/scripts/build-scratch-rootfs.sh")"
assert_contains "$installer_src" "cmdline_value 'ooonana.install.image'"
assert_contains "$installer_src" "ooonana-scratch-disk.raw"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana full-i3 installer ISO"
assert_contains "$help" "--disk-image"
assert_contains "$help" "--iso"
assert_contains "$help" "--install-target"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin"
printf 'kernel\n' > "$tmp/vmlinuz"
printf 'initramfs\n' > "$tmp/initramfs.cpio.gz"
printf 'full disk\n' > "$tmp/full.raw"

cat > "$tmp/bin/grub-mkrescue" <<'FAKE'
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
printf 'fake full iso\n' > "$out"
FAKE
chmod +x "$tmp/bin/grub-mkrescue"

PATH="$tmp/bin:$PATH" bash "$SCRIPT" \
  --work-dir "$tmp/build" \
  --kernel "$tmp/vmlinuz" \
  --initramfs "$tmp/initramfs.cpio.gz" \
  --disk-image "$tmp/full.raw" \
  --iso "$tmp/ooonana-full-i3.iso" \
  --install-target /dev/vdb \
  --smoke \
  --force >/dev/null

[[ -s "$tmp/ooonana-full-i3.iso" ]] || fail "missing full-i3 ISO"
[[ -f "$tmp/build/full-i3-iso-tree/boot/vmlinuz" ]] || fail "missing staged kernel"
[[ -f "$tmp/build/full-i3-iso-tree/boot/initramfs.cpio.gz" ]] || fail "missing staged initramfs"
[[ -f "$tmp/build/full-i3-iso-tree/images/ooonana-full-i3-disk.raw" ]] || fail "missing staged full disk image"
[[ "$(<"$tmp/build/full-i3-iso-tree/images/ooonana-full-i3-disk.raw")" == "full disk" ]] || fail "wrong staged disk image"

cfg="$(<"$tmp/build/full-i3-iso-tree/boot/grub/grub.cfg")"
assert_contains "$cfg" "menuentry 'Ooonana OS Full i3 Installer'"
assert_contains "$cfg" "ooonana.install=1"
assert_contains "$cfg" "ooonana.install.target=/dev/vdb"
assert_contains "$cfg" "ooonana.install.image=/mnt/install/images/ooonana-full-i3-disk.raw"
assert_contains "$cfg" "ooonana.smoke=1"

printf 'ok full-i3-iso\n'
