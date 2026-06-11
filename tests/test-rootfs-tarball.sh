#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-rootfs-tarball.sh"

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

[[ -x "$SCRIPT" ]] || fail "missing executable rootfs tarball builder"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana generic rootfs tarball"
assert_contains "$help" "--rootfs"
assert_contains "$help" "--tarball"
assert_contains "$help" "--force"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
rootfs="$tmp/rootfs"
tarball="$tmp/ooonana-rootfs.tar.gz"

mkdir -p \
  "$rootfs/bin" \
  "$rootfs/dev" \
  "$rootfs/etc" \
  "$rootfs/proc" \
  "$rootfs/run" \
  "$rootfs/sys" \
  "$rootfs/tmp" \
  "$rootfs/usr/bin" \
  "$rootfs/usr/lib/ooonana/repo" \
  "$rootfs/usr/share/ooonana" \
  "$rootfs/var/cache/ooonana" \
  "$rootfs/var/lib/ooonana/packages/installed"

cat > "$rootfs/bin/sh" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$rootfs/bin/sh"
cat > "$rootfs/usr/bin/ooonana" <<'EOF'
#!/bin/sh
echo ooonana 0.8.0
EOF
chmod +x "$rootfs/usr/bin/ooonana"
printf 'NAME="Ooonana OS"\n' > "$rootfs/etc/os-release"
printf 'root:x:0:0:root:/root:/bin/sh\n' > "$rootfs/etc/passwd"
printf 'root:x:0:\n' > "$rootfs/etc/group"
printf 'Ooonana OS\n' > "$rootfs/usr/share/ooonana/logo.txt"
cp "$rootfs/usr/share/ooonana/logo.txt" "$rootfs/etc/motd"
cp "$rootfs/usr/share/ooonana/logo.txt" "$rootfs/etc/issue"
printf 'OOONANA_PKG_ID="base"\n' > "$rootfs/usr/lib/ooonana/repo/base.pkg"
cp "$rootfs/usr/lib/ooonana/repo/base.pkg" "$rootfs/var/lib/ooonana/packages/installed/base.pkg"
printf 'do not archive\n' > "$rootfs/dev/null"
printf 'do not archive\n' > "$rootfs/proc/cpuinfo"
printf 'do not archive\n' > "$rootfs/sys/kernel"
printf 'do not archive\n' > "$rootfs/run/state"
printf 'do not archive\n' > "$rootfs/tmp/tempfile"

bash "$SCRIPT" --rootfs "$rootfs" --tarball "$tarball" --force
[[ -f "$tarball" ]] || fail "missing rootfs tarball"

contents="$(tar -tzf "$tarball" | sort)"
assert_contains "$contents" "./bin/sh"
assert_contains "$contents" "./etc/os-release"
assert_contains "$contents" "./etc/passwd"
assert_contains "$contents" "./etc/group"
assert_contains "$contents" "./etc/motd"
assert_contains "$contents" "./etc/issue"
assert_contains "$contents" "./usr/bin/ooonana"
assert_contains "$contents" "./usr/share/ooonana/logo.txt"
assert_contains "$contents" "./usr/lib/ooonana/repo/base.pkg"
assert_contains "$contents" "./var/lib/ooonana/packages/installed/base.pkg"
assert_not_contains "$contents" "./dev/null"
assert_not_contains "$contents" "./proc/cpuinfo"
assert_not_contains "$contents" "./sys/kernel"
assert_not_contains "$contents" "./run/state"
assert_not_contains "$contents" "./tmp/tempfile"

mkdir -p "$tmp/extract"
tar -xzf "$tarball" -C "$tmp/extract"
[[ -x "$tmp/extract/bin/sh" ]] || fail "extracted rootfs missing executable /bin/sh"
[[ -x "$tmp/extract/usr/bin/ooonana" ]] || fail "extracted rootfs missing executable ooonana"
diff -u "$rootfs/usr/share/ooonana/logo.txt" "$tmp/extract/etc/motd" || fail "motd logo mismatch"
diff -u "$rootfs/usr/share/ooonana/logo.txt" "$tmp/extract/etc/issue" || fail "issue logo mismatch"

second="$tmp/second.tar.gz"
bash "$SCRIPT" --rootfs "$rootfs" --tarball "$second" --force >/dev/null
cmp "$tarball" "$second" || fail "rootfs tarball must be reproducible"

printf 'ok rootfs-tarball\n'
