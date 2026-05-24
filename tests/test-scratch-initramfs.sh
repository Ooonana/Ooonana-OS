#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-scratch-initramfs.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable scratch initramfs builder"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana scratch initramfs"
assert_contains "$help" "--rootfs"
assert_contains "$help" "--initramfs"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

rootfs="$tmp/scratch-rootfs"
mkdir -p "$rootfs/bin" "$rootfs/etc" "$rootfs/dev"
cat > "$rootfs/init" <<'EOF'
#!/bin/sh
echo boot
EOF
chmod +x "$rootfs/init"
: > "$rootfs/bin/busybox"
chmod +x "$rootfs/bin/busybox"
: > "$rootfs/dev/console"
cat > "$rootfs/etc/os-release" <<'EOF'
NAME="Ooonana OS"
ID=ooonana
EOF

initramfs="$tmp/ooonana-scratch-initramfs.cpio.gz"
bash "$SCRIPT" --rootfs "$rootfs" --initramfs "$initramfs" --force >/dev/null

[[ -s "$initramfs" ]] || fail "missing initramfs output"
gzip -t "$initramfs"

listing="$(gzip -dc "$initramfs" | cpio -it 2>/dev/null)"
assert_contains "$listing" "init"
assert_contains "$listing" "bin/busybox"
assert_contains "$listing" "etc/os-release"

printf 'ok scratch-initramfs\n'
