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
assert_contains "$fragment_src" "CONFIG_EMBEDDED=y"
assert_contains "$fragment_src" "CONFIG_EXPERT=y"
assert_contains "$fragment_src" "CONFIG_EFI=y"
assert_contains "$fragment_src" "CONFIG_FB_EFI=y"
assert_contains "$fragment_src" "CONFIG_FB_SIMPLE=y"
assert_contains "$fragment_src" "CONFIG_SYSFB_SIMPLEFB=y"
assert_contains "$fragment_src" "CONFIG_FRAMEBUFFER_CONSOLE=y"
assert_contains "$fragment_src" "CONFIG_USB_SUPPORT=y"
assert_contains "$fragment_src" "CONFIG_USB_XHCI_HCD=y"
assert_contains "$fragment_src" "CONFIG_USB_STORAGE=y"
assert_contains "$fragment_src" "CONFIG_USB_HID=y"
assert_contains "$fragment_src" "CONFIG_INPUT_EVDEV=y"
assert_contains "$fragment_src" "CONFIG_OVERLAY_FS=y"
assert_contains "$fragment_src" "# CONFIG_MODULES is not set"
assert_contains "$fragment_src" "# CONFIG_DEBUG_KERNEL is not set"
assert_contains "$fragment_src" "# CONFIG_KALLSYMS is not set"
assert_contains "$fragment_src" "# CONFIG_BPF is not set"
assert_contains "$fragment_src" "# CONFIG_SOUND is not set"
assert_contains "$fragment_src" "# CONFIG_DRM is not set"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana Linux kernel"
assert_contains "$help" "--source"
assert_contains "$help" "--kernel"
assert_contains "$help" "--config-fragment"
assert_contains "$help" "--dry-run"

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

PATH="$tmp/bin:$PATH" \
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

env_file="$(<"$tmp/out/kernel.env")"
assert_contains "$env_file" "OOONANA_KERNEL=$tmp/out/custom-vmlinuz"
assert_contains "$env_file" "OOONANA_KERNEL_SOURCE=$tmp/source"
assert_contains "$env_file" "OOONANA_KERNEL_DEFCONFIG=x86_64_defconfig"

printf 'ok kernel-build\n'
