#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-scratch-grub-iso.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable scratch GRUB ISO builder"

script_src="$(<"$SCRIPT")"
assert_contains "$script_src" "/usr/lib/grub/i386-pc"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana scratch GRUB ISO"
assert_contains "$help" "--kernel"
assert_contains "$help" "--initramfs"
assert_contains "$help" "--rootfs-image"
assert_contains "$help" "--disk-image"
assert_contains "$help" "--install"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin"
printf 'kernel\n' > "$tmp/vmlinuz"
printf 'initramfs\n' > "$tmp/initramfs.cpio.gz"
printf 'rootfs\n' > "$tmp/rootfs.ext4"
printf 'disk\n' > "$tmp/disk.raw"

cat > "$tmp/bin/grub-mkrescue" <<'EOF'
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
printf 'fake grub iso\n' > "$out"
EOF
chmod +x "$tmp/bin/grub-mkrescue"

PATH="$tmp/bin:$PATH" bash "$SCRIPT" \
  --work-dir "$tmp/build" \
  --kernel "$tmp/vmlinuz" \
  --initramfs "$tmp/initramfs.cpio.gz" \
  --rootfs-image "$tmp/rootfs.ext4" \
  --disk-image "$tmp/disk.raw" \
  --iso "$tmp/ooonana-grub.iso" \
  --install \
  --smoke \
  --force >/dev/null

[[ -s "$tmp/ooonana-grub.iso" ]] || fail "missing GRUB ISO"
[[ -f "$tmp/build/scratch-grub-iso-tree/boot/vmlinuz" ]] || fail "missing staged kernel"
[[ -f "$tmp/build/scratch-grub-iso-tree/boot/initramfs.cpio.gz" ]] || fail "missing staged initramfs"
[[ -f "$tmp/build/scratch-grub-iso-tree/images/ooonana-scratch-disk.raw" ]] || fail "missing staged disk image"
[[ -f "$tmp/build/scratch-grub-iso-tree/boot/grub/grub.cfg" ]] || fail "missing grub config"
[[ "$(<"$tmp/build/scratch-grub-iso-tree/images/ooonana-scratch-disk.raw")" == "disk" ]] || fail "wrong staged disk image"

cfg="$(<"$tmp/build/scratch-grub-iso-tree/boot/grub/grub.cfg")"
assert_contains "$cfg" "menuentry 'Ooonana OS'"
assert_contains "$cfg" "linux /boot/vmlinuz"
assert_contains "$cfg" "console=ttyS0"
assert_contains "$cfg" "rdinit=/init"
assert_contains "$cfg" "ooonana.install=1"
assert_contains "$cfg" "ooonana.install.target=/dev/vda"
assert_contains "$cfg" "ooonana.smoke=1"
assert_contains "$cfg" "initrd /boot/initramfs.cpio.gz"

printf 'ok scratch-grub-iso\n'
