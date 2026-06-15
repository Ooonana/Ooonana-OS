#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/verify-vmware-uefi-input.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable verifier"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Verify Ooonana VMware, UEFI, and input readiness"
assert_contains "$help" "--release-dir"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin" "$tmp/release"
printf 'fake iso\n' > "$tmp/release/ooonana-full-i3.iso"
printf 'OOONANA_INSTALL_OK\n' > "$tmp/release/qemu-full-i3-uefi-installer.log"
cat > "$tmp/release/qemu-full-i3-live-iso.log" <<'EOF'
Using config directory: "/etc/X11/xorg.conf.d"
OOONANA_FULL_I3_OK
EOF
cat > "$tmp/fake-grub.cfg" <<'EOF'
terminal_input console serial
terminal_output console serial
linux /boot/vmlinuz console=ttyS0 console=tty0 panic=1
EOF

cat > "$tmp/bin/xorriso" <<'EOF'
#!/bin/sh
case "$*" in
  *-report_el_torito*)
    cat <<'REPORT'
--grub2-mbr --interval:local_fs:0s-15s:zero_mbrpt,zero_gpt,zero_apm:'fake.iso'
-eltorito-alt-boot
-e '/efi.img'
REPORT
    ;;
  *-extract*)
    for arg in "$@"; do
      last="$arg"
    done
    cp "$FAKE_GRUB_CFG" "$last"
    ;;
  *)
    exit 2
    ;;
esac
EOF
chmod +x "$tmp/bin/xorriso"

out="$(FAKE_GRUB_CFG="$tmp/fake-grub.cfg" PATH="$tmp/bin:$PATH" bash "$SCRIPT" --release-dir "$tmp/release")"
assert_contains "$out" "[done] UEFI + BIOS hybrid ISO"
assert_contains "$out" "[done] VMware-visible GRUB and VGA-first release console"
assert_contains "$out" "[done] init chooses tty1 for humans and ttyS0 for smoke"
assert_contains "$out" "[done] full-i3 input stack"
assert_contains "$out" "[done] VMware full-i3 2GB live-rootfs fix"
assert_contains "$out" "[done] QEMU UEFI installer and live i3 proof logs"
assert_contains "$out" "OOONANA_VMWARE_UEFI_INPUT_OK"

printf 'ok vmware-uefi-input-verify\n'
