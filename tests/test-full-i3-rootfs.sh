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
printf 'OOONANA_PKG_ID="base"\nOOONANA_PKG_VERSION="0.1.0"\nOOONANA_PKG_SUMMARY="Base"\n' > "$scratch/var/lib/ooonana/packages/installed/base.pkg"
for pkg in branding i3 full-i3; do
  cat > "$repo/$pkg.pkg" <<EOF
OOONANA_PKG_ID="$pkg"
OOONANA_PKG_VERSION="0.1.0"
OOONANA_PKG_KIND="profile"
OOONANA_PKG_SUMMARY="$pkg profile"
OOONANA_PKG_DEPS=""
EOF
done

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
[[ -f "$rootfs/usr/share/ooonana/logo.svg" ]] || fail "missing rootfs logo svg"
[[ -f "$rootfs/usr/share/ooonana/logo.png" ]] || fail "missing rootfs logo png"
[[ -f "$rootfs/usr/share/ooonana/wallpapers/ooonana-wallpaper.png" ]] || fail "missing rootfs wallpaper"
[[ -f "$rootfs/etc/i3/config" ]] || fail "missing rootfs i3 config"
[[ -f "$rootfs/var/lib/ooonana/packages/installed/branding.pkg" ]] || fail "missing branding installed marker"
[[ -f "$rootfs/var/lib/ooonana/packages/installed/i3.pkg" ]] || fail "missing i3 installed marker"
[[ -f "$rootfs/var/lib/ooonana/packages/installed/full-i3.pkg" ]] || fail "missing full-i3 installed marker"

start_script="$(<"$rootfs/usr/bin/start-ooonana-i3")"
assert_contains "$start_script" "OOONANA_FULL_I3_OK"
assert_contains "$start_script" "startx"

contents="$(tar -tzf "$tmp/ooonana-full-i3-rootfs.tar.gz" | sort)"
assert_contains "$contents" "./etc/ooonana/edition"
assert_contains "$contents" "./usr/bin/start-ooonana-i3"
assert_contains "$contents" "./usr/share/ooonana/wallpapers/ooonana-wallpaper.png"

printf 'ok full-i3-rootfs\n'
