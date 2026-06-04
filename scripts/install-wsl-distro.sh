#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
DISTRO="${OOONANA_WSL_DISTRO:-Ooonana}"
INSTALL_DIR="${OOONANA_WSL_INSTALL_DIR:-}"
TARBALL="$WORK_DIR/ooonana-wsl-rootfs.tar.gz"
FORCE=0
SET_DEFAULT=0
DRY_RUN=0
SHOULD_UNREGISTER=0

usage() {
  cat <<'USAGE'
Install Ooonana OS as a WSL distro.

Usage:
  scripts/install-wsl-distro.sh [options]

Options:
  --distro NAME       WSL distro name (default: Ooonana)
  --install-dir PATH  WSL install directory (default: Windows LocalAppData/OoonanaWSL)
  --tarball PATH      Rootfs tarball (default: WORK_DIR/ooonana-wsl-rootfs.tar.gz)
  --force             Unregister existing distro before import
  --set-default       Set distro as default WSL distro
  --dry-run           Print wsl.exe commands only
  -h, --help          Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --distro) DISTRO="$2"; shift 2 ;;
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --tarball) TARBALL="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --set-default) SET_DEFAULT=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    ooonana_print_command "$@"
  else
    "$@"
  fi
}

default_install_dir() {
  local local_appdata
  local_appdata="$(cmd.exe /C echo %LOCALAPPDATA% 2>/dev/null | tr -d '\r' | tail -n 1 || true)"
  if [[ -n "$local_appdata" && "$local_appdata" != "%LOCALAPPDATA%" ]]; then
    printf '%s\\%sWSL\n' "$local_appdata" "$DISTRO"
    return 0
  fi
  printf '%s/%sWSL\n' "$WORK_DIR" "$DISTRO"
}

for_wsl_exe() {
  local path="$1"
  if command -v wslpath >/dev/null 2>&1 && [[ "$path" == /* ]]; then
    wslpath -w "$path"
  else
    printf '%s\n' "$path"
  fi
}

distro_exists() {
  wsl.exe --list --quiet 2>/dev/null | tr -d '\000\r' | grep -Fx "$DISTRO" >/dev/null 2>&1
}

main() {
  ooonana_require_linux
  [[ -n "$DISTRO" ]] || ooonana_die "--distro required"
  [[ -f "$TARBALL" ]] || ooonana_die "missing tarball: $TARBALL"
  command -v wsl.exe >/dev/null 2>&1 || ooonana_die "missing wsl.exe"

  if [[ -z "$INSTALL_DIR" ]]; then
    INSTALL_DIR="$(default_install_dir)"
  fi

  import_dir="$(for_wsl_exe "$INSTALL_DIR")"
  import_tarball="$(for_wsl_exe "$TARBALL")"

  if [[ "$DRY_RUN" -eq 0 && "$FORCE" -eq 0 ]] && distro_exists; then
    ooonana_die "distro exists: $DISTRO (use --force)"
  fi

  if [[ "$FORCE" -eq 1 ]]; then
    if [[ "$DRY_RUN" -eq 1 ]] || distro_exists; then
      SHOULD_UNREGISTER=1
    fi
  fi

  if [[ "$SHOULD_UNREGISTER" -eq 1 ]]; then
    run_cmd wsl.exe --unregister "$DISTRO"
  fi
  run_cmd wsl.exe --import "$DISTRO" "$import_dir" "$import_tarball" --version 2
  if [[ "$SET_DEFAULT" -eq 1 ]]; then
    run_cmd wsl.exe --set-default "$DISTRO"
  fi
  run_cmd wsl.exe -d "$DISTRO" -- /usr/bin/ooonana me
  run_cmd wsl.exe -d "$DISTRO" -- /usr/bin/ooonana wsl status
  ooonana_log "WSL distro ready: $DISTRO"
}

main "$@"
