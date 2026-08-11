#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-kernel.sh"
FRAGMENT="$ROOT/configs/kernel/ooonana-minimal-x86_64.fragment"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable kernel builder"
[[ -f "$FRAGMENT" ]] || fail "missing minimal kernel fragment"

fragment_src="$(<"$FRAGMENT")"
assert_contains "$fragment_src" "CONFIG_EXPERT=y"
assert_contains "$fragment_src" "CONFIG_EFI=y"
assert_contains "$fragment_src" "CONFIG_EFI_STUB=y"
assert_contains "$fragment_src" "CONFIG_EFIVAR_FS=y"
assert_contains "$fragment_src" "CONFIG_FB_EFI=y"
assert_contains "$fragment_src" "CONFIG_SYSFB_SIMPLEFB=y"
assert_contains "$fragment_src" "CONFIG_FRAMEBUFFER_CONSOLE=y"
assert_contains "$fragment_src" "CONFIG_USB_SUPPORT=y"
assert_contains "$fragment_src" "CONFIG_USB_XHCI_HCD=y"
assert_contains "$fragment_src" "CONFIG_USB_STORAGE=y"
assert_contains "$fragment_src" "CONFIG_USB_HID=y"
assert_contains "$fragment_src" "CONFIG_USB_RTL8152=y"
assert_contains "$fragment_src" "CONFIG_USB_VIDEO_CLASS=y"
assert_contains "$fragment_src" "CONFIG_CFG80211=y"
assert_contains "$fragment_src" "# CONFIG_CFG80211_DEFAULT_PS is not set"
assert_contains "$fragment_src" "CONFIG_MAC80211=y"
assert_contains "$fragment_src" "CONFIG_RFKILL=y"
assert_contains "$fragment_src" "CONFIG_FW_LOADER=y"
assert_contains "$fragment_src" "CONFIG_FW_LOADER_COMPRESS=y"
assert_contains "$fragment_src" "CONFIG_FW_LOADER_COMPRESS_ZSTD=y"
assert_contains "$fragment_src" "CONFIG_IWLWIFI=y"
assert_contains "$fragment_src" "CONFIG_IWLMVM=y"
assert_contains "$fragment_src" "CONFIG_RTW88=y"
assert_contains "$fragment_src" "CONFIG_RTW89=y"
assert_contains "$fragment_src" "CONFIG_MT7921E=y"
assert_contains "$fragment_src" "CONFIG_BRCMFMAC=y"
assert_contains "$fragment_src" "CONFIG_ATH11K_PCI=y"
assert_contains "$fragment_src" "CONFIG_E1000E=y"
assert_contains "$fragment_src" "CONFIG_IGC=y"
assert_contains "$fragment_src" "CONFIG_R8169=y"
assert_contains "$fragment_src" "CONFIG_BT=y"
assert_contains "$fragment_src" "CONFIG_BT_HCIBTUSB=y"
assert_contains "$fragment_src" "CONFIG_BT_INTEL=y"
assert_contains "$fragment_src" "CONFIG_BT_RTL=y"
assert_contains "$fragment_src" "CONFIG_UHID=y"
assert_contains "$fragment_src" "CONFIG_INPUT_UINPUT=y"
assert_contains "$fragment_src" "CONFIG_MMC=y"
assert_contains "$fragment_src" "CONFIG_MMC_SDHCI_PCI=y"
assert_contains "$fragment_src" "CONFIG_MMC_REALTEK_PCI=y"
assert_contains "$fragment_src" "CONFIG_MISC_RTSX_PCI=y"
assert_contains "$fragment_src" "CONFIG_BLK_DEV_LOOP=y"
assert_contains "$fragment_src" "CONFIG_ISO9660_FS=y"
assert_contains "$fragment_src" "CONFIG_VFAT_FS=y"
assert_contains "$fragment_src" "CONFIG_EXFAT_FS=y"
assert_contains "$fragment_src" "CONFIG_BLK_DEV_SR=y"
assert_contains "$fragment_src" "CONFIG_SCSI=y"
assert_contains "$fragment_src" "CONFIG_BLK_DEV_SD=y"
assert_contains "$fragment_src" "CONFIG_BLK_DEV_NVME=y"
assert_contains "$fragment_src" "CONFIG_SATA_AHCI=y"
assert_contains "$fragment_src" "CONFIG_INPUT_EVDEV=y"
assert_contains "$fragment_src" "CONFIG_MOUSE_PS2_SYNAPTICS=y"
assert_contains "$fragment_src" "CONFIG_MOUSE_PS2_SYNAPTICS_SMBUS=y"
assert_contains "$fragment_src" "CONFIG_MOUSE_PS2_ELANTECH=y"
assert_contains "$fragment_src" "CONFIG_MOUSE_PS2_ELANTECH_SMBUS=y"
assert_contains "$fragment_src" "CONFIG_I2C_HID_ACPI=y"
assert_contains "$fragment_src" "CONFIG_HID_MULTITOUCH=y"
assert_contains "$fragment_src" "CONFIG_HID_RMI=y"
assert_contains "$fragment_src" "CONFIG_HID_ELAN=y"
assert_contains "$fragment_src" "CONFIG_I2C_AMD_MP2=y"
assert_contains "$fragment_src" "CONFIG_MFD_INTEL_LPSS=y"
assert_contains "$fragment_src" "CONFIG_MFD_INTEL_LPSS_ACPI=y"
assert_contains "$fragment_src" "CONFIG_MFD_INTEL_LPSS_PCI=y"
assert_contains "$fragment_src" "CONFIG_INTEL_ISH_HID=y"
assert_contains "$fragment_src" "CONFIG_AMD_SFH_HID=y"
assert_contains "$fragment_src" "CONFIG_SAMSUNG_GALAXYBOOK=y"
assert_contains "$fragment_src" "CONFIG_PINCTRL_METEORLAKE=y"
assert_contains "$fragment_src" "CONFIG_PINCTRL_METEORPOINT=y"
assert_contains "$fragment_src" "CONFIG_OVERLAY_FS=y"
assert_contains "$fragment_src" "CONFIG_CC_OPTIMIZE_FOR_PERFORMANCE=y"
assert_contains "$fragment_src" "CONFIG_PREEMPT=y"
assert_contains "$fragment_src" "CONFIG_PREEMPT_DYNAMIC=y"
assert_contains "$fragment_src" "CONFIG_HIGH_RES_TIMERS=y"
assert_contains "$fragment_src" "CONFIG_HZ_1000=y"
assert_contains "$fragment_src" "CONFIG_HZ=1000"
assert_contains "$fragment_src" "CONFIG_SCHED_AUTOGROUP=y"
assert_contains "$fragment_src" "# CONFIG_MODULES is not set"
assert_contains "$fragment_src" "# CONFIG_DEBUG_KERNEL is not set"
assert_contains "$fragment_src" "# CONFIG_KALLSYMS is not set"
assert_contains "$fragment_src" "# CONFIG_BPF is not set"
assert_contains "$fragment_src" "CONFIG_SOUND=y"
assert_contains "$fragment_src" "CONFIG_SND_HDA_INTEL=y"
assert_contains "$fragment_src" "CONFIG_SND_USB_AUDIO=y"
assert_contains "$fragment_src" "CONFIG_SND_SOC_SOF_ALDERLAKE=y"
assert_contains "$fragment_src" "CONFIG_SND_SOC_SOF_METEORLAKE=y"
assert_contains "$fragment_src" "CONFIG_SND_SOC_SOF_HDA_LINK=y"
assert_contains "$fragment_src" "CONFIG_SND_SOC_INTEL_SOUNDWIRE_SOF_MACH=y"
assert_contains "$fragment_src" "CONFIG_SND_SOC_MAX98390=y"
assert_contains "$fragment_src" "CONFIG_SECCOMP_FILTER=y"
assert_contains "$fragment_src" "CONFIG_SOUNDWIRE_INTEL=y"
assert_contains "$fragment_src" "CONFIG_DRM=y"
assert_contains "$fragment_src" "CONFIG_DRM_AMDGPU=y"
assert_contains "$fragment_src" "CONFIG_DRM_RADEON=y"
assert_contains "$fragment_src" "CONFIG_DRM_NOUVEAU=y"
assert_contains "$fragment_src" "CONFIG_DRM_BOCHS=y"
assert_contains "$fragment_src" "CONFIG_DRM_VIRTIO_GPU=y"
assert_contains "$fragment_src" "CONFIG_DRM_SIMPLEDRM=y"
assert_contains "$fragment_src" "CONFIG_USB_ROLE_SWITCH=y"
assert_contains "$fragment_src" "CONFIG_TYPEC=y"
assert_contains "$fragment_src" "CONFIG_TYPEC_UCSI=y"
assert_contains "$fragment_src" "CONFIG_UCSI_ACPI=y"
assert_contains "$fragment_src" "CONFIG_IPV6=y"
assert_contains "$fragment_src" "CONFIG_VLAN_8021Q=y"
assert_contains "$fragment_src" "CONFIG_TUN=y"

kernel_builder_src="$(<"$SCRIPT")"
assert_contains "$kernel_builder_src" "verify_required_config"
assert_contains "$kernel_builder_src" "required kernel option did not resolve"
assert_contains "$kernel_builder_src" "BT BT_HCIBTUSB UHID INPUT_UINPUT"
assert_contains "$kernel_builder_src" 'install -m 0644 "$KERNEL_BUILD/.config" "$KERNEL_OUT/config-ooonana"'

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana Linux kernel"
assert_contains "$help" "--source"
assert_contains "$help" "--kernel"
assert_contains "$help" "--config-fragment"
assert_contains "$help" "--dry-run"
assert_contains "$help" "--resume"
assert_contains "$kernel_builder_src" 'cannot resume: missing $KERNEL_BUILD/.config'

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/source/arch/x86" "$tmp/source/scripts/kconfig" "$tmp/bin"
touch "$tmp/source/Makefile"
mkdir -p "$tmp/fragment dir"
printf 'CONFIG_DEVTMPFS=y\nCONFIG_DEVTMPFS_MOUNT=y\n' > "$tmp/fragment dir/fragment.config"

cat > "$tmp/source/scripts/kconfig/merge_config.sh" <<EOF
#!/bin/sh
[ "\$(pwd)" = "$tmp/source" ] || exit 21
out=""
base=""
while [ "\$#" -gt 0 ]; do
  case "\$1" in
    -O)
      shift
      out="\$1"
      ;;
    *)
      case "\$1" in
        *" "*) exit 22 ;;
      esac
      if [ -z "\$base" ]; then
        base="\$1"
      else
        cat "\$1" >> "\$out/.config"
      fi
      ;;
  esac
  shift || true
done
EOF
chmod +x "$tmp/source/scripts/kconfig/merge_config.sh"

dry_run="$(bash "$SCRIPT" \
  --source "$tmp/source" \
  --build-dir "$tmp/build" \
  --out-dir "$tmp/out" \
  --jobs 2 \
  --dry-run)"
assert_contains "$dry_run" "make -C $tmp/source"
assert_contains "$dry_run" "x86_64_defconfig"
assert_contains "$dry_run" "configs/kernel/ooonana-minimal-x86_64.fragment"
assert_contains "$dry_run" "bzImage"
assert_contains "$dry_run" "$tmp/out/vmlinuz-ooonana"

cat > "$tmp/bin/make" <<'EOF'
#!/bin/sh
out=""
target=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -C)
      shift
      ;;
    O=*)
      out="${1#O=}"
      ;;
    -j)
      shift
      ;;
    -j*)
      ;;
    *)
      target="$1"
      ;;
  esac
  shift || true
done

[ -n "$out" ] || exit 7
if [ "$target" = "x86_64_defconfig" ]; then
  mkdir -p "$out"
  printf 'CONFIG_BASE=y\n' > "$out/.config"
fi
if [ "$target" = "bzImage" ]; then
  mkdir -p "$out/arch/x86/boot"
  printf 'fake kernel\n' > "$out/arch/x86/boot/bzImage"
fi
EOF
chmod +x "$tmp/bin/make"

PATH="$tmp/bin:$PATH" OOONANA_VERIFY_HARDWARE_CONFIG=0 \
bash "$SCRIPT" \
  --source "$tmp/source" \
  --build-dir "$tmp/build" \
  --out-dir "$tmp/out" \
  --kernel "$tmp/out/custom-vmlinuz" \
  --config-fragment "$tmp/fragment dir/fragment.config" \
  --jobs 2 \
  --force >/dev/null

[[ -f "$tmp/out/custom-vmlinuz" ]] || fail "missing kernel output"
[[ "$(<"$tmp/out/custom-vmlinuz")" == "fake kernel" ]] || fail "wrong kernel payload"
grep -q 'CONFIG_DEVTMPFS=y' "$tmp/build/.config" || fail "missing config fragment"
[[ -f "$tmp/out/kernel.env" ]] || fail "missing kernel env"
[[ -f "$tmp/out/config-ooonana" ]] || fail "missing resolved kernel config"

env_file="$(<"$tmp/out/kernel.env")"
assert_contains "$env_file" "OOONANA_KERNEL=$tmp/out/custom-vmlinuz"
assert_contains "$env_file" "OOONANA_KERNEL_SOURCE=$tmp/source"
assert_contains "$env_file" "OOONANA_KERNEL_DEFCONFIG=x86_64_defconfig"
assert_contains "$env_file" "OOONANA_KERNEL_CONFIG=$tmp/out/config-ooonana"
assert_contains "$env_file" "OOONANA_KERNEL_CONFIG_SHA256="

printf 'ok kernel-build\n'
