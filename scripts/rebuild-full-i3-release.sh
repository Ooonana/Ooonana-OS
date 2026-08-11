#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
BUILD_DIR="${OOONANA_BUILD_DIR:-/mnt/winf/Ooonana/ooonana-os/build}"
RELEASE_DIR="${OOONANA_RELEASE_DIR:-/mnt/winf/Ooonana/ooonana-os/release-current}"
STAGE_DIR="${OOONANA_STAGE_DIR:-/var/tmp/ooonana-release-stage}"
RUN_BOOT_MATRIX=1
PREFLIGHT_ONLY=0
RESUME_AFTER_ROOTFS=0
RESUME_AFTER_ISO=0
MIN_FREE_KB=$((20 * 1024 * 1024))

usage() {
  cat <<'USAGE'
Build, verify, and promote the Ooonana full i3 ISO.

Usage:
  scripts/rebuild-full-i3-release.sh [options]

Options:
  --build-dir PATH       Build/cache directory
  --release-dir PATH     Release output directory
  --skip-boot-matrix     Skip direct BIOS and UEFI QEMU boots
  --preflight-only       Verify inputs and source without building
  --resume-after-rootfs  Reuse completed scratch and full rootfs
  --resume-after-iso     Reuse completed .iso.new and continue verification
  -h, --help             Show help
USAGE
}

die() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-dir) BUILD_DIR="$2"; shift 2 ;;
    --release-dir) RELEASE_DIR="$2"; shift 2 ;;
    --skip-boot-matrix) RUN_BOOT_MATRIX=0; shift ;;
    --preflight-only) PREFLIGHT_ONLY=1; shift ;;
    --resume-after-rootfs) RESUME_AFTER_ROOTFS=1; shift ;;
    --resume-after-iso) RESUME_AFTER_ISO=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[[ "${EUID:-$(id -u)}" -eq 0 ]] || die "run as root"

ensure_default_build_mount() {
  case "$BUILD_DIR" in
    /mnt/winf|/mnt/winf/*)
      mkdir -p /mnt/winf
      if ! mountpoint -q /mnt/winf; then
        mount -t drvfs F: /mnt/winf -o metadata,uid=0,gid=0,umask=022 ||
          die "could not mount F: at /mnt/winf"
      fi
      mount_source="$(findmnt -n -o SOURCE --target /mnt/winf 2>/dev/null || true)"
      mount_type="$(findmnt -n -o FSTYPE --target /mnt/winf 2>/dev/null || true)"
      [[ "$mount_source" == "F:" && "$mount_type" == "9p" ]] ||
        die "/mnt/winf is not the F: drvfs mount (source=$mount_source type=$mount_type)"
      ;;
  esac
}

for command_name in findmnt mount mountpoint; do
  command -v "$command_name" >/dev/null 2>&1 || die "missing command: $command_name"
done

ensure_default_build_mount

for command_name in awk cmp cp df find flock grep install mv python3 qemu-system-x86_64 realpath sha256sum sort stat sync timeout xargs; do
  command -v "$command_name" >/dev/null 2>&1 || die "missing command: $command_name"
done

mkdir -p /var/lock
exec 9>/var/lock/ooonana-full-i3-release.lock
flock -n 9 || die "another Ooonana full-i3 release build is already running"

STAGE_DIR="$(realpath -m "$STAGE_DIR")"
[[ "$STAGE_DIR" == /var/tmp/ooonana-* ]] ||
  die "unsafe stage directory: $STAGE_DIR"

KERNEL="$BUILD_DIR/ooonana-kernel/vmlinuz-ooonana"
KERNEL_CONFIG="$BUILD_DIR/ooonana-kernel/config-ooonana"
KERNEL_FRAGMENT="$ROOT/configs/kernel/ooonana-minimal-x86_64.fragment"
REPO="$BUILD_DIR/full-i3-repo"
NEW_ISO="$RELEASE_DIR/ooonana-full-i3.iso.new"
ISO="$RELEASE_DIR/ooonana-full-i3.iso"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/ooonana-release-check.XXXXXX")"
VERIFY_ISO="$NEW_ISO"
OVMF_VARS=""
QEMU_PID=""
QEMU_ACCEL="${OOONANA_QEMU_ACCEL:-}"
if [[ -z "$QEMU_ACCEL" ]]; then
  if [[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then
    QEMU_ACCEL=kvm
  else
    QEMU_ACCEL=tcg,thread=multi
  fi
fi

cleanup() {
  if [[ -n "$QEMU_PID" ]] && kill -0 "$QEMU_PID" 2>/dev/null; then
    kill "$QEMU_PID" 2>/dev/null || true
    wait "$QEMU_PID" 2>/dev/null || true
  fi
  [[ -n "$OVMF_VARS" ]] && rm -f "$OVMF_VARS"
  rm -rf "$WORK"
}
trap cleanup EXIT INT TERM

release_input_fingerprint() {
  {
    find \
      "$ROOT/branding" \
      "$ROOT/packages/ooonana" \
      "$ROOT/configs/packages/full-i3.list" \
      "$ROOT/scripts/build-scratch-rootfs.sh" \
      "$ROOT/scripts/build-scratch-initramfs.sh" \
      "$ROOT/scripts/build-full-i3-rootfs.sh" \
      "$ROOT/scripts/build-full-i3-live-initramfs.sh" \
      "$ROOT/scripts/build-full-i3-disk.sh" \
      "$ROOT/scripts/build-full-i3-iso.sh" \
      "$ROOT/scripts/install-intel-wireless-firmware.sh" \
      -type f -print0 |
      sort -z |
      xargs -0 sha256sum
    sha256sum "$KERNEL" "$KERNEL_CONFIG" "$REPO/SHA256SUMS" "$REPO/i3.pkg"
  } | sha256sum | awk '{ print $1 }'
}

mkdir -p "$BUILD_DIR" "$RELEASE_DIR"
if [[ "$RESUME_AFTER_ISO" -eq 0 ]]; then
  [[ -s "$KERNEL" ]] || die "missing cached kernel: $KERNEL"
  [[ -s "$KERNEL_CONFIG" ]] ||
    die "cached kernel has no resolved config; rebuild it with build-kernel.sh"
  while IFS= read -r kernel_option; do
    [[ -n "$kernel_option" ]] || continue
    grep -Fqx "$kernel_option" "$KERNEL_CONFIG" ||
      die "cached kernel differs from requested option: $kernel_option"
  done < <(grep -E '^CONFIG_[A-Z0-9_]+=' "$KERNEL_FRAGMENT")
  [[ -s "$REPO/index.tsv" ]] || die "missing package index: $REPO/index.tsv"
  [[ -s "$REPO/i3.pkg" ]] || die "package repo missing i3.pkg"
  [[ -s "$REPO/SHA256SUMS" ]] || die "missing package checksums: $REPO/SHA256SUMS"
  [[ -s "$REPO/dbus-daemon-launch-helper.pkg" ]] ||
    die "package repo missing dbus-daemon-launch-helper; rerun import-i3-package-set.sh"
  i3_deps="$(awk -F'"' '$1 == "OOONANA_PKG_DEPS=" { print $2; exit }' "$REPO/i3.pkg")"
  case " $i3_deps " in
    *' dbus-daemon-launch-helper '*) ;;
    *) die "stale i3.pkg dependency bundle; run import-i3-package-set.sh --metadata-only" ;;
  esac

  FIRMWARE_SCRIPT="$ROOT/scripts/install-intel-wireless-firmware.sh"
  FIRMWARE_VERSION="$(awk -F'"' '/^VERSION=/{ print $2; exit }' "$FIRMWARE_SCRIPT")"
  FIRMWARE_SHA256="$(awk -F'"' '/^SHA256=/{ print $2; exit }' "$FIRMWARE_SCRIPT")"
  FIRMWARE_APK="$BUILD_DIR/firmware-cache/linux-firmware-intel-$FIRMWARE_VERSION.apk"
  [[ -s "$FIRMWARE_APK" ]] || die "missing cached Intel wireless firmware: $FIRMWARE_APK"
  printf '%s  %s\n' "$FIRMWARE_SHA256" "$FIRMWARE_APK" | sha256sum -c - >/dev/null

  available_kb="$(df -Pk "$BUILD_DIR" | awk 'NR == 2 { print $4 }')"
  [[ "$available_kb" =~ ^[0-9]+$ ]] || die "cannot read build disk space"
  (( available_kb >= MIN_FREE_KB )) || die "need at least 20 GiB free in $BUILD_DIR"
  stage_available_kb="$(df -Pk "$(dirname "$STAGE_DIR")" | awk 'NR == 2 { print $4 }')"
  [[ "$stage_available_kb" =~ ^[0-9]+$ ]] || die "cannot read stage disk space"
  (( stage_available_kb >= MIN_FREE_KB )) || die "need at least 20 GiB free for stage: $STAGE_DIR"
else
  [[ -s "$NEW_ISO" ]] || die "missing completed ISO: $NEW_ISO"
fi

printf '[1/7] Preflight\n'
if [[ "$RESUME_AFTER_ISO" -eq 0 ]]; then
  (
    cd "$REPO"
    sha256sum -c SHA256SUMS >"$WORK/repo-check.log"
  )
fi
find "$ROOT/scripts" "$ROOT/tests" -type f -name '*.sh' -print0 |
  xargs -0 -n1 bash -n
grep -q 'GENERAL.NM-MANAGED' "$ROOT/packages/ooonana/usr/lib/ooonana/ui/wifi_app.py"
! grep -q 'GENERAL.MANAGED' "$ROOT/packages/ooonana/usr/lib/ooonana/ui/wifi_app.py"
! grep -q '"device", "set", device, "managed"' "$ROOT/packages/ooonana/usr/lib/ooonana/ui/wifi_app.py"
grep -q 'wifi.backend=wpa_supplicant' "$ROOT/scripts/build-full-i3-rootfs.sh"
grep -q 'auth-polkit=false' "$ROOT/scripts/build-full-i3-rootfs.sh"
grep -q 'CONFIG_UHID=y' "$ROOT/configs/kernel/ooonana-minimal-x86_64.fragment"
grep -q 'CONFIG_INPUT_UINPUT=y' "$ROOT/configs/kernel/ooonana-minimal-x86_64.fragment"
grep -q 'start_wpa_supplicant' "$ROOT/scripts/build-full-i3-rootfs.sh"
grep -q 'org.freedesktop.DBus.StartServiceByName' "$ROOT/scripts/build-full-i3-rootfs.sh"
! grep -q ' -f /var/log/wpa_supplicant.log' "$ROOT/scripts/build-full-i3-rootfs.sh"
! grep -q '"$supplicant" -u' "$ROOT/scripts/build-full-i3-rootfs.sh"
grep -q 'Do not validate certificate' "$ROOT/packages/ooonana/usr/lib/ooonana/ui/wifi_app.py"
grep -q 'WPA2/WPA3 Enterprise' "$ROOT/packages/ooonana/usr/lib/ooonana/ui/wifi_app.py"
grep -q 'Wi-Fi routers (orange)' "$ROOT/packages/ooonana/usr/lib/ooonana/ui/signal_map.py"
grep -q 'Nearby LAN devices (green)' "$ROOT/packages/ooonana/usr/lib/ooonana/ui/signal_map.py"
grep -q 'wifi-3d-fusion' "$ROOT/packages/ooonana/usr/lib/ooonana/ui/wifi_app.py"
bash "$ROOT/tests/test-logo-sync.sh"
PYTHONDONTWRITEBYTECODE=1 bash "$ROOT/tests/test-native-ui.sh"
bash "$ROOT/tests/test-qemu-service-smoke-source.sh"

if [[ "$PREFLIGHT_ONLY" -eq 1 ]]; then
  printf 'OOONANA_RELEASE_PREFLIGHT_OK\n'
  exit 0
fi

if [[ "$RESUME_AFTER_ISO" -eq 0 ]]; then
  rm -f "$NEW_ISO"
  input_fingerprint="$(release_input_fingerprint)"

  if [[ "$RESUME_AFTER_ROOTFS" -eq 0 ]]; then
    rm -rf "$STAGE_DIR"
    mkdir -p "$STAGE_DIR/ooonana-kernel" "$STAGE_DIR/firmware-cache"
    install -m 0755 "$KERNEL" "$STAGE_DIR/ooonana-kernel/vmlinuz-ooonana"
    cp -a "$REPO" "$STAGE_DIR/full-i3-repo"
    cp -a "$BUILD_DIR/firmware-cache/." "$STAGE_DIR/firmware-cache/"
    printf '%s\n' "$input_fingerprint" >"$STAGE_DIR/.release-inputs.sha256"
  else
    [[ -f "$STAGE_DIR/.ooonana-rootfs-complete" ]] ||
      die "resume stage is incomplete; rerun without --resume-after-rootfs"
    [[ "$(cat "$STAGE_DIR/.release-inputs.sha256" 2>/dev/null || true)" == "$input_fingerprint" ]] ||
      die "resume stage inputs changed; rerun without --resume-after-rootfs"
    [[ -s "$STAGE_DIR/ooonana-kernel/vmlinuz-ooonana" ]] ||
      die "resume stage missing kernel; rerun without --resume-after-rootfs"
    [[ -s "$STAGE_DIR/full-i3-repo/index.tsv" ]] ||
      die "resume stage missing package repo; rerun without --resume-after-rootfs"
    [[ -d "$STAGE_DIR/full-i3-rootfs" ]] ||
      die "resume stage missing full rootfs; rerun without --resume-after-rootfs"
  fi

  printf '[2/7] Scratch rootfs\n'
  if [[ "$RESUME_AFTER_ROOTFS" -eq 0 ]]; then
    bash "$ROOT/scripts/build-scratch-rootfs.sh" --work-dir "$STAGE_DIR" --force
    bash "$ROOT/scripts/build-scratch-initramfs.sh" --work-dir "$STAGE_DIR" --force

    printf '[3/7] Full rootfs\n'
    bash "$ROOT/scripts/build-full-i3-rootfs.sh" \
      --work-dir "$STAGE_DIR" \
      --repo "$STAGE_DIR/full-i3-repo" \
      --force
  else
    printf 'Reusing completed scratch and full rootfs\n'
    [[ -s "$STAGE_DIR/ooonana-scratch-initramfs.cpio.gz" ]] ||
      die "missing scratch initramfs; rerun without --resume-after-rootfs"
  fi

  ROOTFS="$STAGE_DIR/full-i3-rootfs"
  for command_name in python3 ooonana chromium nmcli bluetoothctl sudo su; do
    if [[ ! -x "$ROOTFS/usr/bin/$command_name" &&
          ! -x "$ROOTFS/bin/$command_name" &&
          ! -x "$ROOTFS/usr/sbin/$command_name" ]]; then
      die "generated rootfs missing: $command_name"
    fi
  done
  [[ -x "$ROOTFS/usr/libexec/dbus-daemon-launch-helper" ]] ||
    die "generated rootfs missing: dbus-daemon-launch-helper"
  [[ "$(stat -c %a "$ROOTFS/usr/libexec/dbus-daemon-launch-helper")" == "4750" ]] ||
    die "dbus-daemon-launch-helper has unsafe mode"
  [[ "$(stat -c %g "$ROOTFS/usr/libexec/dbus-daemon-launch-helper")" == "81" ]] ||
    die "dbus-daemon-launch-helper has wrong group"
  grep -q 'GENERAL.NM-MANAGED' "$ROOTFS/usr/lib/ooonana/ui/wifi_app.py"
  ! grep -q 'GENERAL.MANAGED' "$ROOTFS/usr/lib/ooonana/ui/wifi_app.py"
  ! grep -q '"device", "set", device, "managed"' "$ROOTFS/usr/lib/ooonana/ui/wifi_app.py"
  grep -q 'WPA2/WPA3 Enterprise' "$ROOTFS/usr/lib/ooonana/ui/wifi_app.py"
  grep -q 'Nearby LAN devices (green)' "$ROOTFS/usr/lib/ooonana/ui/signal_map.py"
  grep -q 'wifi.backend=wpa_supplicant' "$ROOTFS/etc/NetworkManager/NetworkManager.conf"
  grep -q 'auth-polkit=false' "$ROOTFS/etc/NetworkManager/NetworkManager.conf"
  grep -q 'managed=1' "$ROOTFS/etc/NetworkManager/NetworkManager.conf"
  grep -q 'start_wpa_supplicant' "$ROOTFS/usr/bin/ooonana-service-repair"
  grep -q 'org.freedesktop.DBus.StartServiceByName' "$ROOTFS/usr/bin/ooonana-service-repair"
  [[ -x "$ROOTFS/usr/bin/ooonana-service-watchdog" ]] ||
    die "generated rootfs missing: ooonana-service-watchdog"
  grep -q 'ooonana-service-repair force-wifi' "$ROOTFS/usr/bin/ooonana-service-watchdog"
  grep -q 'ooonana-service-repair force-bluetooth' "$ROOTFS/usr/bin/ooonana-service-watchdog"
  ! grep -q ' -f /var/log/wpa_supplicant.log' "$ROOTFS/usr/bin/ooonana-service-repair"
  ! grep -q '"$supplicant" -u' "$ROOTFS/usr/bin/ooonana-service-repair"
  cmp -s "$ROOTFS/usr/share/ooonana/logo.txt" "$ROOTFS/usr/share/ooonana/boot-logo.txt" ||
    die "generated rootfs boot logo differs from canonical logo"
  grep -q 'shadow = false' "$ROOTFS/etc/ooonana/picom.conf"
  grep -q 'governor="schedutil"' "$ROOTFS/etc/init.d/rcS"
  python3 "$ROOT/tests/audit-full-i3-runtime.py" "$ROOTFS"
  cp -f "$STAGE_DIR/ooonana-full-i3-rootfs.tar.gz" \
    "$BUILD_DIR/ooonana-full-i3-rootfs.tar.gz"
  rm -f "$STAGE_DIR/ooonana-full-i3-rootfs.tar.gz"
  : >"$STAGE_DIR/.ooonana-rootfs-complete"

  printf '[4/7] Live and installer images\n'
  bash "$ROOT/scripts/build-full-i3-live-initramfs.sh" --work-dir "$STAGE_DIR" --force
  bash "$ROOT/scripts/build-full-i3-disk.sh" --work-dir "$STAGE_DIR" --force

  printf '[5/7] ISO\n'
  bash "$ROOT/scripts/build-full-i3-iso.sh" \
    --work-dir "$STAGE_DIR" \
    --iso "$NEW_ISO" \
    --force
  rm -rf "$STAGE_DIR"
else
  printf '[2-5/7] Reusing completed ISO: %s\n' "$NEW_ISO"
fi

printf '[6/7] Verification\n'
if [[ "$(findmnt -n -o FSTYPE --target "$NEW_ISO" 2>/dev/null || true)" == "9p" ]]; then
  VERIFY_ISO="$WORK/ooonana-full-i3.iso"
  printf '[verify] Copying ISO to WSL-native storage for QEMU\n'
  cp "$NEW_ISO" "$VERIFY_ISO"
  [[ "$(stat -c %s "$VERIFY_ISO")" == "$(stat -c %s "$NEW_ISO")" ]] ||
    die "verification ISO copy is incomplete"
  sync "$VERIFY_ISO"
fi
bash "$ROOT/scripts/verify-rufus-iso.sh" --iso "$VERIFY_ISO" --edition full-i3
bash "$ROOT/tests/qemu-service-smoke.sh" --iso-runtime "$VERIFY_ISO"

boot_check() {
  local name="$1"
  shift
  local log="$WORK/$name.log"
  local status=0
  local deadline=$((SECONDS + 300))

  : >"$log"
  qemu-system-x86_64 \
    -accel "$QEMU_ACCEL" -machine q35 -m 2048 -smp 2 \
    "$@" \
    -cdrom "$VERIFY_ISO" -boot d \
    -display none -serial stdio -monitor none -no-reboot \
    >"$log" 2>&1 &
  QEMU_PID=$!

  while kill -0 "$QEMU_PID" 2>/dev/null; do
    if grep -q 'Ooonana full i3 rootfs' "$log"; then
      kill "$QEMU_PID" 2>/dev/null || true
      wait "$QEMU_PID" 2>/dev/null || true
      QEMU_PID=""
      printf 'PASS: %s boot\n' "$name"
      return 0
    fi
    if (( SECONDS >= deadline )); then
      kill "$QEMU_PID" 2>/dev/null || true
      wait "$QEMU_PID" 2>/dev/null || status=$?
      QEMU_PID=""
      break
    fi
    sleep 1
  done

  if [[ -n "$QEMU_PID" ]]; then
    wait "$QEMU_PID" 2>/dev/null || status=$?
    QEMU_PID=""
  fi

  if ! grep -q 'Ooonana full i3 rootfs' "$log"; then
    tail -200 "$log" >&2
    die "$name boot failed with status $status"
  fi
  printf 'PASS: %s boot\n' "$name"
}

if [[ "$RUN_BOOT_MATRIX" -eq 1 ]]; then
  boot_check bios

  uefi_args=()
  if [[ -f /usr/share/ovmf/OVMF.fd ]]; then
    uefi_args=(-bios /usr/share/ovmf/OVMF.fd)
  elif [[ -f /usr/share/OVMF/OVMF.fd ]]; then
    uefi_args=(-bios /usr/share/OVMF/OVMF.fd)
  elif [[ -f /usr/share/OVMF/OVMF_CODE_4M.fd && -f /usr/share/OVMF/OVMF_VARS_4M.fd ]]; then
    OVMF_VARS="$WORK/OVMF_VARS.fd"
    cp /usr/share/OVMF/OVMF_VARS_4M.fd "$OVMF_VARS"
    uefi_args=(
      -drive "if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd"
      -drive "if=pflash,format=raw,unit=1,file=$OVMF_VARS"
    )
  elif [[ -f /usr/share/OVMF/OVMF_CODE.fd ]]; then
    uefi_args=(-bios /usr/share/OVMF/OVMF_CODE.fd)
  else
    die "OVMF firmware missing; cannot verify UEFI boot"
  fi
  boot_check uefi "${uefi_args[@]}"
fi

printf '[7/7] Promote\n'
iso_sha256="$(sha256sum "$VERIFY_ISO" | awk '{ print $1 }')"
iso_size="$(stat -c %s "$VERIFY_ISO")"
mv -f "$NEW_ISO" "$ISO"
printf '%s  ooonana-full-i3.iso\n' "$iso_sha256" >"$RELEASE_DIR/ooonana-full-i3.iso.sha256"
sync
printf 'ISO: %s (%s bytes)\n' "$ISO" "$iso_size"
cat "$RELEASE_DIR/ooonana-full-i3.iso.sha256"
printf 'OOONANA_REBUILD_COMPLETE\n'
