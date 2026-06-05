#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/import-i3-package-set.sh"
CLI="$ROOT/packages/ooonana/usr/bin/ooonana"
BUILTIN_REPO="$ROOT/packages/ooonana/usr/lib/ooonana/repo"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

make_fake_apk() {
  local path="$1"
  local name="$2"
  local version="$3"
  local tmp="$4"
  rm -rf "$tmp/pkg"
  mkdir -p "$tmp/pkg/usr/bin"
  cat > "$tmp/pkg/.PKGINFO" <<EOF
pkgname = $name
pkgver = $version
arch = x86_64
origin = $name
pkgdesc = Fake $name package
EOF
  printf '#!/bin/sh\necho %s\n' "$name" > "$tmp/pkg/usr/bin/$name"
  chmod +x "$tmp/pkg/usr/bin/$name"
  tar -C "$tmp/pkg" -czf "$path" .
}

[[ -x "$SCRIPT" ]] || fail "missing executable i3 package-set importer"
script_src="$(<"$SCRIPT")"
assert_contains "$script_src" "xsetroot"
assert_contains "$script_src" "xinput"
assert_contains "$script_src" "xf86-input-libinput"
assert_contains "$script_src" "xf86-input-evdev"
assert_contains "$script_src" "parted"
assert_contains "$script_src" "grub-bios"
assert_contains "$script_src" "rsync"
assert_contains "$script_src" "e2fsprogs"
assert_contains "$script_src" "coreutils"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
apk_repo="$tmp/apk-repo"
out="$tmp/ooonana-repo"
sources="$tmp/sources"
mkdir -p "$apk_repo" "$out" "$sources"

make_fake_apk "$apk_repo/i3wm-1.0-r0.apk" i3wm 1.0-r0 "$tmp"
make_fake_apk "$apk_repo/i3status-1.0-r0.apk" i3status 1.0-r0 "$tmp"
cat > "$tmp/APKINDEX" <<'EOF'
P:i3wm
V:1.0-r0
A:x86_64
S:123
D:
o:i3wm

P:i3status
V:1.0-r0
A:x86_64
S:123
D:
o:i3status

EOF
tar -C "$tmp" -czf "$apk_repo/APKINDEX.tar.gz" APKINDEX

bash "$SCRIPT" --repo-url "file://$apk_repo" --out-dir "$out" --packages "i3wm i3status"

[[ -f "$out/i3wm.pkg" ]] || fail "missing imported i3wm package"
[[ -f "$out/i3status.pkg" ]] || fail "missing imported i3status package"
[[ -f "$out/i3.pkg" ]] || fail "missing i3 wrapper"
[[ -f "$out/branding.pkg" ]] || fail "missing branding wrapper"
[[ -f "$out/full-i3.pkg" ]] || fail "missing full-i3 wrapper"
[[ -f "$out/archives/ooonana-branding-0.1.0.tar.gz" ]] || fail "missing branding archive"
[[ -f "$out/index.tsv" ]] || fail "missing index"
[[ -f "$out/SHA256SUMS" ]] || fail "missing checksums"

i3_pkg="$(<"$out/i3.pkg")"
branding_pkg="$(<"$out/branding.pkg")"
full_pkg="$(<"$out/full-i3.pkg")"
assert_contains "$i3_pkg" 'OOONANA_PKG_ID="i3"'
assert_contains "$i3_pkg" 'OOONANA_PKG_DEPS="i3wm i3status"'
assert_contains "$branding_pkg" 'OOONANA_PKG_ARCHIVE="archives/ooonana-branding-0.1.0.tar.gz"'
assert_contains "$full_pkg" 'OOONANA_PKG_DEPS="base branding i3"'

branding_contents="$(tar -tzf "$out/archives/ooonana-branding-0.1.0.tar.gz" | sort)"
assert_contains "$branding_contents" "./etc/i3/config"
assert_contains "$branding_contents" "./usr/share/ooonana/logo.svg"
assert_contains "$branding_contents" "./usr/share/ooonana/logo.png"
assert_contains "$branding_contents" "./usr/share/ooonana/wallpapers/ooonana-wallpaper.png"

cat > "$sources/i3.repo" <<EOF
OOONANA_REPO_NAME="i3test"
OOONANA_REPO_URI="$out"
EOF

dry_run="$(OOONANA_REPO_DIR="$BUILTIN_REPO" \
  OOONANA_SOURCES_DIR="$sources" \
  OOONANA_STATE_DIR="$tmp/state" \
  OOONANA_CACHE_DIR="$tmp/cache" \
  OOONANA_ROOT="$tmp/root" \
  "$CLI" get full-i3 --dry-run)"
assert_contains "$dry_run" "would install i3wm"
assert_contains "$dry_run" "would install i3status"
assert_contains "$dry_run" "would install i3"
assert_contains "$dry_run" "would install branding"
assert_contains "$dry_run" "would install full-i3"

printf 'ok i3-package-set\n'
