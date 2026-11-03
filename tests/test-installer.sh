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
assert_contains "$installer_help" "--swap-size-mib N"
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
assert_contains "$uefi_partition_dry_run" '--checksum'
assert_not_contains "$installer_dry_run_normal" '--checksum'

duplicate_part="$(bash "$INSTALLER" --dry-run --yes \
  --target /dev/sda2 \
  --bootloader none \
  --home-part /dev/sda2 \
  --keep-root 2>&1 || true)"
assert_contains "$duplicate_part" "partition reused for install roles: /dev/sda2"

wiped_extra="$(bash "$INSTALLER" --dry-run --yes \
  --target /dev/sda \
  --home-part /dev/sda3 2>&1 || true)"
assert_contains "$wiped_extra" "whole-disk mode creates its own partitions; do not name extra partitions"
cross_disk_swap="$(bash "$INSTALLER" --dry-run --yes \
  --target /dev/sda2 --bootloader none --swap-part /dev/sdb3 2>&1 || true)"
assert_contains "$cross_disk_swap" "refusing cross-disk install partition: /dev/sdb3"
bad_swap_size="$(bash "$INSTALLER" --dry-run --yes \
  --target /dev/sda --swap-size-mib nope 2>&1 || true)"
assert_contains "$bad_swap_size" "--swap-size-mib must be a nonnegative integer"

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
assert_contains "$installer_src" "refusing live boot media partition"
assert_contains "$installer_src" "validate_partition_roles_same_disk"
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
assert_contains "$installer_src" "set theme=/boot/grub/theme.txt"
assert_contains "$installer_src" 'if [ "\$ooonana_theme_ready" = 1 ]; then'
assert_contains "$installer_src" 'if [ -z "\$theme" ]; then'
assert_contains "$installer_src" "set color_normal=yellow/black"
assert_contains "$installer_src" "set color_highlight=black/yellow"
grub_theme="$(<"$ROOT/packages/ooonana/usr/share/ooonana/grub.theme")"
assert_contains "$grub_theme" 'title-color: "#f5f5f7"'
assert_contains "$grub_theme" 'desktop-color: "#101317"'
assert_contains "$grub_theme" 'message-color: "#f5f5f7"'
assert_not_contains "$installer_src" "selected-item-color"
assert_not_contains "$installer_src" "selected-item-background-color"
assert_not_contains "$installer_src" "item-color"
assert_not_contains "$installer_src" "item-font"
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/tests/test-installed-grub-ui.py"

run_help="$(bash "$ROOT/scripts/run-qemu.sh" --help)"
assert_contains "$run_help" "--disk"
assert_contains "$run_help" "--install"
assert_contains "$run_help" "--disk-boot"

iso_help="$(bash "$ROOT/scripts/build-iso.sh" --help)"
assert_contains "$iso_help" "--install"
assert_contains "$iso_help" "--install-target"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/identity-source/etc" "$tmp/mutation-bin"
printf 'root:x:0:0:root:/root:/bin/sh\ndaemon:x:2:2:daemon:/tmp:/bin/false\nroot-alias:x:0:0:alias:/root:/bin/sh\n' >"$tmp/identity-source/etc/passwd"
printf 'inert QA target\n' >"$tmp/identity-target.raw"
for tool in parted mkfs.ext4 mkfs.vfat mount rsync grub-install losetup; do
  printf '#!/bin/sh\nprintf "UNSAFE_MUTATION\\n" >&2\nexit 99\n' >"$tmp/mutation-bin/$tool"
  chmod 0755 "$tmp/mutation-bin/$tool"
done
for option in user hostname theme; do
  case "$option" in
    user) bad_value=bad/name; expected_error='bad user name' ;;
    hostname) bad_value=bad/name; expected_error='bad hostname' ;;
    theme) bad_value=unknown; expected_error='theme must be dark or light' ;;
  esac
  identity_failure="$(printf 'fixture-password\n' | PATH="$tmp/mutation-bin:$PATH" bash "$INSTALLER" \
    --yes --target "$tmp/identity-target.raw" --source "$tmp/identity-source" \
    --mount-point "$tmp/identity-mount" --user fixture --password-stdin "--$option" "$bad_value" 2>&1 || true)"
  assert_contains "$identity_failure" "$expected_error"
  assert_not_contains "$identity_failure" UNSAFE_MUTATION
done
for account in root daemon root-alias; do
  identity_failure="$(printf 'fixture-password\n' | PATH="$tmp/mutation-bin:$PATH" bash "$INSTALLER" \
    --yes --target "$tmp/identity-target.raw" --source "$tmp/identity-source" \
    --mount-point "$tmp/identity-mount" --user "$account" --password-stdin 2>&1 || true)"
  if [[ "$account" == root ]]; then assert_contains "$identity_failure" 'bad user name';
  else assert_contains "$identity_failure" 'reserved or invalid install user'; fi
  assert_not_contains "$identity_failure" UNSAFE_MUTATION
done
[[ "$(<"$tmp/identity-target.raw")" == 'inert QA target' ]] || fail 'identity validation changed target'

sed '/^while \[\[ \$# -gt 0 \]\]/,$d' "$INSTALLER" >"$tmp/resume-copy.sh"
cat >>"$tmp/resume-copy.sh" <<'CHECK'
SOURCE="$1" MOUNT_POINT="$2" TARGET_MODE=partition FORMAT_ROOT=0 DRY_RUN=0
copy_rootfs
CHECK
mkdir -p "$tmp/resume-source/etc" "$tmp/resume-target/etc" "$tmp/resume-target/home"
printf 'new-data' >"$tmp/resume-source/etc/reproducible-file"
printf 'old-data' >"$tmp/resume-target/etc/reproducible-file"
touch -r "$tmp/resume-source/etc/reproducible-file" "$tmp/resume-target/etc/reproducible-file"
printf 'retained user data\n' >"$tmp/resume-target/home/retained"
bash "$tmp/resume-copy.sh" "$tmp/resume-source" "$tmp/resume-target"
cmp "$tmp/resume-source/etc/reproducible-file" "$tmp/resume-target/etc/reproducible-file" || fail 'resume skipped stale same-size/timestamp content'
[[ "$(<"$tmp/resume-target/home/retained")" == 'retained user data' ]] || fail 'resume removed unrelated user file'

sed '/^while \[\[ \$# -gt 0 \]\]/,$d' "$INSTALLER" >"$tmp/root-policy.sh"
printf '\nlock_installed_root "$1"\n' >>"$tmp/root-policy.sh"
mkdir -p "$tmp/root-policy/etc"
printf 'root::0:0:root:/root:/bin/sh\nfixture:x:1000:1000:fixture:/home/fixture:/bin/sh\n' >"$tmp/root-policy/etc/passwd"
printf 'fixture:fixture-hash:20000:0:99999:7:::\n' >"$tmp/root-policy/etc/shadow"
bash "$tmp/root-policy.sh" "$tmp/root-policy"
grep -qx 'root:x:0:0:root:/root:/bin/sh' "$tmp/root-policy/etc/passwd" || fail 'inline root password was not shadowed'
grep -q '^root:!:' "$tmp/root-policy/etc/shadow" || fail 'missing root shadow entry was not locked'
grep -qx 'fixture:fixture-hash:20000:0:99999:7:::' "$tmp/root-policy/etc/shadow" || fail 'root policy changed normal user'
[[ "$(stat -c %a "$tmp/root-policy/etc/shadow")" == 600 ]] || fail 'root shadow mode incorrect'
before_root_policy="$(sha256sum "$tmp/root-policy/etc/passwd" "$tmp/root-policy/etc/shadow")"
bash "$tmp/root-policy.sh" "$tmp/root-policy"
[[ "$(sha256sum "$tmp/root-policy/etc/passwd" "$tmp/root-policy/etc/shadow")" == "$before_root_policy" ]] || fail 'root policy not idempotent'
printf 'root:old-root-hash:20000:0:99999:7:::\n' >>"$tmp/root-policy/etc/shadow"
cp "$tmp/root-policy/etc/shadow" "$tmp/duplicate-root.before"
if bash "$tmp/root-policy.sh" "$tmp/root-policy"; then fail 'duplicate root shadow records accepted'; fi
cmp "$tmp/duplicate-root.before" "$tmp/root-policy/etc/shadow" || fail 'root policy replaced ambiguous shadow'
! compgen -G "$tmp/root-policy/etc/.*.install.*" >/dev/null || fail 'root policy leaked temporary files'

# A missing inventory tool must fail before target discovery or any mutation.
sed '/^while \[\[ \$# -gt 0 \]\]/,$d' "$INSTALLER" >"$tmp/missing-inventory.sh"
cat >>"$tmp/missing-inventory.sh" <<'CHECK'
DRY_RUN=0
PATH=/nonexistent-ooonana-qa-path
detect_target_mode() { printf 'unsafe discovery reached\n' >&2; return 1; }
prepare_target
CHECK
inventory_failure="$(bash "$tmp/missing-inventory.sh" 2>&1 || true)"
assert_contains "$inventory_failure" 'missing command: lsblk'
assert_not_contains "$inventory_failure" 'unsafe discovery reached'
sed '/^while \[\[ \$# -gt 0 \]\]/,$d' "$INSTALLER" >"$tmp/missing-operation-tool.sh"
cat >>"$tmp/missing-operation-tool.sh" <<'CHECK'
DRY_RUN=0
TARGET="$1"
MISSING_TOOL="$2"
SWAP_SIZE_MIB="${QA_SWAP_SIZE_MIB:-512}"
FORMAT_ROOT="${QA_FORMAT_ROOT:-1}"
detect_target_mode() { printf '%s\n' "${QA_TARGET_MODE:-disk}"; }
command() { [[ "$#" -eq 2 && "$1" == -v && "$2" != "$MISSING_TOOL" ]]; }
validate_current_root_safety() { printf 'operation preflight skipped\n' >&2; exit 99; }
prepare_target
CHECK
touch "$tmp/inert-image.raw"
for missing in blkid mkswap losetup; do
  operation_failure="$(bash "$tmp/missing-operation-tool.sh" "$tmp/inert-image.raw" "$missing" 2>&1 || true)"
  assert_contains "$operation_failure" "missing command: $missing"
  assert_not_contains "$operation_failure" 'operation preflight skipped'
done
partition_preflight_failure="$(QA_TARGET_MODE=partition QA_SWAP_SIZE_MIB=0 QA_FORMAT_ROOT=0 \
  bash "$tmp/missing-operation-tool.sh" /dev/ooonana-qa-inert blkid 2>&1 || true)"
assert_contains "$partition_preflight_failure" 'missing command: blkid'
assert_not_contains "$partition_preflight_failure" 'operation preflight skipped'
sed '/^while \[\[ \$# -gt 0 \]\]/,$d' "$INSTALLER" >"$tmp/fstab-driver.sh"
cat >>"$tmp/fstab-driver.sh" <<'CHECK'
DRY_RUN=0
TARGET_PART=/dev/vdb3
HOME_PART=/dev/vdb5
EFI_PART=/dev/vdb2
SWAP_PART=/dev/vdb4
FORMAT_ROOT="$2" FORMAT_HOME="$2" FORMAT_EFI="$2" FORMAT_SWAP="$2"
blkid() {
  [[ "$#" == 7 && "$1 $2 $3 $4 $5 $6" == '-p -s UUID -o value --' ]] || return 91
  if [[ "${7}" == "${FAIL_UUID_FOR:-}" ]]; then
    case "${UUID_FAILURE:-missing}" in
      missing) return 2 ;;
      empty) return 0 ;;
      malformed) printf 'bad uuid\n/dev/sda\n'; return 0 ;;
    esac
  fi
  case "${7}" in
    /dev/vdb3) printf 'deadbeef-1111-2222-3333-444455556666\n' ;;
    /dev/vdb5) printf '01234567-89ab-cdef-0123-456789abcdef\n' ;;
    /dev/vdb2) printf 'AB12-CD34\n' ;;
    /dev/vdb4) printf '00000000-aaaa-bbbb-cccc-123456789abc\n' ;;
    *) return 92 ;;
  esac
}
case "$1" in
  print) build_fstab ;;
  write) write_fstab "$3" ;;
  chmod-failure) chmod() { return 1; }; write_fstab "$3" ;;
  rename-failure) mv() { return 1; }; write_fstab "$3" ;;
esac
CHECK
expected_fstab=$'UUID=deadbeef-1111-2222-3333-444455556666 / ext4 defaults 0 1\nUUID=01234567-89ab-cdef-0123-456789abcdef /home ext4 defaults 0 2\nUUID=AB12-CD34 /boot/efi vfat umask=0077 0 1\nUUID=00000000-aaaa-bbbb-cccc-123456789abc none swap sw 0 0\nproc /proc proc defaults 0 0'
for formatted in 0 1; do
  actual_fstab="$(bash "$tmp/fstab-driver.sh" print "$formatted")"
  [[ "$actual_fstab" == "$expected_fstab" ]] || fail 'filesystem identities depend on format mode'
done
mkdir -p "$tmp/fstab-root/etc"
printf 'preserve old fstab\n' >"$tmp/fstab-root/etc/fstab"
cp "$tmp/fstab-root/etc/fstab" "$tmp/fstab.before"
for part in /dev/vdb3 /dev/vdb5 /dev/vdb2 /dev/vdb4; do
  for reason in missing empty malformed; do
    if FAIL_UUID_FOR="$part" UUID_FAILURE="$reason" bash "$tmp/fstab-driver.sh" write 0 "$tmp/fstab-root" >"$tmp/fstab-failure.log" 2>&1; then
      fail "accepted $reason UUID for $part"
    fi
    cmp "$tmp/fstab.before" "$tmp/fstab-root/etc/fstab" || fail 'UUID failure replaced existing fstab'
    ! compgen -G "$tmp/fstab-root/etc/.fstab.ooonana.*" >/dev/null || fail 'fstab temporary file leaked'
  done
done
for failure in chmod-failure rename-failure; do
  if bash "$tmp/fstab-driver.sh" "$failure" 0 "$tmp/fstab-root"; then
    fail "accepted fstab $failure"
  fi
  cmp "$tmp/fstab.before" "$tmp/fstab-root/etc/fstab" || fail 'failed publication changed fstab'
  ! compgen -G "$tmp/fstab-root/etc/.fstab.ooonana.*" >/dev/null || fail 'failed publication leaked temporary file'
done
bash "$tmp/fstab-driver.sh" write 0 "$tmp/fstab-root"
[[ "$(<"$tmp/fstab-root/etc/fstab")" == "$expected_fstab" ]] || fail 'UUID fstab publication failed'
[[ "$(stat -c %a "$tmp/fstab-root/etc/fstab")" == 644 ]] || fail 'wrong fstab permissions'

truncate -s 12G "$tmp/swap-disk.raw"
swap_preview="$(bash "$INSTALLER" --dry-run --yes \
  --target "$tmp/swap-disk.raw" --swap-size-mib 4096)"
assert_contains "$swap_preview" "mkpart ROOT ext4 515MiB 8192MiB mkpart SWAP linux-swap 8192MiB 100%"
assert_contains "$swap_preview" "mkswap -L OOONANA_SWAP LOOP_SWAP_PARTITION"
assert_contains "$swap_preview" "LABEL=OOONANA_SWAP none swap sw 0 0"
truncate -s 6G "$tmp/too-small.raw"
too_small="$(bash "$INSTALLER" --dry-run --yes \
  --target "$tmp/too-small.raw" --swap-size-mib 4096 2>&1 || true)"
assert_contains "$too_small" "target too small for root plus 4096 MiB swap"
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
