#!/usr/bin/env bash

ooonana_alpine_branch() {
  local branch="${OOONANA_ALPINE_BRANCH:-v3.24}"
  [[ "$branch" =~ ^v[0-9]+\.[0-9]+$ ]] || { printf 'invalid Alpine branch\n' >&2; return 1; }
  printf '%s\n' "$branch"
}

ooonana_alpine_repositories() {
  local branch
  branch="$(ooonana_alpine_branch)" || return 1
  printf 'https://dl-cdn.alpinelinux.org/alpine/%s/main/x86_64 https://dl-cdn.alpinelinux.org/alpine/%s/community/x86_64\n' "$branch" "$branch"
}

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

# Capture a producer beside the destination, then replace without writing through
# saved hardlinks. Producer failure must leave the previous file intact.
ooonana_write_atomic() (
  set -euo pipefail
  local archive="$1" archive_tmp="" mode mask
  shift
  if [[ -L "$archive" || ( -e "$archive" && ! -f "$archive" ) ]]; then
    printf 'output destination is not a regular file: %s\n' "$archive" >&2
    return 1
  fi
  if [[ -f "$archive" ]]; then
    mode="$(stat -c '%a' -- "$archive")" || return 1
  else
    mask="$(umask)"
    printf -v mode '%o' "$((0666 & ~8#$mask))"
  fi
  archive_tmp="$(mktemp -- "${archive}.tmp.XXXXXXXX")" || return 1
  trap '[[ -z "$archive_tmp" ]] || rm -f -- "$archive_tmp"' EXIT
  if ! "$@" >"$archive_tmp"; then
    return 1
  fi
  chmod "$mode" -- "$archive_tmp" || return 1
  mv -fT -- "$archive_tmp" "$archive" || return 1
  archive_tmp=""
)

ooonana_tar_gzip_stream() (
  set -o pipefail
  tar "$@" | gzip -n
)

ooonana_tar_gzip_atomic() {
  local archive="$1"
  shift
  ooonana_write_atomic "$archive" ooonana_tar_gzip_stream "$@"
}

ooonana_require_unix_permissions() {
  local directory="$1"
  local probe="$directory/.ooonana-permission-probe.$$"
  local mode

  mkdir -p "$directory"
  : > "$probe"
  chmod 0600 "$probe"
  mode="$(stat -c '%a' "$probe" 2>/dev/null || true)"
  rm -f "$probe"

  [[ "$mode" == "600" ]] ||
    ooonana_die "build path lacks Unix permissions: $directory (mount drvfs with -o metadata)"
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
