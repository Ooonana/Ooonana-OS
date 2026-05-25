#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
VERSION="${OOONANA_KERNEL_VERSION:-6.6.32}"
SOURCE_DIR="$WORK_DIR/linux"
ARCHIVE="$WORK_DIR/linux-$VERSION.tar.xz"
TARBALL=""
URL=""
SHA256=""
FORCE=0
DRY_RUN=0

usage() {
  cat <<'USAGE'
Fetch Ooonana Linux kernel source.

Usage:
  scripts/fetch-kernel-source.sh [options]

Options:
  --work-dir PATH    Build directory (default: /var/tmp/ooonana-os/build)
  --version VERSION  Linux version (default: 6.6.32)
  --source-dir PATH  Source output directory (default: WORK_DIR/linux)
  --archive PATH     Download archive path (default: WORK_DIR/linux-VERSION.tar.xz)
  --tarball PATH     Use existing tarball instead of downloading
  --url URL          Source tarball URL
  --sha256 HASH      Verify tarball SHA256
  --force            Delete existing source directory first
  --dry-run          Print commands only
  -h, --help         Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; SOURCE_DIR="$2/linux"; ARCHIVE="$2/linux-$VERSION.tar.xz"; shift 2 ;;
    --version) VERSION="$2"; ARCHIVE="$WORK_DIR/linux-$2.tar.xz"; shift 2 ;;
    --source-dir) SOURCE_DIR="$2"; shift 2 ;;
    --archive) ARCHIVE="$2"; shift 2 ;;
    --tarball) TARBALL="$2"; shift 2 ;;
    --url) URL="$2"; shift 2 ;;
    --sha256) SHA256="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

kernel_major() {
  printf '%s\n' "${VERSION%%.*}"
}

default_url() {
  printf 'https://cdn.kernel.org/pub/linux/kernel/v%s.x/linux-%s.tar.xz\n' "$(kernel_major)" "$VERSION"
}

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    ooonana_print_command "$@"
  else
    "$@"
  fi
}

verify_hash() {
  local actual
  [[ -n "$SHA256" ]] || return 0
  actual="$(sha256sum "$ARCHIVE" | awk '{ print $1 }')"
  [[ "$actual" == "$SHA256" ]] || ooonana_die "sha256 mismatch for $ARCHIVE"
}

write_metadata() {
  cat > "$SOURCE_DIR/.ooonana-kernel-source" <<EOF
OOONANA_KERNEL_VERSION=$VERSION
OOONANA_KERNEL_SOURCE=$SOURCE_DIR
OOONANA_KERNEL_ARCHIVE=$ARCHIVE
OOONANA_KERNEL_URL=$URL
EOF
}

main() {
  ooonana_require_linux
  ooonana_require_commands mkdir rm tar

  [[ -n "$URL" ]] || URL="$(default_url)"
  if [[ -n "$TARBALL" ]]; then
    ARCHIVE="$TARBALL"
    [[ -f "$ARCHIVE" ]] || ooonana_die "missing tarball: $ARCHIVE"
  else
    ooonana_require_command curl
  fi

  if [[ "$FORCE" -eq 1 ]]; then
    run_cmd rm -rf "$SOURCE_DIR"
  fi

  if [[ -z "$TARBALL" && ! -f "$ARCHIVE" ]]; then
    run_cmd mkdir -p "$(dirname "$ARCHIVE")"
    run_cmd curl -fL "$URL" -o "$ARCHIVE"
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    ooonana_print_command mkdir -p "$SOURCE_DIR"
    ooonana_print_command tar -xJf "$ARCHIVE" --strip-components=1 -C "$SOURCE_DIR"
    exit 0
  fi

  verify_hash
  mkdir -p "$SOURCE_DIR"
  tar -xJf "$ARCHIVE" --strip-components=1 -C "$SOURCE_DIR"
  [[ -f "$SOURCE_DIR/Makefile" ]] || ooonana_die "extracted source missing Makefile"
  [[ -d "$SOURCE_DIR/arch/x86" ]] || ooonana_die "extracted source missing arch/x86"
  write_metadata

  ooonana_log "kernel source ready: $SOURCE_DIR"
}

main "$@"
