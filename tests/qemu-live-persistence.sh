#!/usr/bin/env bash
# File-backed USB fixtures only. Never attach host disks; never build release ISO.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KERNEL=""
SEED_INITRAMFS=""
BOOT_FS=ext4
FORMAT_ROOTFS=""
UPGRADE_ONLY=0
FILE_SPACE_ONLY=0
QEMU_ACCEL="${OOONANA_QEMU_ACCEL:-tcg}"
QEMU_TIMEOUT="${OOONANA_QEMU_PERSIST_TIMEOUT:-180}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --kernel) KERNEL="$2"; shift 2 ;;
    --seed-initramfs) SEED_INITRAMFS="$2"; shift 2 ;;
    --boot-fs) BOOT_FS="$2"; shift 2 ;;
    --format-rootfs) FORMAT_ROOTFS="$2"; shift 2 ;;
    --upgrade-only) UPGRADE_ONLY=1; shift ;;
    --file-space-only) FILE_SPACE_ONLY=1; shift ;;
    *) printf 'usage: %s --kernel FILE --seed-initramfs FILE\n' "$0" >&2; exit 2 ;;
  esac
done
[[ -f "$KERNEL" && -f "$SEED_INITRAMFS" ]] || { printf 'kernel and seed initramfs files required\n' >&2; exit 2; }
[[ "$FILE_SPACE_ONLY" != 1 || -n "$FORMAT_ROOTFS" ]] || { echo '--file-space-only requires --format-rootfs' >&2; exit 2; }
case "$BOOT_FS" in ext4|vfat) ;; *) echo 'boot filesystem must be ext4 or vfat' >&2; exit 2 ;; esac
case "$QEMU_ACCEL" in tcg|kvm) ;; *) echo 'QEMU acceleration must be tcg or kvm' >&2; exit 2 ;; esac
[[ "$QEMU_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || { echo 'QEMU timeout must be positive seconds' >&2; exit 2; }
for tool in qemu-system-x86_64 sfdisk mke2fs cpio gzip dd sha256sum debugfs e2fsck python3; do
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
if [[ -n "$FORMAT_ROOTFS" ]]; then
  [[ -x "$FORMAT_ROOTFS/sbin/mke2fs" ]] || fail 'format rootfs must contain bundled mke2fs'
  install -m 0755 "$FORMAT_ROOTFS/sbin/mke2fs" "$tmp/rootfs/sbin/mke2fs"
  install -m 0644 "$FORMAT_ROOTFS/etc/mke2fs.conf" "$tmp/rootfs/etc/mke2fs.conf"
  while IFS= read -r -d '' dependency; do
    relative="${dependency#"$FORMAT_ROOTFS"/}"
    mkdir -p "$(dirname "$tmp/rootfs/$relative")"
    cp -a "$dependency" "$tmp/rootfs/$relative"
  done < <(find "$FORMAT_ROOTFS/lib" "$FORMAT_ROOTFS/usr/lib" -maxdepth 1 \
    \( -name 'libext2fs.so*' -o -name 'libcom_err.so*' -o -name 'libblkid.so*' \
       -o -name 'libuuid.so*' -o -name 'libe2p.so*' -o -name 'libeconf.so*' \) -print0)
  chroot "$tmp/rootfs" /sbin/mke2fs -V >"$tmp/formatter-check.log" 2>&1 || fail 'fixture formatter dependency closure incomplete'
fi
for applet in sh cat grep mkdir sync poweroff sleep readlink tr mount umount swapoff awk basename chmod cp dirname flock id mktemp mv rm rmdir sed sha256sum sort stat tar touch wc; do ln -s busybox "$tmp/rootfs/bin/$applet"; done
install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana" "$tmp/rootfs/usr/bin/ooonana"
mkdir -p "$tmp/rootfs/usr/lib/ooonana"
install -m 0644 "$ROOT/packages/ooonana/usr/lib/ooonana/version-order.awk" "$tmp/rootfs/usr/lib/ooonana/version-order.awk"
python3 - "$tmp/rootfs/usr/lib/ooonana" <<'PY'
import hashlib
import io
from pathlib import Path
import sys
import tarfile
base = Path(sys.argv[1])
for version, name in (('1', 'fixture-old'), ('2', 'fixture-new')):
    repo = base / name
    repo.mkdir(parents=True)
    archive = repo / 'fixture.tar.gz'
    files = {'etc/fixture.conf': 'default=' + version, 'usr/share/fixture/version': version}
    if version == '2':
        files['usr/share/fixture/new-file'] = 'new'
        (repo / 'hooks').mkdir()
        hook = repo / 'hooks/fixture.healthcheck'
        hook.write_text('#!/bin/sh\necho FIXTURE_UPGRADE_READY\nwhile :; do sleep 1; done\n')
        hook.chmod(0o755)
    with tarfile.open(archive, 'w:gz') as stream:
        for path, content in files.items():
            entry = tarfile.TarInfo(path)
            data = content.encode()
            entry.size, entry.mode = len(data), 0o644
            stream.addfile(entry, io.BytesIO(data))
    fields = dict(ID='fixture', VERSION=version, KIND='archive', SUMMARY='Disposable VM upgrade',
                  DEPS='', ARCHIVE=archive.name, SHA256=hashlib.sha256(archive.read_bytes()).hexdigest())
    (repo / 'fixture.pkg').write_text(''.join(f'OOONANA_PKG_{key}="{value}"\n' for key, value in fields.items()))
PY
awk -v marker='write_file "$ROOTFS/sbin/init"' '
  index($0, marker) { capture=1; next }
  capture && $0 == "EOF" { exit }
  capture { print }
' "$ROOT/scripts/build-scratch-rootfs.sh" >"$tmp/rootfs/sbin/init"
[[ -s "$tmp/rootfs/sbin/init" ]] || fail 'source init wrapper missing'
chmod 0755 "$tmp/rootfs/sbin/init"
install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana-shutdown-cleanup" "$tmp/rootfs/usr/bin/ooonana-shutdown-cleanup"
printf '::sysinit:/etc/init.d/rcS\n::shutdown:/usr/bin/ooonana-shutdown-cleanup --from-init\n' >"$tmp/rootfs/etc/inittab"
printf 'full-i3\n' >"$tmp/rootfs/etc/ooonana/edition"
printf '#!/bin/sh\nexit 0\n' >"$tmp/rootfs/usr/bin/start-ooonana-i3"
cat >"$tmp/rootfs/etc/init.d/rcS" <<'EOF'
#!/bin/sh
set -eu
PATH=/bin:/sbin
mount -t tmpfs -o mode=0755,size=4m tmpfs /run
echo "FIXTURE_PID1_CMD:$(tr '\000' ' ' </proc/1/cmdline)"
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
case " $(cat /proc/cmdline) " in
  *' fixture.update-crash=1 '*)
    OOONANA_REPO_DIR=/usr/lib/ooonana/fixture-old /usr/bin/ooonana get fixture
    printf 'custom=yes' >/etc/fixture.conf
    OOONANA_REPO_DIR=/usr/lib/ooonana/fixture-new /usr/bin/ooonana upgrade fixture
    echo FIXTURE_UPGRADE_DID_NOT_WAIT
    poweroff -f
    ;;
  *' fixture.update-recover=1 '*)
    /usr/bin/ooonana recover
    [ "$(cat /usr/share/fixture/version)" = 1 ] || { echo FIXTURE_UPGRADE_BAD_VERSION; poweroff -f; }
    [ "$(cat /etc/fixture.conf)" = custom=yes ] || { echo FIXTURE_UPGRADE_BAD_CONFIG; poweroff -f; }
    [ ! -e /usr/share/fixture/new-file ] || { echo FIXTURE_UPGRADE_EXTRA_FILE; poweroff -f; }
    [ ! -e /etc/fixture.conf.ooonana-new ] || { echo FIXTURE_UPGRADE_EXTRA_CONFIG; poweroff -f; }
    /usr/bin/ooonana verify fixture
    echo FIXTURE_UPGRADE_RECOVERED
    ;;
  *' fixture.crash=1 '*)
    # Only the committed sentinel is guaranteed after an abrupt power cut.
    echo FIXTURE_CRASH_READY
    while :; do printf 'uncommitted write\n' >/root/inflight-fixture; done
    ;;
  *' fixture.full=1 '*)
    if /bin/busybox dd if=/dev/zero of=/root/full-fixture bs=1048576 count=1024 2>/run/full-error; then
      echo FIXTURE_FULL_NOT_REACHED
      poweroff -f
    fi
    grep -q 'No space left' /run/full-error || { cat /run/full-error; echo FIXTURE_FULL_WRONG_ERROR; poweroff -f; }
    sync
    echo FIXTURE_FULL_WRITTEN
    ;;
esac
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
  mkfifo "$tmp/$name.input"
  local input_fd
  exec {input_fd}<>"$tmp/$name.input"
  qemu-system-x86_64 -accel "$QEMU_ACCEL" -m 384 -smp 1 -display none -serial stdio \
    -monitor none -no-reboot -kernel "$KERNEL" -initrd "$tmp/live.cpio.gz" \
    -append "console=ttyS0 panic=1 rdinit=/init ooonana.live=1 $args" \
    -device qemu-xhci,id=usb \
    -drive "if=none,id=stick,format=raw,file=$disk" -device usb-storage,bus=usb.0,drive=stick \
    -drive "if=none,id=unrelated,format=raw,file=$tmp/unrelated.ext4" -device usb-storage,bus=usb.0,drive=unrelated \
    "$@" <"$tmp/$name.input" >"$tmp/$name.log" 2>"$tmp/$name.stderr" &
  qemu_pid=$!
  local elapsed=0
  local size_sent=0 confirm_sent=0 recovery_sent=0
  while kill -0 "$qemu_pid" 2>/dev/null; do
    if [[ -n "${power_cut_marker:-}" ]] && grep -q "^${power_cut_marker}[[:space:]]*$" "$tmp/$name.log" 2>/dev/null; then
      # SIGKILL only this newly spawned guest: no guest sync/shutdown trap.
      kill -KILL "$qemu_pid"
      break
    fi
    if [[ -n "${setup_size:-}" && "$size_sent" = 0 ]] && grep -q 'Storage size MiB:' "$tmp/$name.log" 2>/dev/null; then
      printf '%s\n' "$setup_size" >&"$input_fd"
      size_sent=1
    fi
    if [[ -n "${setup_confirm:-}" && "$confirm_sent" = 0 ]] && grep -q 'Type CREATE:' "$tmp/$name.log" 2>/dev/null; then
      printf '%s\n' "$setup_confirm" >&"$input_fd"
      confirm_sent=1
    fi
    if grep -q 'Ooonana live init failed:' "$tmp/$name.log" 2>/dev/null; then
      if [[ "${inspect_recovery:-0}" = 1 ]]; then
        if [[ "$recovery_sent" = 0 ]]; then
          printf 'echo FIXTURE_RECOVERY_BEGIN; cat /proc/mounts; if losetup /dev/loop1; then echo FIXTURE_LOOP_OPEN; else echo FIXTURE_LOOP_CLOSED; fi; echo FIXTURE_RECOVERY_END\n' >&"$input_fd"
          recovery_sent=1
        fi
        if ! grep -q '^FIXTURE_RECOVERY_END[[:space:]]*$' "$tmp/$name.log"; then
          if (( elapsed >= QEMU_TIMEOUT )); then fail "$name recovery inspection timed out"; fi
          sleep 1
          elapsed=$((elapsed + 1))
          continue
        fi
      fi
      kill "$qemu_pid" 2>/dev/null || true
      break
    fi
    if (( elapsed >= QEMU_TIMEOUT )); then
      tail -30 "$tmp/$name.log" >&2
      fail "$name timed out"
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  local qemu_status=0
  wait "$qemu_pid" 2>/dev/null || qemu_status=$?
  exec {input_fd}>&-
  qemu_pid=""
  if ! grep -q "$expected" "$tmp/$name.log"; then
    tail -35 "$tmp/$name.log" >&2
    cat "$tmp/$name.stderr" >&2
    fail "$name missing $expected"
  fi
  [[ "$(sha256sum "$tmp/unrelated.ext4")" = "$unrelated_before" ]] || fail "$name changed unrelated USB"
  if [[ -n "${power_cut_marker:-}" ]]; then
    [[ "$qemu_status" = 137 ]] || fail "$name not stopped by simulated power cut"
    ! grep -q '^OOONANA_SHUTDOWN_CLEANUP_DONE' "$tmp/$name.log" || fail "$name unexpectedly shut down cleanly"
  elif [[ "$expected" == FIXTURE_* ]]; then
    [[ "$qemu_status" = 0 ]] || fail "$name QEMU failed with $qemu_status"
    grep -q '^OOONANA_SHUTDOWN_CLEANUP_DONE[[:space:]]*$' "$tmp/$name.log" || fail "$name skipped orderly shutdown"
    grep -q '^OOONANA_PERSISTENCE_READ_ONLY[[:space:]]*$' "$tmp/$name.log" || { tail -25 "$tmp/$name.log" >&2; fail "$name persistence not remounted read-only"; }
    grep -q 'reboot: Power down' "$tmp/$name.log" || fail "$name did not power down"
    if grep -Eq 'Volume was not properly unmounted|OOONANA_SHUTDOWN_.*(WARNING|FAILED)' "$tmp/$name.log"; then
      tail -30 "$tmp/$name.log" >&2
      fail "$name dirty filesystem or incomplete cleanup"
    fi
    case "$name" in file-*)
      grep -q '^OOONANA_BOOT_STORAGE_READ_ONLY[[:space:]]*$' "$tmp/$name.log" || fail "$name outer USB not remounted read-only"
      ;;
    esac
  fi
  printf 'ok persistence-qemu-%s\n' "$name"
}
persistent_args="ooonana.live.boot_uuid=$boot_uuid ooonana.persistence=1"
if [[ "$FILE_SPACE_ONLY" != 1 ]]; then
cp --sparse=always "$tmp/usb.raw" "$tmp/upgrade-power-cut.raw"
power_cut_marker=FIXTURE_UPGRADE_READY
run_guest upgrade-power-cut FIXTURE_UPGRADE_READY "$persistent_args fixture.update-crash=1" "$tmp/upgrade-power-cut.raw"
power_cut_marker=""
run_guest upgrade-recovery FIXTURE_UPGRADE_RECOVERED "$persistent_args fixture.update-recover=1" "$tmp/upgrade-power-cut.raw"
if [[ "$UPGRADE_ONLY" = 1 ]]; then
  printf 'ok interrupted-upgrade-qemu (real guest CLI, old payload/config restored)\n'
  exit 0
fi
run_guest save FIXTURE_DATA_SAVED "$persistent_args" "$tmp/usb.raw"
grep -q FIXTURE_MODE:usb "$tmp/save.log" || fail 'saved mode not USB'
run_guest restore FIXTURE_DATA_RESTORED "$persistent_args" "$tmp/usb.raw"
temporary_args="ooonana.live.boot_uuid=$boot_uuid fixture.temporary=1"
run_guest temporary-first FIXTURE_TEMP_RESET "$temporary_args" "$tmp/usb.raw"
grep -q FIXTURE_MODE:usb-temporary "$tmp/temporary-first.log" || fail 'temporary mode not USB'
run_guest temporary-reset FIXTURE_TEMP_RESET "$temporary_args" "$tmp/usb.raw"
run_guest saved-survives-temporary FIXTURE_DATA_RESTORED "$persistent_args" "$tmp/usb.raw"
# Abrupt loss and ENOSPC on copies only; original saved baseline remains intact.
cp --sparse=always "$tmp/usb.raw" "$tmp/power-cut.raw"
power_cut_marker=FIXTURE_CRASH_READY
run_guest power-cut FIXTURE_CRASH_READY "$persistent_args fixture.crash=1" "$tmp/power-cut.raw"
power_cut_marker=""
run_guest power-cut-recovery FIXTURE_DATA_RESTORED "$persistent_args" "$tmp/power-cut.raw"
cp --sparse=always "$tmp/usb.raw" "$tmp/full.raw"
run_guest full-storage FIXTURE_FULL_WRITTEN "$persistent_args fixture.full=1" "$tmp/full.raw"
run_guest full-storage-refused 'persistence unwritable or below 16 MiB free' "$persistent_args" "$tmp/full.raw"
dd if="$tmp/full.raw" of="$tmp/full.partition" bs=512 skip=395264 count=131072 status=none
e2fsck -fn "$tmp/full.partition" >"$tmp/full-before-fsck.log" 2>&1 || fail 'full partition not clean'
# Offline recovery deletes one known disposable filler, never saved user data.
debugfs -w -R 'rm /overlay/upper/root/full-fixture' "$tmp/full.partition" >"$tmp/full-recovery.log" 2>&1
e2fsck -fn "$tmp/full.partition" >"$tmp/full-after-fsck.log" 2>&1 || fail 'recovered partition not clean'
dd if="$tmp/full.partition" of="$tmp/full.raw" bs=512 seek=395264 conv=notrunc status=none
run_guest full-storage-recovery FIXTURE_DATA_RESTORED "$persistent_args" "$tmp/full.raw"
run_guest no-identity 'persistent boot needs GRUB boot UUID' 'ooonana.persistence=1' "$tmp/usb.raw"

truncate -s 194M "$tmp/boot-only.raw"
printf 'label: dos\nstart=2048,size=393216,type=83\n' | sfdisk "$tmp/boot-only.raw" >/dev/null
dd if="$tmp/boot.ext4" of="$tmp/boot-only.raw" bs=512 seek=2048 conv=notrunc status=none
run_guest missing-partition 'OOONANA_PERSIST missing on boot USB; no RAM fallback' "$persistent_args" "$tmp/boot-only.raw"
run_guest cloned-uuid 'boot UUID ambiguous across drives' "$persistent_args" "$tmp/usb.raw" \
  -drive "if=none,id=clone,format=raw,file=$tmp/boot-only.raw" -device usb-storage,bus=usb.0,drive=clone
fi
if [[ -n "$FORMAT_ROOTFS" ]]; then
  # Writable boot filesystem with space, no persistence partition. Setup may
  # create a file only inside this disposable guest USB, never a host device.
  truncate -s 768M "$tmp/setup.bootfs"
  if [[ "$BOOT_FS" = vfat ]]; then
    mkfs.vfat -F 32 -i A1B2C3D4 -n OOONANAUSB "$tmp/setup.bootfs" >/dev/null
    mmd -i "$tmp/setup.bootfs" ::/images
    mcopy -i "$tmp/setup.bootfs" "$tmp/boot/images/ooonana-full-i3-live-rootfs.ext4" ::/images/
  else
    mke2fs -q -t ext4 -m 0 -U "$boot_uuid" -L OOONANAUSB -d "$tmp/boot" "$tmp/setup.bootfs"
  fi
  truncate -s 770M "$tmp/setup.raw"
  printf 'label: dos\nstart=2048,size=1572864,type=83\n' | sfdisk "$tmp/setup.raw" >/dev/null
  dd if="$tmp/setup.bootfs" of="$tmp/setup.raw" bs=512 seek=2048 conv=notrunc status=none
  setup_before="$(sha256sum "$tmp/setup.raw")"
  setup_size=256
  setup_confirm=CANCEL
  if [[ "$FILE_SPACE_ONLY" != 1 ]]; then
  run_guest file-cancel 'file setup unavailable/cancelled/failed' "$persistent_args" "$tmp/setup.raw"
  [[ "$(sha256sum "$tmp/setup.raw")" = "$setup_before" ]] || fail 'cancelled setup wrote boot USB'
  setup_size=999999
  run_guest file-too-large 'file setup unavailable/cancelled/failed' "$persistent_args" "$tmp/setup.raw"
  [[ "$(sha256sum "$tmp/setup.raw")" = "$setup_before" ]] || fail 'invalid size wrote boot USB'
  fi
  setup_size=256
  setup_confirm=CREATE
  run_guest file-create FIXTURE_DATA_SAVED "$persistent_args" "$tmp/setup.raw"
  grep -q FIXTURE_MODE:usb "$tmp/file-create.log" || fail 'created file not persistent'
  setup_size=""
  setup_confirm=""

  cp --sparse=always "$tmp/setup.raw" "$tmp/file-full.raw"
  run_guest file-full-storage FIXTURE_FULL_WRITTEN "$persistent_args fixture.full=1" "$tmp/file-full.raw"
  run_guest file-full-refused 'persistence unwritable or below 16 MiB free' "$persistent_args" "$tmp/file-full.raw"
  dd if="$tmp/file-full.raw" of="$tmp/full.outer" bs=512 skip=2048 count=1572864 status=none
  if [[ "$BOOT_FS" == vfat ]]; then
    fsck.fat -n "$tmp/full.outer" >"$tmp/file-full-outer-fsck.log" 2>&1 || fail 'full outer FAT not clean'
    mcopy -i "$tmp/full.outer" ::/ooonana-persistence.ext4 "$tmp/full.inner"
  else
    e2fsck -fn "$tmp/full.outer" >"$tmp/file-full-outer-fsck.log" 2>&1 || fail 'full outer ext4 not clean'
    debugfs -R "dump /ooonana-persistence.ext4 $tmp/full.inner" "$tmp/full.outer" >"$tmp/file-full-dump.log" 2>&1
  fi
  e2fsck -fn "$tmp/full.inner" >"$tmp/file-full-inner-fsck.log" 2>&1 || fail 'full inner ext4 not clean'
  debugfs -w -R 'rm /overlay/upper/root/full-fixture' "$tmp/full.inner" >"$tmp/file-full-reclaim.log" 2>&1
  e2fsck -fn "$tmp/full.inner" >>"$tmp/file-full-inner-fsck.log" 2>&1 || fail 'recovered inner ext4 not clean'
  if [[ "$BOOT_FS" == vfat ]]; then
    mcopy -o -i "$tmp/full.outer" "$tmp/full.inner" ::/ooonana-persistence.ext4
    fsck.fat -n "$tmp/full.outer" >>"$tmp/file-full-outer-fsck.log" 2>&1 || fail 'recovered outer FAT not clean'
  else
    debugfs -w -R 'rm /ooonana-persistence.ext4' "$tmp/full.outer" >"$tmp/file-full-replace.log" 2>&1
    debugfs -w -R "write $tmp/full.inner /ooonana-persistence.ext4" "$tmp/full.outer" >>"$tmp/file-full-replace.log" 2>&1
    e2fsck -fn "$tmp/full.outer" >>"$tmp/file-full-outer-fsck.log" 2>&1 || fail 'recovered outer ext4 not clean'
  fi
  dd if="$tmp/full.outer" of="$tmp/file-full.raw" bs=512 seek=2048 conv=notrunc status=none
  run_guest file-full-recovery FIXTURE_DATA_RESTORED "$persistent_args" "$tmp/file-full.raw"
  if [[ "$FILE_SPACE_ONLY" = 1 ]]; then
    printf 'ok persistence-file-space-qemu (inner/outer clean; saved data and unrelated USB retained)\n'
    exit 0
  fi
  run_guest file-reboot FIXTURE_DATA_RESTORED "$persistent_args" "$tmp/setup.raw"
  ! grep -q 'Storage size MiB:' "$tmp/file-reboot.log" || fail 'existing storage prompted again'
  run_guest file-temporary FIXTURE_TEMP_RESET "$temporary_args" "$tmp/setup.raw"
  run_guest file-temporary-reset FIXTURE_TEMP_RESET "$temporary_args" "$tmp/setup.raw"
  run_guest file-survives-temporary FIXTURE_DATA_RESTORED "$persistent_args" "$tmp/setup.raw"

  cp --sparse=always "$tmp/setup.raw" "$tmp/file-power-cut.raw"
  power_cut_marker=FIXTURE_CRASH_READY
  run_guest file-power-cut FIXTURE_CRASH_READY "$persistent_args fixture.crash=1" "$tmp/file-power-cut.raw"
  power_cut_marker=""
  if [[ "$BOOT_FS" == vfat ]]; then
    # Dirty FAT must remain byte-identical and RO until explicit offline repair.
    dirty_before="$(sha256sum "$tmp/file-power-cut.raw")"
    run_guest file-power-cut-refused 'OOONANA_BOOT_STORAGE_NEEDS_OFFLINE_CHECK' "$persistent_args" "$tmp/file-power-cut.raw"
    [[ "$(sha256sum "$tmp/file-power-cut.raw")" = "$dirty_before" ]] || fail 'dirty FAT refusal wrote USB'
    dd if="$tmp/file-power-cut.raw" of="$tmp/recovery.bootfs" bs=512 skip=2048 count=1572864 status=none
    cp --sparse=always "$tmp/recovery.bootfs" "$tmp/recovery-before-repair.bootfs"
    # Repair only a copied regular-file fixture, never auto-repair during boot.
    fsck.fat -a "$tmp/recovery.bootfs" >"$tmp/recovery-fat-fsck.log" 2>&1 || [[ "$?" = 1 ]] || fail 'offline FAT repair failed'
    fsck.fat -n "$tmp/recovery.bootfs" >>"$tmp/recovery-fat-fsck.log" 2>&1 || fail 'FAT remains inconsistent'
    dd if="$tmp/recovery.bootfs" of="$tmp/file-power-cut.raw" bs=512 seek=2048 conv=notrunc status=none
  fi
  run_guest file-power-cut-recovery FIXTURE_DATA_RESTORED "$persistent_args" "$tmp/file-power-cut.raw"

  # Corrupt only a disposable copy. Valid ext4 magic/label with unsupported
  # feature bits reaches real kernel mount failure, not just helper validation.
  command -v debugfs >/dev/null || fail 'debugfs needed for mount-failure fixture'
  dd if="$tmp/setup.raw" of="$tmp/corrupt.bootfs" bs=512 skip=2048 count=1572864 status=none
  if [[ "$BOOT_FS" = vfat ]]; then
    fsck.fat -n "$tmp/corrupt.bootfs" >"$tmp/outer-fsck.log" 2>&1 || fail 'outer FAT not clean after shutdown'
  else
    e2fsck -fn "$tmp/corrupt.bootfs" >"$tmp/outer-fsck.log" 2>&1 || fail 'outer ext4 not clean after shutdown'
  fi
  if [[ "$BOOT_FS" = vfat ]]; then
    mcopy -i "$tmp/corrupt.bootfs" ::/ooonana-persistence.ext4 "$tmp/corrupt.storage"
  else
    debugfs -R "dump /ooonana-persistence.ext4 $tmp/corrupt.storage" "$tmp/corrupt.bootfs" >"$tmp/corrupt-dump.log" 2>&1
  fi
  e2fsck -fn "$tmp/corrupt.storage" >"$tmp/inner-fsck.log" 2>&1 || fail 'inner ext4 not clean after shutdown'
  debugfs -w -R 'set_super_value feature_incompat 0x80000000' "$tmp/corrupt.storage" >"$tmp/corrupt-feature.log" 2>&1
  corrupt_before="$(sha256sum "$tmp/corrupt.storage")"
  if [[ "$BOOT_FS" = vfat ]]; then
    mcopy -o -i "$tmp/corrupt.bootfs" "$tmp/corrupt.storage" ::/ooonana-persistence.ext4
  else
    debugfs -w -R 'rm /ooonana-persistence.ext4' "$tmp/corrupt.bootfs" >"$tmp/corrupt-replace.log" 2>&1
    debugfs -w -R "write $tmp/corrupt.storage /ooonana-persistence.ext4" "$tmp/corrupt.bootfs" >>"$tmp/corrupt-replace.log" 2>&1
  fi
  cp --sparse=always "$tmp/setup.raw" "$tmp/corrupt.raw"
  dd if="$tmp/corrupt.bootfs" of="$tmp/corrupt.raw" bs=512 seek=2048 conv=notrunc status=none
  inspect_recovery=1
  run_guest file-corrupt 'cannot mount persistence' "$persistent_args" "$tmp/corrupt.raw"
  inspect_recovery=0
  grep -q '^OOONANA_BOOT_STORAGE_READ_ONLY[[:space:]]*$' "$tmp/file-corrupt.log" || fail 'failed boot outer USB not readonly'
  grep -q '^FIXTURE_LOOP_CLOSED[[:space:]]*$' "$tmp/file-corrupt.log" || fail 'failed boot left loop attached'
  awk '$2 == "/mnt/iso" && $4 ~ /^ro,/ { found=1 } END { exit !found }' "$tmp/file-corrupt.log" || fail 'recovery mounts show writable USB'
  dd if="$tmp/corrupt.raw" of="$tmp/corrupt.bootfs" bs=512 skip=2048 count=1572864 status=none
  # Mtools can prompt for read-only existing host targets even with -o.
  # Delete only this owned scratch copy, never guest saved storage.
  rm "$tmp/corrupt.storage"
  if [[ "$BOOT_FS" = vfat ]]; then
    mcopy -i "$tmp/corrupt.bootfs" ::/ooonana-persistence.ext4 "$tmp/corrupt.storage"
  else
    debugfs -R "dump /ooonana-persistence.ext4 $tmp/corrupt.storage" "$tmp/corrupt.bootfs" >"$tmp/corrupt-dump-after.log" 2>&1
  fi
  [[ "$(sha256sum "$tmp/corrupt.storage")" = "$corrupt_before" ]] || fail 'failed boot modified saved image'

  # Exercise rollback after every handoff mount has moved, not just a failure
  # before overlay mounting. Changes below touch only extracted test initramfs.
  mkdir "$tmp/fault-init"
  gzip -dc "$tmp/live.cpio.gz" | (cd "$tmp/fault-init"; cpio -id --quiet --no-absolute-filenames)
  cp "$tmp/fault-init/init" "$tmp/init.original"
  sed -i '/^mount --move \/dev \/newroot\/dev /a fail "FIXTURE_LATE_HANDOFF_FAILURE"' "$tmp/fault-init/init"
  (cd "$tmp/fault-init"; find . -print0 | cpio --null -o --format=newc 2>/dev/null | gzip -n >"$tmp/live.cpio.gz")
  inspect_recovery=1
  run_guest file-late-handoff 'live init failed: FIXTURE_LATE_HANDOFF_FAILURE' "$persistent_args" "$tmp/setup.raw"
  inspect_recovery=0
  grep -q '^OOONANA_BOOT_STORAGE_READ_ONLY[[:space:]]*$' "$tmp/file-late-handoff.log" || fail 'late handoff USB writable'
  grep -q '^FIXTURE_LOOP_CLOSED[[:space:]]*$' "$tmp/file-late-handoff.log" || fail 'late handoff loop open'
  awk '$2 == "/mnt/iso" && $4 ~ /^ro,/ { found=1 } END { exit !found }' "$tmp/file-late-handoff.log" || fail 'late handoff mount not readonly'

  # Force ordinary unmount failure in a private copy. Repeated rescue-shell
  # exits must not return the shutdown action to PID1 or trigger power-down.
  cp "$tmp/init.original" "$tmp/fault-init/init"
  sed -i 's|^umount /oldroot$|echo FIXTURE_SHUTDOWN_FAULT; false|' "$tmp/fault-init/lib/ooonana-live-shutdown.sh"
  (cd "$tmp/fault-init"; find . -print0 | cpio --null -o --format=newc 2>/dev/null | gzip -n >"$tmp/live.cpio.gz")
  cp --sparse=always "$tmp/setup.raw" "$tmp/shutdown-fault.raw"
  mkfifo "$tmp/shutdown-fault.input"
  exec {fault_fd}<>"$tmp/shutdown-fault.input"
  qemu-system-x86_64 -accel "$QEMU_ACCEL" -m 384 -smp 1 -display none -serial stdio \
    -monitor none -no-reboot -kernel "$KERNEL" -initrd "$tmp/live.cpio.gz" \
    -append "console=ttyS0 panic=1 rdinit=/init ooonana.live=1 $persistent_args" \
    -device qemu-xhci,id=usb \
    -drive "if=none,id=stick,format=raw,file=$tmp/shutdown-fault.raw" -device usb-storage,bus=usb.0,drive=stick \
    -drive "if=none,id=unrelated,format=raw,file=$tmp/unrelated.ext4" -device usb-storage,bus=usb.0,drive=unrelated \
    <"$tmp/shutdown-fault.input" >"$tmp/shutdown-fault.log" 2>"$tmp/shutdown-fault.stderr" &
  qemu_pid=$!
  for ((elapsed=0; elapsed<QEMU_TIMEOUT; elapsed++)); do
    grep -q '^OOONANA_SHUTDOWN_CLEANUP_FAILED[[:space:]]*$' "$tmp/shutdown-fault.log" 2>/dev/null && break
    kill -0 "$qemu_pid" 2>/dev/null || fail 'shutdown fault exited before rescue'
    sleep 1
  done
  grep -q '^FIXTURE_SHUTDOWN_FAULT[[:space:]]*$' "$tmp/shutdown-fault.log" || fail 'shutdown fault not injected'
  grep -q '^OOONANA_SHUTDOWN_CLEANUP_FAILED[[:space:]]*$' "$tmp/shutdown-fault.log" || fail 'shutdown fault rescue missing'
  printf 'echo FIXTURE_RESCUE_BEGIN; cat /proc/mounts; echo FIXTURE_RESCUE_END\n' >&"$fault_fd"
  for ((elapsed=0; elapsed<15; elapsed++)); do
    grep -q '^FIXTURE_RESCUE_END[[:space:]]*$' "$tmp/shutdown-fault.log" && break
    kill -0 "$qemu_pid" 2>/dev/null || fail 'shutdown exited during rescue inspection'
    sleep 1
  done
  awk '$2 == "/iso" && $4 ~ /^rw,/ { found=1 } END { exit !found }' "$tmp/shutdown-fault.log" || fail 'rescue storage not inspected'
  for iteration in 1 2 3; do
    printf 'exit\n' >&"$fault_fd"
    for ((elapsed=0; elapsed<10; elapsed++)); do
      kill -0 "$qemu_pid" 2>/dev/null || fail 'rescue exit completed unsafe shutdown'
      held_count="$(grep -c '^OOONANA_SHUTDOWN_HELD[[:space:]]*$' "$tmp/shutdown-fault.log" || true)"
      (( held_count >= iteration )) && break
      sleep 1
    done
    (( held_count >= iteration )) || fail 'rescue exit did not reenter shutdown hold'
  done
  sleep 3
  kill -0 "$qemu_pid" 2>/dev/null || fail 'held shutdown guest powered off'
  if grep -Eq 'reboot: Power down|^OOONANA_SHUTDOWN_CLEANUP_DONE[[:space:]]*$' "$tmp/shutdown-fault.log"; then
    fail 'failed shutdown reported success or powered off'
  fi
  [[ "$(sha256sum "$tmp/unrelated.ext4")" = "$unrelated_before" ]] || fail 'shutdown hold changed unrelated USB'
  # Controlled host stop of this disposable fault guest; never poweroff host.
  kill "$qemu_pid"
  wait "$qemu_pid" 2>/dev/null || true
  qemu_pid=""
  exec {fault_fd}>&-
  printf 'ok persistence-qemu-file-shutdown-hold (three rescue exits)\n'
fi
printf 'ok live-persistence-qemu (unrelated USB hash unchanged)\n'
