#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

usage() {
  cat <<'USAGE'
Install WSL dependencies for Ooonana OS.

Usage:
  scripts/install-wsl-deps.sh
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

ooonana_require_linux
ooonana_reexec_as_root "$@"
ooonana_require_command apt-get

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  debootstrap \
  e2fsprogs \
  qemu-system-x86 \
  qemu-utils \
  rsync \
  sudo \
  xz-utils

ooonana_log "WSL dependencies installed"
