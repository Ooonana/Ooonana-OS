#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

INSTALLER="$ROOT/packages/ooonana/usr/sbin/ooonana-install"
[[ -x "$INSTALLER" ]] || fail "missing executable installer"

installer_help="$(bash "$INSTALLER" --help)"
assert_contains "$installer_help" "Install Ooonana OS"
assert_contains "$installer_help" "--target"
assert_contains "$installer_help" "--yes"
assert_contains "$installer_help" "--dry-run"
assert_contains "$installer_help" "--hostname NAME"
assert_contains "$installer_help" "--user NAME"
assert_contains "$installer_help" "--theme dark|light"
assert_contains "$installer_help" "--cloud-repo URI"
assert_contains "$installer_help" "--password-stdin"
assert_contains "$installer_help" "--kernel PATH"
assert_contains "$installer_help" "--bootloader auto|grub|none"
assert_contains "$installer_help" "--home-part PATH"
assert_contains "$installer_help" "--swap-part PATH"
assert_contains "$installer_help" "--efi-part PATH"
assert_contains "$installer_help" "--keep-root"
assert_contains "$installer_help" "--keep-home"
assert_contains "$installer_help" "--format-efi"
assert_contains "$installer_help" "--danger-allow-current-root"
assert_contains "$installer_help" "--smoke"
assert_contains "$installer_help" "--gui-smoke"
assert_contains "$installer_help" "/run/ooonana-target"

installer_dry_run="$(bash "$INSTALLER" --dry-run --yes --target /tmp/ooonana-test-disk.raw --source /tmp/ooonana-source --kernel /tmp/vmlinuz-ooonana --hostname ooonana-lab --user ryan --theme dark --cloud-repo https://example.test/repo --smoke --gui-smoke)"
assert_contains "$installer_dry_run" "parted -s /tmp/ooonana-test-disk.raw mklabel gpt"
assert_contains "$installer_dry_run" "mkpart BIOSBOOT 1MiB 3MiB set 1 bios_grub on"
assert_contains "$installer_dry_run" "mkpart ESP fat32 3MiB 515MiB set 2 esp on"
assert_contains "$installer_dry_run" "mkpart ROOT ext4 515MiB 100%"
assert_contains "$installer_dry_run" "losetup --find --show --partscan /tmp/ooonana-test-disk.raw"
assert_contains "$installer_dry_run" "mkfs.ext4 -F -L OOONANA_ROOT LOOP_ROOT_PARTITION"
assert_contains "$installer_dry_run" "mount LOOP_ROOT_PARTITION /run/ooonana-target"
assert_contains "$installer_dry_run" "mkfs.vfat -F 32 -n OOONANA_EFI LOOP_EFI_PARTITION"
assert_contains "$installer_dry_run" "mount LOOP_EFI_PARTITION /run/ooonana-target/boot/efi"
assert_contains "$installer_dry_run" "rsync -aHAX"
assert_contains "$installer_dry_run" "--exclude /dev/\\*"
assert_contains "$installer_dry_run" "install -m 0644 /tmp/vmlinuz-ooonana /run/ooonana-target/boot/vmlinuz"
assert_contains "$installer_dry_run" "grub.cfg: linux /boot/vmlinuz root=PARTUUID=TARGET_PARTUUID rw console=tty0 console=ttyS0 panic=1 init=/sbin/init ooonana.edition=full-i3 ooonana.smoke=1 ooonana.gui-smoke=1"
assert_contains "$installer_dry_run" "grub-install --target=i386-pc"
assert_contains "$installer_dry_run" "--modules=part_gpt\\ biosdisk\\ ext2\\ normal\\ linux\\ configfile"
assert_contains "$installer_dry_run" "grub-install --target=x86_64-efi"
assert_contains "$installer_dry_run" "--removable --no-nvram"
assert_contains "$installer_dry_run" "write hostname ooonana-lab"
assert_contains "$installer_dry_run" "create user ryan"
assert_contains "$installer_dry_run" "write theme dark"
assert_contains "$installer_dry_run" "write cloud repo https://example.test/repo"
assert_not_contains "$installer_dry_run" "/dev/null"
assert_contains "$installer_dry_run" "OOONANA_INSTALL_OK"

installer_dry_run_normal="$(bash "$INSTALLER" --dry-run --yes --target /tmp/ooonana-test-disk.raw --source /tmp/ooonana-source --kernel /tmp/vmlinuz-ooonana)"
assert_contains "$installer_dry_run_normal" "grub.cfg: linux /boot/vmlinuz root=PARTUUID=TARGET_PARTUUID rw console=ttyS0 console=tty0 panic=1 init=/sbin/init ooonana.edition=full-i3"

for whole_disk in /dev/nvme0n1 /dev/mmcblk0 /dev/loop0; do
  whole_disk_dry_run="$(bash "$INSTALLER" --dry-run --yes --target "$whole_disk" --source /tmp/ooonana-source --kernel /tmp/vmlinuz-ooonana)"
  assert_contains "$whole_disk_dry_run" "parted -s $whole_disk mklabel gpt"
done

by_id_dry_run="$(bash "$INSTALLER" --dry-run --yes --target /dev/disk/by-id/ooonana-test --source /tmp/ooonana-source --kernel /tmp/vmlinuz-ooonana)"
assert_contains "$by_id_dry_run" "mount /dev/disk/by-id/ooonana-test-part3 /run/ooonana-target"
assert_contains "$by_id_dry_run" "mount /dev/disk/by-id/ooonana-test-part2 /run/ooonana-target/boot/efi"

nvme_partition_dry_run="$(bash "$INSTALLER" --dry-run --yes --target /dev/nvme0n1p3 --source /tmp/ooonana-source --bootloader none --keep-root)"
assert_contains "$nvme_partition_dry_run" "keep root filesystem: /dev/nvme0n1p3"
assert_not_contains "$nvme_partition_dry_run" "parted -s /dev/nvme0n1p3"

custom_dry_run="$(bash "$INSTALLER" --dry-run --yes \
  --target /dev/sda2 \
  --source /tmp/ooonana-source \
  --home-part /dev/sda3 \
  --swap-part /dev/sda4 \
  --efi-part /dev/sda1 \
  --keep-root \
  --keep-home \
  --keep-efi \
  --bootloader none \
  --hostname custom-lab \
  --user ryan \
  --theme light)"
assert_contains "$custom_dry_run" "keep root filesystem: /dev/sda2"
assert_contains "$custom_dry_run" "mount /dev/sda2 /run/ooonana-target"
assert_contains "$custom_dry_run" "mount /dev/sda3 /run/ooonana-target/home"
assert_contains "$custom_dry_run" "mkswap -L OOONANA_SWAP /dev/sda4"
assert_contains "$custom_dry_run" "mount /dev/sda1 /run/ooonana-target/boot/efi"
assert_contains "$custom_dry_run" "fstab:"
assert_contains "$custom_dry_run" "/dev/sda3 /home ext4 defaults 0 2"
assert_contains "$custom_dry_run" "/dev/sda1 /boot/efi vfat umask=0077 0 1"
assert_contains "$custom_dry_run" "LABEL=OOONANA_SWAP none swap sw 0 0"
assert_contains "$custom_dry_run" "umount /run/ooonana-target/boot/efi"
assert_contains "$custom_dry_run" "umount /run/ooonana-target/home"
assert_not_contains "$custom_dry_run" "grub-install"

uefi_partition_dry_run="$(bash "$INSTALLER" --dry-run --yes \
  --target /dev/sda2 \
  --source /tmp/ooonana-source \
  --efi-part /dev/sda1 \
  --keep-root \
  --keep-efi \
  --bootloader grub)"
assert_contains "$uefi_partition_dry_run" "grub-install --target=x86_64-efi"
assert_contains "$uefi_partition_dry_run" "--efi-directory=/run/ooonana-target/boot/efi"
assert_contains "$uefi_partition_dry_run" "grub.cfg: linux /boot/vmlinuz root=PARTUUID=TARGET_PARTUUID"
assert_contains "$uefi_partition_dry_run" "/dev/sda2 / ext4 defaults 0 1"
assert_not_contains "$uefi_partition_dry_run" "grub-install --target=i386-pc"

duplicate_part="$(bash "$INSTALLER" --dry-run --yes \
  --target /dev/sda2 \
  --bootloader none \
  --home-part /dev/sda2 \
  --keep-root 2>&1 || true)"
assert_contains "$duplicate_part" "partition reused for install roles: /dev/sda2"

wiped_extra="$(bash "$INSTALLER" --dry-run --yes \
  --target /dev/sda \
  --home-part /dev/sda3 2>&1 || true)"
assert_contains "$wiped_extra" "extra partition would be wiped by disk target: /dev/sda3 on /dev/sda"

installer_src="$(<"$INSTALLER")"
assert_not_contains "$installer_src" "750XGK"
assert_contains "$installer_src" "submenu 'Audio compatibility'"
assert_contains "$installer_src" "force Intel SOF audio"
assert_contains "$installer_src" "force legacy Intel HDA audio"
assert_contains "$installer_src" "snd_intel_dspcfg.dsp_driver=1"
assert_contains "$installer_src" "snd_intel_dspcfg.dsp_driver=3"
assert_contains "$installer_src" "refusing current root partition target"
assert_contains "$installer_src" "refusing current root disk target"
assert_contains "$installer_src" "refusing live boot media target"
assert_contains "$installer_src" "/mnt/ooonana-live/iso"
assert_contains "$installer_src" "/mnt/ooonana-live/boot-device"
prepare_target_src="$(sed -n '/^prepare_target()/,/^}/p' "$INSTALLER")"
root_guard_line="$(grep -n 'validate_current_root_safety' <<<"$prepare_target_src" | head -n 1 | cut -d: -f1)"
live_guard_line="$(grep -n 'validate_live_media_safety' <<<"$prepare_target_src" | head -n 1 | cut -d: -f1)"
partition_line="$(grep -n 'parted -s' <<<"$prepare_target_src" | head -n 1 | cut -d: -f1)"
[[ -n "$root_guard_line" && -n "$live_guard_line" && -n "$partition_line" &&
  "$root_guard_line" -lt "$partition_line" && "$live_guard_line" -lt "$partition_line" ]] ||
  fail "disk guards must run before partitioning"
assert_contains "$installer_src" "target disk or child partition is mounted"
assert_contains "$installer_src" "install partition is mounted"
assert_contains "$installer_src" '[[ "$TARGET_MODE" == "disk" || -n "$EFI_PART" ]]'
assert_contains "$installer_src" "terminal_input console serial"
assert_contains "$installer_src" "terminal_output console serial"
assert_contains "$installer_src" "terminal_output gfxterm serial"
assert_contains "$installer_src" "ooonana-logo.txt"
assert_not_contains "$installer_src" "set theme=/boot/grub/theme.txt"
assert_contains "$installer_src" "set color_normal=yellow/black"
assert_contains "$installer_src" "set color_highlight=black/yellow"
assert_contains "$installer_src" 'title-color: "#ffb21a"'
assert_contains "$installer_src" 'message-color: "#ffb21a"'
assert_not_contains "$installer_src" "selected-item-color"
assert_not_contains "$installer_src" "selected-item-background-color"
assert_not_contains "$installer_src" "item-color"
assert_not_contains "$installer_src" "item-font"

run_help="$(bash "$ROOT/scripts/run-qemu.sh" --help)"
assert_contains "$run_help" "--disk"
assert_contains "$run_help" "--install"
assert_contains "$run_help" "--disk-boot"

iso_help="$(bash "$ROOT/scripts/build-iso.sh" --help)"
assert_contains "$iso_help" "--install"
assert_contains "$iso_help" "--install-target"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/rootfs/boot"
touch "$tmp/rootfs/boot/vmlinuz-6.1.0-ooonana"
touch "$tmp/rootfs/boot/initrd.img-6.1.0-ooonana"
touch "$tmp/ooonana.iso" "$tmp/install.ext4"

dry_run="$(bash "$ROOT/scripts/run-qemu.sh" --dry-run --install --smoke --iso "$tmp/ooonana.iso" --disk "$tmp/install.ext4" --rootfs "$tmp/rootfs")"
assert_contains "$dry_run" "qemu-system-x86_64"
assert_contains "$dry_run" "-cdrom"
assert_contains "$dry_run" "$tmp/ooonana.iso"
assert_contains "$dry_run" "-drive"
assert_contains "$dry_run" "file=$tmp/install.ext4\\,format=raw\\,if=virtio"
assert_not_contains "$dry_run" "-kernel"

grep -q 'OOONANA_INSTALL_OK' "$ROOT/scripts/run-qemu.sh" || fail "run-qemu install smoke must check install marker"
grep -q 'ooonana.smoke=1' "$ROOT/scripts/build-scratch-grub-iso.sh" || fail "installer smoke ISO must bypass text prompt"
grep -q '/bin/sh -ec' "$ROOT/scripts/build-rootfs.sh" || fail "install service must stop before marker on failure"
grep -q 'exec >/dev/console 2>&1' "$ROOT/scripts/build-rootfs.sh" || fail "install service must print installer errors to console"
grep -q 'grep -o "ooonana.install.target=' "$ROOT/scripts/build-rootfs.sh" || fail "install service must parse target without systemd escape warnings"

printf 'ok installer\n'
