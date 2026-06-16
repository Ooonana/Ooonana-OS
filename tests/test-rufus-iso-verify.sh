#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/verify-rufus-iso.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable Rufus verifier"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Verify Ooonana ISO Rufus USB readiness"
assert_contains "$help" "--iso PATH"
assert_contains "$help" "--edition full-i3|minimal"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin"
printf 'fake iso\n' > "$tmp/full.iso"
printf 'fake iso\n' > "$tmp/min.iso"

cat > "$tmp/full-grub.cfg" <<'EOF'
terminal_input console serial
terminal_output console serial
set color_normal=yellow/black
set color_highlight=black/yellow
set timeout=5
cat /boot/grub/ooonana-logo.txt
menuentry 'Ooonana OS Full i3 Live' { linux /boot/vmlinuz console=ttyS0 console=tty0 }
menuentry 'Ooonana OS Full i3 Live (persistent USB)' { linux /boot/vmlinuz ooonana.persistence=1 }
menuentry 'Install Ooonana OS Full i3' { linux /boot/vmlinuz ooonana.install=1 ooonana.edition=full-i3; initrd /boot/live-initramfs.cpio.gz }
menuentry 'Install Ooonana OS Full i3 (safe graphics)' { linux /boot/vmlinuz ooonana.install=1 ooonana.edition=full-i3 nomodeset; initrd /boot/live-initramfs.cpio.gz }
EOF

cat > "$tmp/min-grub.cfg" <<'EOF'
terminal_input console serial
terminal_output console serial
set color_normal=yellow/black
set color_highlight=black/yellow
set theme=/boot/grub/theme.txt
export theme
set timeout=5
cat /boot/grub/ooonana-logo.txt
menuentry 'Ooonana OS Minimal' { linux /boot/vmlinuz console=ttyS0 console=tty0 }
EOF

cat > "$tmp/full-RUFUS.md" <<'EOF'
# Ooonana OS Rufus USB
Write in DD Image mode
Disable Secure Boot
OOONANA_PERSIST
EOF

cat > "$tmp/min-RUFUS.md" <<'EOF'
# Ooonana OS Minimal Rufus USB
Write in DD Image mode
Disable Secure Boot
Ooonana OS Minimal
EOF

cat > "$tmp/theme.txt" <<'EOF'
title-color: "#ffb21a"
message-color: "#ffb21a"
+ boot_menu {
  left = 16%
}
+ progress_bar {
  id = "__timeout__"
  fg_color = "#ffb21a"
  bg_color = "#1b1202"
}
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
  *"-extract /boot/grub/grub.cfg"*)
    for arg in "$@"; do
      last="$arg"
    done
    case "$OOONANA_FAKE_EDITION" in
      minimal) cp "$OOONANA_FAKE_ROOT/min-grub.cfg" "$last" ;;
      *) cp "$OOONANA_FAKE_ROOT/full-grub.cfg" "$last" ;;
    esac
    ;;
  *"-extract /boot/grub/theme.txt"*)
    for arg in "$@"; do
      last="$arg"
    done
    cp "$OOONANA_FAKE_ROOT/theme.txt" "$last"
    ;;
  *"-extract /RUFUS.md"*)
    for arg in "$@"; do
      last="$arg"
    done
    case "$OOONANA_FAKE_EDITION" in
      minimal) cp "$OOONANA_FAKE_ROOT/min-RUFUS.md" "$last" ;;
      *) cp "$OOONANA_FAKE_ROOT/full-RUFUS.md" "$last" ;;
    esac
    ;;
  *)
    exit 2
    ;;
esac
EOF
chmod +x "$tmp/bin/xorriso"

out="$(OOONANA_FAKE_ROOT="$tmp" OOONANA_FAKE_EDITION=full-i3 PATH="$tmp/bin:$PATH" bash "$SCRIPT" --iso "$tmp/full.iso")"
assert_contains "$out" "[done] ISOHybrid BIOS and UEFI boot paths"
assert_contains "$out" "[done] Rufus DD-mode note and orange GRUB"
assert_contains "$out" "[done] edition menus"
assert_contains "$out" "[done] release GRUB has no smoke auto-reboot args"
assert_contains "$out" "[done] USB-friendly volume labels"
assert_contains "$out" "OOONANA_RUFUS_ISO_OK"

minimal_out="$(OOONANA_FAKE_ROOT="$tmp" OOONANA_FAKE_EDITION=minimal PATH="$tmp/bin:$PATH" bash "$SCRIPT" --iso "$tmp/min.iso" --edition minimal)"
assert_contains "$minimal_out" "OOONANA_RUFUS_ISO_OK"

printf 'ok rufus-iso-verify\n'
