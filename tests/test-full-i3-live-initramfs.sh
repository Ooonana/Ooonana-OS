#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-full-i3-live-initramfs.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable full-i3 live initramfs builder"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana full-i3 live initramfs"
assert_contains "$help" "--rootfs"
assert_contains "$help" "--rootfs-image"
assert_contains "$help" "--initramfs"
assert_contains "$help" "--kernel"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin" "$tmp/rootfs/bin" "$tmp/rootfs/etc/ooonana" "$tmp/rootfs/lib/firmware" "$tmp/rootfs/usr/bin" "$tmp/rootfs/dev" "$tmp/rootfs/proc" "$tmp/rootfs/sys" "$tmp/rootfs/run" "$tmp/rootfs/tmp"
mkdir -p "$tmp/rootfs/usr/share/ooonana"
cat > "$tmp/bin/cpio" <<'EOF'
#!/bin/sh
cat >/dev/null
printf 'fake cpio\n'
EOF
chmod +x "$tmp/bin/cpio"
cat > "$tmp/bin/mke2fs" <<'EOF'
#!/bin/sh
last=""
for arg in "$@"; do
  last="$arg"
done
printf 'fake ext4 rootfs\n' > "$last"
EOF
chmod +x "$tmp/bin/mke2fs"
printf 'kernel\n' > "$tmp/vmlinuz"
cat > "$tmp/rootfs/bin/busybox" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$tmp/rootfs/bin/busybox"
printf 'loader\n' > "$tmp/rootfs/lib/ld-musl-x86_64.so.1"
printf 'libc\n' > "$tmp/rootfs/lib/libc.musl-x86_64.so.1"
printf 'regdb\n' > "$tmp/rootfs/lib/firmware/regulatory.db"
printf 'regsig\n' > "$tmp/rootfs/lib/firmware/regulatory.db.p7s"
printf 'iwl\n' > "$tmp/rootfs/lib/firmware/iwlwifi-test.ucode"
mkdir -p "$tmp/rootfs/lib/firmware/intel" "$tmp/rootfs/lib/firmware/rtl_bt" "$tmp/rootfs/lib/firmware/rtw89"
ln -s intel/iwlwifi/iwlwifi-test.ucode "$tmp/rootfs/lib/firmware/iwlwifi-test-link.ucode"
mkdir -p "$tmp/rootfs/lib/firmware/intel/iwlwifi"
printf 'iwl-target\n' > "$tmp/rootfs/lib/firmware/intel/iwlwifi/iwlwifi-test.ucode"
printf 'ibt\n' > "$tmp/rootfs/lib/firmware/intel/ibt-test.sfi"
printf 'rtlbt\n' > "$tmp/rootfs/lib/firmware/rtl_bt/rtl8761bu_fw.bin"
printf 'rtw89\n' > "$tmp/rootfs/lib/firmware/rtw89/rtw8852b_fw.bin"
printf 'full-i3\n' > "$tmp/rootfs/etc/ooonana/edition"
printf 'Ooonana OS\n' > "$tmp/rootfs/usr/share/ooonana/logo.txt"
printf 'LARGE OOONANA BOOT LOGO\n' > "$tmp/rootfs/usr/share/ooonana/boot-logo.txt"
cat > "$tmp/rootfs/usr/bin/start-ooonana-i3" <<'EOF'
#!/bin/sh
echo start
EOF
chmod +x "$tmp/rootfs/usr/bin/start-ooonana-i3"

PATH="$tmp/bin:$PATH" bash "$SCRIPT" \
  --rootfs "$tmp/rootfs" \
  --rootfs-image "$tmp/live-rootfs.ext4" \
  --kernel "$tmp/vmlinuz" \
  --initramfs "$tmp/live.cpio.gz" \
  --force >/dev/null

[[ -s "$tmp/live.cpio.gz" ]] || fail "missing live initramfs"
[[ -s "$tmp/live-rootfs.ext4" ]] || fail "missing live rootfs image"
grep -q "fake ext4 rootfs" "$tmp/live-rootfs.ext4" || fail "rootfs image not built with mke2fs"
gzip -dc "$tmp/live.cpio.gz" | grep -q "fake cpio" || fail "cpio output not compressed"
[[ -f "$tmp/rootfs/boot/vmlinuz" ]] || fail "kernel not staged in live rootfs"
[[ -d "$tmp/rootfs/dev" ]] || fail "dev dir removed"
[[ -d "$tmp/rootfs/proc" ]] || fail "proc dir removed"

script_src="$(<"$SCRIPT")"
assert_contains "$script_src" "/images/ooonana-full-i3-live-rootfs.ext4"
assert_contains "$script_src" 'used_kb / 8 + 131072'
assert_contains "$script_src" "-m 0 -O '^has_journal'"
assert_contains "$script_src" "mount -t iso9660"
assert_contains "$script_src" "losetup /dev/loop0"
assert_contains "$script_src" "mount -t overlay overlay"
assert_contains "$script_src" "switch_root /newroot /sbin/init"
assert_contains "$script_src" "splash \"starting live boot\" 1"
assert_contains "$script_src" "splash \"finding boot media\" 2"
assert_contains "$script_src" "splash \"starting desktop\" 9"
assert_contains "$script_src" "center_line"
assert_contains "$script_src" "draw_logo"
assert_contains "$script_src" "boot-logo.txt"
assert_contains "$script_src" "stty size"
assert_contains "$script_src" "start_row"
assert_contains "$script_src" "P3ffb21a"
assert_contains "$script_src" "mount -o ro,noload"
assert_contains "$script_src" "/sys/class/block/*"
assert_contains "$script_src" 'candidates="$candidates /dev/${devpath##*/}"'
assert_contains "$script_src" 'boot_media_device="$dev"'
assert_contains "$script_src" '/newroot/mnt/ooonana-live/boot-device'
assert_contains "$script_src" '/newroot/mnt/ooonana-live/persistence-mode'
assert_contains "$script_src" '/newroot/mnt/ooonana-live/persistence-device'
[[ "$script_src" != *'/newroot/run/ooonana-live'* ]] || fail "live mounts must survive /run tmpfs"
assert_contains "$script_src" "parent_disk_name()"
assert_contains "$script_src" '[ "$(parent_disk_name "$candidate")" = "$boot_parent" ] || continue'
assert_contains "$script_src" 'blkid -s LABEL -o value'
assert_contains "$script_src" '"OOONANA_PERSIST"'
assert_contains "$script_src" 'blkid -s TYPE -o value'
assert_contains "$script_src" '"ext4"'
assert_contains "$script_src" 'mount -t ext4 -o rw "$candidate" /persist'
assert_contains "$script_src" '/persist/overlay/upper'
assert_contains "$script_src" 'lowerdir=/mnt/root-ro,upperdir="$overlay_upper",workdir="$overlay_work"'
assert_contains "$script_src" 'persistence_mode="usb"'
assert_contains "$script_src" 'persistence_mode="ram"'
assert_contains "$script_src" "usr/share/ooonana/logo.txt"
assert_contains "$script_src" "ld-musl-x86_64.so.1"
assert_contains "$script_src" "libc.musl-x86_64.so.1"
assert_contains "$script_src" "regulatory.db"
assert_contains "$script_src" "copy_early_firmware"
assert_contains "$script_src" "iwlwifi-*"
assert_contains "$script_src" '-type l'
assert_contains "$script_src" 'cp -a "$fw"'
assert_contains "$script_src" "intel/ibt-*"
assert_contains "$script_src" "rtl_bt"
assert_contains "$script_src" "rtw89"
assert_contains "$script_src" '[ -e /proc/sys/kernel/hotplug ]'
assert_contains "$script_src" 'suid,dev,exec,lowerdir='
assert_contains "$script_src" 'mount -t tmpfs -o mode=0755 tmpfs /cow'

kernel_fragment="$(<"$ROOT/configs/kernel/ooonana-minimal-x86_64.fragment")"
assert_contains "$kernel_fragment" "CONFIG_BLK_DEV_LOOP=y"
assert_contains "$kernel_fragment" "CONFIG_ISO9660_FS=y"
assert_contains "$kernel_fragment" "CONFIG_BLK_DEV_SR=y"
assert_contains "$kernel_fragment" "CONFIG_SCSI=y"
assert_contains "$kernel_fragment" "CONFIG_BLK_DEV_SD=y"
assert_contains "$kernel_fragment" "CONFIG_BLK_DEV_NVME=y"
assert_contains "$kernel_fragment" "CONFIG_USB_XHCI_PCI=y"
assert_contains "$kernel_fragment" "CONFIG_BT_HCIBTUSB_POLL_SYNC=y"
assert_contains "$kernel_fragment" "CONFIG_BT_INTEL_PCIE=y"
assert_contains "$kernel_fragment" "CONFIG_UHID=y"
assert_contains "$kernel_fragment" "CONFIG_INPUT_UINPUT=y"
assert_contains "$kernel_fragment" "CONFIG_INTEL_MEI_ME=y"

printf 'ok full-i3-live-initramfs\n'
