#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
KERNEL_SOURCE="$WORK_DIR/linux"
KERNEL_BUILD="$WORK_DIR/kernel-build"
KERNEL_OUT="$WORK_DIR/ooonana-kernel"
KERNEL="$KERNEL_OUT/vmlinuz-ooonana"
DEFCONFIG="x86_64_defconfig"
CONFIG=""
CONFIG_FRAGMENTS=()
JOBS="${OOONANA_KERNEL_JOBS:-$(command -v nproc >/dev/null 2>&1 && nproc || printf '2')}"
DRY_RUN=0
FORCE=0
FRAGMENT_STAGE=""

cleanup() {
  if [[ -n "$FRAGMENT_STAGE" && -d "$FRAGMENT_STAGE" ]]; then
    rm -rf "$FRAGMENT_STAGE"
  fi
}
trap cleanup EXIT

usage() {
  cat <<'USAGE'
Build Ooonana Linux kernel.

Usage:
  scripts/build-kernel.sh [options]

Options:
  --work-dir PATH   Build directory (default: /var/tmp/ooonana-os/build)
  --source PATH     Linux source tree (default: WORK_DIR/linux)
  --build-dir PATH  Kernel object directory (default: WORK_DIR/kernel-build)
  --out-dir PATH    Kernel output directory (default: WORK_DIR/ooonana-kernel)
  --kernel PATH     Kernel output path (default: OUT_DIR/vmlinuz-ooonana)
  --defconfig NAME  Kernel defconfig target (default: x86_64_defconfig)
  --config PATH     Existing .config to copy before olddefconfig
  --config-fragment PATH  Merge or append kernel config fragment
  --jobs N          Parallel make jobs (default: nproc)
  --dry-run         Print build commands only
  --force           Delete kernel build/output before building
  -h, --help        Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; KERNEL_SOURCE="$2/linux"; KERNEL_BUILD="$2/kernel-build"; KERNEL_OUT="$2/ooonana-kernel"; KERNEL="$2/ooonana-kernel/vmlinuz-ooonana"; shift 2 ;;
    --source) KERNEL_SOURCE="$2"; shift 2 ;;
    --build-dir) KERNEL_BUILD="$2"; shift 2 ;;
    --out-dir) KERNEL_OUT="$2"; KERNEL="$2/vmlinuz-ooonana"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --defconfig) DEFCONFIG="$2"; shift 2 ;;
    --config) CONFIG="$2"; shift 2 ;;
    --config-fragment) CONFIG_FRAGMENTS+=("$2"); shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

if [[ "${#CONFIG_FRAGMENTS[@]}" -eq 0 && -f "$ROOT/configs/kernel/ooonana-minimal-x86_64.fragment" ]]; then
  CONFIG_FRAGMENTS+=("$ROOT/configs/kernel/ooonana-minimal-x86_64.fragment")
fi

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    ooonana_print_command "$@"
  else
    "$@"
  fi
}

absolute_path() {
  local path="$1"
  local dir base
  if [[ "$path" == /* ]]; then
    printf '%s\n' "$path"
    return 0
  fi

  dir="$(dirname "$path")"
  base="$(basename "$path")"
  printf '%s/%s\n' "$(cd "$dir" && pwd)" "$base"
}

validate_source() {
  [[ -f "$KERNEL_SOURCE/Makefile" ]] || ooonana_die "missing Linux Makefile: $KERNEL_SOURCE"
  [[ -d "$KERNEL_SOURCE/arch/x86" ]] || ooonana_die "missing x86 kernel arch tree: $KERNEL_SOURCE/arch/x86"
  if [[ -n "$CONFIG" ]]; then
    [[ -f "$CONFIG" ]] || ooonana_die "missing kernel config: $CONFIG"
  fi
  local fragment
  for fragment in "${CONFIG_FRAGMENTS[@]}"; do
    [[ -f "$fragment" ]] || ooonana_die "missing kernel config fragment: $fragment"
  done
}

append_config_fragment() {
  local fragment="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    ooonana_print_command sh -c "cat '$fragment' >> '$KERNEL_BUILD/.config'"
  else
    cat "$fragment" >> "$KERNEL_BUILD/.config"
  fi
}

apply_config_fragments() {
  local merge_script="$KERNEL_SOURCE/scripts/kconfig/merge_config.sh"
  local fragment
  local absolute_fragments=()
  local merge_fragments=()
  local index=0

  [[ "${#CONFIG_FRAGMENTS[@]}" -gt 0 ]] || return 0

  for fragment in "${CONFIG_FRAGMENTS[@]}"; do
    absolute_fragments+=("$(absolute_path "$fragment")")
  done

  if [[ -f "$merge_script" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      FRAGMENT_STAGE="${TMPDIR:-/tmp}/ooonana-kernel-fragments"
      ooonana_print_command mkdir -p "$FRAGMENT_STAGE"
    else
      FRAGMENT_STAGE="$(mktemp -d "${TMPDIR:-/tmp}/ooonana-kernel-fragments.XXXXXXXXXX")"
    fi

    for fragment in "${absolute_fragments[@]}"; do
      index=$((index + 1))
      merge_fragments+=("$FRAGMENT_STAGE/fragment-$index.config")
      run_cmd cp "$fragment" "$FRAGMENT_STAGE/fragment-$index.config"
    done

    (cd "$KERNEL_SOURCE" && run_cmd bash scripts/kconfig/merge_config.sh -O "$KERNEL_BUILD" "$KERNEL_BUILD/.config" "${merge_fragments[@]}")
    return 0
  fi

  for fragment in "${absolute_fragments[@]}"; do
    append_config_fragment "$fragment"
  done
}

write_kernel_env() {
  cat > "$KERNEL_OUT/kernel.env" <<EOF
OOONANA_KERNEL=$KERNEL
OOONANA_KERNEL_SOURCE=$KERNEL_SOURCE
OOONANA_KERNEL_BUILD=$KERNEL_BUILD
OOONANA_KERNEL_DEFCONFIG=$DEFCONFIG
EOF
}

main() {
  ooonana_require_linux
  ooonana_require_commands make install cp mkdir dirname chmod mktemp
  validate_source

  if [[ "$FORCE" -eq 1 ]]; then
    rm -rf "$KERNEL_BUILD"
    rm -f "$KERNEL" "$KERNEL_OUT/kernel.env"
  fi

  mkdir -p "$KERNEL_BUILD" "$KERNEL_OUT" "$(dirname "$KERNEL")"

  if [[ -n "$CONFIG" ]]; then
    run_cmd cp "$CONFIG" "$KERNEL_BUILD/.config"
  else
    run_cmd make -C "$KERNEL_SOURCE" O="$KERNEL_BUILD" "$DEFCONFIG"
  fi

  apply_config_fragments
  run_cmd make -C "$KERNEL_SOURCE" O="$KERNEL_BUILD" olddefconfig
  run_cmd make -C "$KERNEL_SOURCE" O="$KERNEL_BUILD" -j "$JOBS" bzImage

  if [[ "$DRY_RUN" -eq 1 ]]; then
    ooonana_print_command install -m 0644 "$KERNEL_BUILD/arch/x86/boot/bzImage" "$KERNEL"
    printf 'OOONANA_KERNEL=%s\n' "$KERNEL"
    exit 0
  fi

  [[ -f "$KERNEL_BUILD/arch/x86/boot/bzImage" ]] || ooonana_die "kernel build did not produce bzImage"
  install -m 0644 "$KERNEL_BUILD/arch/x86/boot/bzImage" "$KERNEL"
  write_kernel_env
  chmod a+r "$KERNEL" "$KERNEL_OUT/kernel.env"

  ooonana_log "kernel ready: $KERNEL"
}

main "$@"
