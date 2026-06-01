#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/import-apk-package.sh"

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

make_fake_apk() {
  local path="$1"
  local name="$2"
  local version="$3"
  local dep="${4:-}"
  local tmp="$5"
  rm -rf "$tmp/pkg"
  mkdir -p "$tmp/pkg/usr/bin" "$tmp/pkg/usr/share/$name"
  cat > "$tmp/pkg/.PKGINFO" <<EOF
pkgname = $name
pkgver = $version
arch = x86_64
origin = $name
pkgdesc = Fake $name package
url = https://example.invalid/$name
license = MIT
EOF
  if [[ -n "$dep" ]]; then
    printf 'depend = %s\n' "$dep" >> "$tmp/pkg/.PKGINFO"
  fi
  printf '#!/bin/sh\necho %s\n' "$name" > "$tmp/pkg/usr/bin/$name"
  chmod +x "$tmp/pkg/usr/bin/$name"
  printf '%s data\n' "$name" > "$tmp/pkg/usr/share/$name/readme.txt"
  tar -C "$tmp/pkg" -czf "$path" .
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
repo="$tmp/apk-repo"
repo_extra="$tmp/apk-repo-extra"
out="$tmp/ooonana-repo"
mkdir -p "$repo" "$repo_extra" "$out"

make_fake_apk "$repo/nano-1.0-r0.apk" nano 1.0-r0 libncurses "$tmp"
make_fake_apk "$repo_extra/libncurses-1.0-r0.apk" libncurses 1.0-r0 "" "$tmp"

cat > "$tmp/APKINDEX" <<'EOF'
P:nano
V:1.0-r0
A:x86_64
S:123
D:libncurses so:libc.musl-x86_64.so.1
o:nano

P:libncurses
V:1.0-r0
A:x86_64
S:123
D:
o:libncurses

EOF
awk 'BEGIN { RS = ""; ORS = "\n\n" } /P:nano/ { print }' "$tmp/APKINDEX" > "$tmp/APKINDEX.main"
awk 'BEGIN { RS = ""; ORS = "\n\n" } /P:libncurses/ { print }' "$tmp/APKINDEX" > "$tmp/APKINDEX.extra"
mv "$tmp/APKINDEX.main" "$tmp/APKINDEX"
tar -C "$tmp" -czf "$repo/APKINDEX.tar.gz" APKINDEX
mv "$tmp/APKINDEX.extra" "$tmp/APKINDEX"
tar -C "$tmp" -czf "$repo_extra/APKINDEX.tar.gz" APKINDEX

bash "$SCRIPT" --repo-url "file://$repo" --repo-url "file://$repo_extra" --out-dir "$out" nano

[[ -f "$out/nano.pkg" ]] || fail "missing nano.pkg"
[[ -f "$out/libncurses.pkg" ]] || fail "missing libncurses.pkg"
[[ -f "$out/archives/nano-1.0-r0.tar.gz" ]] || fail "missing nano archive"
[[ -f "$out/archives/libncurses-1.0-r0.tar.gz" ]] || fail "missing libncurses archive"
[[ -f "$out/index.tsv" ]] || fail "missing index"
[[ -f "$out/SHA256SUMS" ]] || fail "missing checksums"

nano_pkg="$(<"$out/nano.pkg")"
assert_contains "$nano_pkg" 'OOONANA_PKG_ID="nano"'
assert_contains "$nano_pkg" 'OOONANA_PKG_VERSION="1.0-r0"'
assert_contains "$nano_pkg" 'OOONANA_PKG_DEPS="libncurses"'
assert_contains "$nano_pkg" 'OOONANA_PKG_ARCHIVE="archives/nano-1.0-r0.tar.gz"'
assert_contains "$nano_pkg" 'OOONANA_PKG_COMPONENTS="apk-import alpine x86_64"'
assert_not_contains "$nano_pkg" 'so:libc'

contents="$(tar -tzf "$out/archives/nano-1.0-r0.tar.gz" | sort)"
assert_contains "$contents" "./usr/bin/nano"
assert_contains "$contents" "./usr/share/nano/readme.txt"
assert_not_contains "$contents" "./.PKGINFO"

index="$(<"$out/index.tsv")"
assert_contains "$index" $'nano\t1.0-r0\tapk'
assert_contains "$index" $'libncurses\t1.0-r0\tapk'
grep -q 'archives/nano-1.0-r0.tar.gz' "$out/SHA256SUMS" || fail "missing archive checksum"

printf 'ok import-apk-package\n'
