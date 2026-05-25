#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-kernel.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable kernel builder"

help="$(bash "$SCRIPT" --help)"
assert_contains "$help" "Build Ooonana Linux kernel"
assert_contains "$help" "--source"
assert_contains "$help" "--kernel"
assert_contains "$help" "--dry-run"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/source/arch/x86" "$tmp/bin"
touch "$tmp/source/Makefile"

dry_run="$(bash "$SCRIPT" \
  --source "$tmp/source" \
  --build-dir "$tmp/build" \
  --out-dir "$tmp/out" \
  --jobs 2 \
  --dry-run)"
assert_contains "$dry_run" "make -C $tmp/source"
assert_contains "$dry_run" "x86_64_defconfig"
assert_contains "$dry_run" "bzImage"
assert_contains "$dry_run" "$tmp/out/vmlinuz-ooonana"

cat > "$tmp/bin/make" <<'EOF'
#!/bin/sh
out=""
target=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -C)
      shift
      ;;
    O=*)
      out="${1#O=}"
      ;;
    -j)
      shift
      ;;
    -j*)
      ;;
    *)
      target="$1"
      ;;
  esac
  shift || true
done

[ -n "$out" ] || exit 7
if [ "$target" = "bzImage" ]; then
  mkdir -p "$out/arch/x86/boot"
  printf 'fake kernel\n' > "$out/arch/x86/boot/bzImage"
fi
EOF
chmod +x "$tmp/bin/make"

PATH="$tmp/bin:$PATH" \
bash "$SCRIPT" \
  --source "$tmp/source" \
  --build-dir "$tmp/build" \
  --out-dir "$tmp/out" \
  --kernel "$tmp/out/custom-vmlinuz" \
  --jobs 2 \
  --force >/dev/null

[[ -f "$tmp/out/custom-vmlinuz" ]] || fail "missing kernel output"
[[ "$(<"$tmp/out/custom-vmlinuz")" == "fake kernel" ]] || fail "wrong kernel payload"
[[ -f "$tmp/out/kernel.env" ]] || fail "missing kernel env"

env_file="$(<"$tmp/out/kernel.env")"
assert_contains "$env_file" "OOONANA_KERNEL=$tmp/out/custom-vmlinuz"
assert_contains "$env_file" "OOONANA_KERNEL_SOURCE=$tmp/source"
assert_contains "$env_file" "OOONANA_KERNEL_DEFCONFIG=x86_64_defconfig"

printf 'ok kernel-build\n'
