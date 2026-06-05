#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${OOONANA_PDF_WORK_DIR:-/var/tmp/ooonana-os/linuxpdf}"
LINUXPDF_REPO="${OOONANA_LINUXPDF_REPO:-https://github.com/ading2210/linuxpdf.git}"
LINUXPDF_REF="${OOONANA_LINUXPDF_REF:-main}"
OUT="$ROOT/docs/ooonana.pdf"
BITS="32"
FORCE=0
DRY_RUN=0
PREPARE_ONLY=0

usage() {
  cat <<'USAGE'
Build bootable Ooonana OS PDF from linuxpdf.

This builds a TinyEMU RISC-V PDF and injects the minimal Ooonana shell OS
payload. It writes docs/ooonana.pdf. The docs-only guide is docs/ooonana-guide.pdf.

Usage:
  scripts/build-ooonana-pdf-os.sh [options]

Options:
  --work-dir PATH   Work dir outside repo (default: /var/tmp/ooonana-os/linuxpdf)
  --out PATH        Output PDF (default: docs/ooonana.pdf)
  --bits 32|64      linuxpdf machine width (default: 32, faster)
  --prepare-only    Clone/patch/inject but do not run old Emscripten build
  --dry-run         Print actions only
  --force           Rebuild linuxpdf out/files and overwrite output
  -h, --help        Show help

Notes:
  linuxpdf is GPLv3 and downloads old Emscripten 1.39.20 plus TinyEMU assets.
  Keep work dir in /var/tmp or another big Linux filesystem, not C:.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --bits) BITS="$2"; shift 2 ;;
    --prepare-only) PREPARE_ONLY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'build-ooonana-pdf-os: unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done

case "$BITS" in
  32|64) ;;
  *) printf 'build-ooonana-pdf-os: --bits must be 32 or 64\n' >&2; exit 1 ;;
esac

SRC="$WORK_DIR/linuxpdf"

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

patch_linuxpdf() {
  local build_sh="$SRC/build.sh"
  local gen_pdf="$SRC/gen_pdf.py"
  grep -q 'OOONANA_SOURCE_ROOT' "$build_sh" 2>/dev/null && return 0
  python3 - "$build_sh" "$gen_pdf" <<'PY'
from pathlib import Path
import sys

build = Path(sys.argv[1])
gen = Path(sys.argv[2])
text = build.read_text()
text = text.replace('BITS="32"', 'BITS="${OOONANA_PDF_BITS:-32}"')
needle = "build_files\ncp vm_$BITS.cfg build/vm/bbl$BITS.bin build/vm/kernel-riscv$BITS.bin build/files\n"
insert = """build_files
if [ -n "${OOONANA_SOURCE_ROOT:-}" ]; then
  bash "$OOONANA_SOURCE_ROOT/scripts/inject-ooonana-pdf-root.sh" "$root_dir"
  rm -rf build/files
  mkdir -p build/files/root
  sudo build/build_files "$root_dir" build/files/root
fi
cp vm_$BITS.cfg build/vm/bbl$BITS.bin build/vm/kernel-riscv$BITS.bin build/files
"""
if needle not in text:
    raise SystemExit("linuxpdf build.sh patch point missing")
build.write_text(text.replace(needle, insert))

pdf = gen.read_text()
pdf = pdf.replace('"LinuxPDF"', '"OoonanaPDF"')
pdf = pdf.replace('"Source code: https://github.com/ading2210/linuxpdf"', '"Ooonana OS in PDF | based on linuxpdf"')
pdf = pdf.replace('"Note: This PDF only works in Chromium-based browsers."', '"Works best in Chromium PDF viewer. Boot can take 30-60s."')
gen.write_text(pdf)
PY
}

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'would build Ooonana OS PDF\n'
  printf 'repo: %s\n' "$LINUXPDF_REPO"
  printf 'work: %s\n' "$SRC"
  printf 'out: %s\n' "$OUT"
fi

if [[ ! -d "$SRC/.git" ]]; then
  run mkdir -p "$WORK_DIR"
  run git clone --depth 1 --branch "$LINUXPDF_REF" "$LINUXPDF_REPO" "$SRC"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '+ patch linuxpdf build for Ooonana payload\n'
else
  patch_linuxpdf
fi

if [[ "$FORCE" -eq 1 ]]; then
  run rm -rf "$SRC/build/root" "$SRC/build/files" "$SRC/out/linux.pdf"
fi

if [[ "$PREPARE_ONLY" -eq 1 ]]; then
  printf 'prepared Ooonana PDF source: %s\n' "$SRC"
  exit 0
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '+ python3 -m venv %q\n' "$SRC/.venv"
  printf '+ pip install -r %q\n' "$SRC/requirements.txt"
  printf '+ OOONANA_SOURCE_ROOT=%q OOONANA_PDF_BITS=%q ./build.sh\n' "$ROOT" "$BITS"
  printf '+ install -m 0644 %q %q\n' "$SRC/out/linux.pdf" "$OUT"
  exit 0
fi

python3 -m venv "$SRC/.venv"
"$SRC/.venv/bin/pip" install -r "$SRC/requirements.txt"
(
  cd "$SRC"
  OOONANA_SOURCE_ROOT="$ROOT" OOONANA_PDF_BITS="$BITS" ./build.sh
)
install -D -m 0644 "$SRC/out/linux.pdf" "$OUT"
printf 'Ooonana OS PDF ready: %s\n' "$OUT"
