#!/usr/bin/env bash

ooonana_log() {
  printf '[ooonana] %s\n' "$*"
}

ooonana_die() {
  printf '[ooonana] ERROR: %s\n' "$*" >&2
  exit 1
}

ooonana_project_root() {
  local source_dir
  source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  printf '%s\n' "$source_dir"
}

ooonana_default_build_dir() {
  if [[ -n "${OOONANA_BUILD_DIR:-}" ]]; then
    printf '%s\n' "$OOONANA_BUILD_DIR"
  else
    printf '%s\n' "/var/tmp/ooonana-os/build"
  fi
}

ooonana_require_linux() {
  [[ "$(uname -s)" == "Linux" ]] || ooonana_die "run inside WSL/Linux"
}

ooonana_require_command() {
  local command_name="$1"
  command -v "$command_name" >/dev/null 2>&1 || ooonana_die "missing command: $command_name"
}

ooonana_require_commands() {
  local command_name
  for command_name in "$@"; do
    ooonana_require_command "$command_name"
  done
}

ooonana_read_package_profile() {
  local profile="$1"
  [[ -f "$profile" ]] || ooonana_die "missing package profile: $profile"

  sed -e 's/[[:space:]]*#.*$//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$profile" |
    awk 'NF { print }'
}

ooonana_reexec_as_root() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    return 0
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    exec sudo -E bash "$0" "$@"
  fi

  if command -v wsl.exe >/dev/null 2>&1; then
    exec wsl.exe -u root -- bash "$0" "$@"
  fi

  ooonana_die "need root. run with: wsl.exe -u root bash -lc 'cd \"$(pwd)\" && bash $0'"
}

ooonana_print_command() {
  local arg
  for arg in "$@"; do
    printf '%q ' "$arg"
  done
  printf '\n'
}
