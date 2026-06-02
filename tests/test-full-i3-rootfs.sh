#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-full-i3-rootfs.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable full-i3 rootfs builder"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
scratch="$tmp/scratch-rootfs"
repo="$tmp/repo"
mkdir -p \
  "$scratch/bin" \
  "$scratch/etc/ooonana" \
  "$scratch/usr/bin" \
  "$scratch/usr/lib/ooonana/repo" \
  "$scratch/usr/share/ooonana" \
  "$scratch/var/lib/ooonana/packages/installed" \
  "$repo"
cat > "$scratch/bin/sh" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$scratch/bin/sh"
cat > "$scratch/usr/bin/ooonana" <<'EOF'
#!/bin/sh
echo ooonana 0.7.0
EOF
chmod +x "$scratch/usr/bin/ooonana"
cat > "$scratch/usr/bin/ooonana-setup" <<'EOF'
#!/bin/sh
echo OOONANA_SETUP_OK
EOF
chmod +x "$scratch/usr/bin/ooonana-setup"
printf 'OOONANA_PKG_ID="base"\nOOONANA_PKG_VERSION="0.1.0"\nOOONANA_PKG_SUMMARY="Base"\n' > "$scratch/var/lib/ooonana/packages/installed/base.pkg"
cp "$scratch/var/lib/ooonana/packages/installed/base.pkg" "$scratch/usr/lib/ooonana/repo/base.pkg"

make_archive_pkg() {
  local id="$1"
  local payload_file="$2"
  local payload_text="$3"
  local payload_dir="$tmp/payload-$id"
  local archive="$repo/$id.tar.gz"
  rm -rf "$payload_dir"
  mkdir -p "$payload_dir/$(dirname "$payload_file")"
  printf '%s\n' "$payload_text" > "$payload_dir/$payload_file"
  tar -C "$payload_dir" -czf "$archive" .
  local archive_sha
  archive_sha="$(sha256sum "$archive" | awk '{print $1}')"
  cat > "$repo/$id.pkg" <<EOF
OOONANA_PKG_ID="$id"
OOONANA_PKG_VERSION="0.1.0"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="$id payload"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="$id.tar.gz"
OOONANA_PKG_SHA256="$archive_sha"
EOF
}

make_archive_pkg branding usr/share/ooonana/pkg-branding.txt branding-installed
make_archive_pkg fake-i3-bin usr/bin/fake-i3-bin fake-i3-installed
chmod +x "$tmp/payload-fake-i3-bin/usr/bin/fake-i3-bin" 2>/dev/null || true
tar -C "$tmp/payload-fake-i3-bin" -czf "$repo/fake-i3-bin.tar.gz" .
fake_i3_sha="$(sha256sum "$repo/fake-i3-bin.tar.gz" | awk '{print $1}')"
sed -i "s/^OOONANA_PKG_SHA256=.*/OOONANA_PKG_SHA256=\"$fake_i3_sha\"/" "$repo/fake-i3-bin.pkg"

cat > "$repo/i3.pkg" <<'EOF'
OOONANA_PKG_ID="i3"
OOONANA_PKG_VERSION="0.1.0"
OOONANA_PKG_KIND="profile"
OOONANA_PKG_SUMMARY="i3 profile"
OOONANA_PKG_DEPS="fake-i3-bin"
EOF

cat > "$repo/full-i3.pkg" <<'EOF'
OOONANA_PKG_ID="full-i3"
OOONANA_PKG_VERSION="0.1.0"
OOONANA_PKG_KIND="profile"
OOONANA_PKG_SUMMARY="full i3 profile"
OOONANA_PKG_DEPS="base branding i3"
EOF

"$ROOT/packages/ooonana/usr/bin/ooonana" repo index "$repo" >/dev/null

bash "$SCRIPT" \
  --scratch-rootfs "$scratch" \
  --repo "$repo" \
  --rootfs "$tmp/full-rootfs" \
  --tarball "$tmp/ooonana-full-i3-rootfs.tar.gz" \
  --force

rootfs="$tmp/full-rootfs"
[[ -f "$tmp/ooonana-full-i3-rootfs.tar.gz" ]] || fail "missing full-i3 tarball"
[[ -f "$rootfs/etc/ooonana/edition" ]] || fail "missing edition marker"
[[ "$(<"$rootfs/etc/ooonana/edition")" == "full-i3" ]] || fail "wrong edition marker"
[[ -x "$rootfs/usr/bin/start-ooonana-i3" ]] || fail "missing start script"
[[ -x "$rootfs/usr/bin/ooonana-gui-installer" ]] || fail "missing GUI installer"
[[ -x "$rootfs/usr/bin/ooonana-setup" ]] || fail "missing setup command"
[[ -x "$rootfs/usr/bin/ooonana-i3-session" ]] || fail "missing i3 session"
[[ -x "$rootfs/usr/bin/ooonana-i3-smoke-session" ]] || fail "missing GUI smoke session"
[[ -f "$rootfs/usr/share/ooonana/logo.svg" ]] || fail "missing rootfs logo svg"
[[ -f "$rootfs/usr/share/ooonana/logo.png" ]] || fail "missing rootfs logo png"
[[ -f "$rootfs/usr/share/ooonana/wallpapers/ooonana-wallpaper.png" ]] || fail "missing rootfs wallpaper"
[[ -f "$rootfs/etc/i3/config" ]] || fail "missing rootfs i3 config"
[[ -f "$rootfs/usr/share/applications/ooonana-installer.desktop" ]] || fail "missing GUI installer desktop entry"
[[ -f "$rootfs/usr/share/applications/ooonana-setup.desktop" ]] || fail "missing setup desktop entry"
[[ -d "$rootfs/var/log" ]] || fail "missing var log for Xorg"
assert_contains "$(<"$rootfs/etc/hosts")" "127.0.0.1 localhost ooonana"
[[ -f "$rootfs/var/lib/ooonana/packages/installed/branding.pkg" ]] || fail "missing branding installed marker"
[[ -f "$rootfs/var/lib/ooonana/packages/installed/i3.pkg" ]] || fail "missing i3 installed marker"
[[ -f "$rootfs/var/lib/ooonana/packages/installed/full-i3.pkg" ]] || fail "missing full-i3 installed marker"
[[ -f "$rootfs/var/lib/ooonana/packages/installed/fake-i3-bin.pkg" ]] || fail "missing fake i3 installed marker"
[[ -f "$rootfs/usr/share/ooonana/pkg-branding.txt" ]] || fail "branding package payload not installed"
[[ -x "$rootfs/usr/bin/fake-i3-bin" ]] || fail "i3 package payload not installed"
[[ -f "$rootfs/var/lib/ooonana/packages/files/branding.list" ]] || fail "missing branding file manifest"
[[ "$(<"$rootfs/etc/ooonana/edition-state")" == "packages-installed" ]] || fail "full-i3 packages not installed through package manager"

start_script="$(<"$rootfs/usr/bin/start-ooonana-i3")"
assert_contains "$start_script" "OOONANA_FULL_I3_OK"
assert_contains "$start_script" "startx"
assert_contains "$start_script" "ooonana.gui-smoke=1"
assert_contains "$start_script" "ooonana-i3-session"

i3_session="$(<"$rootfs/usr/bin/ooonana-i3-session")"
assert_contains "$i3_session" "ooonana-setup --first-boot --gui"
assert_contains "$i3_session" "/var/log/ooonana-setup.log"
assert_contains "$i3_session" 'xsetroot -solid "#ffb21a"'
assert_contains "$i3_session" "exec i3"

gui_installer="$(<"$rootfs/usr/bin/ooonana-gui-installer")"
assert_contains "$gui_installer" "xmessage"
assert_contains "$gui_installer" "/usr/sbin/ooonana-install"

rcs="$(<"$rootfs/etc/init.d/rcS")"
assert_contains "$rcs" "Ooonana full i3 rootfs"
assert_contains "$rcs" "mount -t devpts devpts /dev/pts"
assert_contains "$rcs" "/usr/bin/start-ooonana-i3"
assert_contains "$rcs" "OOONANA_FULL_I3_FAIL"
assert_contains "$rcs" "OOONANA_BOOT_OK"

contents="$(tar -tzf "$tmp/ooonana-full-i3-rootfs.tar.gz" | sort)"
assert_contains "$contents" "./etc/init.d/rcS"
assert_contains "$contents" "./etc/ooonana/edition"
assert_contains "$contents" "./usr/bin/ooonana-gui-installer"
assert_contains "$contents" "./usr/bin/ooonana-setup"
assert_contains "$contents" "./usr/bin/ooonana-i3-session"
assert_contains "$contents" "./usr/bin/start-ooonana-i3"
assert_contains "$contents" "./usr/share/ooonana/wallpapers/ooonana-wallpaper.png"

printf 'ok full-i3-rootfs\n'
