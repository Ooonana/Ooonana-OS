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
assert_contains "$script_src" "/usr/lib/grub/x86_64-efi"
assert_contains "$script_src" "hybrid BIOS/UEFI ISO"
assert_contains "$script_src" "Ooonana OS Minimal"
assert_contains "$script_src" "ooonana-logo.txt"
assert_contains "$script_src" 'VOLUME="OOONANAMIN"'
assert_contains "$script_src" "Write in ISO Image mode (Recommended)"
assert_contains "$script_src" "DD Image mode only as fallback"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana scratch GRUB ISO"
assert_contains "$help" "--kernel"
assert_contains "$help" "--initramfs"
assert_contains "$help" "--rootfs-image"
assert_contains "$help" "--disk-image"
assert_contains "$help" "--install"
assert_contains "$help" "--uefi"

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
[[ -f "$tmp/build/scratch-grub-iso-tree/boot/grub/ooonana-logo.txt" ]] || fail "missing staged GRUB logo"
[[ -f "$tmp/build/scratch-grub-iso-tree/boot/grub/theme.txt" ]] || fail "missing staged GRUB theme"
[[ -f "$tmp/build/scratch-grub-iso-tree/RUFUS.md" ]] || fail "missing staged Rufus note"
[[ -f "$tmp/build/scratch-grub-iso-tree/images/ooonana-scratch-disk.raw" ]] || fail "missing staged disk image"
[[ -f "$tmp/build/scratch-grub-iso-tree/boot/grub/grub.cfg" ]] || fail "missing grub config"
[[ "$(<"$tmp/build/scratch-grub-iso-tree/images/ooonana-scratch-disk.raw")" == "disk" ]] || fail "wrong staged disk image"
assert_contains "$(<"$tmp/build/scratch-grub-iso-tree/RUFUS.md")" "Write in ISO Image mode (Recommended)"
assert_contains "$(<"$tmp/build/scratch-grub-iso-tree/RUFUS.md")" "DD Image mode only as fallback"
assert_contains "$(<"$tmp/build/scratch-grub-iso-tree/RUFUS.md")" "Ooonana OS Minimal"

cfg="$(<"$tmp/build/scratch-grub-iso-tree/boot/grub/grub.cfg")"
assert_contains "$cfg" "set default=1"
assert_contains "$cfg" "set timeout=5"
assert_contains "$cfg" "set theme=/boot/grub/theme.txt"
assert_contains "$cfg" "export theme"
assert_contains "$cfg" "cat /boot/grub/ooonana-logo.txt"
assert_contains "$cfg" "terminal_output gfxterm serial"
assert_contains "$cfg" "set color_normal=yellow/black"
assert_contains "$cfg" "set color_highlight=black/yellow"
assert_contains "$cfg" "menuentry 'Ooonana OS Minimal'"
assert_contains "$cfg" "menuentry 'Install Ooonana OS Minimal'"
assert_contains "$cfg" "linux /boot/vmlinuz"
assert_contains "$cfg" "console=tty0 console=ttyS0"
assert_contains "$cfg" "terminal_input console serial"
assert_contains "$cfg" "terminal_output console serial"
assert_contains "$cfg" "rdinit=/init"
assert_contains "$cfg" "ooonana.install=1"
assert_contains "$cfg" "ooonana.install.target=/dev/vda"
assert_contains "$cfg" "ooonana.smoke=1"
assert_contains "$cfg" "initrd /boot/initramfs.cpio.gz"

PATH="$tmp/bin:$PATH" bash "$SCRIPT" \
  --work-dir "$tmp/build" \
  --kernel "$tmp/vmlinuz" \
  --initramfs "$tmp/initramfs.cpio.gz" \
  --rootfs-image "$tmp/rootfs.ext4" \
  --iso "$tmp/ooonana-grub-normal.iso" \
  --force >/dev/null

normal_cfg="$(<"$tmp/build/scratch-grub-iso-tree/boot/grub/grub.cfg")"
assert_contains "$normal_cfg" "console=ttyS0 console=tty0"
assert_contains "$normal_cfg" "terminal_input console serial"
assert_contains "$normal_cfg" "terminal_output console serial"
theme="$(<"$tmp/build/scratch-grub-iso-tree/boot/grub/theme.txt")"
assert_contains "$theme" 'title-color: "#ffb21a"'
assert_contains "$theme" 'message-color: "#ffb21a"'
assert_contains "$theme" "+ progress_bar"
assert_contains "$theme" 'id = "__timeout__"'
assert_contains "$theme" 'fg_color = "#ffb21a"'
assert_contains "$theme" 'bg_color = "#050505"'
assert_contains "$theme" "+ boot_menu"
[[ "$theme" != *"selected-item-color"* ]] || fail "GRUB theme has invalid selected item color"
[[ "$theme" != *"selected-item-background-color"* ]] || fail "GRUB theme has invalid selected item background"
[[ "$theme" != *"item-color"* ]] || fail "GRUB theme has invalid item color"
[[ "$theme" != *"item-font"* ]] || fail "GRUB theme has invalid item font"
assert_contains "$normal_cfg" "menuentry 'Ooonana OS Minimal'"

printf 'ok scratch-grub-iso\n'
