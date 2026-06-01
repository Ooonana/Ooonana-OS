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
assert_contains "$script_src" 'chmod -R a+rwX "$ROOTFS"'
assert_contains "$script_src" 'mknod -m 600 "$ROOTFS/dev/console" c 5 1 || : > "$ROOTFS/dev/console"'

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
[[ -L "$rootfs/bin/basename" ]] || fail "missing basename applet"
[[ -L "$rootfs/bin/dirname" ]] || fail "missing dirname applet"
[[ -L "$rootfs/bin/mv" ]] || fail "missing mv applet"
[[ -L "$rootfs/bin/readlink" ]] || fail "missing readlink applet"
[[ -L "$rootfs/bin/sed" ]] || fail "missing sed applet"
[[ -L "$rootfs/bin/sh" ]] || fail "missing sh applet"
[[ -L "$rootfs/bin/tar" ]] || fail "missing tar applet"
[[ -L "$rootfs/bin/sha256sum" ]] || fail "missing sha256sum applet"
[[ -L "$rootfs/bin/wc" ]] || fail "missing wc applet"
[[ -L "$rootfs/bin/awk" ]] || fail "missing awk applet"
[[ -L "$rootfs/sbin/reboot" ]] || fail "missing reboot applet"
[[ -x "$rootfs/sbin/init" ]] || fail "missing init"
[[ -x "$rootfs/etc/init.d/rcS" ]] || fail "missing rcS"
[[ -x "$rootfs/usr/bin/ooonana" ]] || fail "missing ooonana cli"
[[ -f "$rootfs/usr/share/ooonana/logo.txt" ]] || fail "missing ooonana logo"
[[ -f "$rootfs/etc/motd" ]] || fail "missing motd"
[[ -f "$rootfs/etc/issue" ]] || fail "missing issue"
[[ -f "$rootfs/etc/passwd" ]] || fail "missing passwd"
[[ -f "$rootfs/etc/group" ]] || fail "missing group"
[[ -f "$rootfs/etc/wsl.conf" ]] || fail "missing wsl.conf"
[[ -d "$rootfs/etc/ooonana/sources.d" ]] || fail "missing repo sources dir"
[[ -f "$rootfs/usr/lib/ooonana/repo/base.pkg" ]] || fail "missing base package metadata"
[[ -f "$rootfs/var/lib/ooonana/packages/installed/base.pkg" ]] || fail "missing installed base package marker"
[[ -f "$rootfs/usr/lib/ooonana/repo/gui.pkg" ]] || fail "missing ooonana repo metadata"
[[ -L "$rootfs/bin/dd" ]] || fail "missing dd applet"

rcs="$(<"$rootfs/etc/init.d/rcS")"
init_script="$(<"$rootfs/sbin/init")"
wsl_conf="$(<"$rootfs/etc/wsl.conf")"
passwd="$(<"$rootfs/etc/passwd")"
assert_contains "$init_script" "exec >/dev/console 2>&1 </dev/console"
assert_contains "$init_script" "/etc/init.d/rcS"
assert_contains "$wsl_conf" "[boot]"
assert_contains "$wsl_conf" "systemd=false"
assert_contains "$wsl_conf" "[user]"
assert_contains "$wsl_conf" "default=root"
assert_contains "$wsl_conf" "[automount]"
assert_contains "$wsl_conf" "mountFsTab=false"
assert_contains "$passwd" "root:x:0:0:root:/root:/bin/sh"
assert_contains "$rcs" "OOONANA_BOOT_OK"
assert_contains "$rcs" "OOONANA_CLI_OK"
assert_contains "$rcs" "OOONANA_INSTALL_OK"
assert_contains "$rcs" "Ooonana installer"
assert_contains "$rcs" "Target disk:"
assert_contains "$rcs" "Type INSTALL to erase"
assert_contains "$rcs" "read -r confirm"
assert_contains "$rcs" "OOONANA_INSTALL_CANCELLED"
assert_contains "$rcs" "ooonana.install=1"
assert_contains "$rcs" "ooonana.install.target="
assert_contains "$rcs" "cat /usr/share/ooonana/logo.txt"
assert_contains "$rcs" "ooonana-scratch-disk.raw"
assert_contains "$rcs" "ooonana-scratch.ext4"
assert_contains "$rcs" 'dd if="$install_image" of="$target" bs=4M'
assert_contains "$rcs" "/usr/bin/ooonana version"
assert_contains "$rcs" "/usr/bin/ooonana me"
assert_contains "$rcs" "/usr/bin/ooonana list --installed"
assert_contains "$rcs" "grep -q 'base'"
assert_contains "$rcs" "ooonana.smoke=1"
assert_contains "$rcs" "reboot -f"
assert_not_contains "$rcs" "poweroff -f"
diff -u "$rootfs/usr/share/ooonana/logo.txt" "$rootfs/etc/motd" || fail "motd logo mismatch"
diff -u "$rootfs/usr/share/ooonana/logo.txt" "$rootfs/etc/issue" || fail "issue logo mismatch"

real_busybox="/usr/lib/initramfs-tools/bin/busybox"
if [[ -x "$real_busybox" ]] && ldd "$real_busybox" 2>/dev/null | grep -q 'ld-linux'; then
  bash "$SCRIPT" --work-dir "$tmp/dynamic-build" --busybox "$real_busybox" --no-image --force >/dev/null
  [[ -e "$tmp/dynamic-build/scratch-rootfs/lib64/ld-linux-x86-64.so.2" ]] || fail "missing dynamic loader copy"
fi

printf 'ok scratch-rootfs\n'
