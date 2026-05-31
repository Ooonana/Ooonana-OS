#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_SCRIPT="$ROOT/scripts/build-wsl-rootfs.sh"
INSTALL_SCRIPT="$ROOT/scripts/install-wsl-distro.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$BUILD_SCRIPT" ]] || fail "missing executable WSL rootfs builder"
[[ -x "$INSTALL_SCRIPT" ]] || fail "missing executable WSL distro installer"

build_help="$(bash "$BUILD_SCRIPT" --help)"
assert_contains "$build_help" "Build Ooonana WSL rootfs tarball"
assert_contains "$build_help" "--rootfs"
assert_contains "$build_help" "--tarball"
assert_contains "$build_help" "--force"

install_help="$(bash "$INSTALL_SCRIPT" --help)"
assert_contains "$install_help" "Install Ooonana OS as a WSL distro"
assert_contains "$install_help" "--distro"
assert_contains "$install_help" "--install-dir"
assert_contains "$install_help" "--tarball"
assert_contains "$install_help" "--dry-run"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/rootfs/bin" "$tmp/rootfs/etc" "$tmp/rootfs/usr/bin"
printf 'busybox\n' > "$tmp/rootfs/bin/busybox"
ln -s busybox "$tmp/rootfs/bin/sh"
chmod +x "$tmp/rootfs/bin/busybox"
printf 'NAME="Ooonana OS"\n' > "$tmp/rootfs/etc/os-release"
printf 'root:x:0:0:root:/root:/bin/sh\n' > "$tmp/rootfs/etc/passwd"
printf '[boot]\nsystemd=false\n[user]\ndefault=root\n' > "$tmp/rootfs/etc/wsl.conf"
printf '#!/bin/sh\necho ooonana 0.3.0\n' > "$tmp/rootfs/usr/bin/ooonana"
chmod +x "$tmp/rootfs/usr/bin/ooonana"

bash "$BUILD_SCRIPT" \
  --rootfs "$tmp/rootfs" \
  --tarball "$tmp/ooonana-wsl.tar.gz" \
  --force >/dev/null

[[ -s "$tmp/ooonana-wsl.tar.gz" ]] || fail "missing WSL tarball"
listing="$(tar -tzf "$tmp/ooonana-wsl.tar.gz")"
assert_contains "$listing" "./etc/os-release"
assert_contains "$listing" "./usr/bin/ooonana"

dry_run="$(bash "$INSTALL_SCRIPT" \
  --distro OoonanaTest \
  --install-dir "$tmp/install" \
  --tarball "$tmp/ooonana-wsl.tar.gz" \
  --force \
  --dry-run)"

assert_contains "$dry_run" "wsl.exe --import OoonanaTest"
assert_contains "$dry_run" "ooonana-wsl.tar.gz"
assert_contains "$dry_run" "wsl.exe -d OoonanaTest -- /usr/bin/ooonana me"
assert_contains "$dry_run" "wsl.exe -d OoonanaTest -- /usr/bin/ooonana wsl status"

printf 'ok wsl-distro\n'
