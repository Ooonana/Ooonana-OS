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
assert_contains "$build_help" "--edition minimal|full-i3"
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

full_default_dir="$(bash "$INSTALL_SCRIPT" \
  --distro Ooonana \
  --tarball "$tmp/ooonana-wsl.tar.gz" \
  --force \
  --dry-run)"
assert_contains "$full_default_dir" "OoonanaWSL"

mkdir -p "$tmp/fakebin"
cat > "$tmp/fakebin/wsl.exe" <<'EOF'
#!/bin/sh
printf '%s\n' "$*" >> "$OOONANA_FAKE_WSL_LOG"
case "$1" in
  --list) printf 'Ubuntu\r\n'; exit 0 ;;
  --unregister) exit 0 ;;
  *) exit 0 ;;
esac
EOF
chmod +x "$tmp/fakebin/wsl.exe"

OOONANA_FAKE_WSL_LOG="$tmp/fake-wsl.log" \
  PATH="$tmp/fakebin:$PATH" \
  bash "$INSTALL_SCRIPT" \
    --distro Ooonana \
    --install-dir "$tmp/install" \
    --tarball "$tmp/ooonana-wsl.tar.gz" \
    --force >/dev/null
fake_wsl="$(<"$tmp/fake-wsl.log")"
assert_contains "$fake_wsl" "--import Ooonana"
if [[ "$fake_wsl" == *"--unregister Ooonana"* ]]; then
  fail "force unregistered absent distro"
fi

mkdir -p "$tmp/full-rootfs/bin" "$tmp/full-rootfs/etc/ooonana" "$tmp/full-rootfs/usr/bin"
printf 'busybox\n' > "$tmp/full-rootfs/bin/busybox"
ln -s busybox "$tmp/full-rootfs/bin/sh"
chmod +x "$tmp/full-rootfs/bin/busybox"
printf 'root:x:0:0:root:/root:/bin/sh\n' > "$tmp/full-rootfs/etc/passwd"
printf '[boot]\nsystemd=false\n[user]\ndefault=root\n' > "$tmp/full-rootfs/etc/wsl.conf"
printf 'full-i3\n' > "$tmp/full-rootfs/etc/ooonana/edition"
for bin in start-ooonana-i3 ooonana-gui-installer ooonana-install-wizard; do
  printf '#!/bin/sh\necho %s\n' "$bin" > "$tmp/full-rootfs/usr/bin/$bin"
  chmod +x "$tmp/full-rootfs/usr/bin/$bin"
done

bash "$BUILD_SCRIPT" \
  --edition full-i3 \
  --rootfs "$tmp/full-rootfs" \
  --tarball "$tmp/ooonana-full-i3-wsl-rootfs.tar.gz" \
  --force >/dev/null

[[ -s "$tmp/ooonana-full-i3-wsl-rootfs.tar.gz" ]] || fail "missing full-i3 WSL tarball"
full_listing="$(tar -tzf "$tmp/ooonana-full-i3-wsl-rootfs.tar.gz")"
assert_contains "$full_listing" "./etc/ooonana/edition"
assert_contains "$full_listing" "./usr/bin/start-ooonana-i3"
assert_contains "$full_listing" "./usr/bin/ooonana-gui-installer"
assert_contains "$full_listing" "./usr/bin/ooonana-install-wizard"
assert_contains "$(bash "$BUILD_SCRIPT" --work-dir "$tmp" --edition full-i3 --help)" "ooonana-full-i3-wsl-rootfs.tar.gz"

printf 'ok wsl-distro\n'
