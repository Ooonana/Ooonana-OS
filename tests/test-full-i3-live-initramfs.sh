#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-full-i3-live-initramfs.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable full-i3 live initramfs builder"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana full-i3 live initramfs"
assert_contains "$help" "--rootfs"
assert_contains "$help" "--initramfs"
assert_contains "$help" "--kernel"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin" "$tmp/rootfs/bin" "$tmp/rootfs/etc/ooonana" "$tmp/rootfs/usr/bin" "$tmp/rootfs/dev" "$tmp/rootfs/proc" "$tmp/rootfs/sys" "$tmp/rootfs/run" "$tmp/rootfs/tmp"
cat > "$tmp/bin/cpio" <<'EOF'
#!/bin/sh
cat >/dev/null
printf 'fake cpio\n'
EOF
chmod +x "$tmp/bin/cpio"
printf 'kernel\n' > "$tmp/vmlinuz"
cat > "$tmp/rootfs/bin/sh" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$tmp/rootfs/bin/sh"
printf 'full-i3\n' > "$tmp/rootfs/etc/ooonana/edition"
cat > "$tmp/rootfs/usr/bin/start-ooonana-i3" <<'EOF'
#!/bin/sh
echo start
EOF
chmod +x "$tmp/rootfs/usr/bin/start-ooonana-i3"

PATH="$tmp/bin:$PATH" bash "$SCRIPT" \
  --rootfs "$tmp/rootfs" \
  --kernel "$tmp/vmlinuz" \
  --initramfs "$tmp/live.cpio.gz" \
  --force >/dev/null

[[ -s "$tmp/live.cpio.gz" ]] || fail "missing live initramfs"
gzip -dc "$tmp/live.cpio.gz" | grep -q "fake cpio" || fail "cpio output not compressed"
[[ -f "$tmp/rootfs/boot/vmlinuz" ]] || fail "kernel not staged in live rootfs"
[[ -d "$tmp/rootfs/dev" ]] || fail "dev dir removed"
[[ -d "$tmp/rootfs/proc" ]] || fail "proc dir removed"

printf 'ok full-i3-live-initramfs\n'
