#!/usr/bin/env bash
set -euo pipefail

EFI_DIR=""
KERNEL=""
OUT_DIR=""
KEY=""
CERT=""
DRY_RUN=0

usage() {
  cat <<'USAGE'
Prepare optional Ooonana Secure Boot signing assets.

Usage:
  scripts/build-secure-boot-assets.sh --efi-dir DIR --kernel PATH --key MOK.key --cert MOK.crt --out-dir DIR [--dry-run]

Requires user-owned Machine Owner Key files. Output contains signed kernel plus enrollment notes.
USAGE
}

die() {
  printf 'secure-boot-assets: %s\n' "$*" >&2
  exit 1
}

print_cmd() {
  local arg
  for arg in "$@"; do
    printf '%q ' "$arg"
  done
  printf '\n'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --efi-dir) EFI_DIR="$2"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --cert) CERT="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[[ -n "$EFI_DIR" ]] || die "--efi-dir required"
[[ -n "$KERNEL" ]] || die "--kernel required"
[[ -n "$KEY" ]] || die "--key required"
[[ -n "$CERT" ]] || die "--cert required"
[[ -n "$OUT_DIR" ]] || die "--out-dir required"

if [[ "$DRY_RUN" -eq 1 ]]; then
  print_cmd mkdir -p "$OUT_DIR"
  print_cmd sbsign --key "$KEY" --cert "$CERT" --output "$OUT_DIR/vmlinuz-ooonana.signed" "$KERNEL"
  print_cmd mokutil --import "$CERT"
  printf 'copy signed kernel to EFI/Linux/vmlinuz-ooonana.efi or /boot/vmlinuz\n'
  printf 'OOONANA_SECURE_BOOT_PLAN_OK\n'
  exit 0
fi

command -v sbsign >/dev/null 2>&1 || die "missing sbsign"
[[ -d "$EFI_DIR" ]] || die "EFI dir missing: $EFI_DIR"
[[ -f "$KERNEL" ]] || die "kernel missing: $KERNEL"
[[ -f "$KEY" ]] || die "key missing: $KEY"
[[ -f "$CERT" ]] || die "cert missing: $CERT"

mkdir -p "$OUT_DIR"
sbsign --key "$KEY" --cert "$CERT" --output "$OUT_DIR/vmlinuz-ooonana.signed" "$KERNEL"
cat > "$OUT_DIR/SECURE_BOOT.txt" <<EOF
Ooonana Secure Boot

1. Enroll key:
   mokutil --import $CERT
2. Reboot and enroll MOK.
3. Copy signed kernel:
   $OUT_DIR/vmlinuz-ooonana.signed
4. Keep unsigned rescue boot entry until native hardware boot passes.
EOF
printf 'OOONANA_SECURE_BOOT_ASSETS_OK\n'
