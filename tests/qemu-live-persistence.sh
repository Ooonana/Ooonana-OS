#!/usr/bin/env bash
# File-backed USB fixtures only. Never attach host disks; never build release ISO.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KERNEL=""
SEED_INITRAMFS=""
BOOT_FS=ext4
while [[ $# -gt 0 ]]; do
  case "$1" in
    --kernel) KERNEL="$2"; shift 2 ;;
    --seed-initramfs) SEED_INITRAMFS="$2"; shift 2 ;;
    --boot-fs) BOOT_FS="$2"; shift 2 ;;
    *) printf 'usage: %s --kernel FILE --seed-initramfs FILE\n' "$0" >&2; exit 2 ;;
  esac
done
[[ -f "$KERNEL" && -f "$SEED_INITRAMFS" ]] || { printf 'kernel and seed initramfs files required\n' >&2; exit 2; }
case "$BOOT_FS" in ext4|vfat) ;; *) echo 'boot filesystem must be ext4 or vfat' >&2; exit 2 ;; esac
for tool in qemu-system-x86_64 sfdisk mke2fs cpio gzip dd sha256sum; do
  command -v "$tool" >/dev/null || { printf 'missing %s\n' "$tool" >&2; exit 2; }
done
tmp="$(mktemp -d /var/tmp/ooonana-persist-smoke.XXXXXXXX)"
qemu_pid=""
cleanup() {
  local result=$?
  if [[ -n "$qemu_pid" ]]; then kill "$qemu_pid" 2>/dev/null || true; wait "$qemu_pid" 2>/dev/null || true; fi
  if [[ "$result" -eq 0 ]]; then
    case "$tmp" in /var/tmp/ooonana-persist-smoke.????????) rm -rf -- "$tmp" ;; esac
  else
    printf 'Failed fixture/logs retained: %s\n' "$tmp" >&2
  fi
}
trap cleanup EXIT
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
mkdir -p "$tmp/rootfs" "$tmp/boot/images" "$tmp/unrelated-root"
gzip -dc "$SEED_INITRAMFS" | (
  cd "$tmp/rootfs"
  cpio -id --quiet --no-absolute-filenames \
    './bin/busybox' 'bin/busybox' './lib/ld-musl-x86_64.so.1' 'lib/ld-musl-x86_64.so.1' \
    './lib/libc.musl-x86_64.so.1' 'lib/libc.musl-x86_64.so.1'
)
[[ -x "$tmp/rootfs/bin/busybox" ]] || fail 'seed BusyBox missing'
mkdir -p "$tmp/rootfs/etc/ooonana" "$tmp/rootfs/etc/init.d" "$tmp/rootfs/usr/bin" "$tmp/rootfs/sbin" "$tmp/rootfs/root"
for applet in sh cat grep mkdir sync poweroff sleep readlink mount umount swapoff; do ln -s busybox "$tmp/rootfs/bin/$applet"; done
ln -s ../bin/busybox "$tmp/rootfs/sbin/init"
install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana-shutdown-cleanup" "$tmp/rootfs/usr/bin/ooonana-shutdown-cleanup"
printf '::sysinit:/etc/init.d/rcS\n::shutdown:/usr/bin/ooonana-shutdown-cleanup --from-init\n' >"$tmp/rootfs/etc/inittab"
printf 'full-i3\n' >"$tmp/rootfs/etc/ooonana/edition"
printf '#!/bin/sh\nexit 0\n' >"$tmp/rootfs/usr/bin/start-ooonana-i3"
cat >"$tmp/rootfs/etc/init.d/rcS" <<'EOF'
#!/bin/sh
set -eu
PATH=/bin:/sbin
case " $(cat /proc/cmdline) " in
  *' fixture.temporary=1 '*)
    [ ! -e /root/temporary-fixture ] || { echo FIXTURE_TEMP_NOT_RESET; poweroff -f; }
    printf 'temporary\n' >/root/temporary-fixture
    sync
    echo FIXTURE_TEMP_RESET
    ;;
  *)
    if [ -f /root/saved-fixture ]; then
      [ "$(cat /root/saved-fixture)" = 'saved across reboot' ] || { echo FIXTURE_DATA_BAD; poweroff -f; }
      echo FIXTURE_DATA_RESTORED
    else
      printf 'saved across reboot\n' >/root/saved-fixture
      sync
      echo FIXTURE_DATA_SAVED
    fi
    ;;
esac
echo "FIXTURE_MODE:$(cat /mnt/ooonana-live/persistence-mode)"
sync
poweroff
EOF
chmod +x "$tmp/rootfs/etc/init.d/rcS" "$tmp/rootfs/usr/bin/start-ooonana-i3"
bash "$ROOT/scripts/build-full-i3-live-initramfs.sh" --rootfs "$tmp/rootfs" \
  --kernel "$KERNEL" --initramfs "$tmp/live.cpio.gz" \
  --rootfs-image "$tmp/boot/images/ooonana-full-i3-live-rootfs.ext4" --force >"$tmp/build.log" 2>&1

# All format/partition/copy targets below are regular files under this new fixture.
boot_uuid=11111111-2222-3333-4444-555555555555
truncate -s 192M "$tmp/boot.ext4"
if [[ "$BOOT_FS" == vfat ]]; then
  boot_uuid=A1B2-C3D4
  for tool in mkfs.vfat mcopy mmd; do command -v "$tool" >/dev/null || fail "missing $tool"; done
  mkfs.vfat -F 32 -i A1B2C3D4 -n OOONANAUSB "$tmp/boot.ext4" >/dev/null
  mmd -i "$tmp/boot.ext4" ::/images
  mcopy -i "$tmp/boot.ext4" "$tmp/boot/images/ooonana-full-i3-live-rootfs.ext4" ::/images/
else
  mke2fs -q -t ext4 -m 0 -U "$boot_uuid" -L OOONANAUSB -d "$tmp/boot" "$tmp/boot.ext4"
fi
truncate -s 64M "$tmp/persist.ext4"
mke2fs -q -t ext4 -m 0 -L OOONANA_PERSIST "$tmp/persist.ext4"
truncate -s 258M "$tmp/usb.raw"
printf 'label: dos\nstart=2048,size=393216,type=83\nstart=395264,size=131072,type=83\n' | sfdisk "$tmp/usb.raw" >/dev/null
dd if="$tmp/boot.ext4" of="$tmp/usb.raw" bs=512 seek=2048 conv=notrunc status=none
dd if="$tmp/persist.ext4" of="$tmp/usb.raw" bs=512 seek=395264 conv=notrunc status=none
printf 'unrelated disk must not change\n' >"$tmp/unrelated-root/important"
truncate -s 32M "$tmp/unrelated.ext4"
mke2fs -q -t ext4 -m 0 -L OOONANA_PERSIST -d "$tmp/unrelated-root" "$tmp/unrelated.ext4"
unrelated_before="$(sha256sum "$tmp/unrelated.ext4")"

run_guest() {
  local name="$1" expected="$2" args="$3" disk="$4"
  shift 4
  qemu-system-x86_64 -m 384 -smp 1 -display none -serial "file:$tmp/$name.log" \
    -monitor none -no-reboot -kernel "$KERNEL" -initrd "$tmp/live.cpio.gz" \
    -append "console=ttyS0 panic=1 rdinit=/init ooonana.live=1 $args" \
    -device qemu-xhci,id=usb \
    -drive "if=none,id=stick,format=raw,file=$disk" -device usb-storage,bus=usb.0,drive=stick \
    -drive "if=none,id=unrelated,format=raw,file=$tmp/unrelated.ext4" -device usb-storage,bus=usb.0,drive=unrelated \
    "$@" >"$tmp/$name.stderr" 2>&1 &
  qemu_pid=$!
  local elapsed=0
  while kill -0 "$qemu_pid" 2>/dev/null; do
    if grep -q 'Ooonana live init failed:' "$tmp/$name.log" 2>/dev/null; then
      kill "$qemu_pid" 2>/dev/null || true
      break
    fi
    if (( elapsed >= 45 )); then
      tail -30 "$tmp/$name.log" >&2
      fail "$name timed out"
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  wait "$qemu_pid" 2>/dev/null || true
  qemu_pid=""
  if ! grep -q "$expected" "$tmp/$name.log"; then
    tail -35 "$tmp/$name.log" >&2
    cat "$tmp/$name.stderr" >&2
    fail "$name missing $expected"
  fi
  [[ "$(sha256sum "$tmp/unrelated.ext4")" = "$unrelated_before" ]] || fail "$name changed unrelated USB"
  if [[ "$expected" == FIXTURE_* ]]; then
    grep -q OOONANA_SHUTDOWN_CLEANUP_DONE "$tmp/$name.log" || fail "$name skipped orderly shutdown"
    grep -q OOONANA_PERSISTENCE_READ_ONLY "$tmp/$name.log" || { tail -25 "$tmp/$name.log" >&2; fail "$name persistence not remounted read-only"; }
  fi
  printf 'ok persistence-qemu-%s\n' "$name"
}
persistent_args="ooonana.live.boot_uuid=$boot_uuid ooonana.persistence=1"
run_guest save FIXTURE_DATA_SAVED "$persistent_args" "$tmp/usb.raw"
grep -q FIXTURE_MODE:usb "$tmp/save.log" || fail 'saved mode not USB'
run_guest restore FIXTURE_DATA_RESTORED "$persistent_args" "$tmp/usb.raw"
temporary_args="ooonana.live.boot_uuid=$boot_uuid fixture.temporary=1"
run_guest temporary-first FIXTURE_TEMP_RESET "$temporary_args" "$tmp/usb.raw"
grep -q FIXTURE_MODE:usb-temporary "$tmp/temporary-first.log" || fail 'temporary mode not USB'
run_guest temporary-reset FIXTURE_TEMP_RESET "$temporary_args" "$tmp/usb.raw"
run_guest saved-survives-temporary FIXTURE_DATA_RESTORED "$persistent_args" "$tmp/usb.raw"
run_guest no-identity 'persistent boot needs GRUB boot UUID' 'ooonana.persistence=1' "$tmp/usb.raw"

truncate -s 194M "$tmp/boot-only.raw"
printf 'label: dos\nstart=2048,size=393216,type=83\n' | sfdisk "$tmp/boot-only.raw" >/dev/null
dd if="$tmp/boot.ext4" of="$tmp/boot-only.raw" bs=512 seek=2048 conv=notrunc status=none
run_guest missing-partition 'OOONANA_PERSIST missing on boot USB; no RAM fallback' "$persistent_args" "$tmp/boot-only.raw"
run_guest cloned-uuid 'boot UUID ambiguous across drives' "$persistent_args" "$tmp/usb.raw" \
  -drive "if=none,id=clone,format=raw,file=$tmp/boot-only.raw" -device usb-storage,bus=usb.0,drive=clone
printf 'ok live-persistence-qemu (unrelated USB hash unchanged)\n'
