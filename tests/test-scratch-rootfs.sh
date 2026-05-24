#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-scratch-rootfs.sh"

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

[[ -x "$SCRIPT" ]] || fail "missing executable scratch builder"

script_src="$(<"$SCRIPT")"
assert_not_contains "$script_src" "debootstrap"
assert_not_contains "$script_src" "apt-get"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana scratch rootfs"
assert_contains "$help" "--busybox"
assert_contains "$help" "--no-image"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

fake_busybox="$tmp/busybox"
cat > "$fake_busybox" <<'EOF'
#!/bin/sh
echo "fake busybox"
EOF
chmod +x "$fake_busybox"

bash "$SCRIPT" --work-dir "$tmp/build" --busybox "$fake_busybox" --no-image --force >/dev/null

rootfs="$tmp/build/scratch-rootfs"
[[ -x "$rootfs/bin/busybox" ]] || fail "missing busybox"
[[ -L "$rootfs/bin/sh" ]] || fail "missing sh applet"
[[ -L "$rootfs/sbin/reboot" ]] || fail "missing reboot applet"
[[ -x "$rootfs/sbin/init" ]] || fail "missing init"
[[ -x "$rootfs/etc/init.d/rcS" ]] || fail "missing rcS"
[[ -x "$rootfs/usr/bin/ooonana" ]] || fail "missing ooonana cli"
[[ -f "$rootfs/usr/lib/ooonana/repo/gui.pkg" ]] || fail "missing ooonana repo metadata"

rcs="$(<"$rootfs/etc/init.d/rcS")"
assert_contains "$rcs" "OOONANA_BOOT_OK"
assert_contains "$rcs" "ooonana.smoke=1"
assert_contains "$rcs" "reboot -f"
assert_not_contains "$rcs" "poweroff -f"

real_busybox="/usr/lib/initramfs-tools/bin/busybox"
if [[ -x "$real_busybox" ]] && ldd "$real_busybox" 2>/dev/null | grep -q 'ld-linux'; then
  bash "$SCRIPT" --work-dir "$tmp/dynamic-build" --busybox "$real_busybox" --no-image --force >/dev/null
  [[ -e "$tmp/dynamic-build/scratch-rootfs/lib64/ld-linux-x86-64.so.2" ]] || fail "missing dynamic loader copy"
fi

printf 'ok scratch-rootfs\n'
