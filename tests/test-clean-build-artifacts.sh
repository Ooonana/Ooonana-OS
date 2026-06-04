#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/clean-build-artifacts.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable clean builder"
script_src="$(<"$SCRIPT")"
assert_contains "$script_src" "ooonana_reexec_as_root"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Clean Ooonana build artifacts"
assert_contains "$help" "--work-dir"
assert_contains "$help" "--keep-source"
assert_contains "$help" "--yes"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

unsafe="$tmp/not-build"
mkdir -p "$unsafe"
unsafe_out="$(bash "$SCRIPT" --work-dir "$unsafe" --yes 2>&1 || true)"
assert_contains "$unsafe_out" "refusing unsafe build dir"

work="$tmp/ooonana-os/build"
mkdir -p "$work/rootfs" "$work/scratch-rootfs" "$work/linux" "$work/kernel-build" "$work/ooonana-kernel"
mkdir -p "$work/full-i3-rootfs" "$work/release-full-i3-rootfs" "$work/full-i3-repo" "$work/full-i3-iso-tree"
touch \
  "$work/keep.txt" \
  "$work/ooonana.iso" \
  "$work/ooonana-scratch.iso" \
  "$work/ooonana-full-i3.iso" \
  "$work/ooonana-full-i3-disk.raw" \
  "$work/ooonana-full-i3-rootfs.tar.gz" \
  "$work/ooonana-installer-created.raw" \
  "$work/ooonana-wsl-rootfs.tar.gz" \
  "$work/linux-6.6.32.tar.xz" \
  "$work/qemu-smoke.log" \
  "$work/qemu-rootfs-smoke.log"

no_yes="$(bash "$SCRIPT" --work-dir "$work" 2>&1 || true)"
assert_contains "$no_yes" "use --yes"
[[ -d "$work/rootfs" ]] || fail "no-yes removed rootfs"

dry="$(bash "$SCRIPT" --work-dir "$work" --dry-run --yes)"
assert_contains "$dry" "rm -rf"
assert_contains "$dry" "$work/rootfs"
[[ -d "$work/rootfs" ]] || fail "dry-run removed rootfs"

bash "$SCRIPT" --work-dir "$work" --keep-source --yes >/dev/null
[[ ! -e "$work/rootfs" ]] || fail "rootfs not removed"
[[ ! -e "$work/ooonana.iso" ]] || fail "iso not removed"
[[ ! -e "$work/full-i3-rootfs" ]] || fail "full-i3 rootfs not removed"
[[ ! -e "$work/release-full-i3-rootfs" ]] || fail "release full-i3 rootfs not removed"
[[ ! -e "$work/full-i3-repo" ]] || fail "full-i3 repo not removed"
[[ ! -e "$work/full-i3-iso-tree" ]] || fail "full-i3 ISO tree not removed"
[[ ! -e "$work/ooonana-full-i3.iso" ]] || fail "full-i3 iso not removed"
[[ ! -e "$work/ooonana-full-i3-disk.raw" ]] || fail "full-i3 disk not removed"
[[ ! -e "$work/ooonana-full-i3-rootfs.tar.gz" ]] || fail "full-i3 tarball not removed"
[[ ! -e "$work/ooonana-installer-created.raw" ]] || fail "installer-created disk not removed"
[[ ! -e "$work/qemu-rootfs-smoke.log" ]] || fail "extra qemu log not removed"
[[ -e "$work/linux" ]] || fail "keep-source removed linux"
[[ -e "$work/linux-6.6.32.tar.xz" ]] || fail "keep-source removed archive"
[[ -e "$work/keep.txt" ]] || fail "removed unrelated file"

bash "$SCRIPT" --work-dir "$work" --yes >/dev/null
[[ ! -e "$work/linux" ]] || fail "linux not removed"
[[ ! -e "$work/linux-6.6.32.tar.xz" ]] || fail "archive not removed"
[[ -e "$work/keep.txt" ]] || fail "removed unrelated file after full clean"

printf 'ok clean-build-artifacts\n'
