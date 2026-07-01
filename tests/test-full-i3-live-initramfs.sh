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
printf 'full-i3\n' > "$tmp/rootfs/etc/ooonana/edition"
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
assert_contains "$script_src" "mount -t iso9660"
assert_contains "$script_src" "losetup /dev/loop0"
assert_contains "$script_src" "mount -t overlay overlay"
assert_contains "$script_src" "switch_root /newroot /sbin/init"
assert_contains "$script_src" "ld-musl-x86_64.so.1"
assert_contains "$script_src" "libc.musl-x86_64.so.1"
assert_contains "$script_src" "regulatory.db"
assert_contains "$script_src" '[ -e /proc/sys/kernel/hotplug ]'

kernel_fragment="$(<"$ROOT/configs/kernel/ooonana-minimal-x86_64.fragment")"
assert_contains "$kernel_fragment" "CONFIG_BLK_DEV_LOOP=y"
assert_contains "$kernel_fragment" "CONFIG_ISO9660_FS=y"
assert_contains "$kernel_fragment" "CONFIG_BLK_DEV_SR=y"
assert_contains "$kernel_fragment" "CONFIG_SCSI=y"
assert_contains "$kernel_fragment" "CONFIG_BLK_DEV_SD=y"
assert_contains "$kernel_fragment" "CONFIG_BLK_DEV_NVME=y"

printf 'ok full-i3-live-initramfs\n'
