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
assert_contains "$script_src" 'DISK_IMAGE_STAGED="ooonana-full-i3-disk.raw.gz"'
assert_contains "$script_src" 'ooonana.install.image=/mnt/install/images/$DISK_IMAGE_STAGED'
assert_contains "$script_src" "gzip -n -c"
assert_contains "$script_src" "Ooonana OS Full i3 Live"
assert_contains "$script_src" "Ooonana OS Full i3 Live (persistent USB)"
assert_contains "$script_src" "ooonana.persistence=1"
assert_contains "$script_src" 'VOLUME="OOONANAUSB"'
assert_contains "$script_src" "Write in DD Image mode"
assert_contains "$script_src" "OOONANA_PERSIST"
assert_contains "$script_src" "grub-mkrescue"
assert_contains "$script_src" "/usr/lib/grub/x86_64-efi"
assert_contains "$script_src" "hybrid BIOS/UEFI ISO"
[[ "$script_src" != *"insmod gfxmenu"* ]] || fail "full-i3 GRUB must not load gfxmenu"
[[ "$script_src" != *"set theme=/boot/grub/theme.txt"* ]] || fail "full-i3 GRUB must not load bitmap theme"
[[ "$script_src" != *"set gfxpayload=keep"* ]] || fail "full-i3 GRUB must not keep forced graphics payload"
[[ "$script_src" != *"set gfxmode="* ]] || fail "full-i3 GRUB must not force VM framebuffer size"
[[ "$script_src" != *"terminal_output gfxterm"* ]] || fail "full-i3 GRUB must use stable console output"
assert_contains "$script_src" "terminal_output console serial"

installer_src="$(<"$ROOT/scripts/build-scratch-rootfs.sh")"
assert_contains "$installer_src" "cmdline_value 'ooonana.install.image'"
assert_contains "$installer_src" "ooonana-scratch-disk.raw"
assert_contains "$installer_src" "*.gz)"
assert_contains "$installer_src" "gzip -dc"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana full-i3 live/installer ISO"
assert_contains "$help" "--disk-image"
assert_contains "$help" "--live-initramfs"
assert_contains "$help" "--live-rootfs-image"
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
printf 'live rootfs image\n' > "$tmp/live-rootfs.ext4"
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
  --live-rootfs-image "$tmp/live-rootfs.ext4" \
  --disk-image "$tmp/full.raw" \
  --iso "$tmp/ooonana-full-i3-normal.iso" \
  --force >/dev/null

normal_cfg="$(<"$tmp/build/full-i3-iso-tree/boot/grub/grub.cfg")"
assert_contains "$normal_cfg" "terminal_input console serial"
assert_contains "$normal_cfg" "terminal_output console serial"
[[ "$normal_cfg" != *"insmod gfxmenu"* ]] || fail "full-i3 GRUB config must not load gfxmenu"
[[ "$normal_cfg" != *"insmod gfxterm"* ]] || fail "full-i3 GRUB config must not use gfxterm"
[[ "$normal_cfg" != *"insmod font"* ]] || fail "full-i3 GRUB config must not load font path"
[[ "$normal_cfg" != *"set gfxpayload=keep"* ]] || fail "full-i3 GRUB config must not keep graphics payload"
[[ "$normal_cfg" != *"set gfxmode="* ]] || fail "full-i3 GRUB config must not force VM framebuffer size"
[[ "$normal_cfg" != *"terminal_output gfxterm"* ]] || fail "full-i3 GRUB config must not use gfxterm"
assert_contains "$normal_cfg" "set color_normal=yellow/black"
assert_contains "$normal_cfg" "set color_highlight=black/yellow"
assert_contains "$normal_cfg" "console=ttyS0 console=tty0 quiet loglevel=3"
assert_contains "$normal_cfg" "set default=0"
assert_contains "$normal_cfg" "set timeout=5"
[[ "$normal_cfg" != *"set theme=/boot/grub/theme.txt"* ]] || fail "full-i3 GRUB config must not load theme"
if command -v grub-script-check >/dev/null 2>&1; then
  grub-script-check "$tmp/build/full-i3-iso-tree/boot/grub/grub.cfg" || fail "invalid GRUB config"
fi
assert_contains "$normal_cfg" "cat /boot/grub/ooonana-logo.txt"
assert_contains "$normal_cfg" "menuentry 'Ooonana OS Full i3 Live'"
assert_contains "$normal_cfg" "menuentry 'Ooonana OS Full i3 Live (persistent USB)'"
assert_contains "$normal_cfg" "menuentry 'Install Ooonana OS Full i3'"
assert_contains "$normal_cfg" "menuentry 'Install Ooonana OS Full i3 (safe graphics)'"
assert_contains "$normal_cfg" "ooonana.live=1"
assert_contains "$normal_cfg" "ooonana.persistence=1"
assert_contains "$normal_cfg" "ooonana.install.target=auto"
assert_contains "$normal_cfg" "ooonana.install=1 ooonana.edition=full-i3"
assert_contains "$normal_cfg" "menuentry 'Install Ooonana OS Full i3'"
assert_contains "$normal_cfg" "menuentry 'Install Ooonana OS Full i3 (safe graphics)'"
assert_contains "$normal_cfg" "initrd /boot/live-initramfs.cpio.gz"
[[ "$normal_cfg" != *"initrd /boot/install-initramfs.cpio.gz"* ]] || fail "full-i3 install entries should boot live GUI installer"
[[ "$normal_cfg" != *"ooonana.smoke=1"* ]] || fail "normal full-i3 ISO must not auto-smoke/reboot"

PATH="$tmp/bin:$PATH" bash "$SCRIPT" \
  --work-dir "$tmp/build" \
  --kernel "$tmp/vmlinuz" \
  --initramfs "$tmp/initramfs.cpio.gz" \
  --live-initramfs "$tmp/live-initramfs.cpio.gz" \
  --live-rootfs-image "$tmp/live-rootfs.ext4" \
  --disk-image "$tmp/full.raw" \
  --iso "$tmp/ooonana-full-i3.iso" \
  --install-target /dev/vdb \
  --smoke \
  --force >/dev/null

[[ -s "$tmp/ooonana-full-i3.iso" ]] || fail "missing full-i3 ISO"
[[ -f "$tmp/build/full-i3-iso-tree/boot/vmlinuz" ]] || fail "missing staged kernel"
[[ -f "$tmp/build/full-i3-iso-tree/boot/install-initramfs.cpio.gz" ]] || fail "missing staged install initramfs"
[[ -f "$tmp/build/full-i3-iso-tree/boot/live-initramfs.cpio.gz" ]] || fail "missing staged live initramfs"
[[ -f "$tmp/build/full-i3-iso-tree/images/ooonana-full-i3-live-rootfs.ext4" ]] || fail "missing staged live rootfs image"
[[ -f "$tmp/build/full-i3-iso-tree/boot/grub/ooonana-logo.txt" ]] || fail "missing staged GRUB logo"
[[ -f "$tmp/build/full-i3-iso-tree/RUFUS.md" ]] || fail "missing staged Rufus note"
[[ -f "$tmp/build/full-i3-iso-tree/images/ooonana-full-i3-disk.raw.gz" ]] || fail "missing staged compressed full disk image"
[[ "$(gzip -dc "$tmp/build/full-i3-iso-tree/images/ooonana-full-i3-disk.raw.gz")" == "full disk" ]] || fail "wrong staged disk image"
[[ "$(<"$tmp/build/full-i3-iso-tree/boot/live-initramfs.cpio.gz")" == "live initramfs" ]] || fail "wrong staged live initramfs"
[[ "$(<"$tmp/build/full-i3-iso-tree/images/ooonana-full-i3-live-rootfs.ext4")" == "live rootfs image" ]] || fail "wrong staged live rootfs image"
assert_contains "$(<"$tmp/build/full-i3-iso-tree/RUFUS.md")" "Write in DD Image mode"
assert_contains "$(<"$tmp/build/full-i3-iso-tree/RUFUS.md")" "OOONANA_PERSIST"
assert_contains "$(<"$tmp/build/full-i3-iso-tree/RUFUS.md")" "live rootfs is stored outside initramfs"

cfg="$(<"$tmp/build/full-i3-iso-tree/boot/grub/grub.cfg")"
assert_contains "$cfg" "set default=2"
assert_contains "$cfg" "menuentry 'Ooonana OS Full i3 Live'"
assert_contains "$cfg" "menuentry 'Ooonana OS Full i3 Live (persistent USB)'"
assert_contains "$cfg" "menuentry 'Install Ooonana OS Full i3'"
assert_contains "$cfg" "menuentry 'Install Ooonana OS Full i3 (safe graphics)'"
assert_contains "$cfg" "ooonana.install=1"
assert_contains "$cfg" "ooonana.install.target=/dev/vdb"
assert_contains "$cfg" "ooonana.install.image=/mnt/install/images/ooonana-full-i3-disk.raw.gz"
assert_contains "$cfg" "nomodeset"
assert_contains "$cfg" "initrd /boot/live-initramfs.cpio.gz"
assert_contains "$cfg" "initrd /boot/install-initramfs.cpio.gz"
assert_contains "$cfg" "console=tty0 console=ttyS0"
[[ "$cfg" != *"quiet loglevel=3"* ]] || fail "smoke ISO must keep verbose console"
assert_contains "$cfg" "terminal_input console serial"
assert_contains "$cfg" "terminal_output console serial"
assert_contains "$cfg" "ooonana.smoke=1"

PATH="$tmp/bin:$PATH" bash "$SCRIPT" \
  --work-dir "$tmp/build" \
  --kernel "$tmp/vmlinuz" \
  --initramfs "$tmp/initramfs.cpio.gz" \
  --live-initramfs "$tmp/live-initramfs.cpio.gz" \
  --live-rootfs-image "$tmp/live-rootfs.ext4" \
  --disk-image "$tmp/full.raw" \
  --iso "$tmp/ooonana-full-i3-live-smoke.iso" \
  --smoke \
  --live-smoke \
  --force >/dev/null

live_smoke_cfg="$(<"$tmp/build/full-i3-iso-tree/boot/grub/grub.cfg")"
assert_contains "$live_smoke_cfg" "set default=0"
assert_contains "$live_smoke_cfg" "ooonana.live=1"
assert_contains "$live_smoke_cfg" "ooonana.smoke=1 ooonana.gui-smoke=1"
assert_contains "$live_smoke_cfg" "ooonana.persistence=1"
[[ "$live_smoke_cfg" != *"ooonana.install=1"*"ooonana.smoke=1"* ]] || fail "live smoke must not auto-install"

printf 'ok full-i3-iso\n'
