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
assert_contains "$script_src" "Ooonana OS Full i3 Live"
assert_contains "$script_src" "OOONANA_FULL_I3"
assert_contains "$script_src" "grub-mkrescue"
assert_contains "$script_src" "/usr/lib/grub/x86_64-efi"
assert_contains "$script_src" "hybrid BIOS/UEFI ISO"

installer_src="$(<"$ROOT/scripts/build-scratch-rootfs.sh")"
assert_contains "$installer_src" "cmdline_value 'ooonana.install.image'"
assert_contains "$installer_src" "ooonana-scratch-disk.raw"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana full-i3 live/installer ISO"
assert_contains "$help" "--disk-image"
assert_contains "$help" "--live-initramfs"
assert_contains "$help" "--iso"
assert_contains "$help" "--install-target"
assert_contains "$help" "--live-smoke"
assert_contains "$help" "--uefi"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin"
printf 'kernel\n' > "$tmp/vmlinuz"
printf 'initramfs\n' > "$tmp/initramfs.cpio.gz"
printf 'live initramfs\n' > "$tmp/live-initramfs.cpio.gz"
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
  --live-initramfs "$tmp/live-initramfs.cpio.gz" \
  --disk-image "$tmp/full.raw" \
  --iso "$tmp/ooonana-full-i3-normal.iso" \
  --force >/dev/null

normal_cfg="$(<"$tmp/build/full-i3-iso-tree/boot/grub/grub.cfg")"
assert_contains "$normal_cfg" "terminal_input console serial"
assert_contains "$normal_cfg" "terminal_output console serial"
assert_contains "$normal_cfg" "console=ttyS0 console=tty0"
assert_contains "$normal_cfg" "set default=0"
assert_contains "$normal_cfg" "menuentry 'Ooonana OS Full i3 Live'"
assert_contains "$normal_cfg" "menuentry 'Install Ooonana OS Full i3'"
assert_contains "$normal_cfg" "ooonana.live=1"
assert_contains "$normal_cfg" "ooonana.install.target=auto"
[[ "$normal_cfg" != *"ooonana.smoke=1"* ]] || fail "normal full-i3 ISO must not auto-smoke/reboot"

PATH="$tmp/bin:$PATH" bash "$SCRIPT" \
  --work-dir "$tmp/build" \
  --kernel "$tmp/vmlinuz" \
  --initramfs "$tmp/initramfs.cpio.gz" \
  --live-initramfs "$tmp/live-initramfs.cpio.gz" \
  --disk-image "$tmp/full.raw" \
  --iso "$tmp/ooonana-full-i3.iso" \
  --install-target /dev/vdb \
  --smoke \
  --force >/dev/null

[[ -s "$tmp/ooonana-full-i3.iso" ]] || fail "missing full-i3 ISO"
[[ -f "$tmp/build/full-i3-iso-tree/boot/vmlinuz" ]] || fail "missing staged kernel"
[[ -f "$tmp/build/full-i3-iso-tree/boot/install-initramfs.cpio.gz" ]] || fail "missing staged install initramfs"
[[ -f "$tmp/build/full-i3-iso-tree/boot/live-initramfs.cpio.gz" ]] || fail "missing staged live initramfs"
[[ -f "$tmp/build/full-i3-iso-tree/images/ooonana-full-i3-disk.raw" ]] || fail "missing staged full disk image"
[[ "$(<"$tmp/build/full-i3-iso-tree/images/ooonana-full-i3-disk.raw")" == "full disk" ]] || fail "wrong staged disk image"
[[ "$(<"$tmp/build/full-i3-iso-tree/boot/live-initramfs.cpio.gz")" == "live initramfs" ]] || fail "wrong staged live initramfs"

cfg="$(<"$tmp/build/full-i3-iso-tree/boot/grub/grub.cfg")"
assert_contains "$cfg" "set default=1"
assert_contains "$cfg" "menuentry 'Ooonana OS Full i3 Live'"
assert_contains "$cfg" "menuentry 'Install Ooonana OS Full i3'"
assert_contains "$cfg" "ooonana.install=1"
assert_contains "$cfg" "ooonana.install.target=/dev/vdb"
assert_contains "$cfg" "ooonana.install.image=/mnt/install/images/ooonana-full-i3-disk.raw"
assert_contains "$cfg" "initrd /boot/live-initramfs.cpio.gz"
assert_contains "$cfg" "initrd /boot/install-initramfs.cpio.gz"
assert_contains "$cfg" "console=tty0 console=ttyS0"
assert_contains "$cfg" "terminal_input console serial"
assert_contains "$cfg" "terminal_output console serial"
assert_contains "$cfg" "ooonana.smoke=1"

PATH="$tmp/bin:$PATH" bash "$SCRIPT" \
  --work-dir "$tmp/build" \
  --kernel "$tmp/vmlinuz" \
  --initramfs "$tmp/initramfs.cpio.gz" \
  --live-initramfs "$tmp/live-initramfs.cpio.gz" \
  --disk-image "$tmp/full.raw" \
  --iso "$tmp/ooonana-full-i3-live-smoke.iso" \
  --smoke \
  --live-smoke \
  --force >/dev/null

live_smoke_cfg="$(<"$tmp/build/full-i3-iso-tree/boot/grub/grub.cfg")"
assert_contains "$live_smoke_cfg" "set default=0"
assert_contains "$live_smoke_cfg" "ooonana.live=1"
assert_contains "$live_smoke_cfg" "ooonana.smoke=1 ooonana.gui-smoke=1"
[[ "$live_smoke_cfg" != *"ooonana.install=1"*"ooonana.smoke=1"* ]] || fail "live smoke must not auto-install"

printf 'ok full-i3-iso\n'
